# Topology of the Space of All Texts

## Why this project exists

Imagine the complete space of all possible pages.

Every book.
Every conversation.
Every scientific paper.
Every future idea.
Every typo.
Every random sequence of symbols.

All of them already exist inside:

```text
Σ^L
```

The question is not:

```text
"Can we generate text?"
```

The question is:

```text
Can we build coordinates for the space of all texts?
```

A raw Library of Babel already gives a coordinate system:

```text
integer ↔ page
```

but it treats:

```text
human language
and
random noise
```

as equally close.

This project asks whether a different topology can exist:

```text
small ranks
→ meaningful pages

large ranks
→ increasingly noisy pages
```

while preserving:

```text
no missing pages
no duplicate pages
exact reversibility
```

---

## Core goal

Build:

```text
rank ↔ page
```

for:

```text
all pages = Σ^L
```

while preserving strict bijection and introducing human-shaped ordering.

---

## Current architecture

```text
raw corpus
→ token/context vectors
→ k-means clusters
→ cluster transition graph
→ finite student states
→ integer energies
→ exact counting
→ rank/unrank
```

Current main student:

```text
cluster student v2
```

---

## Current status

Completed:

- dataset pipeline
- top alphabet
- raw page/address bijection
- hierarchical students
- cluster student v1/v2
- LLM arena evaluation
- student_rank MVP
- sparse counting experiments
- website explorer

In progress:

- exact counting layer
- production rank/unrank
- cluster-path counting

---

## Read order

Start here:

```text
1. notes/current/architecture.md
2. notes/current/status.md
3. notes/current/open_problems.md
4. notes/current/roadmap.md
```

Then historical evolution:

```text
notes/phases/*
```

Then research and experiments:

```text
notes/research/*
notes/experiments/*
```

---

## Repository structure

```text
site/          interactive explorer and generators
experiments/   training and research code
models/        compact versioned models
notes/current/ current truth
notes/phases/  historical evolution
notes/         research and worklogs
```

## Screenshot

![Topology of the Space of All Texts site screenshot](docs/screenshots/site.png)

