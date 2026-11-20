"""Short-lived Search jobs for the single-slot Qwen address service."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from os import environ
from secrets import token_urlsafe
from threading import Lock
from time import monotonic

from ollama_generative_address import INDEX as EDITION_INDEX
from qwen_reference import ADDRESS_ENDPOINT, EDITION, PAGE, ReferenceClient, ReferenceUnavailable, parse_number


MODE = "qwen_reference_v1"
MAX_DECIMAL_DIGITS = len(str(Decimal((1 << (8 * PAGE)) - 1)))


def job_input(operation, body):
    field = "text" if operation == "rank" else "rank"
    if body.keys() - {"mode", "length", field}:
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
        return value.ljust(PAGE, " ")
    if not isinstance(value, str):
        raise ValueError("Введите десятичный номер или шестнадцатеричный номер с префиксом 0x.")
    limit = 2 + 2 * PAGE if value.startswith(("0x", "0X")) else MAX_DECIMAL_DIGITS
    if len(value) > limit:
        raise ValueError("Слишком много цифр в номере страницы.")
    return parse_number(value)


def job_result(client, operation, value):
    if operation == "rank":
        page, number = value, client.rank(value)
    else:
        page, number = client.unrank(value), value
        if not isinstance(page, str) or len(page) != PAGE or any(ch not in EDITION_INDEX for ch in page):
            return {"status": "error", "error": "Служба Qwen вернула страницу неверной длины или вне алфавита издания."}, 503
    return {"status": "done", "edition": EDITION, "length": PAGE,
            "page": page, "rank": str(Decimal(number)), "rank_hex": hex(number)}, 200


class QueueFull(Exception):
    pass


class QwenJobs:
    def __init__(self, client_factory=ReferenceClient, *, max_active=4, max_results=16, ttl=900):
        self.client_factory = client_factory
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

    def submit(self, operation, value):
        with self.lock:
            self._prune()
            if len(self.active) >= self.max_active:
                raise QueueFull
            job_id = token_urlsafe(24)
            self.active[job_id] = self.executor.submit(self._run, job_id, operation, value)
        return job_id

    def _run(self, job_id, operation, value):
        try:
            client = self.client_factory(endpoint=environ.get("BABEL_QWEN_ENDPOINT", ADDRESS_ENDPOINT))
            result, code = job_result(client, operation, value)
        except ValueError as exc:
            result, code = {"status": "error", "error": str(exc)}, 400
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
