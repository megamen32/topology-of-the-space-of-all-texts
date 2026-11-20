#!/usr/bin/env python3
"""Legacy round-trip canary and blind sampling of production Babel-1 and raw pages.

The `blind` subcommand freezes addresses, excerpt positions and presentation
order before decoding. Only blind.jsonl goes to the annotator. The private
key contains the complete plan, input identifiers and hashes of the full pages.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from io import TextIOWrapper
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from typing import TextIO
import argparse
import json
import sys

from babel_shell_v1 import (
    MARKOV5_META, ROOT, BabelRanker4096, BinaryShellRanker, ContextPermutationMarkov5, ContextPermutationV1,
)

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(20_000)

PAGE_LENGTH = 4096
TOP_K = 16
MAX_PER_GROUP = 64
MAX_PROSE_PAGES = 16
PROTOCOL = "babel-1-raw-blind-v1"
RAW_MODEL = "models/student_fsm_v1/student_fsm_v1.json"  # backend_app.ALPHA
# SHA-256 of the 256 one-character symbols concatenated in byte-index order, UTF-8.
BABEL_ALPHABET_SHA256 = "7d7450886f4c94fbc0752fee9961f824f40d97b3209aa86da8f241bf45801d08"
RAW_ALPHABET_SHA256 = "3822ea165690383f71908c46186db495e0c3ce5180a75e934d1b10b99613b6ac"
PROSE_FILE = "datasets/cache_v1/normalized.txt"
# First sentence of Белые ночи after the epigraph. Pin 16 complete, adjacent pages.
PROSE_BYTE_OFFSET = 9_807_492
PROSE_SHA256 = "9a8b376da00189f83fd5f9c14e8de225018978b2f0eff2409ce7acaa40b3a0b0"


def distinct_ranks(rng: Random, start: int, stop: int, count: int) -> list[int]:
    """Draw and swap out each selected slot without materializing the address range."""
    ranks = []
    moved = {}
    for _ in range(count):
        slot = rng.randrange(start, stop)
        ranks.append(moved.get(slot, slot))
        stop -= 1
        moved[slot] = moved.get(stop, stop)
    return ranks


def blind_plan(shell: BinaryShellRanker, count: int, length: int, seed: int, prose: str) -> dict:
    addresses = Random(f"{PROTOCOL}/{seed}/addresses")
    windows = Random(f"{PROTOCOL}/{seed}/windows")
    end_zero = shell.shell_starts[1]  # exclusive, k**4096
    strata = {
        "first": range(count),
        "rest_of_shell_0": distinct_ranks(addresses, count, end_zero, count),
        "outside_shell_0": distinct_ranks(addresses, end_zero, shell.space_size, count),
    }
    samples = []
    prose_fragments = set()
    for index in range(count):
        # The same position across all groups for this draw, including each raw pair.
        window = {"draw_index": index, "offset": windows.randrange(shell.length - length + 1)}
        for stratum, ranks in strata.items():
            rank = ranks[index]
            pair = {**window, "stratum": stratum, "rank_hex": hex(rank)}
            shell_number, _ = shell.shell_for_rank(rank)
            samples.append({**pair, "group": "babel_1_markov5", "shell": shell_number})
            samples.append({**pair, "group": "raw_api_normalized"})
        if prose and index < MAX_PROSE_PAGES:
            # Keep the prespecified window. Short identical positive excerpts enter only once.
            start = index * PAGE_LENGTH + window["offset"]
            fragment = prose[start:start + length]
            if fragment not in prose_fragments:
                prose_fragments.add(fragment)
                samples.append({**window, "group": "known_prose", "source_page": index})
    Random(f"{PROTOCOL}/{seed}/shuffle").shuffle(samples)
    for number, sample in enumerate(samples, start=1):
        sample["id"] = f"S{number:03d}"
    return {
        "protocol": PROTOCOL, "seed": seed, "per_group": count, "fragment_length": length,
        "page_length": shell.length, "q": shell.q, "k": shell.k, "prose_count": len(prose_fragments),
        "samples": samples,
    }


def load_prose() -> str:
    with (ROOT / PROSE_FILE).open("rb") as source:
        source.seek(PROSE_BYTE_OFFSET)
        with TextIOWrapper(source, encoding="utf-8", newline="") as text:
            passage = text.read(MAX_PROSE_PAGES * PAGE_LENGTH)
    if sha256(passage.encode("utf-8")).hexdigest() != PROSE_SHA256:
        raise ValueError("Текст «Белых ночей» в локальном корпусе отличается от контрольного.")
    return passage


def raw_api_page(rank: int, alphabet: tuple[str, ...]) -> str:
    # backend_app.unrank_int extracts 4096 low bytes and then reverses them.
    return "".join(alphabet[byte] for byte in rank.to_bytes(PAGE_LENGTH, "big"))


def write_fragments(
    blind: TextIO, plan: dict, ranker: BabelRanker4096, raw_alphabet: tuple[str, ...], prose: str,
) -> dict[str, str]:
    page_hashes = {}
    for sample in plan["samples"]:
        group = sample["group"]
        if group == "known_prose":
            start = sample["source_page"] * PAGE_LENGTH
            page = prose[start:start + PAGE_LENGTH]
        elif group == "raw_api_normalized":
            page = raw_api_page(int(sample["rank_hex"], 16), raw_alphabet)
        else:
            result = ranker.unrank_page(int(sample["rank_hex"], 16))
            if result["shell"] != sample["shell"]:
                raise ValueError("Оболочка декодированной страницы расходится с планом.")
            page = result["page"]
        if len(page) != PAGE_LENGTH:
            raise ValueError(f"Длина полной страницы {sample['id']} отличается от {PAGE_LENGTH}.")
        offset = sample["offset"]
        fragment = page[offset:offset + plan["fragment_length"]]
        blind.write(json.dumps({"id": sample["id"], "text": fragment}, ensure_ascii=False) + "\n")
        page_hashes[sample["id"]] = sha256(page.encode("utf-8")).hexdigest()
    return page_hashes


def run_blind(args: argparse.Namespace) -> None:
    if not 1 <= args.per_group <= MAX_PER_GROUP:
        raise ValueError(f"--per-group должен быть от 1 до {MAX_PER_GROUP}.")
    if not 1 <= args.fragment_length <= PAGE_LENGTH:
        raise ValueError(f"--fragment-length должен быть от 1 до {PAGE_LENGTH}.")
    if args.out and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError(f"Путь {args.out} уже занят.")

    # Same constructor as backend_app.babel_1_ranker(). Planning alone needs only its shell counts.
    ranker = None if args.plan_only else BabelRanker4096(length=PAGE_LENGTH, k=TOP_K)
    shell = ranker.shell if ranker is not None else BinaryShellRanker(length=PAGE_LENGTH, q=256, k=TOP_K)
    prose = "" if args.no_prose else load_prose()
    plan = blind_plan(shell, args.per_group, args.fragment_length, args.seed, prose)
    encoded_plan = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("ascii")
    digest = sha256(encoded_plan).hexdigest()
    print(f"Образцов {len(plan['samples'])}, страниц Babel-1 {3 * args.per_group}, "
          f"литературных контролей {plan['prose_count']}. SHA-256 плана {digest}", flush=True)
    if ranker is None:
        return

    raw_alphabet = tuple(json.loads((ROOT / RAW_MODEL).read_text(encoding="utf-8"))["alphabet"])
    if sha256("".join(raw_alphabet).encode("utf-8")).hexdigest() != RAW_ALPHABET_SHA256:
        raise ValueError("Изменился порядок символов в нормализованном алфавите raw API.")
    meta_bytes = MARKOV5_META.read_bytes()
    meta = json.loads(meta_bytes)
    babel_alphabet_hash = sha256("".join(ranker.alphabet).encode("utf-8")).hexdigest()
    if int(meta["context_symbols"]) != 5 or babel_alphabet_hash != BABEL_ALPHABET_SHA256:
        raise ValueError("Для Babel-1 нужна Markov-5 с историческим алфавитом из 735d351.")
    sources = {
        "babel_1_markov5": {
            "decoder": "BabelRanker4096.unrank_page", "scramble": shell.scramble,
            "alphabet_reference": "735d351:site/data/model.json", "alphabet_sha256": BABEL_ALPHABET_SHA256,
            "meta_sha256": sha256(meta_bytes).hexdigest(),
            "table_hashes_from_manifest": {
                name: meta[name] for name in ("index_sha256", "dense_rows_sha256") if name in meta
            },
        },
        "raw_api_normalized": {
            "reference_decoder": "backend_app.unrank_int", "alphabet_file": RAW_MODEL,
            "alphabet_sha256": RAW_ALPHABET_SHA256, "byte_order": "big",
        },
    }
    if prose:
        sources["known_prose"] = {
            "work": "Ф. М. Достоевский, «Белые ночи»", "file": PROSE_FILE,
            "start_byte": PROSE_BYTE_OFFSET, "characters": len(prose), "sha256": PROSE_SHA256,
        }

    # Publish both files together. A failed decode leaves the destination free for a retry.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.out.parent, prefix=f".{args.out.name}.") as tmp:
        staging = Path(tmp)
        with (staging / "blind.jsonl").open("w", encoding="utf-8", newline="\n") as blind:
            page_hashes = write_fragments(blind, plan, ranker, raw_alphabet, prose)
        code_files = [Path(__file__), Path(__file__).with_name("babel_shell_v1.py")]
        storage = sys.modules.get("markov5_storage")
        if storage is not None:
            code_files.append(Path(storage.__file__))
        key = {
            "plan": plan, "plan_sha256": digest, "sources": sources, "page_sha256": page_hashes,
            "python": sys.version.split()[0],
            "code_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in code_files},
        }
        with (staging / "key.json").open("w", encoding="utf-8", newline="\n") as out:
            json.dump(key, out, ensure_ascii=False, indent=2)
            out.write("\n")
        staging.rename(args.out)
    print(f"Слепая разметка — {args.out / 'blind.jsonl'}\nКлюч — {args.out / 'key.json'}")


def metrics(page: str) -> dict[str, float | int | str]:
    runs = [1]
    for left, right in zip(page, page[1:]):
        runs.append(runs[-1] + 1 if left == right else 1)
    letters = sum(char.isalpha() for char in page)
    return {
        "preview": page[:240],
        "max_run": max(runs),
        "whitespace_ratio": round(sum(char.isspace() for char in page) / len(page), 4),
        "letter_ratio": round(letters / len(page), 4),
        "unique_symbols": len(Counter(page)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permutation", choices=("cluster", "markov5"),
                        help="перестановка исходного canary (по умолчанию markov5)")
    blind = parser.add_subparsers(dest="command").add_parser(
        "blind", help="подготовить слепую выборку",
        description="Первые адреса, случайные адреса внутри нулевой оболочки и за её пределами. "
                    "На каждый адрес открываются полные страницы Babel-1 и raw. "
                    "Разметчику предназначен файл blind.jsonl.",
    )
    blind.add_argument("--seed", type=int, default=20261120, help="зерно выборки и перемешивания (20261120)")
    blind.add_argument("--per-group", type=int, default=2,
                       help=f"страниц на группу адресов (1–{MAX_PER_GROUP}, по умолчанию 2), до 16 образцов прозы")
    blind.add_argument("--fragment-length", type=int, default=240, help="длина фрагмента в символах (1–4096, по умолчанию 240)")
    blind.add_argument("--no-prose", action="store_true", help="пропустить положительный контроль")
    mode = blind.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true", help="вывести размер и SHA-256 плана без модели и записи файлов")
    mode.add_argument("--out", type=Path, metavar="DIR", help="новый каталог для blind.jsonl и key.json")
    args = parser.parse_args()
    if args.command == "blind":
        if args.permutation is not None:
            blind.error("Режим blind использует штатную перестановку Markov-5.")
        try:
            run_blind(args)
        except (OSError, ValueError) as exc:
            blind.exit(1, f"{blind.prog}: {exc}\n")
        return
    args.permutation = args.permutation or "markov5"
    permutation = ContextPermutationV1() if args.permutation == "cluster" else ContextPermutationMarkov5()
    ranker = BabelRanker4096(permutation=permutation)
    ranks = (0, 1, 2, 15, 16, 255, 256, ranker.space_size // 2, ranker.space_size - 1)
    samples = []
    for position, rank in enumerate(ranks):
        result = ranker.unrank_page(rank)
        assert ranker.rank_page(result["page"])["rank"] == rank
        label = str(rank) if rank < 1_000 else ("middle" if position == len(ranks) - 2 else "last")
        samples.append({"rank": label, "shell": result["shell"], **metrics(result["page"])})
    print(json.dumps({"edition": "Babel-1", "permutation": args.permutation, "samples": samples}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
