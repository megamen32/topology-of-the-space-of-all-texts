"""Search rank/unrank and exact UTF-8 in a browser, with a single injected Qwen client."""
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
from qwen_reference import EDITION, PAGE, ReferenceClient, ReferenceUnavailable
from qwen_web_jobs import MODE, QwenJobs


MAXIMUM = (1 << (8 * PAGE)) - 1
PHRASE = "Привет лол 😂 hello"
LITERAL = "\ufeff  ПAе\u0301  😀\nтекст\n  "
PAGES = {
    MAXIMUM: ("\ufeff  😀\nтекст\n\n" + ALPHABET).ljust(PAGE),
    42: LITERAL.ljust(PAGE),
    7: PHRASE + " " * 4078,
    8: " " * PAGE,
    9: "😂" * PAGE,
}
FILE_WITH_CR = "\ufeff\rстрока\r\n  😀\n".ljust(PAGE)


class FakeReferenceClient(ReferenceClient):
    """Use real client validation and an in-memory address service."""

    def __init__(self):
        self.started = Event()
        self.release = Event()
        self.release.set()
        self.ranked_page = None

    def request(self, path, payload):
        if path == "/rank":
            for number, original in PAGES.items():
                if payload["page"] == original:
                    return {"edition": EDITION, "address": hex(number)}
            raise ValueError("Страница вне тестового издания.")
        assert path == "/unrank"
        self.started.set()
        if not self.release.wait(5):
            raise RuntimeError("test did not release the worker")
        number = int(payload["address"], 16)
        if number not in PAGES:
            raise ReferenceUnavailable("test service offline")
        return {"edition": EDITION, "address": hex(number), "page": PAGES[number]}

    def rank(self, page):
        self.ranked_page = page
        return super().rank(page)


class QwenWebTest(TestCase):
    def setUp(self):
        self.fake = FakeReferenceClient()
        self.endpoints = []

        def client_factory(*, endpoint):
            self.endpoints.append(endpoint)
            return self.fake

        self.jobs = QwenJobs(client_factory, max_active=3, max_results=3)
        self.addCleanup(self.jobs.executor.shutdown)
        self.addCleanup(self.fake.release.set)
        jobs_patch = patch.object(backend_app, "qwen_jobs", self.jobs)
        jobs_patch.start()
        self.addCleanup(jobs_patch.stop)
        self.web = backend_app.app.test_client()

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

    def open_search(self, *, qwen=True):
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
        tab = browser.new_page(permissions=["clipboard-read", "clipboard-write"])
        script_errors = []
        tab.on("pageerror", lambda error: script_errors.append(str(error)))
        self.addCleanup(self.assertEqual, script_errors, [])
        tab.goto(url + ("?mode=" + MODE if qwen else ""))
        return tab

    def assert_page_exports(self, tab, page):
        tab.click("#copyPage")
        expect(tab.locator("#result")).to_contain_text("скопирована")
        self.assertEqual(tab.evaluate("navigator.clipboard.readText()"), page)
        with tab.expect_download() as download:
            tab.click("#downloadPage")
        self.assertEqual(download.value.path().read_bytes(), page.encode("utf-8"))

    def assert_browser_rank(self, tab, number):
        source = tab.input_value("#query")
        with tab.expect_request("**/api/rank") as request:
            tab.click("#rankBtn")
        self.assertEqual(request.value.post_data_json, {"mode": MODE, "text": PAGES[number]})
        expect(tab.locator("#result")).to_contain_text("Адрес найден")
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
        tab = self.open_search()
        self.assertEqual(tab.input_value("#rankInput"), "41")
        self.assert_receipt_cleared(tab)
        tab.fill("#rankInput", str(MAXIMUM))
        tab.click("#unrankBtn")
        expect(tab.locator("#unrankResult")).to_have_js_property("textContent", PAGES[MAXIMUM])
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
        expect(tab.locator("#unrankResult")).to_have_js_property("textContent", PAGES[MAXIMUM])

    def test_search_ui_phrase_and_modes(self):
        tab = self.open_search(qwen=False)
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
        tab.select_option("#rankMode", MODE)
        self.assertEqual(tab.input_value("#rankInput"), "0xabc")
        self.assertEqual(tab.input_value("#query"), PHRASE)
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

        tab.select_option("#rankMode", "exact_cluster_mvp")
        self.assert_receipt_cleared(tab)
        self.assertEqual(tab.input_value("#query"), "")
        tab.fill("#query", PHRASE)
        expect(tab.locator("#counterWrap")).to_be_hidden()
        expect(tab.locator("#qwenHint")).to_be_hidden()
        expect(tab.locator("#qwenFeatured")).to_be_visible()
        self.assertEqual(tab.input_value("#rankInput"), "0x8")
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
        tab = self.open_search()
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
        self.assert_page_exports(tab, FILE_WITH_CR)
        tab.click("#rankBtn")
        expect(tab.locator("#result")).to_contain_text("U+000D")
        self.assertEqual(self.fake.ranked_page, FILE_WITH_CR)
        self.assert_receipt_cleared(tab)

    def test_search_ui_receipt_after_restore_and_errors(self):
        tab = self.open_search()
        tab.fill("#query", PHRASE)
        self.assert_browser_rank(tab, 7)
        tab.click("#addressDetails summary")
        tab.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}))")
        self.assert_receipt_cleared(tab)
        self.assertEqual(tab.input_value("#query"), PHRASE)
        self.assertEqual(tab.input_value("#rankInput"), "7")
        self.assert_browser_rank(tab, 7)
        with patch.object(self.fake, "rank", side_effect=ReferenceUnavailable("offline")):
            tab.click("#rankBtn")
            self.assert_receipt_cleared(tab)
            expect(tab.locator("#result")).to_contain_text("недоступна")
        self.assert_receipt_cleared(tab)
        self.assertNotIn("Адрес найден", tab.text_content("#result"))

    def test_search_ui_rejects_bad_files_and_long_text(self):
        tab = self.open_search()
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
