# Legacy: class-FSM student

The class-FSM student is now considered a **legacy baseline**, not the main product model.

## What it is

A tiny finite-state model over broad classes:

```text
RU
EN
SPACE
PUNCT
EMOJI
NEWLINE
OTHER
```

It is useful because it is very easy to count exactly:

```text
dp[position][state][energy] = count
```

## Why it is legacy

It collapses to low-level attractors.

Observed near-zero frontier examples:

```text
ooooooooooooo...
```

or Russian equivalents like repeated `о`.

This is mathematically useful but aesthetically wrong.

## What it proved

The class-FSM baseline proved that:

- finite student energy can define a strict ordering;
- exact DP counting works;
- low-energy frontier enumeration works;
- bad students produce bad near-zero pages.

That last point is important: the ranking machinery is only as good as the student.

## Current status

```text
status = legacy baseline
```

It remains useful for:

- exact counting experiments;
- algorithm benchmarks;
- regression tests;
- proving the counting/ranking mechanism.

It should not be used as the main Library ordering model.

## Replacement direction

The main model should be:

```text
sentence/word student
+
hierarchical finite grammar
+
raw fallback for completeness
```

This model should define the real human-shaped address order.
