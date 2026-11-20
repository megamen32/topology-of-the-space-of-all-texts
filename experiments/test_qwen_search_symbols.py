"""Browser regressions for the Qwen alphabet, shared page preparation and job polling."""
from unittest import TestCase, main
from unittest.mock import Mock, patch

import backend_app
import test_qwen_web as web
from ollama_generative_address import ALPHABET
from qwen_reference import EDITION, PAGE
from qwen35_reference import EDITION as EDITION_35
from qwen_web_jobs import MODE, MODE_35, QwenJobs


class QwenSearchSymbolsTest(TestCase):
    open_search = web.QwenWebTest.open_search
    assert_page_exports = web.QwenWebTest.assert_page_exports

    def test_search_copy_and_download_in_both_editions(self):
        tab = self.open_search(qwen=False)
        prefix = ("\ufeff  " + ALPHABET + " é e\u0301 ❤️ ").ljust(1206, "😂")
        source = prefix + "\u202f🦦\u00a0" + "\n Z  "
        expected = (prefix + "   " + "\n Z  ").ljust(PAGE)
        tab.fill("#query", source)
        alphabet_requests = []
        tab.on("request", lambda req: alphabet_requests.append(req.url) if req.url.endswith("/api/qwen/alphabet") else None)

        for mode, edition, queue, number in [(MODE, EDITION, "qwen_jobs", 17), (MODE_35, EDITION_35, "qwen35_jobs", 35)]:
            with self.subTest(mode=mode):
                if mode == MODE:
                    with tab.expect_response("**/api/qwen/alphabet") as response:
                        tab.select_option("#rankMode", mode)
                    self.assertEqual(response.value.json()["alphabet"], ALPHABET)
                else:
                    tab.select_option("#rankMode", mode)
                rows = tab.locator("#replacementPreview li")
                web.expect(rows).to_have_count(3)
                for row, pos, ch, name in zip(rows.all(), (1207, 1208, 1209), "\u202f🦦\u00a0",
                                              ("узкий неразрывный пробел", "", "неразрывный пробел"), strict=True):
                    self.assertEqual(row.locator("bdi").text_content(), ch)
                    web.expect(row).to_contain_text(f"Позиция {pos}")
                    web.expect(row).to_contain_text(f"U+{ord(ch):04X}")
                    if name:
                        web.expect(row).to_contain_text(name)
                web.expect(tab.locator("#replacementHint")).to_contain_text("U+0020")

                tab.context.set_offline(True)
                try:
                    self.assert_page_exports(tab, expected)
                finally:
                    tab.context.set_offline(False)

                client = Mock()
                client.rank.return_value = number
                jobs = QwenJobs(Mock(return_value=client), edition=edition)
                self.addCleanup(jobs.executor.shutdown)
                with patch.object(backend_app, queue, jobs):
                    with tab.expect_request("**/api/rank") as request:
                        tab.click("#rankBtn")
                    self.assertEqual(request.value.post_data_json, {"mode": mode, "text": expected})
                    web.expect(tab.locator("#result")).to_have_text(f"Адрес найден\n{number}")
                    client.rank.assert_called_once_with(expected)
                self.assertEqual(tab.input_value("#query"), source)
                tab.select_option("#rankMode", "base256")
                web.expect(tab.locator("#qwenReplacements")).to_be_hidden()
        self.assertEqual(len(alphabet_requests), 1)

    def test_full_page_of_replacements_is_keyboard_accessible(self):
        tab = self.open_search()
        source = "🦦" * (PAGE - 5) + "\t\u00a0\u202e\u200c\u202f"
        tab.fill("#query", source)
        web.expect(tab.locator("#replacementHint")).to_contain_text("4 096")
        web.expect(tab.locator("#qwenHint")).to_have_text("Страница полная.")
        extra = tab.locator("#replacementList")
        web.expect(extra).to_be_hidden()
        summary = tab.locator("#morePositions")
        web.expect(summary).to_have_text("Ещё 4 093 позиции")
        summary.focus()
        summary.press("Enter")
        web.expect(extra.locator("li")).to_have_count(PAGE - 3)
        rows = tab.locator("#qwenReplacements li").all_text_contents()
        for position, (row, symbol) in enumerate(zip(rows, source, strict=True), 1):
            self.assertIn(f"Позиция {position} — {symbol} U+{ord(symbol):04X}", row)
        for row, name in zip(rows[-5:], ("табуляция", "неразрывный пробел", "знак направления письма",
                                         "запрет соединения", "узкий неразрывный пробел"), strict=True):
            self.assertIn(name, row)
        summary.press("Tab")
        web.expect(extra).to_be_focused()
        self.assertTrue(extra.evaluate("list => list.scrollHeight > list.clientHeight"))
        self.assert_page_exports(tab, " " * PAGE)
        tab.fill("#query", ALPHABET)
        web.expect(tab.locator("#qwenReplacements")).to_be_hidden()

    def test_buttons_wait_for_alphabet_and_recover_after_retry(self):
        tab = self.open_search(qwen=False)
        path = "**/api/qwen/alphabet"
        pending = []
        tab.route(path, lambda route: pending.append(route))
        with tab.expect_request(path):
            tab.select_option("#rankMode", MODE)
        web.expect(tab.locator("#alphabetMessage")).to_contain_text("Загружаем алфавит")
        for button in ("#rankBtn", "#copyPage", "#downloadPage"):
            web.expect(tab.locator(button)).to_be_disabled()
        web.expect(tab.locator("#pageFile")).to_be_enabled()
        web.expect(tab.locator("#unrankBtn")).to_be_enabled()
        tab.fill("#query", "A\u202fZ")
        tab.select_option("#rankMode", "base256")
        web.expect(tab.locator("#rankBtn")).to_be_enabled()
        web.expect(tab.locator("#alphabetStatus")).to_be_hidden()
        tab.select_option("#rankMode", MODE_35)
        self.assertEqual(len(pending), 1)

        for status, body in ((503, {}), (200, {"alphabet": "a" * 256})):
            pending.pop().fulfill(status=status, json=body)
            web.expect(tab.locator("#alphabetMessage")).to_contain_text("Загрузить его не удалось")
            web.expect(tab.locator("#rankBtn")).to_be_disabled()
            with tab.expect_request(path):
                tab.click("#retryAlphabet")
        pending.pop().continue_()
        web.expect(tab.locator("#alphabetStatus")).to_be_hidden()
        for button in ("#rankBtn", "#copyPage", "#downloadPage"):
            web.expect(tab.locator(button)).to_be_enabled()
        web.expect(tab.locator("#replacementPreview")).to_contain_text("Позиция 2")
        self.assert_page_exports(tab, "A Z".ljust(PAGE))
        self.assertEqual(tab.input_value("#query"), "A\u202fZ")

    def test_first_status_get_is_immediate_and_repeat_waits_two_seconds(self):
        tab = self.open_search()
        web.expect(tab.locator("#rankBtn")).to_be_enabled()
        tab.clock.install(time="2026-01-01T00:00:00Z")
        tab.clock.pause_at("2026-01-01T00:01:00Z")
        job = {"job_id": "timing"}
        tab.route("**/api/rank", lambda route: route.fulfill(status=202, json={**job, "status": "queued"}))
        path = "**/api/qwen/jobs/timing"
        polls = []

        def status(route):
            polls.append(route.request.method)
            if len(polls) == 1:
                route.fulfill(status=202, json={**job, "status": "running"})
            else:
                route.fulfill(json={**job, "status": "done", "rank": "41", "rank_hex": "0x29"})

        tab.route(path, status)
        with tab.expect_request(path, timeout=3000):
            tab.locator("#rankBtn").evaluate("button => button.click()")
        web.expect(tab.locator("#result")).to_contain_text("Qwen вычисляет")
        tab.clock.run_for(1999)
        self.assertEqual(polls, ["GET"])
        with tab.expect_request(path, timeout=3000):
            tab.clock.run_for(1)
        web.expect(tab.locator("#result")).to_have_text("Адрес найден\n41")
        self.assertEqual(polls, ["GET", "GET"])


if __name__ == "__main__":
    main()
