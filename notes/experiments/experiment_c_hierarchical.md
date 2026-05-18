# Experiment C — Hierarchical Finite Grammar

Goal:

```text
Replace flat 4096-char counting
with paragraph/sentence/token hierarchy.
```

Structure:

```text
page
-> paragraphs
-> sentence templates
-> token transitions
-> raw character fallback
```

Why:
- Human text is hierarchical.
- Counting factorizes better.
- Better semantic locality.
- More realistic generation.

Main risk:

```text
Need completeness fallback
so every 4096-symbol page remains reachable.
```

Prototype:

```text
experiments/hierarchical_student_prototype.py
```

Metrics and scaling results will be appended from runs.
