#!/usr/bin/env python3
"""
MVP: exact bijective ranking/unranking of fixed-length byte pages by dataset-derived byte costs.

This is intentionally small and auditable:
- Alphabet: 256 bytes.
- Page length: configurable.
- Model: unigram byte frequencies from dataset, converted to integer costs.
- Ordering: lower total cost first; lexicographic order inside the same cost.
- Bijection: every length-N byte string has exactly one rank in [0, 256**N).

For page_len=4096 the math is the same, but a naive DP over all costs can be large.
Use small page_len for correctness tests/MVP, then optimize the counting layer.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable, List

ALPHABET = 256


def read_dataset(paths: Iterable[str]) -> bytes:
    chunks = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file():
                    chunks.append(f.read_bytes())
        else:
            chunks.append(path.read_bytes())
    return b"".join(chunks)


def train_costs(data: bytes, scale: int = 256, smoothing: int = 1) -> List[int]:
    """Return positive integer byte costs derived from -log2 probability.

    smoothing>=1 ensures every byte is possible, so coverage of 256^N is preserved.
    We normalize by subtracting the minimum, then add 1, so frequent bytes get cost 1.
    """
    counts = [smoothing] * ALPHABET
    for b in data:
        counts[b] += 1
    total = sum(counts)
    raw = [round(-math.log2(c / total) * scale) for c in counts]
    m = min(raw)
    return [int(x - m + 1) for x in raw]


def default_costs() -> List[int]:
    """Fallback ASCII-ish prior if no dataset is supplied."""
    costs = [80] * ALPHABET
    for b in b" etaoinshrdlucmfwypvbgkqjxzETAOINSHRDLUCMFWYPVBGKQJXZ":
        costs[b] = 4
    for b in b"0123456789.,!?;:-()[]{}\n\r\t\"'":
        costs[b] = min(costs[b], 8)
    return costs


def build_dp(costs: List[int], page_len: int) -> List[List[int]]:
    """dp[remaining][cost] = number of byte strings of length remaining with exact cost."""
    max_cost = page_len * max(costs)
    dp: List[List[int]] = [[0] * (max_cost + 1) for _ in range(page_len + 1)]
    dp[0][0] = 1
    for rem in range(1, page_len + 1):
        prev = dp[rem - 1]
        cur = dp[rem]
        limit = rem * max(costs)
        for b in range(ALPHABET):
            cb = costs[b]
            for c in range(cb, limit + 1):
                v = prev[c - cb]
                if v:
                    cur[c] += v
    return dp


def total_cost(page: bytes, costs: List[int]) -> int:
    return sum(costs[b] for b in page)


def count_less_cost(dp: List[List[int]], page_len: int, c: int) -> int:
    return sum(dp[page_len][:c])


def rank_within_cost(page: bytes, costs: List[int], dp: List[List[int]], target_cost: int) -> int:
    rank = 0
    remaining_cost = target_cost
    n = len(page)
    for i, actual in enumerate(page):
        rem = n - i - 1
        for b in range(actual):
            cb = costs[b]
            if remaining_cost >= cb:
                rank += dp[rem][remaining_cost - cb]
        remaining_cost -= costs[actual]
    assert remaining_cost == 0
    return rank


def rank_page(page: bytes, costs: List[int], dp: List[List[int]]) -> int:
    c = total_cost(page, costs)
    return count_less_cost(dp, len(page), c) + rank_within_cost(page, costs, dp, c)


def unrank_page(rank: int, costs: List[int], dp: List[List[int]], page_len: int) -> bytes:
    total = sum(dp[page_len])
    if not 0 <= rank < total:
        raise ValueError(f"rank out of range: expected 0 <= rank < {total}")

    # Find the cost bucket.
    cost = 0
    while rank >= dp[page_len][cost]:
        rank -= dp[page_len][cost]
        cost += 1

    out = bytearray()
    remaining_cost = cost
    for i in range(page_len):
        rem = page_len - i - 1
        for b in range(ALPHABET):
            cb = costs[b]
            cnt = dp[rem][remaining_cost - cb] if remaining_cost >= cb else 0
            if rank >= cnt:
                rank -= cnt
            else:
                out.append(b)
                remaining_cost -= cb
                break
        else:
            raise RuntimeError("unrank failed; DP table inconsistent")
    assert remaining_cost == 0
    return bytes(out)


def selftest(costs: List[int], page_len: int, samples: int = 1000) -> None:
    import random
    dp = build_dp(costs, page_len)
    total = sum(dp[page_len])
    assert total == ALPHABET ** page_len, (total, ALPHABET ** page_len)

    # Edge ranks.
    for r in [0, 1, 2, min(255, total - 1), total - 1]:
        p = unrank_page(r, costs, dp, page_len)
        rr = rank_page(p, costs, dp)
        assert rr == r, (r, rr, p)

    # Random pages and ranks.
    for _ in range(samples):
        p = bytes(random.randrange(256) for _ in range(page_len))
        r = rank_page(p, costs, dp)
        assert unrank_page(r, costs, dp, page_len) == p
        r2 = random.randrange(total)
        p2 = unrank_page(r2, costs, dp, page_len)
        assert rank_page(p2, costs, dp) == r2

    print(f"OK selftest: page_len={page_len}, total=256^{page_len}={total}, samples={samples}")


def explain_first(costs: List[int], page_len: int, k: int) -> None:
    dp = build_dp(costs, page_len)
    for r in range(k):
        p = unrank_page(r, costs, dp, page_len)
        printable = ''.join(chr(x) if 32 <= x <= 126 else f'\\x{x:02x}' for x in p)
        print(f"rank={r:>4} cost={total_cost(p, costs):>4} bytes={p.hex()} text={printable!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", nargs="*", default=[])
    ap.add_argument("--page-len", type=int, default=8)
    ap.add_argument("--scale", type=int, default=64)
    ap.add_argument("--smoothing", type=int, default=1)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--samples", type=int, default=1000)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--rank-text")
    ap.add_argument("--unrank", type=int)
    args = ap.parse_args()

    if args.dataset:
        data = read_dataset(args.dataset)
        costs = train_costs(data, scale=args.scale, smoothing=args.smoothing)
        print(f"trained on {len(data)} bytes; min_cost={min(costs)} max_cost={max(costs)}")
    else:
        costs = default_costs()
        print(f"using default prior; min_cost={min(costs)} max_cost={max(costs)}")

    if args.selftest:
        selftest(costs, args.page_len, args.samples)

    if args.first:
        explain_first(costs, args.page_len, args.first)

    if args.rank_text is not None:
        page = args.rank_text.encode("utf-8")
        if len(page) != args.page_len:
            raise SystemExit(f"rank-text encodes to {len(page)} bytes, expected --page-len {args.page_len}")
        dp = build_dp(costs, args.page_len)
        print(rank_page(page, costs, dp))

    if args.unrank is not None:
        dp = build_dp(costs, args.page_len)
        p = unrank_page(args.unrank, costs, dp, args.page_len)
        print(p.hex())
        try:
            print(p.decode("utf-8"))
        except UnicodeDecodeError:
            print(repr(p))


if __name__ == "__main__":
    main()
