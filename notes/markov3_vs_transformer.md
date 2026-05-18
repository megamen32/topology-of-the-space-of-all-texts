# Markov-3 vs transformer/tiny LLM

Markov-3 is not a stepping stone to a transformer. It is a separate finite-state path.

## Why Markov-3 is useful

It is useful because it gives a fully discrete finite-state model:

```text
state = previous 3 bytes
next = 0..255
```

This makes exact combinatorial counting possible in principle:

```text
DP[position][state][cost]
```

That supports formal rank/unrank.

## Why it does not solve human text

Markov-3 only captures local byte patterns. It can learn UTF-8 fragments, common letter triples, punctuation, and spaces, but it cannot understand paragraphs, topics, grammar over long range, or Telegram-style intent.

So early pages may become more language-like than unigram, but still not truly human.

## Transformer path

A tiny transformer can give better scores, but exact rank/unrank is hard because its state is a high-dimensional hidden vector, not a small finite automaton.

Possible compromise:

1. Use transformer/LLM as teacher.
2. Distill into finite-state/token automaton with integer costs.
3. Use enumerative ranking on the finite model.

So:

```text
Markov-3 path = proof-first finite model
Transformer path = quality-first teacher, must be distilled for proof
```
