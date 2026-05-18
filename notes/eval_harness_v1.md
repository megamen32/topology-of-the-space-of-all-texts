# Eval Harness v1

Goal:

```text
Turn magic numbers into measurable experiments.
```

Metrics:

```text
1. held-out average energy
2. frontier collapse score
3. model size proxy
4. final combined score
```

Grid search:

```text
clusters: 64 / 128
context window: 2 / 3 / 5
memory size: 1 / 2
```

This harness is intentionally language-agnostic.

No Russian grammar rules.
No English grammar rules.
Only corpus statistics.

Outputs:

```text
models/eval_harness_v1/
```
