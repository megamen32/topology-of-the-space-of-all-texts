# Experiment B — A* Low-Energy Frontier

## Status

```text
B1 class-FSM frontier = legacy baseline
B2 sentence/word frontier = next real experiment
```

B1 was run on the old class-FSM student. It is useful as a baseline, but it is not the product model.

## B1 result: class-FSM collapse

The class-FSM frontier produced low-energy attractors such as repeated vowels:

```text
ооооооооооооооооооаоооооооооооооооооо...
```

This is not a failure of the ranking machinery.

It is a failure of the student quality.

The experiment proves:

```text
bad finite student -> bad zero-address pages
```

## Algorithm

A* over partial pages:

```text
priority = current_energy + optimistic_remaining_cost
```

Complexity:

```text
Worst-case exponential in requested frontier size K.
Memory proportional to active frontier.
```

## Advantages

- Directly targets near-zero addresses.
- Produces pages without counting the whole universe.
- Good way to inspect what a student considers cheap.

## Disadvantages

- Needs a good student.
- Hard random access.
- Frontier can still explode.

## Next: B2 sentence/word frontier

The next frontier experiment must run over:

```text
sentence_student_v1
+
word_student_v1
```

Expected structure:

```text
paragraph
-> sentence template
-> token transition
-> word/emoji realization
```

This is the first real test of:

```text
zero address = human-like page
```

Implementation target:

```text
experiments/sentence_astar_frontier.py
```
