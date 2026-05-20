# Experiment B2 — Sentence/Paragraph Frontier

Goal:

```text
Enumerate low-energy human-like pages using sentence/word/paragraph students,
not legacy class-FSM.
```

This is the first real frontier experiment for product-quality zero-address pages.

Algorithm:

```text
1. rank frequent sentence templates by template energy
2. realize each template through word transitions
3. rank frequent paragraph shapes by paragraph energy
4. realize each shape as a sequence of generated sentences
```

This is currently a frontier sampler, not final exact rank/unrank.

Complexity:

```text
O(K * average_template_length * branch)
```

where:

```text
K      = requested frontier size
branch = number of word candidates considered per token type
```

Advantages:

- Uses sentence/word/paragraph students as comparison models.
- Produces human-like low-energy pages.
- Much better than legacy class-FSM frontier.

Limitations:

- Not yet exact global counting.
- Needs completeness fallback.
- Needs deterministic tie-break and integer-cost formalization.

Implementation:

```text
experiments/sentence_astar_frontier.py
```

Output:

```text
models/astar_sentence_frontier_v1/
```
