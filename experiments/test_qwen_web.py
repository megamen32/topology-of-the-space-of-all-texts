"""Search rank/unrank and exact UTF-8 in a browser, with a single injected Qwen client."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from shutil import which
from threading import Event, Thread
from time import monotonic, sleep
from unittest import TestCase, main
from unittest.mock import patch

from werkzeug.serving import make_server

import backend_app
from ollama_generative_address import ALPHABET
from qwen_reference import EDITION, PAGE, ReferenceUnavailable
from qwen_web_jobs import MODE, QwenJobs


MAXIMUM = (1 << (8 * PAGE)) - 1
PAGES = {
    MAXIMUM: ("\ufeff  😀\nтекст\n\n" + ALPHABET).ljust(PAGE),
    42: "\ufeff\nстрока\n  😀\n".ljust(PAGE),
}
FILE_WITH_CR = "\ufeff\rстрока\r\n  😀\n".ljust(PAGE)


class FakeReferenceClient:
    def __init__(self):
        self.started = Event()
        self.release = Event()
        self.release.set()
        self.ranked_page = None

    def unrank(self, number):
        self.started.set()
        if not self.release.wait(5):
            raise RuntimeError("test did not release the worker")
        if number not in PAGES:
            raise ReferenceUnavailable("test service offline")
        return PAGES[number]

    def rank(self, page):
        self.ranked_page = page
        for number, original in PAGES.items():
            if page == original:
                return number
        raise ValueError("Страница вне тестового издания.")


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
        for fields in [{"text": "x" * (PAGE - 1)}, {"text": " " * (PAGE + 1)}, {"text": 4096},
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

    def test_search_ui(self):
        try:
            from playwright.sync_api import expect, sync_playwright
        except ImportError:
            self.skipTest("Playwright is required for the browser check")
        server = make_server("127.0.0.1", 0, backend_app.app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}/search.html"
        with sync_playwright() as pw:
            chrome = which("google-chrome") or which("chromium") or pw.chromium.executable_path
            if not Path(chrome).is_file():
                self.skipTest("Chromium is required for the browser check")
            browser = pw.chromium.launch(executable_path=chrome)
            tab = browser.new_page(permissions=["clipboard-read", "clipboard-write"])
            script_errors = []
            tab.on("pageerror", lambda error: script_errors.append(str(error)))
            tab.goto(url + "?mode=" + MODE)
            self.assertEqual(tab.evaluate("typeof loadCore"), "function")
            tab.fill("#rankInput", str(MAXIMUM))
            tab.click("#unrankBtn")
            expect(tab.locator("#unrankResult")).to_have_js_property("textContent", PAGES[MAXIMUM])
            self.assertEqual(tab.input_value("#query"), PAGES[MAXIMUM])
            tab.click("#copyPage")
            expect(tab.locator("#result")).to_contain_text("скопирована")
            self.assertEqual(tab.evaluate("navigator.clipboard.readText()"), PAGES[MAXIMUM])
            tab.click("#rankBtn")
            expect(tab.locator("#result")).to_contain_text(hex(MAXIMUM))
            self.assertEqual(tab.input_value("#rankInput"), str(MAXIMUM))
            with tab.expect_download() as download:
                tab.click("#downloadPage")
            self.assertEqual(download.value.path().read_bytes(), PAGES[MAXIMUM].encode())
            tab.set_input_files("#pageFile", {"name": "page.txt", "mimeType": "text/plain", "buffer": FILE_WITH_CR.encode()})
            expect(tab.locator("#result")).to_contain_text("Загружены")
            self.assertEqual(tab.input_value("#query"), FILE_WITH_CR.replace("\r\n", "\n").replace("\r", "\n"))
            with tab.expect_download() as download:
                tab.click("#downloadPage")
            self.assertEqual(download.value.path().read_bytes(), FILE_WITH_CR.encode())
            tab.click("#rankBtn")
            expect(tab.locator("#result")).to_contain_text("вне тестового издания")
            self.assertEqual(self.fake.ranked_page, FILE_WITH_CR)
            tab.fill("#query", PAGES[42])
            tab.click("#rankBtn")
            expect(tab.locator("#rankInput")).to_have_value("42")
            tab.select_option("#rankMode", "base256")
            with tab.expect_response(lambda response: "/data/model.json?" in response.url) as model:
                tab.click("#scoreBtn")
            self.assertEqual(model.value.status, 200, "Base-256 needs site/data/model.json")
            expect(tab.locator("#result")).to_contain_text("normalized")
            self.assertEqual(script_errors, [])
            browser.close()


if __name__ == "__main__":
    main()
