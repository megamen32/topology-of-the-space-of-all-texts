#!/usr/bin/env python3
"""Property tests and the readable-prefix canary for hierarchy catalogue v1."""
from __future__ import annotations

from hierarchical_enumerator_v1 import HierarchicalEnumeratorV1


def is_readable_russian(page: str) -> bool:
    preview = page.rstrip()
    cyrillic = sum("а" <= char <= "я" or char == "ё" for char in preview)
    return len(preview) >= 160 and cyrillic >= 120 and any(mark in preview for mark in ".!?")


def main() -> None:
    hierarchy = HierarchicalEnumeratorV1()
    assert hierarchy.count_paragraph()["exact_count"] == len(hierarchy.paragraphs)
    page_counts = hierarchy.count_page()
    assert page_counts["structured_pages"] == hierarchy.structured_page_count
    assert page_counts["exact_count"] == hierarchy.raw_space_size
    assert page_counts["raw_fallback_pages"] + page_counts["structured_pages"] == hierarchy.raw_space_size

    for rank in range(len(hierarchy.paragraphs)):
        paragraph = hierarchy.unrank_paragraph(rank)
        assert hierarchy.rank_paragraph(paragraph["paragraph"])["rank"] == rank

    # All finite catalogue pages and their counterpart raw addresses round-trip.
    for rank in range(hierarchy.structured_page_count):
        decoded = hierarchy.unrank_page(rank)
        assert hierarchy.rank_page(decoded["page"])["rank"] == rank
    for raw_rank in hierarchy._structured_raw_ranks:
        decoded = hierarchy.unrank_page(raw_rank)
        assert decoded["mode"] == "raw_fallback_swap"
        assert hierarchy.rank_page(decoded["page"])["rank"] == raw_rank

    readable_pages: list[str] = []
    for rank in range(20):
        decoded = hierarchy.unrank_page(rank)
        assert decoded["mode"] == "structured_catalogue"
        assert is_readable_russian(decoded["page"])
        readable_pages.append(decoded["page"])
    assert len(set(readable_pages)) == 20

    # Probe both sides of each transposition and untouched raw-space positions.
    swapped_zero = hierarchy.raw_rank(hierarchy.unrank_page(0)["page"])
    swapped_last = hierarchy.raw_rank(hierarchy.unrank_page(hierarchy.structured_page_count - 1)["page"])
    probes = (
        0,
        1,
        hierarchy.structured_page_count - 1,
        hierarchy.structured_page_count,
        swapped_zero,
        swapped_last,
        hierarchy.raw_space_size // 2,
        hierarchy.raw_space_size - 1,
    )
    for rank in probes:
        decoded = hierarchy.unrank_page(rank)
        assert hierarchy.rank_page(decoded["page"])["rank"] == rank

    # A low raw page is deliberately displaced into its matching swap location.
    raw_zero = hierarchy.raw_unrank(0)
    raw_zero_rank = hierarchy.rank_page(raw_zero)["rank"]
    assert raw_zero_rank == swapped_zero
    assert hierarchy.unrank_page(raw_zero_rank)["page"] == raw_zero

    print("hierarchical catalogue v1: 20 readable pages and exact raw fallback passed")


if __name__ == "__main__":
    main()
