"""Search rank/unrank and exact UTF-8 with local services for both Qwen editions."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from shutil import which
from threading import Event, Thread
from time import monotonic, sleep
from unittest import TestCase, main
from unittest.mock import patch

from werkzeug.serving import make_server

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:
    sync_playwright = None

import backend_app
from ollama_generative_address import ALPHABET
from qwen35_reference import EDITION as EDITION_35, Qwen35Client
from qwen_reference import EDITION, PAGE, ReferenceClient, ReferenceUnavailable
from qwen_web_jobs import MODE, MODE_35, QwenJobs


MAXIMUM = (1 << (8 * PAGE)) - 1
PHRASE = "Привет лол 😂 hello"
LITERAL = "\ufeff  ПAе\u0301  😀\nтекст\n  "
EXPERIMENT_DATA = Path(__file__).resolve().parents[1] / "notes" / "experiments"
QWEN35_PAGE_32 = (EXPERIMENT_DATA / "qwen35_reference/32-ru.txt").read_text(encoding="utf-8")
QWEN3_VERIFICATION = EXPERIMENT_DATA / "qwen_reference_verification.json"
PAGES = {
    41: json.loads(QWEN3_VERIFICATION.read_text(encoding="utf-8"))["address_first"]["page_utf8"],
    MAXIMUM: ("\ufeff  😀\nтекст\n\n" + ALPHABET).ljust(PAGE),
    42: LITERAL.ljust(PAGE),
    7: PHRASE + " " * 4078,
    8: " " * PAGE,
    9: "😂" * PAGE,
    10: "\ufeff строка \n  😀\n".ljust(PAGE),
}
FILE_WITH_CR = "\ufeff\rстрока\r\n  😀\n".ljust(PAGE)
INITIAL_BOOKS = {MODE: (41, PAGES[41]), MODE_35: (32, QWEN35_PAGE_32)}


class FakeReferenceClient:
    """Use real client validation and an in-memory address service."""

    def __init__(self, client_type, edition, pages):
        self.client = client_type(endpoint="http://unused.invalid")
        self.client.request = self.request
        self.edition = edition
        self.pages = pages.copy()
        self.started = Event()
        self.release = Event()
        self.release.set()
        self.ranked_page = None

    def request(self, path, payload):
        if path == "/rank":
            for number, original in self.pages.items():
                if payload["page"] == original:
                    return {"edition": self.edition, "address": hex(number)}
            raise ValueError("Страница вне тестового издания.")
        assert path == "/unrank"
        self.started.set()
        if not self.release.wait(5):
            raise RuntimeError("test did not release the worker")
        number = int(payload["address"], 16)
        if number not in self.pages:
            raise ReferenceUnavailable("test service offline")
        return {"edition": self.edition, "address": hex(number), "page": self.pages[number]}

    def unrank(self, number):
        return self.client.unrank(number)

    def rank(self, page):
        self.ranked_page = page
        return self.client.rank(page)


class QwenSearchCase(TestCase):
    def setUp(self):
        self.fake = FakeReferenceClient(ReferenceClient, EDITION, PAGES)
        self.fake35 = FakeReferenceClient(Qwen35Client, EDITION_35, {32: QWEN35_PAGE_32})
        self.endpoints = []

        def client_factory(*, endpoint):
            self.endpoints.append(endpoint)
            return self.fake

        self.jobs = QwenJobs(client_factory, max_active=3, max_results=3)
        self.jobs35 = QwenJobs(lambda *, endpoint: self.fake35, edition=EDITION_35)
        self.addCleanup(self.jobs.executor.shutdown)
        self.addCleanup(self.jobs35.executor.shutdown)
        self.addCleanup(self.fake.release.set)
        self.addCleanup(self.fake35.release.set)
        jobs_patch = patch.multiple(backend_app, qwen_jobs=self.jobs, qwen35_jobs=self.jobs35)
        jobs_patch.start()
        self.addCleanup(jobs_patch.stop)
        self.web = backend_app.app.test_client()

    def open_search(self, mode=None, *, viewport=None):
        if sync_playwright is None:
            self.skipTest("Playwright is required for the browser check")
        server = make_server("127.0.0.1", 0, backend_app.app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}/search.html"
        pw = sync_playwright().start()
        self.addCleanup(pw.stop)
        chrome = which("google-chrome") or which("chromium") or pw.chromium.executable_path
        if not Path(chrome).is_file():
            self.skipTest("Chromium is required for the browser check")
        browser = pw.chromium.launch(executable_path=chrome)
        self.addCleanup(browser.close)
        tab = browser.new_page(viewport=viewport, permissions=["clipboard-read", "clipboard-write"])
        script_errors = []
        tab.on("pageerror", lambda error: script_errors.append(str(error)))
        self.addCleanup(self.assertEqual, script_errors, [])
        opens = []

        def record_open(request):
            if request.url.endswith("/api/unrank") and request.method == "POST":
                opens.append(request.post_data_json)

        tab.on("request", record_open)
        tab.goto(url if mode is None else f"{url}?mode={mode}")
        selected = mode or MODE_35
        expect(tab.locator("#rankMode")).to_have_value(selected)
        if selected in INITIAL_BOOKS:
            number, _ = INITIAL_BOOKS[selected]
            self.assert_initial_book(tab, selected)
            self.assertEqual(opens, [{"mode": selected, "rank": str(number)}])
        else:
            self.assertEqual(opens, [])
        tab.remove_listener("request", record_open)
        return tab

    def assert_initial_book(self, tab, mode):
        number, page = INITIAL_BOOKS[mode]
        expect(tab.locator("#unrankResult")).to_have_js_property("textContent", page)
        expect(tab.locator("#rankInput")).to_have_value(str(number))

    def reveal_editor(self, tab):
        details = tab.locator("details#reverseLookup")
        if not details.evaluate("details => details.open"):
            details.locator(":scope > summary").click()
        expect(tab.locator("#query")).to_be_visible()

    def open_editor(self, mode=MODE, *, viewport=None):
        tab = self.open_search(mode, viewport=viewport)
        self.reveal_editor(tab)
        return tab

    def select_editor_mode(self, tab, mode):
        tab.select_option("#rankMode", mode)
        if mode in INITIAL_BOOKS:
            self.assert_initial_book(tab, mode)
        self.reveal_editor(tab)

    def assert_page_exports(self, tab, page):
        tab.click("#copyPage")
        expect(tab.locator("#result")).to_contain_text("скопирована")
        self.assertEqual(tab.evaluate("navigator.clipboard.readText()"), page)
        with tab.expect_download() as download:
            tab.click("#downloadPage")
        self.assertEqual(download.value.path().read_bytes(), page.encode("utf-8"))


class QwenWebTest(QwenSearchCase):
    def submit(self, operation, **fields):
        response = backend_app.app.test_client().post("/api/" + operation, json={"mode": MODE, **fields})
        self.assertEqual(response.status_code, 202, response.get_json())
        data = response.get_json()
        self.assertEqual(data["status"], "queued")
        location = response.headers["Location"]
        self.assertEqual(location, "/api/qwen/jobs/" + data["job_id"])
        return location

    def finish(self, location, code=200):
        deadline = monotonic() + 5
        while monotonic() < deadline:
            response = self.web.get(location)
            self.assertTrue(response.cache_control.no_store)
            data = response.get_json()
            self.assertEqual(data["job_id"], location.rsplit("/", 1)[1])
            if response.status_code != 202:
                self.assertEqual(response.status_code, code, data)
                return data
            sleep(.01)
        self.fail("worker did not finish")

    def test_roundtrip(self):
        for address in [str(MAXIMUM), hex(MAXIMUM), "42"]:
            opened = self.finish(self.submit("unrank", rank=address))
            number = int(str(address), 0)
            self.assertEqual((opened["page"], opened["edition"], opened["length"]), (PAGES[number], EDITION, PAGE))
            ranked = self.finish(self.submit("rank", text=opened["page"]))
            self.assertEqual((ranked["rank"], ranked["rank_hex"], ranked["page"]),
                             (str(number), hex(number), PAGES[number]))

    def test_rank_pads_only_on_the_right(self):
        for text, number in [(PHRASE, 7), ("", 8), ("   ", 8), (LITERAL, 42), (PAGES[9], 9)]:
            with self.subTest(length=len(text)):
                result = self.finish(self.submit("rank", text=text))
                self.assertEqual(self.fake.ranked_page, PAGES[number])
                self.assertEqual((result["rank"], result["page"], result["length"]),
                                 (str(number), PAGES[number], PAGE))

    def test_rank_checks_alphabet_after_padding(self):
        for text, code in [("a\r\n", "U+000D"), ("😀🦦", "U+1F9A6")]:
            with self.subTest(text=text):
                error = self.finish(self.submit("rank", text=text), 400)
                self.assertIn(code, error["error"])
                self.assertEqual(self.fake.ranked_page, text.ljust(PAGE))

    def test_rank_replaces_unsupported_only_when_requested(self):
        replaced = PHRASE.replace(" ", "\u202f", 1)
        strict_error = self.finish(self.submit("rank", text=replaced), 400)["error"]
        self.assertIn("узкий неразрывный пробел", strict_error)
        self.assertIn("U+202F", strict_error)
        self.assertIn("позиции 7", strict_error)
        ranked = self.finish(self.submit("rank", text=replaced, replace_unsupported=True))
        self.assertEqual((ranked["rank"], ranked["page"]), ("7", PAGES[7]))
        invalid = self.web.post("/api/rank", json={"mode": MODE, "text": replaced, "replace_unsupported": "false"})
        self.assertEqual(invalid.status_code, 400)
        alphabet = self.web.get("/api/qwen/alphabet")
        self.assertEqual(alphabet.get_json()["alphabet"], ALPHABET)

    def test_invalid_unrank_result(self):
        with patch.object(self.fake, "unrank", return_value=PAGES[42][:-1] + "\r"):
            error = self.finish(self.submit("unrank", rank="42"), 503)
        self.assertEqual(error["status"], "error")
        self.assertIn("алфавита", error["error"])
        self.assertFalse({"rank", "rank_hex", "page"} & error.keys())

    def test_concurrent_jobs_and_retention(self):
        self.fake.release.clear()
        first = self.submit("unrank", rank="42")
        self.assertTrue(self.fake.started.wait(1))
        with ThreadPoolExecutor(max_workers=2) as callers:
            second, third = callers.map(lambda n: self.submit("unrank", rank=n), ["0x2a", hex(MAXIMUM)])
        self.assertEqual(len({first, second, third}), 3)
        self.assertEqual(self.web.get(first).get_json()["status"], "running")
        self.assertEqual(self.web.get(second).get_json()["status"], "queued")
        full = self.web.post("/api/rank", json={"mode": MODE, "text": PAGES[42]})
        self.assertEqual(full.status_code, 429)
        self.fake.release.set()
        for location, number in [(third, MAXIMUM), (second, 42), (first, 42)]:
            self.assertEqual(self.finish(location)["page"], PAGES[number])
        failed = self.finish(self.submit("unrank", rank="0"), 503)
        self.assertIn("недоступна", failed["error"])
        self.assertNotIn("page", failed)
        self.assertEqual(self.web.get(first).status_code, 404)
        with patch("qwen_web_jobs.monotonic", return_value=monotonic() + self.jobs.ttl + 1):
            self.assertEqual(self.web.get(second).status_code, 404)

    def test_inputs_and_endpoint(self):
        for token in [True, None, 42, "-1", "1e2", "0xffg", "0x", str(MAXIMUM + 1),
                      "0x1" + "0" * (2 * PAGE), "0" * 10000]:
            with self.subTest(token=str(token)[:12]):
                response = self.web.post("/api/unrank", json={"mode": MODE, "rank": token})
                self.assertEqual(response.status_code, 400)
        for fields in [{}, {"text": None}, {"text": "😂" * (PAGE + 1)}, {"text": 4096},
                       {"text": "\ud800" * PAGE}, {"text": PAGES[42], "length": 8},
                       {"text": PAGES[42], "endpoint": "http://caller.invalid"}]:
            self.assertEqual(self.web.post("/api/rank", json={"mode": MODE, **fields}).status_code, 400)
        self.assertFalse(self.endpoints)
        with patch.dict("os.environ", BABEL_QWEN_ENDPOINT="http://configured.invalid"):
            error = self.finish(self.submit("rank", text="x" * PAGE), 400)
        self.assertIn("error", error)
        self.assertEqual(self.endpoints, ["http://configured.invalid"])

    def test_large_legacy_requests(self):
        cases = [
            ("/api/rank", "text", "a" * 70000, "a" * PAGE),
            ("/api/unrank", "rank", "0x" + "0" * 70000 + "2a", "42"),
        ]
        for path, field, large, short in cases:
            for mode in [{}, {"mode": "hierarchical_catalogue_v1"}]:
                legacy = self.web.post(path, json={field: large, **mode})
                self.assertEqual(legacy.status_code, 200)
                self.assertEqual(legacy.get_json(), self.web.post(path, json={field: short, **mode}).get_json())
            qwen = self.web.post(path, json={"mode": MODE, field: large})
            self.assertEqual(qwen.status_code, 413)
            self.assertIn("error", qwen.get_json())
        self.assertFalse(self.endpoints)

    def assert_browser_rank(self, tab, number):
        source = tab.input_value("#query")
        with tab.expect_request("**/api/rank") as request:
            tab.click("#rankBtn")
        self.assertEqual(request.value.post_data_json, {"mode": MODE, "text": PAGES[number]})
        expect(tab.locator("#result")).to_contain_text("Адрес найден")
        expect(tab.locator("#unrankResult")).to_have_js_property("textContent", PAGES[number])
        expect(tab.locator("#numberReceipt")).to_be_visible()
        expect(tab.locator("#addressDetails")).to_have_js_property("open", False)
        formats = f"Десятичный номер\n{number}\n\nШестнадцатеричный номер\n{hex(number)}"
        expect(tab.locator("#addressFormats")).to_have_js_property("textContent", formats)
        self.assertEqual(self.fake.ranked_page, PAGES[number])
        self.assertEqual(tab.input_value("#query"), source)
        expect(tab.locator("#query")).to_be_editable()

    def assert_receipt_cleared(self, tab):
        expect(tab.locator("#numberReceipt")).to_be_hidden()
        expect(tab.locator("#addressDetails")).to_have_js_property("open", False)
        expect(tab.locator("#addressFormats")).to_have_js_property("textContent", "")

    def test_search_ui_unrank(self):
        tab = self.open_editor()
        self.assertEqual(tab.input_value("#rankInput"), "41")
        self.assert_receipt_cleared(tab)
        expect(tab.locator("#query")).to_have_value("")
        tab.fill("#query", PHRASE)
        tab.fill("#rankInput", str(MAXIMUM))
        tab.click("#unrankBtn")
        expect(tab.locator("#unrankResult")).to_have_js_property("textContent", PAGES[MAXIMUM])
        expect(tab.locator("#query")).to_have_value(PHRASE)
        expect(tab.locator("#charCount")).to_have_text("18 / 4 096")
        self.assert_page_exports(tab, PAGES[7])
        tab.click("#useOpenedPage")
        self.assertEqual(tab.input_value("#query"), PAGES[MAXIMUM])
        expect(tab.locator("#charCount")).to_have_text("4 096 / 4 096")
        expect(tab.locator("#qwenHint")).to_contain_text("полная")
        self.assert_page_exports(tab, PAGES[MAXIMUM])
        self.assert_browser_rank(tab, MAXIMUM)
        address = str(MAXIMUM)
        self.assertEqual(tab.input_value("#rankInput"), address)
        summary = tab.text_content("#result")
        self.assertIn(address[:10] + "…" + address[-10:], summary)
        self.assertIn("9 865", summary)
        self.assertLess(len(summary), 100)
        expect(tab.locator("#addressFormats")).to_be_hidden()
        tab.click("#copyAddress")
        expect(tab.locator("#result")).to_contain_text("Адрес скопирован")
        self.assertEqual(tab.evaluate("navigator.clipboard.readText()"), address)
        tab.click("#addressDetails summary")
        expect(tab.locator("#addressFormats")).to_be_visible()
        tab.click("#unrankBtn")
        self.assert_receipt_cleared(tab)
        expect(tab.locator("#unrankBtn")).to_be_enabled()
        expect(tab.locator("#unrankResult")).to_have_js_property("textContent", PAGES[MAXIMUM])
        tab.fill("#rankInput", "42")
        tab.click("#unrankBtn")
        expect(tab.locator("#unrankResult")).to_have_js_property("textContent", PAGES[42])
        expect(tab.locator("#query")).to_have_value(PAGES[MAXIMUM])

    def test_search_ui_phrase_and_modes(self):
        tab = self.open_editor("base256")
        self.assertEqual(tab.input_value("#rankMode"), "base256")
        self.assertEqual(tab.input_value("#rankInput"), "0x0")
        expect(tab.locator("#counterWrap")).to_be_hidden()
        expect(tab.locator("#qwenFeatured")).to_be_visible()
        tab.fill("#query", PHRASE)
        with tab.expect_response(lambda response: "/data/model.json?" in response.url) as model:
            tab.click("#scoreBtn")
        self.assertEqual(model.value.status, 200)
        expect(tab.locator("#result")).to_contain_text(PHRASE.lower())
        tab.fill("#rankInput", "0xabc")
        self.select_editor_mode(tab, MODE)
        self.assertEqual(tab.input_value("#query"), PHRASE)
        # Choose hexadecimal display for receipts in the newly opened edition.
        tab.fill("#rankInput", "0xabc")
        expect(tab.locator("#counterWrap")).to_be_visible()
        expect(tab.locator("#charCount")).to_have_text("18 / 4 096")
        expect(tab.locator("#qwenHint")).to_be_visible()
        expect(tab.locator("#qwenHint")).to_contain_text("4 078 пробелов")
        self.assert_page_exports(tab, PAGES[7])
        self.assert_browser_rank(tab, 7)
        self.assertEqual(tab.text_content("#result"), "Адрес найден\n7")
        self.assertEqual(tab.input_value("#rankInput"), "0x7")
        tab.click("#copyAddress")
        expect(tab.locator("#result")).to_contain_text("Адрес скопирован")
        self.assertEqual(tab.evaluate("navigator.clipboard.readText()"), "7")
        tab.fill("#query", "")
        self.assert_receipt_cleared(tab)
        expect(tab.locator("#charCount")).to_have_text("0 / 4 096")
        self.assert_page_exports(tab, PAGES[8])
        self.assert_browser_rank(tab, 8)
        self.assertEqual(tab.input_value("#rankInput"), "0x8")

        self.select_editor_mode(tab, "exact_cluster_mvp")
        self.assert_receipt_cleared(tab)
        self.assertEqual(tab.input_value("#query"), "")
        tab.fill("#query", PHRASE)
        expect(tab.locator("#counterWrap")).to_be_hidden()
        expect(tab.locator("#qwenHint")).to_be_hidden()
        expect(tab.locator("#qwenFeatured")).to_be_visible()
        self.assertEqual(tab.input_value("#rankInput"), "0x0")
        with tab.expect_request("**/api/rank") as request:
            tab.click("#rankBtn")
        self.assertEqual(request.value.post_data_json, {"mode": "exact_cluster_mvp", "length": 8, "text": PHRASE})
        expect(tab.locator("#result")).to_contain_text("at most 8 symbols")
        tab.fill("#query", "abc")
        tab.click("#rankBtn")
        expect(tab.locator("#result")).to_contain_text("rank_hex")
        tab.select_option("#rankMode", "exact_hierarchical_v1")
        self.assertEqual(tab.input_value("#rankLength"), "4096")
        self.assertEqual(tab.input_value("#query"), "abc")
        expect(tab.locator("#counterWrap")).to_be_hidden()

    def test_search_ui_files(self):
        tab = self.open_editor()
        for source, number in [("", 8), (LITERAL, 42), (PAGES[9], 9)]:
            with self.subTest(length=len(source)):
                tab.set_input_files("#pageFile", {"name": "page.txt", "mimeType": "text/plain", "buffer": source.encode()})
                expect(tab.locator("#result")).to_contain_text("загружен")
                self.assert_receipt_cleared(tab)
                self.assertEqual(tab.input_value("#query"), source)
                self.assert_page_exports(tab, PAGES[number])
                self.assert_browser_rank(tab, number)

        tab.set_input_files("#pageFile", {"name": "cr.txt", "mimeType": "text/plain", "buffer": FILE_WITH_CR.encode()})
        expect(tab.locator("#result")).to_contain_text("загружен")
        self.assertEqual(tab.input_value("#query"), FILE_WITH_CR.replace("\r\n", "\n").replace("\r", "\n"))
        expect(tab.locator("#charCount")).to_have_text("4 096 / 4 096")
        for item, position in zip(tab.locator("#replacementPreview li").all(), (2, 9), strict=True):
            expect(item).to_contain_text(f"Позиция {position}")
            expect(item).to_contain_text("U+000D")
        self.assert_page_exports(tab, PAGES[10])
        self.assert_browser_rank(tab, 10)

        source = "\ufeffA\r\n\n😀\rB"
        tab.set_input_files("#pageFile", {"name": "short-cr.txt", "mimeType": "text/plain", "buffer": source.encode()})
        expect(tab.locator("#result")).to_contain_text("загружен")
        query = tab.locator("#query")
        # Delete the LF immediately following CRLF. They look identical in the textarea.
        query.evaluate("q => { q.focus(); q.setSelectionRange(3, 4); }")
        query.press("Backspace")
        self.assert_page_exports(tab, "\ufeffA \n😀 B".ljust(PAGE))
        query.evaluate("q => { q.focus(); q.setSelectionRange(1, 1); }")
        tab.evaluate("text => navigator.clipboard.writeText(text)", "X\r\nY")
        query.press("Control+v")
        self.assert_page_exports(tab, "\ufeffX \nYA \n😀 B".ljust(PAGE))

    def test_search_ui_receipt_after_restore_and_errors(self):
        tab = self.open_editor()
        tab.fill("#query", PHRASE)
        self.assert_browser_rank(tab, 7)
        tab.click("#addressDetails summary")
        tab.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}))")
        with self.subTest(event="restored from back-forward cache"):
            self.assert_receipt_cleared(tab)
        self.assertEqual(tab.input_value("#query"), PHRASE)
        self.assertEqual(tab.input_value("#rankInput"), "7")
        self.assert_browser_rank(tab, 7)
        with patch.object(self.fake, "rank", side_effect=ReferenceUnavailable("offline")):
            tab.click("#rankBtn")
            self.assert_receipt_cleared(tab)
            expect(tab.locator("#result")).to_contain_text("недоступна")
            expect(tab.locator("#bookStatus")).to_be_empty()
            expect(tab.locator("#unrankResult")).to_have_js_property("textContent", PAGES[7])
        self.assert_receipt_cleared(tab)
        self.assertNotIn("Адрес найден", tab.text_content("#result"))

    def test_search_ui_rejects_bad_files_and_long_text(self):
        tab = self.open_editor()
        tab.fill("#query", PHRASE)
        self.assert_browser_rank(tab, 7)
        for data, message in [(b"a" * (PAGE + 1), "превышает"), (b"x" * (4 * PAGE + 1), "16 КиБ"),
                              (b"\xff", "некорректный UTF-8")]:
            with self.subTest(size=len(data)):
                tab.set_input_files("#pageFile", {"name": "invalid.txt", "mimeType": "text/plain", "buffer": data})
                expect(tab.locator("#result")).to_contain_text(message)
                self.assert_receipt_cleared(tab)
                self.assertEqual(tab.input_value("#query"), PHRASE)

        overflow = PAGES[9] + "x"
        tab.fill("#query", overflow)
        expect(tab.locator("#charCount")).to_have_text("4 097 / 4 096")
        expect(tab.locator("#qwenHint")).to_contain_text("превышает")
        expect(tab.locator("#counterWrap.over-limit")).to_be_visible()
        requests, downloads = [], []
        tab.on("request", lambda request: requests.append(request.url))
        tab.on("download", lambda download: downloads.append(download))
        tab.evaluate("navigator.clipboard.writeText('clipboard before overflow')")
        for button in ("#rankBtn", "#copyPage", "#downloadPage"):
            tab.click(button)
            expect(tab.locator("#result")).to_contain_text("превышает")
        self.assertEqual(tab.input_value("#query"), overflow)
        self.assertEqual(tab.evaluate("navigator.clipboard.readText()"), "clipboard before overflow")
        self.assertFalse(any(url.endswith("/api/rank") for url in requests))
        self.assertFalse(downloads)
        tab.fill("#query", "😂")
        expect(tab.locator("#charCount")).to_have_text("1 / 4 096")
        expect(tab.locator("#counterWrap.over-limit")).to_have_count(0)


if __name__ == "__main__":
    main()
