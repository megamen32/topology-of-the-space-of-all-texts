# Counting Infinity

## The challenge

We want an addressable Library of Babel over a fixed alphabet:

```text
alphabet size = 256
page length   = 4096 symbols
space size    = 256^4096 = 2^32768
```

The trivial bijection is easy:

```text
page <-> base-256 integer
```

But this is only a codec. It does not solve the actual product/research goal.

The real goal is a **human-shaped ordering**:

```text
address 0        -> most human-like pages
larger addresses -> less human-like pages
far tail         -> noise
```

So the real rank is not raw positional rank.

It is:

```text
student_rank(page)
=
rank_by(
  student_energy(page),
  raw_lexicographic_tiebreaker
)
```

This preserves a strict bijection if the counting layer can answer:

```text
how many pages have energy < E?
how many pages have energy = E and are raw-before this page?
```

That is the core problem.

---

## Why brute force does not work

The naive finite-state dynamic program is:

```text
dp[position][state][energy] = count
```

This is exact and conceptually correct.

But for page length 4096, the energy axis becomes enormous.

Even with a small FSM, the table may contain millions or billions of useful energy cells. Faster languages, assembly, SIMD, or GPU acceleration can help by constant factors, but they do not change the asymptotic shape of the problem.

The bottleneck is not just CPU speed.

The bottleneck is the size of the counting object.

---


---

Detailed results:

```text
notes/research/counting_infinity_results.md
```

Experiments:

```text
notes/research/counting_infinity_experiments.md
```
