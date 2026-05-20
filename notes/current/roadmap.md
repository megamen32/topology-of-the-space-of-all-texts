# Current Roadmap

## Step 1 — Freeze current truth

Create current architecture/status/open-problems docs.

Status:

```text
done
```

## Step 2 — Make cluster student v2 the explicit main path

Update docs and README to point to:

```text
notes/current/architecture.md
notes/current/status.md
notes/current/open_problems.md
notes/current/roadmap.md
```

## Step 3 — Implement exact cluster counting MVP

Target function:

```text
count_cluster_path(state, length, energy_budget)
```

Start small:

```text
length = 16, 32, 64
clusters = 64
```

## Step 4 — Add rank/unrank prototype over cluster graph

Use ordering:

```text
(total_energy, cluster_path_order, raw_tiebreaker)
```

## Step 5 — Scale counting

Investigate:

- chunk decomposition
- polynomial matrices
- mmap/external-memory frontier
- compressed sparse buckets

## Step 6 — Rewrite proof around current architecture

The proof should describe:

```text
raw bijection
+
cluster-student ordering
+
exact counting layer
```

not just manual hierarchy.
