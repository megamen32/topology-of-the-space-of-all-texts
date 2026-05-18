# Product / architecture decisions

## Goal

Build a proof-preserving, enumerable Library of Babel reordered by human-likeness.

```text
all pages remain reachable
but human-like regions become geometrically nearby
```

## Current architecture

```text
internet corpora
↓
top-256 alphabet
↓
Markov manifold experiments
↓
LLM teacher field
↓
finite FSM student
↓
exact rank/unrank
```

## Why finite student

Exact ranking requires:

- finite state
- integer costs
- dynamic-programming countability
- exact reversibility

A raw transformer hidden state is not suitable as the proof layer.

## Teacher choice

Current teacher:

- host: `server-44`
- Ollama endpoint: `http://192.168.2.5:11434`
- model: `qwen3:4b-instruct`
- quantization: `Q4_K_M`

### Why this model

Empirically:

- ~147 tok/s steady-state generation
- ~5 sec warmup
- fits comfortably into 3080 Ti VRAM
- strong RU/EN internet texture
- good emoji/slang behavior

This model is not the final generator.
It is a local estimator of human-likeness.

## How to connect

From any LAN host:

```bash
curl http://192.168.2.5:11434/api/tags
```

Generate:

```bash
curl http://192.168.2.5:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"qwen3:4b-instruct",
    "prompt":"hello",
    "stream":false
  }'
```

## Student design

The student is a weighted finite-state internet-text automaton.

Example classes:

```text
SPACE
NEWLINE
RU
EN
DIGIT
PUNCT
EMOJI
URL
HASHTAG
OTHER
```

The student learns:

```text
P(next_class | state)
P(symbol | class)
```

plus anti-collapse penalties.

## Why this matters

The Library of Babel already proves:

```text
human culture occupies a tiny region
inside combinatorial text space
```

This project tries to:

```text
find that region
measure it
and make it addressable
```
