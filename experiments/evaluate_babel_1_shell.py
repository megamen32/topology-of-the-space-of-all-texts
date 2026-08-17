#!/usr/bin/env python3
"""Reproducible quality canary for the first Babel-1 shells.

This is deliberately an evaluation, not a proof of language quality.  The
round-trip assertion verifies the mathematical claim; the printed metrics make
the separate product hypothesis inspectable.
"""
from __future__ import annotations

from collections import Counter
import json
import sys

from babel_shell_v1 import BabelRanker4096

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(20_000)


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
    ranker = BabelRanker4096()
    ranks = (0, 1, 2, 15, 16, 255, 256, ranker.space_size // 2, ranker.space_size - 1)
    samples = []
    for position, rank in enumerate(ranks):
        result = ranker.unrank_page(rank)
        assert ranker.rank_page(result["page"])["rank"] == rank
        label = str(rank) if rank < 1_000 else ("middle" if position == len(ranks) - 2 else "last")
        samples.append({"rank": label, "shell": result["shell"], **metrics(result["page"])})
    print(json.dumps({"edition": "Babel-1", "samples": samples}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
