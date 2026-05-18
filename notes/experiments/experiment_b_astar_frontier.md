# Experiment B — A* Low-Energy Frontier

Goal:

```text
Enumerate the first human-like pages directly
without counting the whole universe.
```

Algorithm:

```text
priority queue ordered by:
  current_energy + optimistic_remaining_cost
```

Complexity:

```text
Worst-case exponential in requested frontier size K.
Memory proportional to active frontier.
```

Advantages:
- Directly targets near-zero addresses.
- Produces actual pages immediately.
- No need to count the noise tail.

Disadvantages:
- Hard random access.
- Duplicate/tie-break engineering matters.
- Frontier can still explode.

Implementation:

```text
experiments/fsm_astar_frontier.py
```

Real metrics and sample pages will be appended automatically from runs.
