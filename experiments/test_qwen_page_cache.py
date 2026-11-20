"""Public Search regressions for the persistent Qwen address/page pairs."""
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
from unittest import TestCase, main
from unittest.mock import Mock, call, patch

import backend_app
from qwen35_reference import EDITION as EDITION_35
from qwen_page_cache import PageCache, PageCacheConflict
from qwen_reference import EDITION, PAGE, ReferenceClient, ReferenceUnavailable
from qwen_web_jobs import MODE, MODE_35, QwenJobs


PHRASE = "  Привет  😂\nмир "
PADDED = PHRASE.ljust(PAGE)
OTHER_PAGE = "Другая страница".ljust(PAGE)
MAXIMUM = (1 << (8 * PAGE)) - 1
QUEUES = {MODE: ("qwen_jobs", EDITION), MODE_35: ("qwen35_jobs", EDITION_35)}


class QwenPageCacheTest(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "pages.sqlite3"
        queues = patch.multiple(backend_app, qwen_jobs=None, qwen35_jobs=None)
        queues.start()
        self.addCleanup(queues.stop)
        self.web = backend_app.app.test_client()

    @contextmanager
    def queue(self, mode=MODE, *, max_active=4, use_cache=True):
        attribute, edition = QUEUES[mode]
        model = Mock(spec=ReferenceClient)
        cache = PageCache(self.path) if use_cache else None
        jobs = QwenJobs(lambda *, endpoint: model, edition=edition,
                        max_active=max_active, page_cache=cache)
        with jobs.executor, patch.object(backend_app, attribute, jobs):
            yield model

    def submit(self, operation, mode=MODE, **fields):
        response = self.web.post("/api/" + operation, json={"mode": mode, **fields})
        self.assertEqual(response.status_code, 202, response.get_json())
        return response.headers["Location"]

    def finish(self, location):
        deadline = monotonic() + 5
        while monotonic() < deadline:
            response = self.web.get(location)
            if response.status_code != 202:
                return response
            sleep(.005)
        self.fail(f"Job at {location} did not finish")

    def assert_page(self, location, number, page, *, cached=None, mode=MODE):
        # For a warm pair the very first GET must already contain the complete result.
        response = self.web.get(location) if cached is True else self.finish(location)
        result = response.get_json()
        self.assertEqual(response.status_code, 200, result)
        self.assertEqual(result["status"], "done")
        self.assertEqual((result["mode"], result["edition"]), (mode, QUEUES[mode][1]))
        self.assertEqual(result["length"], PAGE)
        self.assertEqual(result["page"], page)
        self.assertEqual((result["rank"], result["rank_hex"]), (str(Decimal(number)), hex(number)))
        if cached is not None:
            self.assertIs(result["cached"], cached)

    def assert_failed(self, location):
        response = self.finish(location)
        result = response.get_json()
        self.assertGreaterEqual(response.status_code, 400, result)
        self.assertEqual(result["status"], "error")

    @contextmanager
    def blocked_unrank(self, model, number, page):
        started, release = Event(), Event()

        def compute(_address):
            started.set()
            if not release.wait(5):
                raise TimeoutError("Test did not release the Qwen worker")
            return page

        model.unrank.side_effect = compute
        location = self.submit("unrank", rank=str(number))
        try:
            self.assertTrue(started.wait(5), "Qwen worker did not start")
            yield location
        finally:
            release.set()

    def test_rank_survives_restart_with_an_offline_model(self):
        with self.queue() as model:
            model.rank.return_value = 42
            self.assert_page(self.submit("rank", text=PHRASE), 42, PADDED, cached=False)
            model.rank.assert_called_once_with(PADDED)
        with self.path.open("rb") as database:
            self.assertEqual(database.read(16), b"SQLite format 3\0")

        with self.queue() as offline:
            offline.rank.side_effect = offline.unrank.side_effect = ReferenceUnavailable("offline")
            for spelling in ("00042", "0X00002A"):
                self.assert_page(self.submit("unrank", rank=spelling), 42, PADDED, cached=True)
            for text in (PADDED, PHRASE.rstrip(" ")):
                self.assert_page(self.submit("rank", text=text), 42, PADDED, cached=True)
            offline.unrank.assert_not_called()
            offline.rank.assert_not_called()

            # Removing leading spaces changes the page and must reach the offline model.
            different = PHRASE.lstrip(" ")
            miss = self.finish(self.submit("rank", text=different))
            self.assertEqual(miss.status_code, 503, miss.get_json())
            offline.rank.assert_called_once_with(different.ljust(PAGE))

    def test_unrank_at_the_32768_bit_limit_populates_both_directions(self):
        page = "😂" * (PAGE - 1) + "я"
        with self.queue() as model:
            model.unrank.return_value = page
            self.assert_page(self.submit("unrank", rank=hex(MAXIMUM)), MAXIMUM, page, cached=False)
            self.assert_page(self.submit("rank", text=page), MAXIMUM, page, cached=True)
            decimal = str(Decimal(MAXIMUM))
            self.assert_page(self.submit("unrank", rank=decimal), MAXIMUM, page, cached=True)
            for outside in (str(Decimal(MAXIMUM + 1)), hex(MAXIMUM + 1)):
                response = self.web.post("/api/unrank", json={"mode": MODE, "rank": outside})
                self.assertEqual(response.status_code, 400)
            model.unrank.assert_called_once_with(MAXIMUM)
            model.rank.assert_not_called()

    def test_both_keys_are_scoped_to_the_edition(self):
        with self.queue() as qwen3, self.queue(MODE_35) as qwen35:
            for mode, model, page in ((MODE, qwen3, PADDED), (MODE_35, qwen35, OTHER_PAGE)):
                model.unrank.return_value = page
                location = self.submit("unrank", mode, rank="42")
                self.assert_page(location, 42, page, cached=False, mode=mode)
            qwen35.rank.return_value = 7
            location = self.submit("rank", MODE_35, text=PHRASE)
            self.assert_page(location, 7, PADDED, cached=False, mode=MODE_35)

            pairs = ((MODE, 42, PADDED), (MODE_35, 42, OTHER_PAGE), (MODE_35, 7, PADDED))
            for mode, number, page in pairs:
                with self.subTest(mode=mode, number=number):
                    opened = self.submit("unrank", mode, rank=str(number))
                    self.assert_page(opened, number, page, cached=True, mode=mode)
                    found = self.submit("rank", mode, text=page)
                    self.assert_page(found, number, page, cached=True, mode=mode)

    def test_warm_pair_is_available_while_the_queue_is_full(self):
        with self.queue(max_active=1) as model:
            model.rank.return_value = 42
            self.assert_page(self.submit("rank", text=PHRASE), 42, PADDED, cached=False)
            with self.blocked_unrank(model, 7, OTHER_PAGE) as busy:
                full = self.web.post("/api/unrank", json={"mode": MODE, "rank": "8"})
                self.assertEqual(full.status_code, 429)
                self.assert_page(self.submit("unrank", rank="0x2a"), 42, PADDED, cached=True)
                self.assert_page(self.submit("rank", text=PHRASE), 42, PADDED, cached=True)
            self.assert_page(busy, 7, OTHER_PAGE, cached=False)
            model.unrank.assert_called_once_with(7)
            model.rank.assert_called_once_with(PADDED)

    def test_queued_duplicate_and_inverse_share_one_calculation(self):
        with self.queue(max_active=3) as model:
            with self.blocked_unrank(model, 42, PADDED) as first:
                duplicate = self.submit("unrank", rank="0x002A")
                inverse = self.submit("rank", text=PHRASE)
            self.assert_page(first, 42, PADDED, cached=False)
            self.assert_page(duplicate, 42, PADDED)
            self.assert_page(inverse, 42, PADDED)
            model.unrank.assert_called_once_with(42)
            model.rank.assert_not_called()

    def test_errors_and_invalid_model_answers_are_retried(self):
        with self.queue() as model:
            model.unrank.side_effect = [
                ReferenceUnavailable("offline"), PADDED[:-1], PADDED[:-1] + "\r", PADDED,
            ]
            for fault in ("offline", "short page", "outside alphabet"):
                with self.subTest(fault=fault):
                    self.assert_failed(self.submit("unrank", rank="42"))
            self.assert_page(self.submit("unrank", rank="42"), 42, PADDED, cached=False)
            self.assert_page(self.submit("rank", text=PHRASE), 42, PADDED, cached=True)
            self.assertEqual(model.unrank.call_args_list, [call(42)] * 4)

            model.rank.side_effect = [MAXIMUM + 1, 7]
            self.assert_failed(self.submit("rank", text=OTHER_PAGE))
            self.assert_page(self.submit("rank", text=OTHER_PAGE), 7, OTHER_PAGE, cached=False)
            self.assert_page(self.submit("unrank", rank="7"), 7, OTHER_PAGE, cached=True)
            self.assertEqual(model.rank.call_args_list, [call(OTHER_PAGE)] * 2)

    def test_conflicting_writers_preserve_the_committed_pair(self):
        writer = PageCache(self.path)
        with self.queue() as slow:
            with self.blocked_unrank(slow, 7, PADDED) as pending:
                # The active worker is about to return this page under a different address.
                writer.store(EDITION, 42, PADDED)
            self.assert_failed(pending)
        with self.assertRaises(PageCacheConflict):
            writer.store(EDITION, 42, OTHER_PAGE)

        with self.queue() as restarted:
            self.assert_page(self.submit("rank", text=PHRASE), 42, PADDED, cached=True)
            self.assert_page(self.submit("unrank", rank="42"), 42, PADDED, cached=True)
            restarted.unrank.return_value = OTHER_PAGE
            self.assert_page(self.submit("unrank", rank="7"), 7, OTHER_PAGE, cached=False)

    def test_unavailable_database_still_returns_fresh_results(self):
        blocker = self.path.with_name("regular-file")
        blocker.touch()
        self.path = blocker / "state" / "pages.sqlite3"
        with self.queue() as model:
            model.rank.return_value = 42
            model.unrank.return_value = PADDED
            self.assert_page(self.submit("rank", text=PHRASE), 42, PADDED, cached=False)
            self.assert_page(self.submit("unrank", rank="42"), 42, PADDED, cached=False)
            model.rank.assert_called_once_with(PADDED)
            model.unrank.assert_called_once_with(42)

    def test_disabled_cache_keeps_computing_repeated_requests(self):
        blank = " " * PAGE
        with self.queue(use_cache=False) as model:
            model.rank.return_value = 0
            model.unrank.return_value = blank
            for text in ("", "   "):
                self.assert_page(self.submit("rank", text=text), 0, blank)
            self.assert_page(self.submit("unrank", rank="0x0000"), 0, blank)
            self.assertEqual(model.rank.call_args_list, [call(blank)] * 2)
            model.unrank.assert_called_once_with(0)


if __name__ == "__main__":
    main()
