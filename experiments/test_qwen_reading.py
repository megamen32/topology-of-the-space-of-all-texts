"""Read the complete Qwen book through the same controls a reader uses."""
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import main

import test_qwen_web as web
from qwen35_reference import EDITION
from qwen_page_cache import PageCache
from qwen_reference import PAGE
from qwen_web_jobs import MODE_35


# DOM text includes all leaves, even when CSS clips their columns. Measure glyphs
# against the leaf window and hit-test them in Chromium to observe the painted leaf.
LEAF_GEOMETRY = r"""frame => {
    const book = frame.querySelector('#unrankResult');
    const bounds = frame.getBoundingClientRect();
    const inside = r => r.width > 0 && r.height > 0 &&
        r.left >= bounds.left - 1 && r.right <= bounds.right + 1 &&
        r.top >= bounds.top - 1 && r.bottom <= bounds.bottom + 1;
    const range = document.createRange();
    const middle = bounds.left + bounds.width / 2;
    const bands = new Set();
    const visible = [];
    let position = 0;
    const walker = document.createTreeWalker(book, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        let offset = 0;
        for (const symbol of node.data) {
            if (/\S/u.test(symbol)) {
                range.setStart(node, offset);
                range.setEnd(node, offset + symbol.length);
                const rect = range.getBoundingClientRect();
                if (inside(rect) && book.contains(document.elementFromPoint(
                    (rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2))) {
                    visible.push(position);
                    if (rect.right < middle) bands.add('left');
                    else if (rect.left > middle) bands.add('right');
                    else bands.add('middle');
                }
            }
            offset += symbol.length;
            position++;
        }
    }
    const scrollable = [frame, book].filter(el => {
        const style = getComputedStyle(el);
        const scrolls = value => ['auto', 'scroll', 'overlay'].includes(value);
        return (scrolls(style.overflowY) && el.scrollHeight > el.clientHeight + 1) ||
               (scrolls(style.overflowX) && el.scrollWidth > el.clientWidth + 1);
    }).map(el => el.id);
    return {visible, bands: [...bands], scrollable};
}"""


class QwenReadingTest(web.QwenSearchCase):
    def assert_all_leaves_readable(self, tab, columns):
        frame = tab.locator("#leafWindow")
        book = frame.locator("#unrankResult")
        position = tab.locator("#leafPosition")
        previous = tab.locator("#prevLeaf")
        following = tab.locator("#nextLeaf")
        web.expect(book).to_have_css("column-count", str(columns))
        unit = "Разворот" if columns == 2 else "Лист"
        web.expect(position).to_have_text(re.compile(rf"^{unit} 1 из [1-9]\d*$"))
        count = int(position.inner_text().split()[-1])
        self.assertGreater(count, 1)
        seen = set()
        history = []
        for number in range(1, count + 1):
            label = f"{unit} {number} из {count}"
            web.expect(position).to_have_text(label)
            web.expect(previous).to_be_enabled(enabled=number > 1)
            web.expect(following).to_be_enabled(enabled=number < count)
            frame.scroll_into_view_if_needed()
            geometry = frame.evaluate(LEAF_GEOMETRY)
            self.assertEqual(geometry["scrollable"], [])
            visible = geometry["visible"]
            self.assertTrue(visible, "Leaf has no fully visible text")
            if history:
                self.assertGreater(visible[-1], history[-1][1][-1], "Next leaf did not advance the text")
            else:
                self.assertEqual(visible[0], 0)
                expected_bands = {"left", "right"} if columns == 2 else {"left", "middle", "right"}
                self.assertEqual(set(geometry["bands"]), expected_bands)
            history.append((label, visible))
            seen.update(visible)
            web.expect(book).to_have_js_property("textContent", web.QWEN35_PAGE_32)
            web.expect(tab.locator("#rankInput")).to_have_value("32")
            if number < count:
                following.click()

        self.assertEqual(visible[-1], PAGE - 1, "The last character is clipped on the final leaf")
        missing = [i for i, char in enumerate(web.QWEN35_PAGE_32) if not char.isspace() and i not in seen]
        self.assertEqual(len(missing), 0, f"First unreadable character offsets: {missing[:10]}")
        for label, visible in reversed(history[:-1]):
            previous.click()
            web.expect(position).to_have_text(label)
            frame.scroll_into_view_if_needed()
            self.assertEqual(frame.evaluate(LEAF_GEOMETRY)["visible"], visible)
        web.expect(previous).to_be_disabled()

    def test_default_cached_book_reflows_and_turns_offline(self):
        with TemporaryDirectory() as directory:
            cache = PageCache(Path(directory) / "pages.sqlite3")
            cache.store(EDITION, 32, web.QWEN35_PAGE_32)
            self.jobs35.page_cache = cache
            tab = self.open_search(viewport={"width": 1280, "height": 800})
            self.assertFalse(self.fake35.started.is_set(), "A warm opening contacted the model")
            details = tab.locator("details#reverseLookup")
            web.expect(details).to_have_js_property("open", False)
            web.expect(tab.locator("#query")).to_be_hidden()
            summary = details.locator(":scope > summary")
            web.expect(summary).to_have_text("Найти номер по тексту")
            summary.press("Enter")
            web.expect(tab.locator("#query")).to_be_visible()
            web.expect(tab.locator("#query")).to_have_value("")
            summary.press("Enter")
            web.expect(details).to_have_js_property("open", False)

            tab.evaluate("document.fonts.ready")
            requests = []
            tab.on("request", lambda request: requests.append(request.url))
            tab.context.set_offline(True)
            self.assert_all_leaves_readable(tab, columns=2)
            for width, columns in ((901, "2"), (900, "1")):
                tab.set_viewport_size({"width": width, "height": 800})
                web.expect(tab.locator("#unrankResult")).to_have_css("column-count", columns)
            tab.set_viewport_size({"width": 390, "height": 740})
            self.assert_all_leaves_readable(tab, columns=1)
            self.assertEqual(requests, [])

    def test_book_menu_exports_full_text_from_a_later_leaf_without_changing_draft(self):
        tab = self.open_editor(mode=None, viewport={"width": 390, "height": 740})
        draft = "Мой\u202fчерновик 😂"
        query = tab.locator("#query")
        query.fill(draft)
        self.assert_page_exports(tab, draft.replace("\u202f", " ").ljust(PAGE))
        tab.click("#reverseLookup > summary")
        web.expect(query).to_be_hidden()

        tail = "😀\n  "
        page = ("\ufeffКнига 33.\n" + web.QWEN35_PAGE_32)[:PAGE - len(tail)] + tail
        self.fake35.pages[33] = page
        tab.click("#nextAddress")
        web.expect(tab.locator("#unrankResult")).to_have_js_property("textContent", page)
        tab.click("#nextLeaf")
        web.expect(tab.locator("#prevLeaf")).to_be_enabled()
        position = tab.locator("#leafPosition")
        leaf = position.inner_text()
        tools = tab.locator("details#bookTools")
        tools.locator(":scope > summary").click()
        status = tools.locator("#bookActionStatus")
        tools.locator("#copyOpenedPage").click()
        web.expect(status).to_contain_text("скопирована")
        self.assertEqual(tab.evaluate("navigator.clipboard.readText()"), page)
        with tab.expect_download() as download:
            tools.locator("#downloadOpenedPage").click()
        web.expect(status).to_contain_text("Скачивание")
        self.assertEqual(download.value.path().read_bytes(), page.encode("utf-8"))
        web.expect(position).to_have_text(leaf)
        web.expect(query).to_have_value(draft)

    def test_adjacent_addresses_are_exact_and_stop_at_edition_limits(self):
        tab = self.open_search()
        previous = tab.locator("#prevAddress")
        following = tab.locator("#nextAddress")
        web.expect(previous).to_have_accessible_name("Предыдущая страница")
        web.expect(following).to_have_accessible_name("Следующая страница")
        big = (1 << 53) + 1
        maximum = web.MAXIMUM
        for index, number in enumerate((0, 1, big - 1, big, big + 1, maximum - 1, maximum)):
            self.fake35.pages[number] = f"Книга {index}.".ljust(PAGE)

        steps = [
            ("unrankBtn", 0), ("nextAddress", 1), ("prevAddress", 0),
            ("unrankBtn", big), ("prevAddress", big - 1), ("nextAddress", big), ("nextAddress", big + 1),
            ("unrankBtn", maximum), ("prevAddress", maximum - 1), ("nextAddress", maximum),
        ]
        for button, number in steps:
            with self.subTest(button=button, number=hex(number)[-20:]):
                if button == "unrankBtn":
                    tab.fill("#rankInput", hex(number) if number == maximum else str(number))
                with tab.expect_request("**/api/unrank") as request:
                    tab.locator("#" + button).press("Enter")
                data = request.value.post_data_json
                self.assertEqual(data["mode"], MODE_35)
                self.assertEqual(int(data["rank"], 0), number)
                web.expect(tab.locator("#unrankResult")).to_have_js_property("textContent", self.fake35.pages[number])
                self.assertEqual(int(tab.input_value("#rankInput"), 0), number)
                web.expect(previous).to_be_enabled(enabled=number > 0)
                web.expect(following).to_be_enabled(enabled=number < maximum)

    def test_pending_and_failed_open_preserve_the_current_leaf(self):
        tab = self.open_search()
        book = tab.locator("#leafWindow #unrankResult")
        status = tab.locator("#bookStatus")
        position = tab.locator("#leafPosition")
        title = tab.locator("#pageTitle")
        tab.click("#nextLeaf")
        current_leaf = position.inner_text()
        current_title = title.inner_text()

        # The automatic opening has already signalled started. Gate the next job.
        self.fake35.started.clear()
        self.fake35.release.clear()
        try:
            tab.click("#nextAddress")  # Address 33 is absent from the injected service.
            self.assertTrue(self.fake35.started.wait(2))
            web.expect(status).to_contain_text(re.compile("очереди|вычисляет", re.I))
            web.expect(tab.locator("#result")).to_be_empty()
            web.expect(book).to_have_js_property("textContent", web.QWEN35_PAGE_32)
            web.expect(position).to_have_text(current_leaf)
        finally:
            self.fake35.release.set()
        web.expect(status).to_contain_text("недоступна")
        web.expect(tab.locator("#result")).to_be_empty()
        web.expect(book).to_have_js_property("textContent", web.QWEN35_PAGE_32)
        web.expect(position).to_have_text(current_leaf)
        web.expect(title).to_have_text(current_title)

        requests = []
        tab.on("request", lambda request: requests.append(request.url))
        for invalid, message in (("-1", "десятичный"), (str(web.MAXIMUM + 1), "превышает")):
            tab.fill("#rankInput", invalid)
            tab.click("#unrankBtn")
            web.expect(status).to_contain_text(message)
            web.expect(book).to_have_js_property("textContent", web.QWEN35_PAGE_32)
            web.expect(position).to_have_text(current_leaf)
            web.expect(title).to_have_text(current_title)
        self.assertFalse(any(url.endswith("/api/unrank") for url in requests))

        self.fake35.pages[33] = "Следующая книга.".ljust(PAGE)
        with tab.expect_request("**/api/unrank") as retry:
            tab.click("#nextAddress")
        self.assertEqual(retry.value.post_data_json, {"mode": MODE_35, "rank": "33"})
        web.expect(book).to_have_js_property("textContent", self.fake35.pages[33])
        web.expect(tab.locator("#rankInput")).to_have_value("33")
        web.expect(status).to_be_empty()
        web.expect(tab.locator("#prevLeaf")).to_be_disabled()


if __name__ == "__main__":
    main()
