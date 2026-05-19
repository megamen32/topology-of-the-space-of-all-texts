# Hierarchical Student — Completion Roadmap

## Goal

Build a production-capable hierarchical finite student that:

```text
1. preserves exact bijection
2. supports rank/unrank
3. keeps every page reachable
4. produces human-shaped ordering
5. remains countable
```

---

# Phase 1 — Freeze the hierarchy

## Minimal grammar

```text
page
-> paragraph blocks
-> sentence templates
-> token classes
-> raw character fallback
```

The important rule:

```text
fallback path must always exist
```

So arbitrary pages remain reachable.

---

# Phase 2 — Unified energy model

## Introduce integer energies

```text
total_energy =
  paragraph_cost
+ sentence_cost
+ token_transition_cost
+ fallback_cost
```

Requirements:

- integer only
- deterministic
- additive
- compositional
- stable across hierarchy levels

---

# Phase 3 — Exact compositional counting

Replace flat DP:

```text
dp[position][state][energy]
```

with hierarchical counting:

```text
count_token
count_sentence
count_paragraph
count_page
```

---

# Phase 4 — Exact rank/unrank MVP

Implement:

```text
length = 64
length = 128
length = 256
```

Required tests:

```text
unrank(rank(x)) == x
rank(unrank(i)) == i
```

---

# Phase 5 — Hierarchical proof

Need proofs for:

- completeness
- uniqueness
- reversibility
- ordered enumeration

---

# Phase 6 — Teacher/student architecture

Teachers:

- M3
- M4
- M5
- transformer
- tiny LLM

Role:

```text
suggest energies
extract templates
shape transitions
```

---

# Current blocker

```text
exact low-energy counting
for long pages
```
