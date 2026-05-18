# Markov scaling notes

The top-256 alphabet makes the corpus almost closed: current coverage is about `99.9648%`.

Observed state growth on the same encoded corpus:

```text
M0/unigram  1 state
M1          256 states
M2          17,305 states
M3          184,646 states
M5          millions of states and still growing while emitting rows
```

This is the central tradeoff:

```text
more context -> better human texture -> harder exact counting
```

Markov models are not the final aesthetic model. They are measuring instruments for the price of context.

The next serious model should be a finite weighted student:

```text
alphabet symbols -> token/FSM states -> integer energy -> exact counting
```

Teacher models can tune the student later, but the proof layer should remain finite and discrete.
