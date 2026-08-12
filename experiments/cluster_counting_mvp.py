#!/usr/bin/env python3
"""Exact counting and rank/unrank for cluster_student_v2 paths.

This is the first vertical exact-counting slice for the current architecture.
It enumerates paths of cluster IDs, not raw bytes yet:

    path = (cluster_0, ..., cluster_{N-1})
    order = (integer transition energy, lexicographic path)

The cluster graph supplies the transition statistics. Costs are deliberately
quantized to a small integer range so the sparse DP remains inspectable for
N=16/32/64. Every K^N cluster path remains reachable.
"""
from __future__ import annotations

import argparse
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "models/cluster_student_v2/model.json"
DEFAULT_ALPHABET = ROOT / "models/top256_alphabet/alphabet_top256.json"
START = -1


class ClusterRanker:
    """Exact energy-ordered enumerator for fixed-length cluster paths."""

    def __init__(self, model_path: Path = DEFAULT_MODEL, length: int = 16, cost_cap: int = 4):
        if length < 1:
            raise ValueError("length must be positive")
        if cost_cap < 1:
            raise ValueError("cost_cap must be positive")
        self.model_path = Path(model_path)
        self.model = json.loads(self.model_path.read_text(encoding="utf-8"))
        self.k = int(self.model["clusters"])
        self.length = int(length)
        self.cost_cap = int(cost_cap)
        raw = self.model.get("cluster_transitions", {})
        self.transitions = {
            int(src): {int(dst): int(n) for dst, n in row.items()}
            for src, row in raw.items()
        }
        self.costs = self._build_costs()

    def _build_costs(self) -> list[list[int]]:
        """Quantize surprise relative to each source state's most likely edge."""
        costs: list[list[int]] = []
        for src in range(self.k):
            row = self.transitions.get(src, {})
            peak = max(row.values(), default=0)
            row_costs = []
            for dst in range(self.k):
                count = row.get(dst, 0)
                if peak <= 0:
                    value = self.cost_cap
                else:
                    # A few integer buckets preserve the learned ordering while
                    # keeping exact DP practical at the first target lengths.
                    surprise = math.log2((peak + 1) / (count + 1))
                    value = min(self.cost_cap, max(0, int(round(surprise))))
                row_costs.append(value)
            costs.append(row_costs)
        return costs

    def transition_cost(self, src: int, dst: int) -> int:
        # The first cluster is the root choice; subsequent positions pay edge cost.
        return 0 if src == START else self.costs[src][dst]

    @property
    def max_energy(self) -> int:
        return self.cost_cap * max(0, self.length - 1)

    @property
    def space_size(self) -> int:
        return self.k ** self.length

    @lru_cache(maxsize=None)
    def count_exact(self, pos: int, src: int, energy: int) -> int:
        """Count suffixes from position *pos* with exactly *energy* remaining."""
        if energy < 0 or energy > self.max_energy:
            return 0
        if pos == self.length:
            return int(energy == 0)
        left = self.length - pos
        if energy > self.cost_cap * max(0, left - (1 if src == START else 0)):
            return 0
        total = 0
        for dst in range(self.k):
            total += self.count_exact(
                pos + 1,
                dst,
                energy - self.transition_cost(src, dst),
            )
        return total

    def count_energy(self, energy: int) -> int:
        return self.count_exact(0, START, int(energy))

    def count_below_energy(self, energy: int) -> int:
        return sum(self.count_energy(e) for e in range(max(0, int(energy))))

    def path_energy(self, path: Iterable[int]) -> int:
        path = list(path)
        self._validate_path(path)
        src = START
        energy = 0
        for dst in path:
            energy += self.transition_cost(src, dst)
            src = dst
        return energy

    def rank(self, path: Iterable[int]) -> dict:
        path = list(path)
        self._validate_path(path)
        energy = self.path_energy(path)
        rank = self.count_below_energy(energy)
        remaining = energy
        src = START
        for pos, chosen in enumerate(path):
            for smaller in range(chosen):
                rank += self.count_exact(
                    pos + 1,
                    smaller,
                    remaining - self.transition_cost(src, smaller),
                )
            remaining -= self.transition_cost(src, chosen)
            src = chosen
        return {"rank": rank, "energy": energy, "path": path}

    def unrank(self, rank: int) -> dict:
        rank = int(rank)
        if rank < 0 or rank >= self.space_size:
            raise ValueError(f"rank must be in [0, {self.space_size})")

        offset = rank
        energy = 0
        while True:
            bucket = self.count_energy(energy)
            if offset < bucket:
                break
            offset -= bucket
            energy += 1
            if energy > self.max_energy:
                raise RuntimeError("rank fell outside the enumerated energy buckets")

        path: list[int] = []
        src = START
        remaining = energy
        for pos in range(self.length):
            for dst in range(self.k):
                count = self.count_exact(
                    pos + 1,
                    dst,
                    remaining - self.transition_cost(src, dst),
                )
                if offset >= count:
                    offset -= count
                    continue
                path.append(dst)
                remaining -= self.transition_cost(src, dst)
                src = dst
                break
            else:
                raise RuntimeError("unrank could not choose a path symbol")
        return {"rank": rank, "energy": energy, "path": path}

    def stats(self) -> dict:
        buckets = [self.count_energy(e) for e in range(self.max_energy + 1)]
        return {
            "model": str(self.model_path),
            "clusters": self.k,
            "length": self.length,
            "cost_cap": self.cost_cap,
            "max_energy": self.max_energy,
            "space_size": self.space_size,
            "counted_paths": sum(buckets),
            "energy_buckets": {str(i): n for i, n in enumerate(buckets) if n},
            "cache_info": str(self.count_exact.cache_info()),
        }

    def selftest(self) -> dict:
        probes = sorted({0, 1, self.space_size // 2, self.space_size - 1})
        checks = []
        for i in probes:
            decoded = self.unrank(i)
            encoded = self.rank(decoded["path"])["rank"]
            checks.append({"rank": i, "roundtrip_rank": encoded, "ok": encoded == i})
        total = sum(self.count_energy(e) for e in range(self.max_energy + 1))
        return {
            "stats": self.stats(),
            "roundtrips": checks,
            "total_is_space_size": total == self.space_size,
            "ok": total == self.space_size and all(x["ok"] for x in checks),
        }

    def _validate_path(self, path: list[int]) -> None:
        if len(path) != self.length:
            raise ValueError(f"path must contain exactly {self.length} cluster IDs")
        if any(not isinstance(x, int) or x < 0 or x >= self.k for x in path):
            raise ValueError(f"every cluster ID must be an integer in [0, {self.k})")


class RawClusterRanker(ClusterRanker):
    """Exact ranker for fixed-length pages over the project's 256-symbol alphabet.

    The learned cluster graph provides the energy. Raw symbols remain the
    enumerable alphabet, so every one of ``256 ** length`` pages is present.
    Within an energy bucket, raw alphabet order is the deterministic tie-breaker.
    """

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL,
        alphabet_path: Path = DEFAULT_ALPHABET,
        length: int = 8,
        cost_cap: int = 4,
        fallback_cluster: int = 0,
    ):
        super().__init__(model_path=model_path, length=length, cost_cap=cost_cap)
        alphabet_model = json.loads(Path(alphabet_path).read_text(encoding="utf-8"))
        alphabet = alphabet_model.get("alphabet")
        if isinstance(alphabet, str):
            alphabet = list(alphabet)
        if not isinstance(alphabet, list) or len(alphabet) != 256 or len(set(alphabet)) != 256:
            raise ValueError("alphabet must contain exactly 256 unique symbols")
        if not 0 <= fallback_cluster < self.k:
            raise ValueError(f"fallback_cluster must be in [0, {self.k})")
        self.alphabet_path = Path(alphabet_path)
        self.alphabet = [str(x) for x in alphabet]
        self.symbol_index = {symbol: i for i, symbol in enumerate(self.alphabet)}
        mapping = self.model.get("mapping", {})
        self.fallback_cluster = fallback_cluster
        self.symbol_clusters = [int(mapping.get(symbol, fallback_cluster)) for symbol in self.alphabet]
        if any(cluster < 0 or cluster >= self.k for cluster in self.symbol_clusters):
            raise ValueError("model mapping contains a cluster outside the model range")
        self.symbol_count_by_cluster = [0] * self.k
        self.symbol_cluster_prefix = [[0] * self.k]
        prefix = [0] * self.k
        for cluster in self.symbol_clusters:
            self.symbol_count_by_cluster[cluster] += 1
            prefix = prefix.copy()
            prefix[cluster] += 1
            self.symbol_cluster_prefix.append(prefix)

        # Only the outgoing cost row influences every possible suffix after a
        # symbol has selected its cluster.  The raw alphabet currently reaches
        # 15 learned clusters, but those clusters have only a few distinct cost
        # rows.  Quotienting equivalent rows keeps the exact same recurrence
        # while making length-256 rank/unrank practical in the request path.
        active_clusters = [
            cluster for cluster, multiplicity in enumerate(self.symbol_count_by_cluster)
            if multiplicity
        ]
        row_types: dict[tuple[int, ...], int] = {}
        self.cluster_suffix_type = [-1] * self.k
        representatives: list[int] = []
        for cluster in active_clusters:
            row = tuple(self.costs[cluster][destination] for destination in active_clusters)
            suffix_type = row_types.get(row)
            if suffix_type is None:
                suffix_type = len(representatives)
                row_types[row] = suffix_type
                representatives.append(cluster)
            self.cluster_suffix_type[cluster] = suffix_type

        self.compact_transitions: list[list[tuple[int, int, int]]] = []
        for source in representatives:
            aggregated: dict[tuple[int, int], int] = {}
            for destination in active_clusters:
                key = (
                    self.cluster_suffix_type[destination],
                    self.transition_cost(source, destination),
                )
                aggregated[key] = aggregated.get(key, 0) + self.symbol_count_by_cluster[destination]
            self.compact_transitions.append([
                (suffix_type, cost, multiplicity)
                for (suffix_type, cost), multiplicity in sorted(aggregated.items())
            ])

        start_aggregated: dict[int, int] = {}
        for destination in active_clusters:
            suffix_type = self.cluster_suffix_type[destination]
            start_aggregated[suffix_type] = (
                start_aggregated.get(suffix_type, 0) + self.symbol_count_by_cluster[destination]
            )
        self.compact_start_transitions = [
            (suffix_type, 0, multiplicity)
            for suffix_type, multiplicity in sorted(start_aggregated.items())
        ]

    @property
    def space_size(self) -> int:
        return len(self.alphabet) ** self.length

    @lru_cache(maxsize=None)
    def count_exact(self, pos: int, src: int, energy: int) -> int:
        """Count raw-symbol suffixes, aggregating symbols by destination cluster."""
        source_type = START if src == START else self.cluster_suffix_type[src]
        if source_type != START and source_type < 0:
            return 0
        return self._count_compact(self.length - pos, source_type, int(energy))

    @lru_cache(maxsize=None)
    def _count_compact(self, left: int, source_type: int, energy: int) -> int:
        """Exact suffix count over behaviorally equivalent transition rows."""
        if energy < 0 or energy > self.max_energy:
            return 0
        if left == 0:
            return int(energy == 0)
        if energy > self.cost_cap * max(0, left - (1 if source_type == START else 0)):
            return 0
        transitions = (
            self.compact_start_transitions
            if source_type == START
            else self.compact_transitions[source_type]
        )
        total = 0
        for destination_type, cost, multiplicity in transitions:
            total += multiplicity * self._count_compact(
                left - 1,
                destination_type,
                energy - cost,
            )
        return total

    def page_from_text(self, text: str) -> list[int]:
        if len(text) > self.length:
            raise ValueError(f"text must contain at most {self.length} symbols")
        page = list(text) + [" "] * (self.length - len(text))
        unknown = [symbol for symbol in page if symbol not in self.symbol_index]
        if unknown:
            raise ValueError(f"symbols are outside the exact alphabet: {unknown[:5]}")
        return [self.symbol_index[symbol] for symbol in page]

    def path_energy(self, path: Iterable[int]) -> int:
        ids = list(path)
        if len(ids) != self.length:
            raise ValueError(f"page must contain exactly {self.length} symbols")
        src = START
        energy = 0
        for symbol_id in ids:
            if not 0 <= symbol_id < len(self.alphabet):
                raise ValueError("symbol index outside alphabet")
            dst = self.symbol_clusters[symbol_id]
            energy += self.transition_cost(src, dst)
            src = dst
        return energy

    def rank_page(self, ids: Iterable[int]) -> dict:
        ids = list(ids)
        if len(ids) != self.length:
            raise ValueError(f"page must contain exactly {self.length} symbols")
        if any(not 0 <= symbol_id < len(self.alphabet) for symbol_id in ids):
            raise ValueError("symbol index outside alphabet")
        energy = self.path_energy(ids)
        rank = self.count_below_energy(energy)
        remaining = energy
        src = START
        for pos, chosen in enumerate(ids):
            chosen_cluster = self.symbol_clusters[chosen]
            # Symbols in one destination cluster have identical suffix counts.
            # Aggregate only the raw-lexicographically smaller symbols by their
            # cluster, preserving the exact tie-break while avoiding 256 equal
            # DP lookups at every page position.
            for candidate_cluster, multiplicity in enumerate(self.symbol_cluster_prefix[chosen]):
                if multiplicity:
                    rank += multiplicity * self.count_exact(
                    pos + 1,
                    candidate_cluster,
                    remaining - self.transition_cost(src, candidate_cluster),
                )
            remaining -= self.transition_cost(src, chosen_cluster)
            src = chosen_cluster
        return {
            "rank": rank,
            "energy": energy,
            "page": "".join(self.alphabet[i] for i in ids),
        }

    def rank_text(self, text: str) -> dict:
        return self.rank_page(self.page_from_text(text))

    def unrank_page(self, rank: int) -> dict:
        rank = int(rank)
        space_size = len(self.alphabet) ** self.length
        if rank < 0 or rank >= space_size:
            raise ValueError(f"rank must be in [0, {space_size})")
        offset = rank
        energy = 0
        while True:
            bucket = self.count_energy(energy)
            if offset < bucket:
                break
            offset -= bucket
            energy += 1
            if energy > self.max_energy:
                raise RuntimeError("rank fell outside the enumerated energy buckets")
        ids: list[int] = []
        src = START
        remaining = energy
        for pos in range(self.length):
            suffix_counts = {}
            for symbol_id, candidate_cluster in enumerate(self.symbol_clusters):
                count = suffix_counts.get(candidate_cluster)
                if count is None:
                    count = self.count_exact(
                        pos + 1,
                        candidate_cluster,
                        remaining - self.transition_cost(src, candidate_cluster),
                    )
                    suffix_counts[candidate_cluster] = count
                if offset >= count:
                    offset -= count
                    continue
                ids.append(symbol_id)
                remaining -= self.transition_cost(src, candidate_cluster)
                src = candidate_cluster
                break
            else:
                raise RuntimeError("unrank could not choose a raw symbol")
        return {
            "rank": rank,
            "energy": energy,
            "page": "".join(self.alphabet[i] for i in ids),
        }

    def raw_selftest(self) -> dict:
        space_size = len(self.alphabet) ** self.length
        probes = sorted({0, 1, space_size // 2, space_size - 1})
        checks = []
        for probe in probes:
            decoded = self.unrank_page(probe)
            encoded = self.rank_text(decoded["page"])["rank"]
            checks.append({"rank": probe, "roundtrip_rank": encoded, "ok": encoded == probe})
        total = sum(self.count_energy(e) for e in range(self.max_energy + 1))
        return {
            "alphabet": len(self.alphabet),
            "length": self.length,
            "space_size": space_size,
            "counted_pages": total,
            "total_is_space_size": total == space_size,
            "roundtrips": checks,
            "ok": total == space_size and all(check["ok"] for check in checks),
        }


class HierarchicalRawRanker:
    """Exact long-page bijection composed from exact human-ordered blocks.

    Each fixed-size block is ranked by :class:`RawClusterRanker`.  Block ranks
    are then digits in base ``256 ** block_length``.  Positional composition is
    a bijection, so every one of ``256 ** length`` pages appears exactly once,
    while the expensive learned ordering is reused at block scale.
    """

    def __init__(self, length: int = 4096, block_length: int = 256):
        length = int(length)
        block_length = int(block_length)
        if length < 1 or block_length < 1 or length % block_length:
            raise ValueError("length must be a positive multiple of block_length")
        self.length = length
        self.block_length = block_length
        self.blocks = length // block_length
        self.block_ranker = RawClusterRanker(length=block_length)
        self.alphabet = self.block_ranker.alphabet
        self.symbol_index = self.block_ranker.symbol_index
        self.block_space_size = self.block_ranker.space_size

    @property
    def space_size(self) -> int:
        return self.block_space_size ** self.blocks

    def page_from_text(self, text: str) -> list[int]:
        if len(text) > self.length:
            raise ValueError(f"text must contain at most {self.length} symbols")
        page = list(text) + [" "] * (self.length - len(text))
        unknown = [symbol for symbol in page if symbol not in self.symbol_index]
        if unknown:
            raise ValueError(f"symbols are outside the exact alphabet: {unknown[:5]}")
        return [self.symbol_index[symbol] for symbol in page]

    def rank_page(self, ids: Iterable[int]) -> dict:
        ids = list(ids)
        if len(ids) != self.length:
            raise ValueError(f"page must contain exactly {self.length} symbols")
        if any(not 0 <= symbol_id < len(self.alphabet) for symbol_id in ids):
            raise ValueError("symbol index outside alphabet")
        rank = 0
        block_energies = []
        for start in range(0, self.length, self.block_length):
            result = self.block_ranker.rank_page(ids[start:start + self.block_length])
            rank = rank * self.block_space_size + result["rank"]
            block_energies.append(result["energy"])
        return {
            "rank": rank,
            "energy": sum(block_energies),
            "block_energies": block_energies,
            "page": "".join(self.alphabet[i] for i in ids),
        }

    def rank_text(self, text: str) -> dict:
        return self.rank_page(self.page_from_text(text))

    def unrank_page(self, rank: int) -> dict:
        rank = int(rank)
        if rank < 0 or rank >= self.space_size:
            raise ValueError(f"rank must be in [0, {self.space_size})")
        value = rank
        block_ranks = [0] * self.blocks
        for index in range(self.blocks - 1, -1, -1):
            value, block_ranks[index] = divmod(value, self.block_space_size)
        pages = []
        block_energies = []
        for block_rank in block_ranks:
            result = self.block_ranker.unrank_page(block_rank)
            pages.append(result["page"])
            block_energies.append(result["energy"])
        return {
            "rank": rank,
            "energy": sum(block_energies),
            "block_energies": block_energies,
            "page": "".join(pages),
        }


def parse_path(value: str) -> list[int]:
    value = value.strip()
    if value.startswith("["):
        parsed = json.loads(value)
        return [int(x) for x in parsed]
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--alphabet", type=Path, default=DEFAULT_ALPHABET)
    ap.add_argument("--raw", action="store_true", help="rank raw 256-symbol pages instead of cluster-ID paths")
    ap.add_argument("--length", type=int, default=16)
    ap.add_argument("--cost-cap", type=int, default=4)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--raw-selftest", action="store_true")
    ap.add_argument("--rank-text")
    ap.add_argument("--rank-path")
    ap.add_argument("--unrank", type=int)
    args = ap.parse_args()
    ranker = (
        RawClusterRanker(args.model, args.alphabet, args.length, args.cost_cap)
        if args.raw
        else ClusterRanker(args.model, args.length, args.cost_cap)
    )
    if args.stats:
        print(json.dumps(ranker.stats(), ensure_ascii=False, indent=2))
    if args.selftest:
        result = ranker.raw_selftest() if args.raw else ranker.selftest()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.raw_selftest:
        if not args.raw:
            ap.error("--raw-selftest requires --raw")
        print(json.dumps(ranker.raw_selftest(), ensure_ascii=False, indent=2))
    if args.rank_text is not None:
        if not args.raw:
            ap.error("--rank-text requires --raw")
        print(json.dumps(ranker.rank_text(args.rank_text), ensure_ascii=False, indent=2))
    if args.rank_path is not None:
        print(json.dumps(ranker.rank(parse_path(args.rank_path)), ensure_ascii=False, indent=2))
    if args.unrank is not None:
        print(json.dumps(ranker.unrank(args.unrank), ensure_ascii=False, indent=2))
    if not any((args.stats, args.selftest, args.raw_selftest, args.rank_text is not None, args.rank_path is not None, args.unrank is not None)):
        ap.error("choose --stats, --selftest, --raw-selftest, --rank-text, --rank-path, or --unrank")


if __name__ == "__main__":
    main()
