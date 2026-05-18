# Counting Infinity

## The challenge

We want an addressable Library of Babel over a fixed alphabet:

```text
alphabet size = 256
page length   = 4096 symbols
space size    = 256^4096 = 2^32768
```

The trivial bijection is easy:

```text
page <-> base-256 integer
```

But this is only a codec. It does not solve the actual product/research goal.

The real goal is a **human-shaped ordering**:

```text
address 0        -> most human-like pages
larger addresses -> less human-like pages
far tail         -> noise
```

So the real rank is not raw positional rank.

It is:

```text
student_rank(page)
=
rank_by(
  student_energy(page),
  raw_lexicographic_tiebreaker
)
```

This preserves a strict bijection if the counting layer can answer:

```text
how many pages have energy < E?
how many pages have energy = E and are raw-before this page?
```

That is the core problem.

---

## Why brute force does not work

The naive finite-state dynamic program is:

```text
dp[position][state][energy] = count
```

This is exact and conceptually correct.

But for page length 4096, the energy axis becomes enormous.

Even with a small FSM, the table may contain millions or billions of useful energy cells. Faster languages, assembly, SIMD, or GPU acceleration can help by constant factors, but they do not change the asymptotic shape of the problem.

The bottleneck is not just CPU speed.

The bottleneck is the size of the counting object.

---

## Current empirical results

### Alphabet and corpus

Normalized top-256 alphabet:

```text
coverage ≈ 99.9768%
normalized corpus symbols ≈ 37.35M
```

### Markov ladder

Observed state growth:

```text
M1      256 states
M2      17k states
M3      184k states
M4      ~885k states
M5      ~2.66M states
```

Disk growth:

```text
M3      ~91 MB
M4      ~433 MB
M5      ~1.36 GB
```

This shows the central tradeoff:

```text
more context -> better human texture -> harder exact counting
```

### FSM student v1

Finite class student:

```text
states/classes: START, RU, EN, SPACE, PUNCT, EMOJI, NEWLINE, OTHER
```

Important observed transitions:

```text
RU    -> RU       ~15.48M
EN    -> EN       ~7.23M
EMOJI -> EMOJI    ~552k
SPACE -> RU       ~3.55M
SPACE -> EN       ~1.64M
```

The model is tiny and countable, but too coarse for beautiful generation.

### Word and sentence students

Word student:

```text
~2.5k token vocabulary
~2.5k transition states
~4.5 MB browser payload
```

Sentence student:

```text
~159,854 unique sentence templates
1,200 exported high-frequency templates
~4.7 MB browser payload
```

These are much better for generation, but exact counting is more complex than the class FSM.

### Exact student-rank MVP

We implemented exact energy-ordered rank/unrank for short lengths.

Ordering:

```text
energy first, raw rank as tie-breaker
```

Example for length 4:

```text
space size = 256^4 = 4,294,967,296
student_rank("прив") = 149,830
energy("прив") = 1341
student_unrank(0) = "оооо"
```

This proves the mechanism, but not yet at production page length.

### Long-page counting experiment

Started a sparse FSM counting run:

```text
length = 1024
band   = min_energy + 50,000
```

The engine uses aggregated transitions:

```text
(prev_state) -> (next_state, cost, multiplicity)
```

This reduced raw 256-symbol branching into about:

```text
234 aggregated transitions per state
```

Early result:

```text
position 4 counted exactly 256^4 pages
```

But even the low-energy frontier grows quickly.

---

# Four approaches

We probably need all four as comparable strategies, not as mutually exclusive options.

---

## 1. Flat FSM dynamic programming

### Idea

Use the finite student directly:

```text
dp[position][state][energy] = count
```

Then:

```text
student_rank(page)
= count(energy < E)
+ count(energy = E, raw-before page)
```

### Advantages

- Exact.
- Easy to reason about.
- Gives a real proof of bijection.
- Good for small models and short pages.
- Great baseline.

### Disadvantages

- Energy dimension explodes.
- Full length 4096 is likely too large in flat form.
- Coarse FSM may generate boring attractors.

### Current status

Implemented:

```text
experiments/student_rank_exact_mvp.py
experiments/fsm_count_1024.py
```

Useful for proof, testing, and low-energy frontier experiments.

---

## 2. Generating functions / polynomial matrices

### Idea

Represent the FSM as a matrix of polynomials:

```text
M(x)[state_from][state_to]
= Σ multiplicity * x^cost
```

Then length-N counts are coefficients of:

```text
M(x)^N
```

### Advantages

- Same exact math as DP.
- Can use fast exponentiation.
- More algebraically compact.
- Natural fit for energy histograms.

### Disadvantages

- Polynomial degrees can still explode.
- Truncation is needed for low-energy bands.
- Implementation is more complex.
- Full exact distribution may still be impossible.

### Best use

Low-energy frontier:

```text
coefficients up to E_min + band
```

This is probably the right next exact-counting improvement over flat DP.

---

## 3. Low-energy enumeration / A* frontier

### Idea

Instead of counting the whole universe, enumerate the cheapest pages first.

Use a priority queue:

```text
next candidate = lowest energy partial/page
```

This gives:

```text
unrank(0), unrank(1), unrank(2), ...
```

without knowing all high-energy counts.

### Advantages

- Directly targets the product goal.
- Very useful near address 0.
- Can produce real early-library pages quickly.
- Avoids counting the noise tail.

### Disadvantages

- Harder to jump to arbitrary huge rank.
- Needs duplicate control and tie-breaking discipline.
- May still grow exponentially with requested K.

### Best use

The first K human-like pages:

```text
K = 1k, 10k, 1M, ...
```

This is probably the fastest way to make the Library feel real.

---

## 4. Hierarchical finite grammar

### Idea

Do not count 4096 characters directly.

Count the page as a hierarchy:

```text
page
-> paragraphs
-> sentences
-> tokens
-> characters
```

Each layer is finite and has integer costs.

### Advantages

- Matches human text structure.
- Much better generation.
- Counting can factor by hierarchy.
- Scales better than flat char-level DP.
- Natural fit for our word/sentence students.

### Disadvantages

- Harder proof engineering.
- Need to ensure every 4096-symbol page is still reachable.
- Need fallback/noise branches to preserve completeness.
- Rank/unrank becomes multi-level.

### Best use

The real production model.

This is probably the correct final direction:

```text
hierarchical finite student
+
exact low-energy counting
+
fallback raw/noise completion
```

---

# Do we need all four?

Probably yes, at least for comparison.

Each approach answers a different question:

```text
Flat FSM DP             -> proof baseline
Generating functions    -> faster exact bucket counting
A* low-energy frontier  -> usable early pages
Hierarchical grammar    -> realistic human-like structure
```

The product likely needs a hybrid:

```text
hierarchical grammar for structure
+
generating functions for bucket counts
+
A* for early human pages
+
flat DP as verification baseline
```

---

# What counts as success?

A successful Library core should support:

```text
student_rank(page) -> address
student_unrank(address) -> page
```

with:

```text
no holes
no duplicates
all 256^4096 pages reachable
human-like pages near zero
noise pages far away
```

The current raw page64 address is only a codec.

The real address must be student-ranked.

---

# Next experiments

## Experiment A: truncated polynomial matrix

Build a generating-function counter for FSM student v1:

```text
length = 1024
band = 10k, 50k, 100k
```

Compare with sparse DP results.

## Experiment B: A* first pages

Enumerate first K pages by energy:

```text
K = 100, 1k, 10k
```

Show them on the website as the first real library pages.

## Experiment C: hierarchical count prototype

Use sentence templates and token automaton:

```text
paragraph count
sentence template count
token transition count
character fallback count
```

Prove a small complete version first.

## Experiment D: completeness fallback

Every hierarchical model must include a fallback path:

```text
raw symbol mode
```

This ensures all pages remain reachable, even if human-shaped branches dominate low energy.


# Detailed experiment notes

```text
notes/experiments/experiment_b_astar_frontier.md
notes/experiments/experiment_c_hierarchical.md
```
