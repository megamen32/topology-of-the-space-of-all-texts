"""Babel's containerized Qwen edition. Rank and unrank share the same two predictions."""
from __future__ import annotations

import argparse
import http.client
import json
import os
from contextlib import closing
from decimal import Decimal
from functools import lru_cache
from hashlib import sha256, shake_256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

if __package__:
    from . import ollama_continuation_v3 as scene
    from . import ollama_generative_address as text
    from .generative_coupling import GenerativeAddress
else:
    import ollama_continuation_v3 as scene
    import ollama_generative_address as text
    from generative_coupling import GenerativeAddress


EDITION = "babel-qwen3-ref-v1"
HALF = 2048
PAGE = HALF * 2
WIRE_LIMIT = 65536
MODEL_ENDPOINT = "http://127.0.0.1:8080"
ADDRESS_ENDPOINT = "http://127.0.0.1:18862"
# Apply the pinned repetition penalties before retaining the single best token.
DECODE = {
    "stream": False, "cache_prompt": False, "id_slot": 0, "seed": 0,
    "samplers": ["penalties", "top_k", "temperature"],
    "temperature": 0, "top_k": 1, "top_p": 1.0, "min_p": 0.0,
    "repeat_penalty": 1.0, "repeat_last_n": 0, "presence_penalty": 0.0,
    "frequency_penalty": 0.0, "stop": text.OPTIONS["stop"],
}
STAGES = {
    "opening": {"n_predict": 1024},
    "read": {"n_predict": 224},
    "plan": {"n_predict": 240, "repeat_penalty": 1.06, "repeat_last_n": 96},
    "write": {"n_predict": 1024, "repeat_penalty": 1.13, "repeat_last_n": 192, "frequency_penalty": 0.10},
}


class ReferenceUnavailable(RuntimeError):
    """An unavailable calculation has no addressable result and is never cached."""


def parse_number(token: str, size: int = PAGE) -> int:
    if not isinstance(token, str):
        raise ValueError("Номер должен быть строкой в десятичной или шестнадцатеричной записи.")
    return text.parse_number(token, size)


def transport(endpoint, timeout):
    url = urlsplit(endpoint)
    if (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
            or url.query or url.fragment):
        raise ValueError("Нужен адрес службы HTTP(S) без реквизитов.")
    connection = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection

    def request(path, payload=None):
        body = None if payload is None else text.canonical_json(payload)
        try:
            with closing(connection(url.hostname, url.port, timeout=timeout)) as conn:
                conn.request("GET" if body is None else "POST", url.path.rstrip("/") + path,
                             body=body, headers={"Content-Type": "application/json"})
                response = conn.getresponse()
                if response.status != 200:
                    raise ReferenceUnavailable(f"Служба вернула HTTP {response.status} на {path}.")
                result = json.loads(response.read())
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise ReferenceUnavailable(f"Не удалось получить ответ на {path}.") from exc
        if not isinstance(result, dict) or "error" in result:
            raise ReferenceUnavailable(f"Некорректный ответ на {path}.")
        return result

    return request


def fill_half(indices, key):
    missing = HALF - len(indices)
    return indices + shake_256(b"tail\0" + key + indices).digest(missing)


class ReferenceEdition:
    """Runs inside the pinned image. The cache holds only completed pure predictions."""

    def __init__(self, endpoint=MODEL_ENDPOINT, *, request=None):
        self.request = transport(endpoint, 600) if request is None else request
        self.codec = GenerativeAddress(HALF, lru_cache(maxsize=32)(self.opening),
                                       lru_cache(maxsize=32)(self.continuation))

    def health(self):
        props = self.request("/props")
        if props.get("total_slots") != 1 or props.get("default_generation_settings", {}).get("n_ctx") != 6144:
            raise ReferenceUnavailable("Нужен эталонный однослотовый вычислитель с контекстом 6144.")
        return {"edition": EDITION, "alphabet_sha256": text.ALPHABET_SHA256, "gguf_sha256": text.GGUF_SHA256}

    def generate(self, stage, prompt):
        params = {**DECODE, **STAGES[stage], "prompt": prompt}
        if stage in scene.CARD_FORMATS:
            params["json_schema"] = scene.CARD_FORMATS[stage]
        reply = self.request("/completion", params)
        if (reply.get("model") != EDITION or reply.get("stop") is not True
                or reply.get("stop_type") not in ("eos", "word", "limit")
                or reply.get("truncated") or not isinstance(reply.get("content"), str)):
            raise ReferenceUnavailable("Вычислитель не завершил запрос по правилам издания.")
        return reply["content"]

    def opening(self, seed):
        # Reuse the original bilingual scene selection. Model execution belongs to this edition.
        key = sha256(text.EDITION.encode("ascii") + b"\0opening\0" + seed).digest()
        story = text.STORY[text.seed_language(seed)]
        opening = story["open"].format(role=story["roles"][key[4] % len(story["roles"])],
                                      place=story["places"][key[5] % len(story["places"])],
                                      object=story["objects"][key[6] % len(story["objects"])],
                                      clock=f"{key[7] % 24:02d}:{key[8] % 60:02d}")
        indices = b""
        for part in range(1, text.MAX_CALLS + 1):
            task = story["continue"] if indices else opening
            if part > 1:
                task += " " + story["retry"].format(part=part)
            prompt = text.raw_prompt(task + " " + story["write"], text.decode(indices))
            indices += text.normalize_response(self.generate("opening", prompt))[:HALF - len(indices)]
            if len(indices) == HALF:
                break
        return fill_half(indices, key)

    def continuation(self, first):
        key = sha256(scene.EDITION.encode("ascii") + b"\0continuation\0" + first).digest()
        source = text.decode(first)
        first_read = None
        accepted_prose = False

        def generate(stage, prompt):
            nonlocal first_read, accepted_prose
            if stage == "read" and not accepted_prose:
                if first_read is None:
                    first_read = prompt
                prompt = first_read
            result = self.generate(stage, prompt)
            if stage == "write":
                result = text.decode(text.normalize_response(result))
                if result:
                    accepted_prose = True
            return result

        prose = scene.compose(source, text.text_language(source, key), generate, HALF, key)
        return fill_half(bytes(text.INDEX[c] for c in prose), key)

    def unrank(self, address: int) -> str:
        return text.decode(self.codec.unrank(address))

    def rank(self, page: str) -> int:
        return self.codec.rank(text.strict_indices(page.encode("utf-8"), PAGE))


class ReferenceClient:
    """Address API. The desktop and website never run their own prediction arithmetic."""

    def __init__(self, endpoint=None):
        self.request = transport(endpoint or os.getenv("BABEL_QWEN_ENDPOINT", ADDRESS_ENDPOINT), 3600)

    def _call(self, path, payload=None):
        result = self.request(path, payload)
        if result.get("edition") != EDITION:
            raise ReferenceUnavailable("Ответ относится к другому изданию библиотеки.")
        return result

    def health(self):
        return self._call("/health")

    def unrank(self, address: int) -> str:
        if not isinstance(address, int) or address < 0 or address.bit_length() > PAGE * 8:
            raise ValueError("Номер выходит за пределы издания.")
        result = self._call("/unrank", {"address": hex(address)})
        page = result.get("page")
        if result.get("address") != hex(address) or not isinstance(page, str) or len(page) != PAGE:
            raise ReferenceUnavailable("Служба вернула неполную страницу или другой номер.")
        return page

    def rank(self, page: str) -> int:
        text.strict_indices(page.encode("utf-8"), PAGE)
        return parse_number(self._call("/rank", {"page": page}).get("address"))


def serve(host, port, endpoint):
    edition = ReferenceEdition(endpoint)
    capacity = Lock()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data):
            body = text.canonical_json(data)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/health":
                return self.reply(404, {"error": "Неизвестная операция."})
            try:
                self.reply(200, edition.health())
            except ReferenceUnavailable as exc:
                self.reply(503, {"error": str(exc)})

        def do_POST(self):
            if self.path not in ("/rank", "/unrank"):
                return self.reply(404, {"error": "Неизвестная операция."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= WIRE_LIMIT:
                    return self.reply(413, {"error": "Недопустимая длина запроса."})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Ожидался объект JSON.")
                with capacity:
                    if self.path == "/rank":
                        page = payload.get("page")
                        if not isinstance(page, str):
                            raise ValueError("Страница должна быть строкой.")
                        result = {"address": hex(edition.rank(page))}
                    else:
                        address = parse_number(payload.get("address"))
                        result = {"address": hex(address), "page": edition.unrank(address)}
            except (ValueError, RecursionError) as exc:
                return self.reply(400, {"error": str(exc)})
            except ReferenceUnavailable as exc:
                return self.reply(503, {"error": str(exc)})
            self.reply(200, {"edition": EDITION, **result})

    with ThreadingHTTPServer((host, port), Handler) as server:
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    service = commands.add_parser("serve")
    service.add_argument("--host", default="127.0.0.1")
    service.add_argument("--port", type=int, default=8081)
    service.add_argument("--endpoint", default=MODEL_ENDPOINT)
    for name in ("rank", "unrank", "health"):
        sub = commands.add_parser(name)
        sub.add_argument("--endpoint", help="URL контейнерной службы адресации")
        if name == "rank":
            sub.add_argument("page", type=Path)
        if name == "unrank":
            sub.add_argument("number")
            sub.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "serve":
        serve(args.host, args.port, args.endpoint)
        return
    client = ReferenceClient(args.endpoint)
    if args.operation == "health":
        print(json.dumps(client.health()))
    elif args.operation == "rank":
        print(Decimal(client.rank(args.page.read_bytes().decode("utf-8"))))
    else:
        page = client.unrank(parse_number(args.number))
        text.write_output(args.out, page.encode("utf-8"))
        print(sha256(page.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, ReferenceUnavailable) as error:
        raise SystemExit(str(error)) from None
