Status: historical transition document

Outcome:

```text
cluster_student_v2 implemented
```

---

# Emergent Structure and Next Steps

## Goal

We do not want merely:

```
text ↔ number
```

We want:

```
small rank
≈
human-like text
```

and increasingly noisy text further away.

---

## Phase 1 — Raw bijection

Strict mapping:

```
page64 ↔ integer
```

Mathematically correct but useless:

```
rank≈0
→
aaaaaaaa
→
оооооооо
```

---

## Phase 2 — FSM

Manual character classes:

```
RU
EN
NUM
PUNCT
SPACE
EMOJI
```

Local structure emerged:

```
RU → RU
```

But globally:

```
symbol soup
```

---

## Phase 3 — Hierarchical students

Architecture:

```
paragraph
↓
sentence
↓
word
↓
token
```

### Manually specified

We introduced:

- paragraph/sentence/word hierarchy
- token classes:

```
R L N P T E
```

---

### Emerged automatically

The system learned:

- sentence templates
- paragraph shapes
- transition statistics
- near‑zero frontier pages

Examples:

```
а почему я.
сказала вам завтра год.
```

instead of:

```
оооооооо
```

---

## Conclusion

We did NOT provide:

- grammar
- parts of speech
- dictionaries
- semantics
- language rules

But we DID provide architectural bias:

```
language
≈
paragraphs
made of
sentences
made of
words
```

Estimated emergence level:

```
0 = entirely manual
1 = fully emergent

≈0.4
```

---

## Next step — Cluster Student

Goal:

Move from manually imposed language structure toward emergent structure.

Target pipeline:

```
tokens
↓
contexts
↓
clusters
↓
cluster transitions
↓
latent discourse states
```

Expected emergent properties:

- words
- themes
- discourse roles
- paragraph organization

---

## Existing groundwork

Already partially present:

- context windows in eval_harness
- sentence/paragraph transition statistics
- frontier evaluation
- LLM + human preference loop

Missing:

- token embeddings
- token context vectors
- clustering
- discourse state memory
- rank/unrank over latent states

Suggested MVP:

```
cluster_student_v1

Top tokens: 5000
Context window: ±3
Clusters: 64/128/256
Memory states: 2–3
```
