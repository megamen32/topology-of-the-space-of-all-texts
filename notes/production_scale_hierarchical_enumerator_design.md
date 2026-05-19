# Production-Scale Hierarchical Enumerator

## Objective

Build:

```text
exact hierarchical rank/unrank
for human-ordered Babel pages
```

with:

```text
page length = 4096
alphabet    = 256
exact bijection preserved
```

---

# Core insight

Flat counting explodes:

```text
dp[position][state][energy]
```

The solution must:

```text
compress structure
instead of compressing bytes
```

---

# Hierarchical layers

```text
page
-> paragraph
-> sentence
-> token
-> fallback bytes
```

---

# Counting strategy

Replace:

```text
dp[position][state][energy]
```

with:

```text
count_token
count_sentence
count_paragraph
count_page
```

---

# Critical requirement

Must preserve:

```text
rank(unrank(i)) = i
unrank(rank(x)) = x
```

---

# Immediate implementation tasks

## Sentence counting

```text
count_sentence(template, length, energy)
```

## Paragraph composition

```text
count_paragraph(sentences, energy)
```

## Chunked page counting

```text
page = chunk₁ + chunk₂ + ...
```

## External-memory frontier

Need:

- mmap tables
- disk-backed sparse arrays
- compressed buckets

## Polynomial matrix path

Resume:

```text
FSM polynomial matrices
```

---

# Main unresolved problem

```text
production-scale exact hierarchical enumeration
```
