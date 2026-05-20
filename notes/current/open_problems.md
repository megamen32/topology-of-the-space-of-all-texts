# Open Problems

## 1. Exact cluster counting

Need to count paths through the finite cluster transition graph:

```text
count_cluster_path(state, length, energy_budget)
```

This replaces the older manual target:

```text
count_paragraph(shape, energy_budget)
```

## 2. Production-scale energy frontier

Sparse DP works for small experiments, but the frontier still grows too quickly for full 4096-symbol pages.

Need:

- compressed energy buckets
- chunked counting
- external-memory tables
- exact merge logic

## 3. Rank/unrank over cluster student v2

Need exact functions:

```text
rank(page) -> integer
unrank(integer) -> page
```

ordered by:

```text
energy first
raw/bijection tie-breaker second
```

## 4. Polynomial/generating-function path

The FSM polynomial matrix approach remains promising but unfinished.

Potential target:

```text
cluster transition matrix with polynomial energy weights
```

## 5. Proof document

Need one rigorous document proving:

- completeness
- no duplicates
- reversibility
- exact ordering
- fallback reachability
