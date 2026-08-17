#!/usr/bin/env python3
"""Exact finite early layer for the Babel hierarchy.

This is deliberately a *catalogue* MVP, not a claim that all ``256**4096``
pages have been globally sorted by semantic energy.  It makes one useful and
fully reversible promise now: a small, explicit prefix of addresses opens
different readable Russian pages, while every other raw page stays reachable.

The full-space map is a finite set of disjoint transpositions.  If ``P_i`` is
the raw address of structured page ``i`` and ``i < S``:

    unrank(i)   = structured_page(i)
    unrank(P_i) = raw_unrank(i)

All other raw addresses are unchanged.  Thus this is an exact permutation of
the complete raw space, rather than a second generator with an unproved
fallback.  The catalogue is mined from the existing paragraph student and is
kept separate from the future global energy order.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import json
import sys
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "data"
WORD = json.loads((SITE / "word_student.json").read_text(encoding="utf-8"))
SENT = json.loads((SITE / "sentence_student.json").read_text(encoding="utf-8"))
PARA = json.loads((SITE / "paragraph_student.json").read_text(encoding="utf-8"))
ALPHABET_MODEL = json.loads(
    (ROOT / "models" / "top256_alphabet" / "alphabet_top256.json").read_text(encoding="utf-8")
)

MAX_PAGE_LEN = 4096

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)


@dataclass(frozen=True)
class SentenceTemplate:
    template: str
    count: int


@dataclass(frozen=True)
class ParagraphShape:
    shape: str
    count: int


class HierarchicalEnumeratorV1:
    """A finite paragraph catalogue plus an exact raw-space fallback.

    A structured page is two catalogue paragraphs.  ``rank_page`` and
    ``unrank_page`` are inverse on the *whole* alphabet**4096 space; paragraph
    rank/unrank are inverse on the finite catalogue.  This is intentionally
    small enough to inspect and property-test before any production wiring.
    """

    version = "hierarchical_catalogue_v1"

    def __init__(self, page_length: int = MAX_PAGE_LEN):
        if page_length < 1:
            raise ValueError("page_length must be positive")
        alphabet = ALPHABET_MODEL["alphabet"]
        self.alphabet = tuple(alphabet if isinstance(alphabet, list) else alphabet)
        if len(self.alphabet) != 256 or len(set(self.alphabet)) != 256:
            raise ValueError("the hierarchy requires the project's 256-symbol alphabet")
        self.symbol_index = {symbol: index for index, symbol in enumerate(self.alphabet)}
        self.page_length = int(page_length)
        self.templates = tuple(
            SentenceTemplate(str(row["template"]), int(row["count"]))
            for row in SENT["templates"]
        )
        self.paragraph_shapes = tuple(
            ParagraphShape(str(row["shape"]), int(row["count"]))
            for row in PARA["top_paragraph_shapes"]
            if isinstance(row, dict) and "shape" in row
        )
        self.vocab = tuple(str(token) for token in WORD["vocab"])
        self.vocab_index = {token: index for index, token in enumerate(self.vocab)}
        self.paragraphs = self._build_catalogue(PARA.get("samples", ()))
        if len(self.paragraphs) < 2:
            raise ValueError("paragraph student must provide at least two usable samples")
        self._paragraph_index = {paragraph: index for index, paragraph in enumerate(self.paragraphs)}
        self.structured_page_count = len(self.paragraphs) ** 2
        self.raw_space_size = len(self.alphabet) ** self.page_length
        self._structured_raw_ranks = tuple(
            self.raw_rank(self._structured_page(index))
            for index in range(self.structured_page_count)
        )
        if len(set(self._structured_raw_ranks)) != self.structured_page_count:
            raise ValueError("structured catalogue produced duplicate pages")
        if any(rank < self.structured_page_count for rank in self._structured_raw_ranks):
            raise ValueError("structured pages must not collide with the early raw prefix")
        self._structured_index_by_raw_rank = {
            raw_rank: index for index, raw_rank in enumerate(self._structured_raw_ranks)
        }

    def hierarchy(self) -> dict[str, list[str]]:
        return {
            "page": ["two catalogue paragraphs", "raw-space transposition fallback"],
            "paragraph": ["sentence templates", "source paragraph catalogue"],
            "sentence_template": ["tokens"],
            "token": ["raw symbols"],
        }

    # -------------------------------------------------
    # deterministic catalogue construction
    # -------------------------------------------------

    def normalize_page(self, text: str) -> str:
        """Normalize to the project alphabet, then right-pad to page length."""
        out: list[str] = []
        for raw in str(text).lower():
            if raw in {"\ufeff", "\u200b", "\u200c", "\u200d", "\ufe0e", "\ufe0f"}:
                continue
            if unicodedata.category(raw).startswith("M"):
                continue
            if raw in "\t\r\u00a0\u2800":
                raw = " "
            elif raw in {"“", "”", "„", "‟"}:
                raw = '"'
            elif raw in {"’", "‘", "‚", "`", "´"}:
                raw = "'"
            elif raw in {"–", "—", "−"}:
                raw = "-"
            out.append(raw if raw in self.symbol_index else " ")
        return ("".join(out) + " " * self.page_length)[: self.page_length]

    def _build_catalogue(self, samples: Iterable[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        paragraphs: list[str] = []
        for sample in samples:
            paragraph = self.normalize_page(str(sample)).rstrip()
            if len(paragraph) < 80 or paragraph in seen:
                continue
            seen.add(paragraph)
            paragraphs.append(paragraph)
        return tuple(paragraphs)

    def _structured_page(self, index: int) -> str:
        if not 0 <= index < self.structured_page_count:
            raise ValueError("structured page index is outside the catalogue")
        first = index % len(self.paragraphs)
        second = index // len(self.paragraphs)
        return self.normalize_page(f"{self.paragraphs[first]}\n\n{self.paragraphs[second]}")

    # -------------------------------------------------
    # hierarchy counts and local rank/unrank
    # -------------------------------------------------

    def sentence_energy(self, template: str) -> int:
        for candidate in self.templates:
            if candidate.template == template:
                return max(1, 1_000_000 // max(1, candidate.count))
        return 10**9

    def token_energy(self, token: str) -> int:
        index = self.vocab_index.get(token)
        return 1_000_000 if index is None else index + 1

    def fallback_energy(self, raw: bytes) -> int:
        return 10**7 + len(raw)

    def count_sentence(self, template: str, energy_budget: int | None = None) -> dict:
        symbols = tuple(symbol for symbol in template.split() if symbol)
        exact_count = 1
        for symbol in symbols:
            exact_count *= self._class_size(symbol)
        minimum_energy = len(symbols)
        return {
            "template": template,
            "symbols": symbols,
            "exact_count": exact_count,
            "min_energy": minimum_energy,
            "energy_budget": energy_budget,
            "reachable_under_budget": energy_budget is None or minimum_energy <= energy_budget,
            "ordering": ["template energy", "token order"],
        }

    def count_paragraph(self, shape: str | None = None, energy_budget: int | None = None) -> dict:
        """Exactly count either one shape's token programs or the catalogue."""
        if shape is None:
            return {
                "mode": "catalogue",
                "exact_count": len(self.paragraphs),
                "energy_budget": energy_budget,
                "reachable_under_budget": energy_budget is None or energy_budget >= 0,
            }
        sentences = tuple(part.strip() for part in shape.split("|") if part.strip())
        counts = [self.count_sentence(sentence, energy_budget) for sentence in sentences]
        exact_count = 1
        for count in counts:
            exact_count *= int(count["exact_count"])
        minimum_energy = sum(int(count["min_energy"]) for count in counts)
        return {
            "mode": "shape",
            "shape": shape,
            "sentences": counts,
            "exact_count": exact_count,
            "min_energy": minimum_energy,
            "energy_budget": energy_budget,
            "reachable_under_budget": energy_budget is None or minimum_energy <= energy_budget,
        }

    def rank_paragraph(self, paragraph: str) -> dict:
        normalized = self.normalize_page(paragraph).rstrip()
        try:
            rank = self._paragraph_index[normalized]
        except KeyError as exc:
            raise ValueError("paragraph is outside the finite catalogue") from exc
        return {"rank": rank, "paragraph": normalized, "mode": "catalogue"}

    def unrank_paragraph(self, rank: int) -> dict:
        rank = int(rank)
        if not 0 <= rank < len(self.paragraphs):
            raise ValueError("paragraph rank is outside the finite catalogue")
        return {"rank": rank, "paragraph": self.paragraphs[rank], "mode": "catalogue"}

    def count_page(self, energy_budget: int | None = None) -> dict:
        """Count the full space and its finite readable prefix exactly."""
        return {
            "structured_pages": self.structured_page_count,
            "raw_fallback_pages": self.raw_space_size - self.structured_page_count,
            "exact_count": self.raw_space_size,
            "energy_budget": energy_budget,
            "ordering": "catalogue prefix, then exact raw fallback permutation",
        }

    # -------------------------------------------------
    # full raw-space exact permutation
    # -------------------------------------------------

    def raw_rank(self, page: str) -> int:
        if len(page) != self.page_length:
            raise ValueError(f"page must contain exactly {self.page_length} symbols")
        rank = 0
        for symbol in page:
            try:
                rank = rank * len(self.alphabet) + self.symbol_index[symbol]
            except KeyError as exc:
                raise ValueError(f"symbol outside the project alphabet: {symbol!r}") from exc
        return rank

    def raw_unrank(self, rank: int) -> str:
        rank = int(rank)
        if not 0 <= rank < self.raw_space_size:
            raise ValueError("raw rank is outside the complete page space")
        symbols = [self.alphabet[0]] * self.page_length
        for position in range(self.page_length - 1, -1, -1):
            rank, symbol = divmod(rank, len(self.alphabet))
            symbols[position] = self.alphabet[symbol]
        return "".join(symbols)

    def unrank_page(self, rank: int) -> dict:
        rank = int(rank)
        if not 0 <= rank < self.raw_space_size:
            raise ValueError("page rank is outside the complete page space")
        if rank < self.structured_page_count:
            return {"rank": rank, "page": self._structured_page(rank), "mode": "structured_catalogue"}
        structured_index = self._structured_index_by_raw_rank.get(rank)
        if structured_index is not None:
            return {
                "rank": rank,
                "page": self.raw_unrank(structured_index),
                "mode": "raw_fallback_swap",
            }
        return {"rank": rank, "page": self.raw_unrank(rank), "mode": "raw_fallback"}

    def rank_page(self, page: str) -> dict:
        raw_rank = self.raw_rank(page)
        structured_index = self._structured_index_by_raw_rank.get(raw_rank)
        if structured_index is not None:
            return {"rank": structured_index, "page": page, "mode": "structured_catalogue"}
        if raw_rank < self.structured_page_count:
            return {
                "rank": self._structured_raw_ranks[raw_rank],
                "page": page,
                "mode": "raw_fallback_swap",
            }
        return {"rank": raw_rank, "page": page, "mode": "raw_fallback"}

    def encode_raw_fallback(self, text: str) -> dict:
        page = self.normalize_page(text)
        return {"mode": "raw_fallback", "page": page, "rank": self.rank_page(page)["rank"]}

    def page_reachable(self, text: str) -> bool:
        return len(self.normalize_page(text)) == self.page_length

    def _class_size(self, symbol: str) -> int:
        symbol = symbol.strip()
        if symbol == "R":
            return len(WORD["abstract_emissions"].get("<ru>", ()))
        if symbol == "L":
            return len(WORD["abstract_emissions"].get("<en>", ()))
        if symbol in {"N", "E"}:
            return len(WORD["abstract_emissions"].get("<num>", ()))
        if symbol == "T":
            return 4
        if symbol == "P":
            return 3
        return 256


def demo() -> None:
    hierarchy = HierarchicalEnumeratorV1()
    first = hierarchy.unrank_page(0)
    print(json.dumps({
        "version": hierarchy.version,
        "hierarchy": hierarchy.hierarchy(),
        "paragraphs": hierarchy.count_paragraph(),
        "pages": hierarchy.count_page(),
        "first_page_mode": first["mode"],
        "first_page_preview": first["page"][:160],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    demo()
