# Current Architecture

Status: current truth as of this repo state.

The project has moved from manual hierarchy toward learned finite structure:

```text
raw corpus
-> token/context vectors
-> k-means clusters
-> cluster transition graph
-> finite student states
-> integer energies
-> exact counting
-> rank/unrank
```

## Main student

Current main student:

```text
cluster student v2
```

Implementation:

```text
experiments/cluster_student_v2.py
models/cluster_student_v2/model.json
site/data/cluster_student_v2.json
```

The older manual hierarchy is still useful as history and comparison:

```text
paragraph student
sentence student
word student
legacy FSM
```

but the main research direction is now:

```text
context vectors -> k-means -> finite cluster graph
```

## Product surface

The website compares multiple finite students:

```text
cluster v1
cluster v2 k-means
paragraph/hierarchical
sentence/word
word
legacy class-FSM
```

Relevant files:

```text
site/generate.html
site/assets/generate.js
```
