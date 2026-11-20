#!/usr/bin/env python3
"""GenerativeAddress с двумя предсказаниями Qwen3 по 2048 индексов Babel-1."""
from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import time
from contextlib import closing
from decimal import Decimal
from hashlib import sha256, shake_256
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

if __package__:
    from .generative_coupling import GenerativeAddress
else:
    from generative_coupling import GenerativeAddress


HALF = 2048
EDITION = "babel-qwen3-1.7b-ollama0.32.1-gpu-b128-v2"
MODEL = "qwen3:1.7b"
RUNTIME = "0.32.1"
MANIFEST_SHA256 = "8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7"
GGUF_SHA256 = "3d0b790534fe4b79525fc3692950408dca41171676ed7e21db57af5c65ef6ab6"
ALPHABET_SHA256 = "7d7450886f4c94fbc0752fee9961f824f40d97b3209aa86da8f241bf45801d08"
ALPHABET_FILE = Path(__file__).resolve().parents[1] / "models/top256_alphabet/alphabet_top256.json"
ALPHABET = "".join(json.loads(ALPHABET_FILE.read_bytes())["alphabet"])
if sha256(ALPHABET.encode("utf-8")).hexdigest() != ALPHABET_SHA256:
    raise ValueError("Изменился исходный алфавит Babel-1.")
INDEX = {char: i for i, char in enumerate(ALPHABET)}

FLAGS = {"raw": True, "stream": False, "think": False, "keep_alive": 0}
OPTIONS = {
    "num_ctx": 4096, "num_batch": 128, "num_gpu": 99, "num_thread": 1, "num_predict": 1024,
    "temperature": 0, "top_k": 1, "top_p": 1.0, "min_p": 0.0,
    "repeat_penalty": 1.0, "repeat_last_n": 0, "presence_penalty": 0.0, "frequency_penalty": 0.0,
    "stop": ["<|im_end|>", "<|im_start|>", "<|endoftext|>"],
}
MAX_CALLS = 8
RAW = "<|im_start|>user\n{excerpt}{task}\n/no_think<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
EXCERPT = "<excerpt>\n{text}\n</excerpt>\n\n"
OMISSION = "\n[…]\n"
STORY = {
    "ru": {
        "open": "Начни рассказ на русском. Герой — {role}, место — {place}, "
                "предмет — {object}, время — {clock}. Свяжи эти детали одним событием. "
                "Начни сразу со сцены.",
        "continue": "Продолжи рассказ на русском с места обрыва. Сохрани голос, персонажей и ход "
                    "событий. Если фрагмент завершён или нечитаем, открой следующую сцену.",
        "retry": "Покажи, что произойдёт дальше. Часть {part}.",
        "write": "Напиши 5–8 новых развёрнутых абзацев, около 600 слов. Не переписывай и не "
                 "пересказывай предыдущий текст. Выведи только новую прозу без заголовка.",
        "roles": ["часовщик", "геолог", "курьер", "врач", "садовник", "переводчица"],
        "places": ["пристань", "обсерватория", "вокзал", "оранжерея", "мастерская", "горная гостиница"],
        "objects": ["ключ", "фотография", "билет", "компас", "конверт", "чертёж"],
    },
    "en": {
        "open": "Begin a story in English. Character: {role}. Setting: {place}. "
                "Object: {object}. Time: {clock}. Connect these details through one event. "
                "Begin directly in the scene.",
        "continue": "Continue the story in English exactly where it breaks off. Preserve its voice, "
                    "characters and events. If the excerpt has ended or is unreadable, start the next scene.",
        "retry": "Show what happens next. Part {part}.",
        "write": "Write 5–8 new, fully developed paragraphs, about 600 words. Do not rewrite, copy "
                 "or summarize the preceding text. Output only new prose, without a heading.",
        "roles": ["watchmaker", "geologist", "courier", "doctor", "gardener", "translator"],
        "places": ["wharf", "observatory", "railway station", "greenhouse", "workshop", "mountain inn"],
        "objects": ["key", "photograph", "ticket", "compass", "envelope", "drawing"],
    },
}


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def decode(indices: bytes) -> str:
    return "".join(ALPHABET[i] for i in indices)


def strict_indices(data: bytes, length: int) -> bytes:
    text = data.decode("utf-8")  # An initial U+FEFF is itself a legal symbol.
    if len(text) != length:
        raise ValueError(f"Ожидалось {length} знаков, получено {len(text)}.")
    try:
        return bytes(INDEX[c] for c in text)
    except KeyError as exc:
        char = exc.args[0]
        raise ValueError(f"Знак U+{ord(char):04X} в позиции {text.index(char) + 1} вне алфавита.") from None


# Only generated text passes through this mapping. Preserve supported code points.
TRANSLATE = str.maketrans({
    "\r": "\n", "\t": " ", "\u00a0": " ", "\u202f": " ", "‑": "-", "‐": "-",
    **{c: c.lower() for c in "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ" if c not in INDEX},
})


def normalize_response(text: str) -> bytes:
    if text.lstrip().startswith("<think>"):
        text = text.partition("</think>")[2].removeprefix("\n\n")
    text = text.replace("\r\n", "\n").translate(TRANSLATE)
    legal = "".join(c for c in text if c in INDEX)
    return bytes(INDEX[c] for c in legal) if legal.strip() else b""


def seed_language(seed: bytes) -> str:
    return "en" if seed[-1] & 1 else "ru"


def text_language(text: str, material: bytes) -> str:
    ru = sum("А" <= c <= "я" or c in "Ёё" for c in text)
    en = sum("A" <= c <= "Z" or "a" <= c <= "z" for c in text)
    if ru == en:
        return seed_language(material)
    return "ru" if ru > en else "en"


def raw_prompt(task: str, context: str) -> str:
    if not context:
        return RAW.format(excerpt="", task=task)
    frame = RAW.format(excerpt=EXCERPT.format(text=""), task=task)
    # Byte-level BPE needs at most one token per UTF-8 byte. Reserve the entire decode budget.
    budget = OPTIONS["num_ctx"] - OPTIONS["num_predict"] - len(frame.encode("utf-8")) - 8
    context = context.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    data = context.encode("utf-8")
    if len(data) > budget:
        available = budget - len(OMISSION.encode("utf-8"))
        head = available // 4
        tail = available - head
        context = data[:head].decode("utf-8", "ignore") + OMISSION + data[-tail:].decode("utf-8", "ignore")
    return RAW.format(excerpt=EXCERPT.format(text=context), task=task)


def http_transport(endpoint: str):
    url = urlsplit(endpoint)
    if (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
            or url.query or url.fragment):
        raise ValueError("Для --endpoint нужен базовый HTTP(S) URL без реквизитов, запроса и фрагмента.")
    connection = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection

    def request(path, body=None):
        with closing(connection(url.hostname, url.port, timeout=600)) as conn:
            data = canonical_json(body) if body is not None else None
            conn.request("GET" if data is None else "POST", url.path.rstrip("/") + path,
                         body=data, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            if response.status != 200:
                raise ValueError(f"{path} вернул HTTP {response.status}.")
            result = json.loads(response.read())
        if not isinstance(result, dict) or "error" in result:
            raise ValueError(f"Некорректный ответ {path}.")
        return result

    return request


def verify_edition(request) -> None:
    if request("/api/version").get("version") != RUNTIME:
        raise ValueError(f"Для этого издания требуется Ollama {RUNTIME}.")
    models = request("/api/tags").get("models")
    if not isinstance(models, list):
        raise ValueError("В /api/tags отсутствует список моделей.")
    matches = [m.get("digest") for m in models if isinstance(m, dict) and m.get("name") == MODEL]
    if matches not in ([MANIFEST_SHA256], ["sha256:" + MANIFEST_SHA256]):
        raise ValueError(f"Модель {MODEL} отсутствует или SHA-256 манифеста не совпадает.")
    modelfile = request("/api/show", {"model": MODEL}).get("modelfile")
    base = re.search(r"^FROM[ \t]+(.+)$", modelfile, re.MULTILINE) if isinstance(modelfile, str) else None
    blob = base[1].strip().strip('"').replace("\\", "/").rsplit("/", 1)[-1] if base else ""
    if blob != "sha256-" + GGUF_SHA256:
        raise ValueError("SHA-256 слоя GGUF в FROM модели не совпадает.")


def cold_generate(request, payload):
    # On the dedicated single-slot endpoint, keep_alive=0 schedules an asynchronous unload.
    # A surviving slot could otherwise evaluate a shared prefix with different batch boundaries.
    def resident():
        models = request("/api/ps").get("models")
        if not isinstance(models, list) or not all(isinstance(m, dict) for m in models):
            raise ValueError("В /api/ps отсутствует список загруженных моделей.")
        return any(m.get("name") == MODEL or m.get("digest") in (MANIFEST_SHA256, "sha256:" + MANIFEST_SHA256)
                   for m in models)

    if resident():
        ack = request("/api/generate", {**payload, "prompt": ""})
        if ack.get("done_reason") != "unload":
            raise ValueError("Ollama не подтвердила выгрузку Qwen3.")
        deadline = time.monotonic() + 30
        while resident():
            if time.monotonic() >= deadline:
                raise ValueError("Qwen3 остаётся загруженной. Для издания нужен выделенный однослотовый endpoint.")
            time.sleep(0.1)
    return request("/api/generate", payload)


class QwenPredictors:
    """Inject request(path, body=None) to run the same checks and predictions offline."""

    def __init__(self, request):
        verify_edition(request)
        self.request = request
        self.report = {}  # Diagnostics only. Predictors never read previous calls.

    def opening(self, seed: bytes) -> bytes:
        return self._predict("opening", seed)

    def continuation(self, first: bytes) -> bytes:
        return self._predict("continuation", first)

    def _predict(self, stage: str, source: bytes) -> bytes:
        if not isinstance(source, bytes) or len(source) != HALF:
            raise ValueError(f"Предиктор ожидает {HALF} байтов индексов.")
        key = sha256(EDITION.encode("ascii") + b"\0" + stage.encode("ascii") + b"\0" + source).digest()
        first = decode(source) if stage == "continuation" else ""
        language = text_language(first, key) if first else seed_language(source)
        story = STORY[language]
        if stage == "opening":
            task = story["open"].format(
                role=story["roles"][key[4] % len(story["roles"])],
                place=story["places"][key[5] % len(story["places"])],
                object=story["objects"][key[6] % len(story["objects"])],
                clock=f"{key[7] % 24:02d}:{key[8] % 60:02d}",
            )
        else:
            task = story["continue"]
        options = {**OPTIONS, "seed": int.from_bytes(key[:4], "big") & 0x7fffffff}
        result = bytearray()
        prompts = []
        for part in range(1, MAX_CALLS + 1):
            instruction = story["continue"] if result else task
            if part > 1:
                instruction += " " + story["retry"].format(part=part)
            prompt = raw_prompt(instruction + " " + story["write"], first + decode(result))
            prompts.append(digest(prompt.encode("utf-8")))
            reply = cold_generate(self.request, {"model": MODEL, **FLAGS, "options": options, "prompt": prompt})
            reason = reply.get("done_reason")
            content = reply.get("response", "")
            if (reply.get("done") is not True or reply.get("model") != MODEL
                    or reason not in (None, "", "stop", "length") or "error" in reply
                    or not isinstance(content, str) or ("response" not in reply and reason == "length")):
                raise ValueError("Ожидался завершённый ответ /api/generate от закреплённой модели.")
            result.extend(normalize_response(content)[:HALF - len(result)])
            if len(result) == HALF:
                break
        missing = HALF - len(result)
        if missing:
            result.extend(shake_256(b"tail\0" + key + result).digest(missing))
        self.report[stage] = {
            "language": language, "seed": options["seed"], "fallback_indices": missing,
            "input_indices_sha256": digest(source), "output_indices_sha256": digest(result),
            "prompt_sha256": prompts, "options_sha256": digest(canonical_json(options)),
        }
        return bytes(result)


def parse_number(token: str, size: int) -> int:
    hexadecimal = token.startswith(("0x", "0X"))
    digits = token[2:] if hexadecimal else token
    if not re.fullmatch(r"[0-9a-fA-F]+" if hexadecimal else r"[0-9]+", digits):
        raise ValueError("Номер задаётся неотрицательным целым в десятичном виде или с префиксом 0x.")
    digits = digits.lstrip("0") or "0"
    limit = 2 * size if hexadecimal else len(str(Decimal((1 << (8 * size)) - 1)))
    if len(digits) <= limit:
        value = int(digits, 16) if hexadecimal else int(Decimal(digits))
        if value.bit_length() <= 8 * size:
            return value
    raise ValueError(f"Номер выходит за пределы {8 * size} бит.")


def write_output(path: Path, data: bytes) -> None:
    # Publish the page only after inference and the entire file write have succeeded.
    tmp = NamedTemporaryFile(dir=path.parent, prefix=".babel-", delete=False)
    name = Path(tmp.name)
    try:
        with tmp:
            tmp.write(data)
        name.replace(path)
    finally:
        name.unlink(missing_ok=True)


def self_test() -> None:
    calls = []
    empty_reply = False

    def fake(path, body=None):
        if path == "/api/version":
            return {"version": RUNTIME}
        if path == "/api/tags":
            return {"models": [{"name": MODEL, "digest": MANIFEST_SHA256}]}
        if path == "/api/show":
            return {"modelfile": "FROM /models/blobs/sha256-" + GGUF_SHA256}
        if path == "/api/ps":
            return {"models": []}
        assert path == "/api/generate" and body["raw"] and not body["think"] and not body["stream"]
        assert body["options"]["num_batch"] == 128 and body["keep_alive"] == 0
        calls.append(digest(canonical_json(body)))
        # Every call ends early. Its text depends on the prompt, including the actual opening.
        return {"model": MODEL, "done": True, "done_reason": "stop",
                "response": "" if empty_reply else (calls[-1] + " ") * 16}

    predictors = QwenPredictors(fake)
    codec = GenerativeAddress(HALF, predictors.opening, predictors.continuation)
    garbage = bytes(range(256)) * 16
    assert strict_indices(decode(garbage).encode(), 2 * HALF) == garbage
    assert normalize_response("Ё\r\n\t漢") == bytes(INDEX[c] for c in "ё\n ")
    maximum = (1 << (16 * HALF)) - 1
    for address in (0, 1, maximum):
        assert codec.rank(codec.unrank(address)) == address
        assert predictors.report["opening"]["language"] == ("en" if address & 1 else "ru")
    assert codec.unrank(codec.rank(garbage)) == garbage
    assert parse_number(str(Decimal(maximum)), 2 * HALF) == maximum
    before = len(calls)
    for _ in range(2):
        predictors.opening(bytes(HALF))
    assert len(calls) == before + 4 and calls[-4:-2] == calls[-2:]
    empty_reply = True
    assert len(predictors.continuation(garbage[:HALF])) == HALF
    report = predictors.report["continuation"]
    assert report["fallback_indices"] == HALF and len(report["prompt_sha256"]) == MAX_CALLS
    print("OK: автономная проверка алфавита, EOS, независимых вызовов и обеих сторон адресации.")


def main(argv=None, request=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18471", help="URL выделенной однослотовой службы Ollama")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, argument, description in (
        ("unrank", "address", "записать страницу по адресу (десятичному или 0x)"),
        ("rank", "page", "найти адрес UTF-8 файла из 4096 знаков исходного алфавита"),
        ("predict", "seed", "записать прогноз начала по 16384-битному семени (десятичному или 0x)"),
        ("continue", "prefix", "записать продолжение реального начала из 2048 знаков UTF-8"),
    ):
        sub = commands.add_parser(name, help=description, description=description)
        sub.add_argument("--endpoint", default=argparse.SUPPRESS, help="базовый URL Ollama")
        sub.add_argument(argument, type=Path if name in ("rank", "continue") else str)
        if name != "rank":
            sub.add_argument("--out", required=True, type=Path, help="выходной UTF-8 файл")
        if name == "continue":
            sub.add_argument("--indices", action="store_true", help="читать начало как 2048 сырых байтов индексов")
    commands.add_parser("self-test", help="проверить адресацию и ответы в памяти без сети")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        self_test()
        return
    if args.command == "rank":
        page = strict_indices(args.page.read_bytes(), 2 * HALF)
    elif args.command == "unrank":
        address = parse_number(args.address, 2 * HALF)
    elif args.command == "predict":
        seed = parse_number(args.seed, HALF)
    else:
        data = args.prefix.read_bytes()
        first = data if args.indices else strict_indices(data, HALF)
        if len(first) != HALF:
            raise ValueError(f"Ожидалось {HALF} байтов индексов начала.")

    predictors = QwenPredictors(request if request is not None else http_transport(args.endpoint))
    codec = GenerativeAddress(HALF, predictors.opening, predictors.continuation)
    numbers = {}
    if args.command in ("rank", "unrank"):
        if args.command == "rank":
            address = codec.rank(page)
        else:
            page = codec.unrank(address)
        numbers["address"] = str(Decimal(address))
    elif args.command == "predict":
        page = predictors.opening(seed.to_bytes(HALF, "big"))
        numbers["seed"] = str(Decimal(seed))
    else:
        page = predictors.continuation(first)
    utf8 = decode(page).encode("utf-8")
    if args.command != "rank":
        write_output(args.out, utf8)
    stage = "continuation" if args.command == "continue" else "opening"
    print(json.dumps({
        "edition": EDITION, "model": MODEL, "ollama_version": RUNTIME,
        "manifest_sha256": MANIFEST_SHA256, "gguf_sha256": GGUF_SHA256, "alphabet_sha256": ALPHABET_SHA256,
        "prompt_spec_sha256": digest(canonical_json([RAW, EXCERPT, STORY, OMISSION, MAX_CALLS])),
        "options_spec_sha256": digest(canonical_json([FLAGS, OPTIONS])),
        **numbers, "language": predictors.report[stage]["language"], "symbols": len(page),
        "indices_sha256": digest(page), "utf8_sha256": digest(utf8), "predictions": predictors.report,
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, http.client.HTTPException) as error:
        sys.exit(str(error))
