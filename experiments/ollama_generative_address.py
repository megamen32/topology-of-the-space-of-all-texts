#!/usr/bin/env python3
"""GenerativeAddress с двумя предсказаниями Qwen3 по 2048 индексов Babel-1."""
from __future__ import annotations

import argparse
import http.client
import inspect
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


def generated_text(request, payload, receipt=None) -> str:
    reply = cold_generate(request, payload)
    reason = reply.get("done_reason")
    content = reply.get("response", "")
    if (reply.get("done") is not True or reply.get("model") != MODEL
            or reason not in (None, "", "stop", "length") or "error" in reply
            or not isinstance(content, str) or ("response" not in reply and reason == "length")):
        raise ValueError("Ожидался завершённый ответ /api/generate от закреплённой модели.")
    if receipt is not None:
        receipt.update(response_sha256=digest(content.encode("utf-8", "surrogatepass")),
                       raw_chars=len(content), done_reason=reason)
    return content


def record_lengths(receipt, normalized, accepted):
    receipt.update(normalized_chars=normalized, accepted_chars=accepted)
    if normalized > accepted:
        receipt["discarded_chars"] = normalized - accepted


def v2_prompts():
    return [RAW, EXCERPT, STORY, OMISSION, MAX_CALLS]


class QwenPredictors:
    """Inject request(path, body=None) to run the same checks and predictions offline."""

    detailed_receipts = False

    def __init__(self, request):
        verify_edition(request)
        self.request = request
        self.report = {}  # Diagnostics only. Predictors never read previous calls.

    def opening(self, seed: bytes) -> bytes:
        return self._predict("opening", seed)

    def continuation(self, first: bytes) -> bytes:
        return self._predict("continuation", first)

    def edition_info(self):
        return {"edition": EDITION, "prompt_spec_sha256": digest(canonical_json(v2_prompts())),
                "options_spec_sha256": digest(canonical_json([FLAGS, OPTIONS]))}

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
        calls = []
        for part in range(1, MAX_CALLS + 1):
            instruction = story["continue"] if result else task
            if part > 1:
                instruction += " " + story["retry"].format(part=part)
            prompt = raw_prompt(instruction + " " + story["write"], first + decode(result))
            prompts.append(digest(prompt.encode("utf-8")))
            receipt = {"stage": stage} if self.detailed_receipts else None
            payload = {"model": MODEL, **FLAGS, "options": options, "prompt": prompt}
            content = generated_text(self.request, payload, receipt)
            normalized = normalize_response(content)
            accepted = normalized[:HALF - len(result)]
            result.extend(accepted)
            if receipt is not None:
                record_lengths(receipt, len(normalized), len(accepted))
                calls.append(receipt)
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
        if self.detailed_receipts:
            self.report[stage]["calls"] = calls
        return bytes(result)


V3_KEY_DOMAIN = b"\0continuation\0"
V3_TAIL_DOMAIN = b"tail\0"
V3_SPEC_SHA256 = "8454f571169bfabef9b8761a2e36f9231200200b2ec7f7a665cd09a03be20015"
V31_EDITION = "babel-qwen3-1.7b-ollama0.32.1-gpu-b128-v3.1"
V31_SPEC_SHA256 = "838c6e6a8b6aea0b9f8ed9e4f99e49d6071586ba573363554e69242d2704f4f5"


def v3_specification(v3):
    return {
        "edition": v3.EDITION, "opening_edition": EDITION, "half_indices": HALF,
        "model": MODEL, "ollama_version": RUNTIME, "manifest_sha256": MANIFEST_SHA256,
        "gguf_sha256": GGUF_SHA256, "alphabet_sha256": ALPHABET_SHA256,
        "prompts": {"opening_v2": v2_prompts(), "continuation": v3.PROMPTS},
        "options": {"flags": FLAGS, "opening": OPTIONS,
                    **{stage: {**OPTIONS, **overrides} for stage, overrides in v3.STAGES.items()}},
        "opening_rules": {
            "reference_file_sha256": "7ff822374107bd4d9a44914f7ad758bd55719277f9804f32d3883ec5207ba35c",
            "key": ["SHA-256", "ascii(opening_edition)", b"\0opening\0".hex(), "seed indices"],
            "language": "odd final input byte selects en, even selects ru",
            "story": "key bytes 4..6 mod list lengths; key[7] mod 24, key[8] mod 60",
            "seed": "key[0:4] as uint32be & 0x7fffffff",
            "retry": "parts 1..MAX_CALLS; normalize and append up to remaining size",
            "context": "escape &, <, >; reserve num_predict, frame UTF-8 bytes and 8 tokens; "
                       "split remaining UTF-8 bytes 1:3 around OMISSION",
            "tail_domain_hex": b"tail\0".hex(),
        },
        "continuation_rules": v3.RULES,
        "key": ["SHA-256", "ascii(edition)", V3_KEY_DOMAIN.hex(), "U indices"],
        "seed": "SHA-256(key || uint16be(zero-based request ordinal))[0:4] as uint32be & 0x7fffffff",
        "language": "count Cyrillic А-я/Ёё and ASCII A-Z/a-z in U; on tie odd key[-1] selects en",
        "tail": ["SHAKE-256", V3_TAIL_DOMAIN.hex(), "key", "accepted indices", "remaining bytes"],
        "normalize": {"think_open": "<think>", "think_close": "</think>", "gap": "\n\n",
                      "crlf": ["\r\n", "\n"], "translate": {chr(k): v for k, v in TRANSLATE.items()},
                      "filter": "Babel-1 indices in order; whitespace-only response is empty"},
        "service": "dedicated single slot; verify version, manifest and GGUF; cold_generate before every decode",
        "continuation_module_sha256": digest(Path(v3.__file__).read_bytes()),
    }


class SceneRetryV31:
    """Per prediction. The frozen composer still constructs every scene and the returned page."""

    def __init__(self, v3, source):
        self.v3 = v3
        suffix = v3.finish_word(source)
        self.restored_chars = len(suffix)
        self.waiting_for_prose = bool(suffix)
        self.first_read = None
        self.remaining = HALF - len(suffix)
        self.last_char = (suffix or source)[-1]

    def read_prompt(self, prompt):
        if self.waiting_for_prose:
            if self.first_read is None:
                self.first_read = prompt
            return self.first_read
        return prompt

    def record_card(self, receipt, raw, fields):
        try:
            card = json.loads(raw)
            status = "object" if isinstance(card, dict) else "not_object"
        except (ValueError, RecursionError):
            card = None
            status = "invalid_json" if raw.strip() else "empty"
        useful = []
        normalized = accepted = 0
        if isinstance(card, dict):
            for field in fields:
                value = card.get(field)
                if isinstance(value, str):
                    data = self.v3.escaped(" ".join(value.split()))
                    normalized += len(data.decode("utf-8"))
                    kept = data[:self.v3.FIELD_BYTES].decode("utf-8", "ignore")
                    accepted += len(kept)
                    if kept.strip():
                        useful.append(field)
        receipt.update(json_status=status, useful_fields=useful)
        record_lengths(receipt, normalized, accepted)

    def record_prose(self, receipt, text):
        kept = 0
        if text:
            # Account for the frozen composer's paragraph break separately from model characters.
            separator = self.v3.PARAGRAPH if self.last_char in self.v3.END_MARKS else ""
            prose = text.lstrip() if separator or self.last_char.isspace() else text
            fragment = (separator + prose)[:self.remaining]
            inserted = min(len(separator), len(fragment))
            if inserted:
                receipt["separator_chars"] = inserted
            kept = len(fragment) - inserted
            if kept:
                self.waiting_for_prose = False
            self.remaining -= len(fragment)
            self.last_char = fragment[-1]
        record_lengths(receipt, len(text), kept)


def v31_specification(v3):
    parent = v3_specification(v3)
    implementations = (
        SceneRetryV31.__init__, SceneRetryV31.read_prompt, SceneRetryV31.record_card, SceneRetryV31.record_prose,
        generated_text, record_lengths, QwenPredictors._predict, QwenPredictorsV3.continuation,
    )
    return {
        **parent, "edition": V31_EDITION, "parent_spec_sha256": digest(canonical_json(parent)),
        "continuation_seed_edition": v3.EDITION,
        "key": ["SHA-256", "ascii(continuation_seed_edition)", V3_KEY_DOMAIN.hex(), "U indices"],
        "continuation_rules": {
            **v3.RULES,
            "retry": "With a restored suffix and no accepted model prose, reuse the first read prompt; "
                     "all other prompts, ordinal seeds, tactics and tail use the frozen v3 rules.",
        },
        "receipts": {
            "response_sha256": "raw response string encoded as UTF-8 (surrogatepass for lone surrogates)",
            "raw_chars": "code points in the raw response string; a missing response at EOS is empty",
            "normalized_chars": "alphabet characters for prose; for cards, code points of expected string "
                                "field values after whitespace compaction and escaping, before the field byte cap",
            "accepted_chars": "model characters retained after trimming and clipping; for cards, the sum of "
                              "retained field lengths; discarded_chars is normalized minus accepted",
            "json_status": ["object", "not_object", "invalid_json", "empty"],
            "useful_fields": "schema names with nonblank values after clipping",
            "accounting": "source word completion, inserted paragraph separators and final SHAKE indices "
                          "are counted separately as restored_chars, separator_chars and fallback_indices",
        },
        "revision_source_sha256": digest("\n".join(inspect.getsource(f).rstrip() for f in implementations).encode()),
    }


class QwenPredictorsV3(QwenPredictors):
    """Inherit F including its v2 domain, prompts, sampling, EOS and tail."""

    specification = staticmethod(v3_specification)
    spec_sha256 = V3_SPEC_SHA256
    retry_type = None

    def __init__(self, request):
        if __package__:
            from . import ollama_continuation_v3 as v3
        else:
            import ollama_continuation_v3 as v3
        self.v3 = v3
        self.spec = self.specification(v3)
        if digest(canonical_json(self.spec)) != self.spec_sha256:
            version = self.spec["edition"].rsplit("-", 1)[-1]
            raise ValueError(f"Спецификация издания {version} не совпадает с закреплённым SHA-256.")
        super().__init__(request)

    def edition_info(self):
        opening = super().edition_info()
        return {"edition": self.spec["edition"], "edition_spec_sha256": self.spec_sha256,
                "opening_edition": opening["edition"], "opening_prompt_spec_sha256": opening["prompt_spec_sha256"],
                "opening_options_spec_sha256": opening["options_spec_sha256"],
                "prompt_spec_sha256": digest(canonical_json(self.spec["prompts"])),
                "options_spec_sha256": digest(canonical_json(self.spec["options"]))}

    def continuation(self, first: bytes) -> bytes:
        if not isinstance(first, bytes) or len(first) != HALF:
            raise ValueError(f"Предиктор ожидает {HALF} байтов индексов.")
        key = sha256(self.v3.EDITION.encode("ascii") + V3_KEY_DOMAIN + first).digest()
        source = decode(first)
        language = text_language(source, key)
        calls = []
        retry = self.retry_type(self.v3, source) if self.retry_type is not None else None

        def generate(stage, prompt):
            if retry is not None and stage == "read":
                prompt = retry.read_prompt(prompt)
            seed_hash = sha256(key + len(calls).to_bytes(2, "big")).digest()
            seed = int.from_bytes(seed_hash[:4], "big") & 0x7fffffff
            options = {**self.spec["options"][stage], "seed": seed}
            payload = {"model": MODEL, **FLAGS, "options": options, "prompt": prompt}
            schema = self.v3.CARD_FORMATS.get(stage)
            if schema is not None:
                payload["format"] = schema
            receipt = {
                "stage": stage, "seed": seed, "prompt_sha256": digest(prompt.encode()),
                "options_sha256": digest(canonical_json(options)), "request_sha256": digest(canonical_json(payload)),
            }
            content = generated_text(self.request, payload, receipt if retry is not None else None)
            calls.append(receipt)
            if schema is not None:
                if retry is not None:
                    retry.record_card(receipt, content, schema["required"])
                return content
            text = decode(normalize_response(content))
            if retry is not None:
                retry.record_prose(receipt, text)
            return text

        prose = self.v3.compose(source, language, generate, HALF, key)
        indices = bytes(INDEX[c] for c in prose)
        missing = HALF - len(indices)
        result = indices + shake_256(V3_TAIL_DOMAIN + key + indices).digest(missing)
        self.report["continuation"] = {
            "language": language, "seed": calls[0]["seed"], "fallback_indices": missing,
            "input_indices_sha256": digest(first), "output_indices_sha256": digest(result),
            "prompt_sha256": [call["prompt_sha256"] for call in calls], "calls": calls,
        }
        if retry is not None:
            self.report["continuation"]["restored_chars"] = retry.restored_chars
        return result


class QwenPredictorsV31(QwenPredictorsV3):
    detailed_receipts = True
    specification = staticmethod(v31_specification)
    spec_sha256 = V31_SPEC_SHA256
    retry_type = SceneRetryV31

    def edition_info(self):
        return {**super().edition_info(), "continuation_seed_edition": self.v3.EDITION}


def greedy_specification(v3):
    parent = v31_specification(v3)
    options = parent["options"]
    writer = {**options["write"], "temperature": 0, "top_k": 1, "top_p": 1.0}
    return {**parent, "edition": V31_EDITION + "-greedy", "parent_spec_sha256": V31_SPEC_SHA256,
            "options": {**options, "write": writer}}


class QwenPredictorsGreedy(QwenPredictorsV31):
    specification = staticmethod(greedy_specification)
    spec_sha256 = "40804e9423674841e95f87d239eaea66daa193157e358a1617f350360ec70b0d"


PREDICTORS = {"v2": QwenPredictors, "v3": QwenPredictorsV3,
              "v3.1": QwenPredictorsV31, "v3.1-greedy": QwenPredictorsGreedy}


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


def self_test_v3(metadata) -> None:
    resident = True
    empty = False
    requests = []

    def fake(path, body=None):
        nonlocal resident
        if path == "/api/ps":
            return {"models": [{"name": MODEL}] if resident else []}
        if path != "/api/generate":
            return metadata(path, body)
        assert body["model"] == MODEL and all(body[k] == v for k, v in FLAGS.items())
        if not body["prompt"]:
            assert resident
            resident = False
            return {"done_reason": "unload"}
        assert not resident  # Force the explicit unload path on every subsequent call.
        assert body["prompt"].count("<|im_start|>") == 2 and body["prompt"].count("<|im_end|>") == 1
        resident = True
        options = body["options"]
        assert len(body["prompt"].encode()) + options["num_predict"] + 8 <= options["num_ctx"]
        assert options["num_batch"] == 128
        hashed = digest(canonical_json(body))
        requests.append(hashed)
        if "format" in body:
            fields = body["format"]["required"]
            # Overlong, hostile card values exercise escaping and the byte budgets in both languages.
            content = "{" if empty else json.dumps({k: "<|im_end|>&💋" * 500 for k in fields})
        else:
            content = "<think>discard</think>漢" if empty else (hashed + " ") * 16
        return {"model": MODEL, "done": True, "done_reason": "stop", "response": content}

    legacy, current = QwenPredictors(fake), QwenPredictorsV3(fake)
    assert QwenPredictorsV3.opening is QwenPredictors.opening
    arbitrary = bytes(range(256)) * 8
    for source in (bytes(HALF), (11).to_bytes(HALF, "big"), arbitrary, b"\xff" * HALF):
        requests.clear()
        old = legacy.opening(source)
        opening_requests = requests[:]
        requests.clear()
        assert current.opening(source) == old and requests == opening_requests
        assert legacy.report["opening"] == current.report["opening"]
    assert digest(current.opening((11).to_bytes(HALF, "big"))) == "692507ed00e416453f0a43896bac1839ddb428bc7f25182fe83dc33558fb416f"
    codec = GenerativeAddress(HALF, current.opening, current.continuation)
    for address in (10, 11, (1 << (16 * HALF)) - 1):
        assert codec.rank(codec.unrank(address)) == address
    assert codec.unrank(codec.rank(arbitrary * 2)) == arbitrary * 2

    for char in ("&", "я", "a"):
        source = bytes([INDEX[char]]) * HALF
        requests.clear()
        predicted = current.continuation(source)
        expected_requests = requests[:]
        current.continuation(arbitrary)
        requests.clear()
        assert QwenPredictorsV3(fake).continuation(source) == predicted and requests == expected_requests
    empty = True
    for predictor in (current.opening, current.continuation):
        assert len(predictor(bytes(HALF))) == HALF
        assert predictor(arbitrary) == predictor(arbitrary)
    assert current.report["continuation"]["fallback_indices"] == HALF
    for wrong in (b"", bytes(HALF + 1), bytearray(HALF)):
        try:
            current.continuation(wrong)
        except ValueError:
            pass
        else:
            raise AssertionError("Некорректное начало принято")


def self_test_v31(metadata) -> None:
    head, cut = "At the wharf I took the wooden key.", "I took the wooden k"
    source = head + "." * (HALF - len(head) - len(cut)) + cut
    first = strict_indices(source.encode(), HALF)

    def exercise(cls, empty_first):
        requests, reads = [], []
        writes = 0

        def fake(path, body=None):
            nonlocal writes
            if path != "/api/generate":
                return metadata(path, body)
            requests.append(canonical_json(body))
            fields = body.get("format", {}).get("required", [])
            if "actor" in fields:
                reads.append(body["prompt"])
                text = json.dumps({"actor": "wharf" if "wharf" in reads[-1] else "unknown"})
            elif fields:
                text = "{" if not writes else "{}"
            else:
                writes += 1
                if writes == 1:
                    text = "" if empty_first else " Next."
                else:
                    text = " " + ("key. " if "wharf" in body["prompt"] else "fog. ") * 600 + "漢"
            return {"model": MODEL, "done": True, "done_reason": "stop", "response": text}

        predictor = cls(fake)
        page = predictor.continuation(first)
        return page, requests, reads, predictor.report["continuation"]

    for empty_first in (False, True):
        old_page, old_requests, old_reads, _ = exercise(QwenPredictorsV3, empty_first)
        page, requests, reads, report = exercise(QwenPredictorsV31, empty_first)
        assert len(requests) == len(old_requests) == 6 and report["restored_chars"] == 2
        if empty_first:
            assert requests[:3] == old_requests[:3]
            assert "<passage>\ney\n</passage>" in old_reads[1]
            assert reads[0] == reads[1] and "wharf" in reads[1] and page != old_page
        else:
            assert page == old_page and requests == old_requests
        read, plan, write, _, retry_plan, retry_write = report["calls"]
        assert read["useful_fields"] == ["actor"] and plan["json_status"] == "invalid_json"
        assert retry_plan["json_status"] == "object" and retry_plan["useful_fields"] == []
        assert plan["response_sha256"] != retry_plan["response_sha256"]
        assert write["accepted_chars"] == (0 if empty_first else len(" Next."))
        assert retry_write["raw_chars"] == retry_write["normalized_chars"] + 1
        assert retry_write["discarded_chars"] == retry_write["normalized_chars"] - retry_write["accepted_chars"]
        appended = sum(c["accepted_chars"] + c.get("separator_chars", 0)
                       for c in report["calls"] if c["stage"] == "write")
        assert appended + report["restored_chars"] + report["fallback_indices"] == HALF


def self_test(edition="v2") -> None:
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
    if edition == "v3.1-greedy":
        sampled = QwenPredictorsV31(fake)
        greedy = QwenPredictorsGreedy(fake)
        assert greedy.opening(bytes(HALF)) == sampled.opening(bytes(HALF))
        assert greedy.spec["prompts"] == sampled.spec["prompts"]
        for stage in ("opening", "read", "plan"):
            assert greedy.spec["options"][stage] == sampled.spec["options"][stage]
        assert greedy.spec["options"]["write"] == {
            **sampled.spec["options"]["write"], "temperature": 0, "top_k": 1, "top_p": 1.0}
        codec = GenerativeAddress(HALF, greedy.opening, greedy.continuation)
        assert codec.unrank(codec.rank(garbage)) == garbage and codec.rank(codec.unrank(33)) == 33
        print("OK: жадное продолжение, закреплённая спецификация и обе стороны адресации.")
    elif edition == "v3.1":
        self_test_v31(fake)
        print("OK: v3.1, повторное чтение сцены, запросы v3 и учёт полученных знаков.")
    elif edition == "v3":
        self_test_v3(fake)
        print("OK: v3, идентичность F, холодные запросы, обе стороны адресации, EOS и заполнение остатка.")
    else:
        print("OK: автономная проверка алфавита, EOS, независимых вызовов и обеих сторон адресации.")


def main(argv=None, request=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18471", help="URL выделенной однослотовой службы Ollama")
    parser.add_argument("--edition", choices=PREDICTORS, default="v2", help="издание предикторов (по умолчанию v2)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, argument, description in (
        ("unrank", "address", "записать страницу по адресу (десятичному или 0x)"),
        ("rank", "page", "найти адрес UTF-8 файла из 4096 знаков исходного алфавита"),
        ("predict", "seed", "записать прогноз начала по 16384-битному семени (десятичному или 0x)"),
        ("continue", "prefix", "записать продолжение реального начала из 2048 знаков UTF-8"),
    ):
        sub = commands.add_parser(name, help=description, description=description)
        sub.add_argument("--endpoint", default=argparse.SUPPRESS, help="базовый URL Ollama")
        sub.add_argument("--edition", choices=PREDICTORS, default=argparse.SUPPRESS)
        sub.add_argument(argument, type=Path if name in ("rank", "continue") else str)
        if name != "rank":
            sub.add_argument("--out", required=True, type=Path, help="выходной UTF-8 файл")
        if name == "continue":
            sub.add_argument("--indices", action="store_true", help="читать начало как 2048 сырых байтов индексов")
    checks = commands.add_parser("self-test", help="проверить адресацию и ответы в памяти без сети")
    checks.add_argument("--edition", choices=PREDICTORS, default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.command == "self-test":
        self_test(args.edition)
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

    predictor_class = PREDICTORS[args.edition]
    predictors = predictor_class(request if request is not None else http_transport(args.endpoint))
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
        **predictors.edition_info(), "model": MODEL, "ollama_version": RUNTIME,
        "manifest_sha256": MANIFEST_SHA256, "gguf_sha256": GGUF_SHA256, "alphabet_sha256": ALPHABET_SHA256,
        **numbers, "language": predictors.report[stage]["language"], "symbols": len(page),
        "indices_sha256": digest(page), "utf8_sha256": digest(utf8), "predictions": predictors.report,
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, http.client.HTTPException) as error:
        sys.exit(str(error))
