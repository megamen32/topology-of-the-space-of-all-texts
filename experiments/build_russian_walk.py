#!/usr/bin/env python3
"""Build the cached exact-address waypoints used by the public Russian walk."""
from __future__ import annotations

import json
import re
from pathlib import Path

from backend_app import RUSSIAN_WALK_TEXTS, exact_cluster_ranker


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "models/russian_walk_v1.json"


def main() -> None:
    ranker = exact_cluster_ranker(64)
    word_re = re.compile(r"[а-яё]+", re.I)
    word_sets = [set(word_re.findall(text.lower())) for _, text in RUSSIAN_WALK_TEXTS]
    pages = []
    for index, (title, text) in enumerate(RUSSIAN_WALK_TEXTS):
        ranked = ranker.rank_text(text)
        previous = word_sets[(index - 1) % len(word_sets)]
        union = word_sets[index] | previous
        novelty = 1 - (len(word_sets[index] & previous) / len(union) if union else 0)
        pages.append({
            "index": index,
            "title": title,
            "text": text,
            "page": ranked["page"],
            "energy": ranked["energy"],
            "rank": str(ranked["rank"]),
            "rank_hex": hex(ranked["rank"]),
            "word_novelty_from_previous": round(novelty, 3),
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"version": "russian_walk_v1", "length": 64, "pages": pages}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(pages)} exact waypoints)")


if __name__ == "__main__":
    main()
