# Legacy note

Merged into: `notes/hierarchical_student_master.md`

Original content preserved below.

---

# MVP 3 / MVP 4: token automaton and discretized transformer

## Cost model

All probabilistic models must be converted into integer energy costs:

```text
cost = floor(-log2(P) * scale)
```

Typical scale:

```text
scale = 256
```

This keeps the proof layer discrete and compatible with dynamic programming / enumerative ranking.

## MVP 3: token automaton

The next serious student is not character-only.

It is a finite token automaton.

Token classes:

- words;
- emoji;
- punctuation;
- whitespace;
- sentence boundaries;
- paragraph boundaries;
- fallback classes like `<ru>`, `<en>`, `<num>`, `<emoji>`, `<other>`.

The automaton learns:

```text
P(next_token | finite_state)
P(token_shape | state)
P(symbols | token)
```

Then converts these probabilities into integer costs.

The token automaton is still finite, discrete, and countable.

This is the current best path for:

```text
human-like generation
+
exact rank/unrank later
```

## MVP 4: tiny transformer teacher

A tiny transformer can be used as a teacher, but not as the proof model.

Very important:

```text
Do not use raw hidden state directly inside rank/unrank.
```

A transformer hidden state is continuous and enormous. It does not give a simple finite-state counting structure.

Instead, if we use a transformer, it must be discretized.

Possible approaches:

### 1. Hidden-state clustering

Run the teacher over corpus windows.

Collect hidden states.

Cluster them:

```text
hidden_state -> cluster_id
```

Then build a finite automaton over cluster IDs.

### 2. VQ-VAE / vector quantization

Learn a codebook:

```text
hidden_state -> discrete_code
```

Then the student operates over discrete codes.

### 3. Finite-state abstraction

Distill transformer behavior into:

```text
state_id
transition_cost
emission_cost
```

The final model must be exportable as finite tables.

## Product rule

Teacher can be neural.

Student must be finite.

```text
Transformer = taste / human-likeness field
Finite student = proof / addressable geometry
```

## Current ladder

```text
MVP 1: base-256 rank/unrank
MVP 2: char/FSM student
MVP 3: token automaton
MVP 4: discretized tiny transformer teacher
```

## Why this matters

The Library must remain complete:

```text
all 256^4096 pages exist
```

The ordering can be human-shaped, but the address space cannot contain holes, duplicates, or continuous hidden variables.
