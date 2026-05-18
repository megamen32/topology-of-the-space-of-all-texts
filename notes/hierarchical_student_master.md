# Hierarchical Student Master Note

## Core idea

The project is moving from flat byte Markov chains toward a hierarchical finite student.

Hierarchy:

```text
symbols
 -> bytes
 -> tokens
 -> sentence templates
 -> paragraph structures
 -> document energy
 -> exact address ordering
```

The important constraint is:

```text
everything used by rank/unrank must remain finite and countable
```

---

# Markov ladder (M1-M5)

Observed empirical scaling on the normalized top-256 corpus.

```text
M1      256 states
M2      17k states
M3      184k states
M4      ~885k states
M5      ~2.66M states
```

Approximate storage growth:

```text
M3      ~91 MB
M4      ~433 MB
M5      ~1.36 GB
```

Interpretation:

```text
more context
 -> better local human texture
 -> exponentially harder counting
```

M1 and M2 are mostly local byte statistics.
M3 starts producing visibly language-like fragments.
M4 begins preserving phrase texture.
M5 starts approximating local stylistic continuity.

But even M5 is still:

```text
finite local context
not semantic understanding
```

So Markov models are:

- proof instruments;
- scaling experiments;
- local texture estimators;
- finite-state counting baselines.

They are not the final aesthetic student.

---

# Why hierarchical student exists

Flat Markov models fail at:

- paragraph structure;
- topic persistence;
- long-range coherence;
- dialogue memory;
- semantic planning.

The hierarchical student tries to preserve:

```text
finite counting
+
human-like structure
```

instead of choosing only one.

---

# Current hierarchy direction

## Layer 1 — byte/symbol layer

Discrete alphabet.

```text
256 normalized symbols
```

Supports exact bijection and raw page encoding.

---

## Layer 2 — token layer

Finite token automaton.

Possible token classes:

- words
- emoji
- punctuation
- whitespace
- sentence boundaries
- paragraph boundaries
- fallback symbolic classes

This is MVP3.

---

## Layer 3 — sentence student

The project already extracted:

```text
~159k sentence templates
```

and exports high-frequency sentence shapes.

This is the first genuinely hierarchical layer.

---

## Layer 4 — paragraph/document layer

Still incomplete.

Goal:

```text
sentence transitions
+
paragraph rhythm
+
document energy accumulation
```

This is where topic persistence and human pacing begin.

---

# Transformer role

Transformers are teachers, not proof engines.

Important rule:

```text
continuous hidden states cannot directly participate in exact rank/unrank
```

Possible path:

```text
Transformer teacher
 -> discretization
 -> finite weighted automaton
 -> exact counting layer
```

So the final architecture is likely:

```text
teacher model
+
finite student
+
exact enumerative ranking
```

---

# Main unfinished areas

## 1. Long-page exact counting

Current experiments explode in frontier size.

Open problem:

```text
exact counting for length 4096 with realistic human energies
```

---

## 2. Paragraph hierarchy

Sentence layer exists.

Paragraph/document transition model is still incomplete.

---

## 3. Energy compression

Need:

```text
better energy bucketing
sparse DP compression
approximate frontier pruning
```

without breaking exactness.

---

## 4. Distilled transformer student

Mentioned but not finished.

Still no finalized discretization pipeline.

---

# Canonical direction

The project direction is now:

```text
Library of Babel
+
finite hierarchical student
+
human-like energy ordering
+
exact reversible addressing
```

not:

```text
"just train a transformer"
```
