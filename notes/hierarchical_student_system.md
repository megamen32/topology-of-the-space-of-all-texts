# Hierarchical Student System

## Core idea

The project is moving away from a flat byte-level Markov-only model toward a hierarchical finite student.

The hierarchy is:

```text
page
-> paragraphs
-> sentence templates
-> token transitions
-> character fallback
```

The important constraint remains unchanged:

```text
Every 4096-symbol page must stay reachable.
```

So all higher layers are guidance/energy layers above a complete base bijection.

---

# Markov ladder (M1-M5)

Observed growth on the normalized top-256 corpus:

```text
M1      256 states
M2      17k states
M3      184k states
M4      ~885k states
M5      ~2.66M states
```

Approximate disk usage:

```text
M3      ~91 MB
M4      ~433 MB
M5      ~1.36 GB
```

Meaning:

```text
more context
-> better local human texture
-> harder exact counting
```

M1 and M2 mostly learn local character regularities.
M3 starts producing recognizable word fragments.
M4 becomes noticeably language-shaped.
M5 begins capturing short semantic rhythm and punctuation habits.

But even M5 is still fundamentally local.

It does not truly model:
- long-range intent
- paragraph structure
- topic persistence
- discourse memory
- Telegram/post style planning

So the Markov ladder is useful mainly as:

```text
measurement instrument
for the price of context
```

not as the final aesthetic model.

---

# Why hierarchical student exists

Flat counting:

```text
dp[position][state][energy]
```

becomes too large for realistic long pages.

The hierarchical student attempts factorization:

```text
page
-> paragraph program
-> sentence program
-> token program
-> byte realization
```

This may reduce counting complexity because structure is reused.

Instead of counting every raw byte path independently, the system counts reusable higher-level constructions.

---

# Transformer relation

Transformers are currently treated as teachers, not exact students.

Reason:

```text
transformer hidden state
!=
small finite exact automaton
```

Possible architecture:

```text
LLM/transformer teacher
-> distilled finite student
-> integer energies
-> exact rank/unrank
```

So:

```text
Markov path      = proof-first
Transformer path = quality-first
Hierarchical FSM = compromise attempt
```

---

# Current unfinished areas / TODO

## 1. Long-page exact counting

Started but not completed:

```text
length = 1024
energy band = min + 50k
```

Problem:
- low-energy frontier still explodes
- sparse DP still grows too fast
- memory pressure remains dominant

---

## 2. Hierarchical factorization proof

Not yet proven:

```text
hierarchical decomposition
preserves exact bijection efficiently
```

Need:
- formal completeness proof
- reversible composition proof
- exact counting decomposition

---

## 3. Sentence/template composition

Partially implemented in:

```text
site/data/sentence_student.json
```

But missing:
- exact compositional grammar
- stable template algebra
- finite token fallback semantics

---

## 4. Energy normalization

Still unresolved:

```text
how to compare energies
across different hierarchy levels
```

Example:
- sentence rarity
- token rarity
- punctuation rhythm
- paragraph coherence

need compatible integer accounting.

---

## 5. Production-scale student_rank

Short exact ranking works.

But production-length pages still need:
- compressed counting
- chunk decomposition
- external-memory DP
- probabilistic pruning with exact correction

---

# Current direction

Current direction appears to be:

```text
base bijection
+
hierarchical finite student
+
teacher-guided energies
+
exact or near-exact counting layer
```

rather than a pure flat Markov generator.
