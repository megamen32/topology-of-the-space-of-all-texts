"""Search jobs for a single-slot Qwen edition and its completed pages."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from os import environ
from secrets import token_urlsafe
from threading import Lock
from time import monotonic
from unicodedata import name as unicode_name

from ollama_generative_address import INDEX as EDITION_INDEX
from qwen_page_cache import PageCacheConflict
from qwen_reference import ADDRESS_ENDPOINT, EDITION, PAGE, ReferenceClient, ReferenceUnavailable, parse_number


MODE = "qwen_reference_v1"
MODE_35 = "qwen35_reference_v1"
MAX_DECIMAL_DIGITS = len(str(Decimal((1 << (8 * PAGE)) - 1)))
CHARACTER_NAMES = {
    "\u202f": "узкий неразрывный пробел", "\u00a0": "неразрывный пробел",
    "\r": "возврат каретки", "\t": "табуляция",
}


def job_input(operation, body):
    field = "text" if operation == "rank" else "rank"
    allowed = {"mode", "length", field}
    if operation == "rank":
        allowed.add("replace_unsupported")
    if body.keys() - allowed:
        raise ValueError("Запрос содержит лишние поля.")
    length = body.get("length", PAGE)
    if type(length) is not int or length != PAGE:
        raise ValueError(f"Длина страницы Qwen — ровно {PAGE} знаков.")
    value = body.get(field)
    if operation == "rank":
        if not isinstance(value, str):
            raise ValueError("Передайте текст страницы строкой в поле text.")
        if len(value) > PAGE:
            raise ValueError(f"Текст страницы превышает лимит в {PAGE} знаков.")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Страница содержит недопустимый символ Unicode.") from None
        replace = body.get("replace_unsupported", False)
        if type(replace) is not bool:
            raise ValueError("Поле replace_unsupported должно быть логическим.")
        if replace:
            value = "".join(ch if ch in EDITION_INDEX else " " for ch in value)
        return value.ljust(PAGE, " ")
    if not isinstance(value, str):
        raise ValueError("Введите десятичный номер или шестнадцатеричный номер с префиксом 0x.")
    limit = 2 + 2 * PAGE if value.startswith(("0x", "0X")) else MAX_DECIMAL_DIGITS
    if len(value) > limit:
        raise ValueError("Слишком много цифр в номере страницы.")
    return parse_number(value)


def page_result(edition, page, number, *, cached):
    return {"status": "done", "edition": edition, "length": PAGE, "cached": cached,
            "page": page, "rank": str(Decimal(number)), "rank_hex": hex(number)}, 200


def describe_rank_error(page, error):
    for position, char in enumerate(page, 1):
        if char not in EDITION_INDEX:
            name = CHARACTER_NAMES.get(char) or unicode_name(char, "знак без имени Unicode")
            glyph = f"«{char}» " if char.isprintable() and not char.isspace() else ""
            return f"Знак {glyph}{name} (U+{ord(char):04X}) в позиции {position} вне алфавита."
    return str(error)


def job_result(client, operation, value, edition=EDITION, page_cache=None):
    if operation == "rank":
        page = value
        try:
            number = client.rank(page)
        except ValueError as exc:
            return {"status": "error", "error": describe_rank_error(page, exc)}, 400
        if type(number) is not int or number < 0 or number.bit_length() > 8 * PAGE:
            return {"status": "error", "error": "Служба Qwen вернула номер вне диапазона издания."}, 503
    else:
        page, number = client.unrank(value), value
        if not isinstance(page, str) or len(page) != PAGE or any(ch not in EDITION_INDEX for ch in page):
            return {"status": "error", "error": "Служба Qwen вернула страницу неверной длины или вне алфавита издания."}, 503
    if page_cache is not None:
        page_cache.store(edition, number, page)
    return page_result(edition, page, number, cached=False)


class QueueFull(Exception):
    pass


class QwenJobs:
    def __init__(self, client_factory=ReferenceClient, *, max_active=4, max_results=16, ttl=900,
                 endpoint_variable="BABEL_QWEN_ENDPOINT", default_endpoint=ADDRESS_ENDPOINT, edition=EDITION,
                 page_cache=None):
        self.client_factory = client_factory
        self.endpoint_variable = endpoint_variable
        self.default_endpoint = default_endpoint
        self.edition = edition
        self.page_cache = page_cache
        self.max_active = max_active
        self.max_results = max_results
        self.ttl = ttl
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="babel-qwen")
        self.lock = Lock()
        self.active = {}
        self.finished = OrderedDict()

    def _prune(self):
        deadline = monotonic() - self.ttl
        while self.finished:
            created, _, _ = next(iter(self.finished.values()))
            if len(self.finished) <= self.max_results and created > deadline:
                break
            self.finished.popitem(last=False)

    def _cached(self, operation, value):
        if self.page_cache is not None:
            pair = self.page_cache.lookup(self.edition, operation, value)
            if pair is not None:
                return page_result(self.edition, *pair, cached=True)

    def submit(self, operation, value):
        cached = self._cached(operation, value)
        with self.lock:
            self._prune()
            job_id = token_urlsafe(24)
            if cached is not None:
                self.finished[job_id] = (monotonic(), *cached)
                self._prune()
                return job_id
            if len(self.active) >= self.max_active:
                raise QueueFull
            self.active[job_id] = self.executor.submit(self._run, job_id, operation, value)
        return job_id

    def _run(self, job_id, operation, value):
        try:
            # A job ahead of this one may have finished either direction of the same page.
            cached = self._cached(operation, value)
            if cached is None:
                client = self.client_factory(endpoint=environ.get(self.endpoint_variable, self.default_endpoint))
                result, code = job_result(client, operation, value, self.edition, self.page_cache)
            else:
                result, code = cached
        except ValueError as exc:
            result, code = {"status": "error", "error": str(exc)}, 400
        except PageCacheConflict as exc:
            result, code = {"status": "error", "error": str(exc)}, 503
        except (ReferenceUnavailable, OSError):
            result, code = {"status": "error", "error": "Служба издания Qwen недоступна. Попробуйте позже."}, 503
        except Exception:
            # Always release the slot and keep internal client details out of public responses.
            result, code = {"status": "error", "error": "Не удалось вычислить страницу Qwen."}, 500
        with self.lock:
            del self.active[job_id]
            self.finished[job_id] = (monotonic(), result, code)
            self._prune()

    def poll(self, job_id):
        with self.lock:
            self._prune()
            if job_id in self.active:
                return {"status": "running" if self.active[job_id].running() else "queued"}, 202
            if job_id in self.finished:
                _, result, code = self.finished[job_id]
                return result, code
        return {"status": "error", "error": "Задание не найдено или срок хранения истёк."}, 404
