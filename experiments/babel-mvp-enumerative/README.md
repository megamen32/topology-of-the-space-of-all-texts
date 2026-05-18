# Babel enumerative MVP

This MVP demonstrates the proof mechanism for a human-ordered Library of Babel over fixed-length byte pages.

It is deliberately not an LLM. It uses a tiny byte-frequency model:

```text
score(page) = sum(cost[byte])
```

Then it orders all pages by:

1. lower score first;
2. lexicographic order inside the same score.

That gives a total order over all `256^N` byte pages.

For real `N=4096`, the same proof holds, but the naive dynamic programming table must be optimized.

## Proof sketch

For fixed `N`, every page has exactly one integer cost.
All pages are partitioned into disjoint cost buckets.
Inside each bucket, lexicographic order is exact and unique.
Therefore every page has exactly one rank.
The DP table counts all pages in all buckets, and `sum(dp[N]) == 256^N` is checked in self-test.

## Run

```bash
./enumerative_babel_mvp.py --page-len 4 --selftest --first 10
```

Train from a dataset:

```bash
./enumerative_babel_mvp.py --dataset ./some_texts --page-len 8 --selftest --first 20
```
