# Action plan: human-ordered bijective Babel

## Goal

Build exact functions:

```text
rank(page_4096_bytes) -> integer in [0, 2^32768)
unrank(integer) -> page_4096_bytes
```

The order should put pages that look like the chosen dataset near the beginning and byte-noise near the end.

## Minimum path

1. Keep the mathematical ordering simple:
   - `energy(page)` is an integer.
   - Sort by `(energy, lexicographic bytes)`.
   - This gives a total order over all fixed-length pages.

2. Validate on short page lengths:
   - `N=4, 8, 16, 32`.
   - Check `rank(unrank(n)) == n`.
   - Check `unrank(rank(page)) == page`.
   - Check total count is exactly `256^N`.

3. Build Markov-3 byte model:
   - state = previous 3 bytes.
   - next byte = 0..255.
   - transition cost = integer `-log P(next | state)`.
   - This is proof-first, not quality-first.

4. Benchmark exact counting:
   - start with small `N`.
   - measure RAM/time for Markov-1/2/3.
   - only then optimize counting.

5. Improve human-likeness with penalties:
   - repeated bytes/runs;
   - invalid UTF-8;
   - no spaces/words;
   - binary/control noise.

6. Build token/FSM model:
   - finite states like word/space/punctuation/newline/dialogue.
   - integer costs.
   - exact rank/unrank remains possible.

7. Optional later: transformer teacher
   - use LLM/tiny transformer only to tune or distill costs into finite FSM.
   - do not put transformer hidden state inside exact rank/unrank.

## Do not do yet

- Do not download terabytes.
- Do not put an LLM directly into rank/unrank.
- Do not start with full `N=4096` exact DP.
- Do not use Huffman bitstream as address.
