#!/usr/bin/env python3
"""Exact chunked energy counting for the raw cluster-energy page model.

The raw ranker remains the authority for rank/unrank.  This module isolates
the scaling layer: a block is an exact 64-state polynomial transfer matrix;
longer pages are composed from blocks plus a short tail.  No path is sampled
or discarded, and all 256 raw symbols retain their multiplicity.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from cluster_counting_mvp import RawClusterRanker


class ChunkedRawCounter:
    def __init__(self, length: int, block_size: int = 16):
        if length < 1 or block_size < 1:
            raise ValueError("length and block_size must be positive")
        self.ranker = RawClusterRanker(length=length)
        self.length = length
        self.block_size = block_size
        self.k = self.ranker.k
        self.symbol_count_by_cluster = self.ranker.symbol_count_by_cluster

    def advance(self, vector: list[Counter]) -> list[Counter]:
        """Apply one exact raw-symbol transition to a state/energy vector."""
        out = [Counter() for _ in range(self.k)]
        for source, poly in enumerate(vector):
            if not poly:
                continue
            for destination, multiplicity in enumerate(self.symbol_count_by_cluster):
                if not multiplicity:
                    continue
                cost = self.ranker.transition_cost(source, destination)
                dest_poly = out[destination]
                for energy, count in poly.items():
                    dest_poly[energy + cost] += count * multiplicity
        return out

    def block_transfer(self, span: int) -> list[list[Counter]]:
        """Return T[source][destination][energy] for exactly ``span`` steps."""
        transfers: list[list[Counter]] = []
        for source in range(self.k):
            vector = [Counter() for _ in range(self.k)]
            vector[source][0] = 1
            for _ in range(span):
                vector = self.advance(vector)
            transfers.append(vector)
        return transfers

    @staticmethod
    def convolve(left: Counter, right: Counter) -> Counter:
        if len(left) > len(right):
            left, right = right, left
        out = Counter()
        for left_energy, left_count in left.items():
            for right_energy, right_count in right.items():
                out[left_energy + right_energy] += left_count * right_count
        return out

    def apply_transfer(self, vector: list[Counter], transfer: list[list[Counter]]) -> list[Counter]:
        out = [Counter() for _ in range(self.k)]
        for source, source_poly in enumerate(vector):
            if not source_poly:
                continue
            for destination, transition_poly in enumerate(transfer[source]):
                if transition_poly:
                    out[destination].update(self.convolve(source_poly, transition_poly))
        return out

    def histogram(self) -> Counter:
        """Count every raw page exactly, composing complete blocks then a tail."""
        # First symbol chooses a cluster without a transition cost.
        vector = [Counter({0: multiplicity}) for multiplicity in self.symbol_count_by_cluster]
        remaining = self.length - 1
        if remaining >= self.block_size:
            transfer = self.block_transfer(self.block_size)
            while remaining >= self.block_size:
                vector = self.apply_transfer(vector, transfer)
                remaining -= self.block_size
        for _ in range(remaining):
            vector = self.advance(vector)
        hist = Counter()
        for poly in vector:
            hist.update(poly)
        return hist

    def stats(self) -> dict:
        hist = self.histogram()
        return {
            "version": "cluster_chunk_counting_v1",
            "length": self.length,
            "block_size": self.block_size,
            "energy_buckets": len(hist),
            "counted_pages": str(sum(hist.values())),
            "space_size": str(self.ranker.space_size),
            "space_complete": sum(hist.values()) == self.ranker.space_size,
        }

    def verify_against_raw_dp(self) -> dict:
        chunked = self.histogram()
        raw = Counter({energy: self.ranker.count_energy(energy) for energy in range(self.ranker.max_energy + 1)})
        raw = Counter({energy: count for energy, count in raw.items() if count})
        return {
            "length": self.length,
            "histograms_equal": chunked == raw,
            "space_complete": sum(chunked.values()) == self.ranker.space_size,
            "chunked_buckets": len(chunked),
            "raw_buckets": len(raw),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=64)
    parser.add_argument("--block-size", type=int, default=16)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--out", type=Path, help="write a compact proof receipt")
    args = parser.parse_args()
    counter = ChunkedRawCounter(args.length, args.block_size)
    result = counter.verify_against_raw_dp() if args.verify else counter.stats()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
