# Current Status

## Done

- dataset/cache pipeline
- fixed top alphabet
- raw page/address bijection
- legacy class FSM
- word student
- sentence student
- paragraph student
- cluster student v1
- cluster student v2 k-means
- static website explorer
- generator comparison UI
- student_rank exact MVP for short lengths
- sparse FSM counting experiments
- Counting Infinity notes

## In progress

- exact counting layer
- production rank/unrank
- cluster-based finite enumeration
- energy/counting alignment

## Current main path

```text
cluster_student_v2
-> exact cluster counting
-> exact rank/unrank
-> production-scale addressable Babel
```

## Important correction

Manual hierarchy is no longer the primary model path.

It is now mostly:

```text
legacy / comparison / fallback / historical research path
```

The current main model path is:

```text
context vectors
-> k-means
-> cluster transitions
```
