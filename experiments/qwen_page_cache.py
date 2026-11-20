"""Persistent bidirectional index of completed pages for the Qwen web editions."""
import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from ollama_generative_address import decode, strict_indices
from qwen_reference import PAGE


logger = logging.getLogger(__name__)


class PageCacheConflict(RuntimeError):
    """Two completed results disagree about an edition's page or address."""


def address_bytes(number):
    if type(number) is not int or number < 0 or number.bit_length() > 8 * PAGE:
        raise ValueError("Номер страницы вне диапазона издания.")
    return number.to_bytes(max(1, (number.bit_length() + 7) // 8), "big")


class PageCache:
    def __init__(self, path):
        self.path = Path(path).expanduser()

    @classmethod
    def from_environment(cls):
        state = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
        return cls(os.environ.get("BABEL_PAGE_CACHE_PATH") or Path(state) / "babel" / "qwen-pages.sqlite3")

    def _connect(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Create privately before SQLite opens the file; leave an existing database intact.
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        db = sqlite3.connect(self.path, timeout=1)
        try:
            db.execute(f"""CREATE TABLE IF NOT EXISTS pages (
                edition TEXT NOT NULL,
                address BLOB NOT NULL CHECK (length(address) BETWEEN 1 AND {PAGE}),
                page BLOB NOT NULL CHECK (length(page) = {PAGE}),
                PRIMARY KEY (edition, address), UNIQUE (edition, page)
            )""")
        except sqlite3.Error:
            db.close()
            raise
        return db

    def lookup(self, edition, operation, value):
        try:
            if operation == "rank":
                key = strict_indices(value.encode("utf-8"), PAGE)
                query = "SELECT address FROM pages WHERE edition = ? AND page = ?"
            else:
                key = address_bytes(value)
                query = "SELECT page FROM pages WHERE edition = ? AND address = ?"
        except ValueError:
            return None
        try:
            with closing(self._connect()) as db:
                row = db.execute(query, (edition, key)).fetchone()
        except (OSError, sqlite3.Error) as exc:
            logger.warning("Page cache lookup unavailable (%s)", type(exc).__name__)
            return None
        if row is None:
            return None
        if operation == "rank":
            return value, int.from_bytes(row[0], "big")
        return decode(row[0]), value

    def store(self, edition, number, page):
        address = address_bytes(number)
        packed = strict_indices(page.encode("utf-8"), PAGE)
        try:
            with closing(self._connect()) as db, db:
                inserted = db.execute(
                    "INSERT INTO pages (edition, address, page) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                    (edition, address, packed),
                )
                if inserted.rowcount == 0:
                    same = db.execute("SELECT 1 FROM pages WHERE edition = ? AND address = ? AND page = ?",
                                      (edition, address, packed)).fetchone()
                    if same is None:
                        raise PageCacheConflict("Полученный результат расходится с сохранённой страницей издания.")
        except (OSError, sqlite3.Error) as exc:
            logger.warning("Page cache write unavailable (%s)", type(exc).__name__)
