# Eval Harness v2

Goal:

```text
Evaluate real generated frontier text, not placeholder cluster IDs.
```

Compared models:

- legacy class-FSM
- word student
- sentence student
- paragraph/hierarchical student

Metrics:

- distribution penalty against held-out corpus profile;
- repetition / collapse penalty;
- sentence length mismatch;
- unique token ratio;
- emoji/punctuation rates;
- sample text for human review.

Outputs:

```text
models/eval_harness_v2/leaderboard.json
models/eval_harness_v2/summary.json
```
