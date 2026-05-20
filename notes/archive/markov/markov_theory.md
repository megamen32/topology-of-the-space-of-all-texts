# Markov Theory Notes

## Markov as a measurement instrument

Observed tradeoff:

```text
more context
-> better human texture
-> harder exact counting
```

Markov models are useful because they provide finite discrete states while exposing the cost of context.

## Proof-first vs quality-first

```text
Markov path      = proof-first finite model
Transformer path = quality-first teacher
```

Possible compromise:

```text
LLM teacher
-> distilled finite student
-> exact counting/ranking layer
```

## Scaling observations

```text
M1      256 states
M2      17k states
M3      184k states
M5      millions of states
```
