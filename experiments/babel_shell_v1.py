#!/usr/bin/env python3
"""Babel-1: an exact shell enumeration with a contextual symbol permutation.

This module deliberately separates the two claims that were previously
coupled in the long-page ranker:

* :class:`BinaryShellRanker` is a proved bijection over ``q ** length`` internal
  digits.  It orders an internal page by the number of digits outside ``[0, k)``.
* :class:`ContextPermutationMarkov5` maps every internal digit to one of the 256
  project symbols and back.  It is allowed to be an approximate language model;
  its only hard contract is to return a deterministic permutation.

The composition is therefore a bijection even if the language ordering is
imperfect. The default permutation uses the versioned top-256 Markov-5 model,
but never participates in counting.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from functools import lru_cache
from hashlib import sha256
from math import comb, gcd, log2
from pathlib import Path
from typing import Iterable, Protocol, Sequence
import json
import mmap
import struct


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALPHABET = ROOT / "models/top256_alphabet/alphabet_top256.json"
DEFAULT_MODEL = ROOT / "models/cluster_student_v2/model.json"
MARKOV5_META = ROOT / "models/top256_markov5/markov5_meta.json"
WORD_MODEL = ROOT / "models/word_student_v1/word_student_v1.json"


class Permutation(Protocol):
    """A deterministic full ordering of every symbol after ``prefix``."""

    alphabet: Sequence[str]

    def order(self, prefix: Sequence[int]) -> Sequence[int]: ...


class BinaryShellRanker:
    """Rank internal digits by the count of non-top-``k`` choices.

    Shell ``s`` contains ``C(length, s) * k**(length-s) * (q-k)**s`` pages.
    The optional affine map is a permutation within, never across, shells.
    """

    def __init__(self, length: int, q: int = 256, k: int = 16, edition: str = "Babel-1", scramble: bool = True):
        if length < 1:
            raise ValueError("length must be positive")
        if not 1 <= k < q:
            raise ValueError("k must satisfy 1 <= k < q")
        self.length, self.q, self.k = int(length), int(q), int(k)
        self.bad = self.q - self.k
        self.edition = edition
        self.scramble = bool(scramble)
        counts = [self.k ** self.length]
        for s in range(self.length):
            counts.append(counts[-1] * (self.length - s) * self.bad // ((s + 1) * self.k))
        self.shell_counts = tuple(counts)
        starts = [0]
        for count in self.shell_counts:
            starts.append(starts[-1] + count)
        self.shell_starts = tuple(starts)
        self.space_size = self.shell_starts[-1]
        if self.space_size != self.q ** self.length:
            raise AssertionError("shell counts do not cover the space")

    def shell_for_rank(self, rank: int) -> tuple[int, int]:
        if not 0 <= rank < self.space_size:
            raise ValueError(f"rank must be in [0, {self.space_size})")
        shell = bisect_right(self.shell_starts, rank) - 1
        return shell, rank - self.shell_starts[shell]

    def _affine(self, shell: int) -> tuple[int, int, int]:
        modulus = self.shell_counts[shell]
        if not self.scramble:
            return 1, 0, modulus
        if modulus == 1:
            return 0, 0, 1
        digest = sha256(f"{self.edition}:{self.length}:{self.q}:{self.k}:{shell}".encode()).digest()
        a = int.from_bytes(digest[:16], "big") % modulus or 1
        while gcd(a, modulus) != 1:
            a = (a + 1) % modulus or 1
        b = int.from_bytes(digest[16:], "big") % modulus
        return a, b, modulus

    @staticmethod
    def _inverse_mod(value: int, modulus: int) -> int:
        return pow(value, -1, modulus)

    def _scramble(self, shell: int, raw: int) -> int:
        a, b, modulus = self._affine(shell)
        return (a * raw + b) % modulus

    def _unscramble(self, shell: int, value: int) -> int:
        a, b, modulus = self._affine(shell)
        return (self._inverse_mod(a, modulus) * (value - b)) % modulus

    @staticmethod
    def _rank_combination(indices: Sequence[int], n: int) -> int:
        rank, previous = 0, -1
        for offset, index in enumerate(indices):
            for candidate in range(previous + 1, index):
                rank += comb(n - candidate - 1, len(indices) - offset - 1)
            previous = index
        return rank

    @staticmethod
    def _unrank_combination(rank: int, n: int, choose: int) -> list[int]:
        result: list[int] = []
        candidate = 0
        for remaining in range(choose, 0, -1):
            while True:
                count = comb(n - candidate - 1, remaining - 1)
                if rank < count:
                    result.append(candidate)
                    candidate += 1
                    break
                rank -= count
                candidate += 1
        return result

    def _raw_rank(self, digits: Sequence[int]) -> tuple[int, int]:
        if len(digits) != self.length or any(not 0 <= digit < self.q for digit in digits):
            raise ValueError(f"digits must contain exactly {self.length} values in [0, {self.q})")
        bad_positions = [index for index, digit in enumerate(digits) if digit >= self.k]
        shell = len(bad_positions)
        local = self._rank_combination(bad_positions, self.length)
        for digit in digits:
            local *= self.bad if digit >= self.k else self.k
            local += digit - self.k if digit >= self.k else digit
        return shell, local

    def _raw_unrank(self, shell: int, local: int) -> list[int]:
        if not 0 <= shell <= self.length or not 0 <= local < self.shell_counts[shell]:
            raise ValueError("local shell rank is outside its shell")
        value_count = self.k ** (self.length - shell) * self.bad ** shell
        combo_rank, values = divmod(local, value_count)
        bad_positions = set(self._unrank_combination(combo_rank, self.length, shell))
        digits = [0] * self.length
        for index in range(self.length - 1, -1, -1):
            base = self.bad if index in bad_positions else self.k
            values, digit = divmod(values, base)
            digits[index] = digit + self.k if index in bad_positions else digit
        return digits

    def rank_digits(self, digits: Sequence[int]) -> int:
        shell, raw = self._raw_rank(digits)
        return self.shell_starts[shell] + self._scramble(shell, raw)

    def unrank_digits(self, rank: int) -> list[int]:
        shell, local = self.shell_for_rank(rank)
        return self._raw_unrank(shell, self._unscramble(shell, local))


class ContextPermutationV1:
    """A total 256-symbol ordering based on the existing student transition model."""

    def __init__(self, alphabet_path: Path = DEFAULT_ALPHABET, model_path: Path = DEFAULT_MODEL):
        alphabet_data = json.loads(Path(alphabet_path).read_text(encoding="utf-8"))
        self.alphabet = tuple(alphabet_data["alphabet"])
        if len(self.alphabet) != 256 or len(set(self.alphabet)) != 256:
            raise ValueError("Babel-1 requires the project's 256 unique symbols")
        model = json.loads(Path(model_path).read_text(encoding="utf-8"))
        self.clusters = int(model["clusters"])
        mapping = model.get("mapping", {})
        self.symbol_clusters = tuple(int(mapping.get(symbol, 0)) for symbol in self.alphabet)
        transitions = {int(src): {int(dst): int(count) for dst, count in row.items()}
                       for src, row in model.get("cluster_transitions", {}).items()}
        self.costs = []
        for source in range(self.clusters):
            row = transitions.get(source, {})
            peak = max(row.values(), default=0)
            self.costs.append(tuple(
                4 if peak == 0 else min(4, max(0, int(round(log2((peak + 1) / (row.get(dest, 0) + 1))))))
                for dest in range(self.clusters)
            ))

    @lru_cache(maxsize=16384)
    def _order_for_state(self, previous_cluster: int, previous_symbol: int) -> tuple[int, ...]:
        # The original alphabet is frequency-ranked.  Transition surprise comes
        # first; the two final numeric keys make ties reproducible and total.
        return tuple(sorted(
            range(256),
            key=lambda candidate: (
                self.costs[previous_cluster][self.symbol_clusters[candidate]],
                0 if candidate != previous_symbol else 1,
                candidate,
            ),
        ))

    def order(self, prefix: Sequence[int]) -> Sequence[int]:
        if not prefix:
            return tuple(range(256))
        previous = prefix[-1]
        return self._order_for_state(self.symbol_clusters[previous], previous)


class ContextPermutationMarkov5:
    """Total byte ordering derived from the stored top-256 Markov-5 model.

    The model supplies a cost for every byte after an observed five-byte context
    and a complete unigram fallback for every other prefix. Small deterministic
    penalties prevent the trivial space/repetition collapse of a greedy path;
    they only reorder slots and cannot affect the Babel-1 bijection.
    """

    def __init__(self, meta_path: Path = MARKOV5_META):
        meta_path = Path(meta_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.alphabet = tuple(meta["alphabet"])
        if len(self.alphabet) != 256 or len(set(self.alphabet)) != 256:
            raise ValueError("Markov-5 model must expose 256 unique symbols")
        self.context_symbols = int(meta["context_symbols"])
        self.fallback_costs = tuple(int(cost) for cost in meta["fallback_costs"])
        index_path = Path(meta["index_file"])
        rows_path = Path(meta["rows_file"])
        if not index_path.exists():
            index_path = meta_path.parent / index_path.name
        if not rows_path.exists():
            rows_path = meta_path.parent / rows_path.name
        self.index = index_path.read_bytes()
        self.row_file = rows_path.open("rb")
        self.rows = mmap.mmap(self.row_file.fileno(), 0, access=mmap.ACCESS_READ)
        self.state_count = len(self.index) // 8
        self.space = self.alphabet.index(" ") if " " in self.alphabet else 0
        self.newline = self.alphabet.index("\n") if "\n" in self.alphabet else -1

    def _state_row(self, prefix: Sequence[int]) -> tuple[int, ...]:
        if len(prefix) < self.context_symbols:
            return self.fallback_costs
        state = 0
        for symbol in prefix[-self.context_symbols:]:
            state = (state << 8) | int(symbol)
        low, high = 0, self.state_count
        while low < high:
            middle = (low + high) // 2
            candidate = struct.unpack_from("<Q", self.index, middle * 8)[0]
            if candidate < state:
                low = middle + 1
            else:
                high = middle
        if low >= self.state_count or struct.unpack_from("<Q", self.index, low * 8)[0] != state:
            return self.fallback_costs
        return struct.unpack_from("<256H", self.rows, low * 512)

    def order(self, prefix: Sequence[int]) -> Sequence[int]:
        costs = self._state_row(prefix)
        if not prefix:
            return tuple(sorted(range(256), key=lambda candidate: (
                costs[candidate] + (4096 if candidate in {self.space, self.newline} else 0), candidate,
            )))
        last = prefix[-1]
        run = 1
        for symbol in reversed(prefix[-33:-1]):
            if symbol != last:
                break
            run += 1
        word_length = 0
        for symbol in reversed(prefix[-32:]):
            if symbol in {self.space, self.newline}:
                break
            word_length += 1

        def penalty(candidate: int) -> int:
            if candidate == last:
                return 2048 * run
            if candidate in {self.space, self.newline}:
                return 4096 if last in {self.space, self.newline} else (1024 if word_length < 2 else 0)
            return 0

        return tuple(sorted(range(256), key=lambda candidate: (costs[candidate] + penalty(candidate), candidate)))


class ContextPermutationWordV1:
    """Word-transition prior completed by the total Markov-5 byte ordering.

    At a word boundary it favours initial letters of observed next words. Inside
    a word it favours only continuations present in that same transition row.
    Every other project symbol retains its Markov-5 position, so this is still a
    total deterministic permutation rather than a text generator.
    """

    def __init__(self, word_path: Path = WORD_MODEL):
        self.fallback = ContextPermutationMarkov5()
        self.alphabet = self.fallback.alphabet
        self.index = {symbol: position for position, symbol in enumerate(self.alphabet)}
        model = json.loads(Path(word_path).read_text(encoding="utf-8"))
        self.transitions = {
            previous: tuple(sorted(row.items(), key=lambda item: (-int(item[1]), item[0]))[:256])
            for previous, row in model["transitions"].items()
        }
        self.abstract = {key: tuple(value) for key, value in model.get("abstract_emissions", {}).items()}

    def _state(self, prefix: Sequence[int]) -> tuple[str, str]:
        text = "".join(self.alphabet[symbol] for symbol in prefix)
        end = len(text)
        while end and (text[end - 1].isalpha() or text[end - 1] in "-'"):
            end -= 1
        partial = text[end:].lower()
        before = text[:end].rstrip()
        start = len(before)
        while start and (before[start - 1].isalpha() or before[start - 1] in "-'"):
            start -= 1
        previous = before[start:].lower() or "<s>"
        return previous, partial

    def _recent_words(self, prefix: Sequence[int]) -> tuple[str, ...]:
        text = "".join(self.alphabet[symbol] for symbol in prefix).lower()
        words, current = [], []
        for char in text:
            if char.isalpha() or char in "-'":
                current.append(char)
            elif current:
                words.append("".join(current)); current = []
        if current:
            words.append("".join(current))
        return tuple(words[-12:])

    def _word_scores(self, prefix: Sequence[int]) -> tuple[int, ...]:
        previous, partial = self._state(prefix)
        primary = self.transitions.get(previous) or self.transitions.get("<s>", ())
        choices = list(primary)
        if not partial:
            seen = {token for token, _ in choices}
            choices.extend((token, count) for token, count in self.transitions.get("<s>", ()) if token not in seen)
        recent = set(self._recent_words(prefix))
        scores = [0] * 256
        for token, count in choices:
            words = self.abstract.get(token, (token,))
            weight = max(1, int(count))
            for word in words[:64]:
                candidate = str(word).lower()
                if not partial and candidate in recent:
                    weight = max(1, weight // 128)
                if not candidate.startswith(partial):
                    continue
                if len(candidate) == len(partial):
                    symbol = self.index.get(" ")
                    if symbol is not None:
                        scores[symbol] += weight
                    continue
                symbol = self.index.get(candidate[len(partial)])
                if symbol is not None:
                    scores[symbol] += weight
        return tuple(scores)

    def order(self, prefix: Sequence[int]) -> Sequence[int]:
        base = self.fallback.order(prefix)
        base_rank = {symbol: position for position, symbol in enumerate(base)}
        scores = self._word_scores(prefix)
        return tuple(sorted(range(256), key=lambda symbol: (-scores[symbol], base_rank[symbol])))


class BabelRanker4096:
    """The Babel-1 composition: exact shell code followed by contextual decoding."""

    def __init__(self, length: int = 4096, k: int = 16, permutation: Permutation | None = None, scramble: bool = True):
        self.permutation = permutation or ContextPermutationMarkov5()
        self.shell = BinaryShellRanker(length=length, q=len(self.permutation.alphabet), k=k, scramble=scramble)
        self.length = length
        self.alphabet = tuple(self.permutation.alphabet)
        self.symbol_index = {symbol: index for index, symbol in enumerate(self.alphabet)}

    @property
    def space_size(self) -> int:
        return self.shell.space_size

    def unrank_page(self, rank: int) -> dict:
        digits = self.shell.unrank_digits(rank)
        symbols: list[int] = []
        for digit in digits:
            order = self.permutation.order(tuple(symbols))
            if len(order) != len(self.alphabet) or set(order) != set(range(len(self.alphabet))):
                raise ValueError("context permutation must return every symbol exactly once")
            symbols.append(order[digit])
        return {"rank": int(rank), "shell": sum(digit >= self.shell.k for digit in digits),
                "page": "".join(self.alphabet[symbol] for symbol in symbols)}

    def rank_page(self, page: str) -> dict:
        if len(page) != self.length:
            raise ValueError(f"page must contain exactly {self.length} project-alphabet symbols")
        symbols = []
        digits = []
        for symbol in page:
            if symbol not in self.symbol_index:
                raise ValueError(f"symbol outside Babel-1 alphabet: {symbol!r}")
            symbol_id = self.symbol_index[symbol]
            order = self.permutation.order(tuple(symbols))
            try:
                digits.append(order.index(symbol_id))
            except ValueError as exc:
                raise ValueError("context permutation omitted a symbol") from exc
            symbols.append(symbol_id)
        rank = self.shell.rank_digits(digits)
        return {"rank": rank, "shell": sum(digit >= self.shell.k for digit in digits), "page": page}


def _exhaustive_reduced_space_test() -> None:
    class RotatingPermutation:
        alphabet = tuple("abcd")
        def order(self, prefix: Sequence[int]) -> Sequence[int]:
            shift = (sum(prefix) + len(prefix)) % 4
            return tuple((index + shift) % 4 for index in range(4))

    # Symmetric, degenerate-good, degenerate-bad, and non-binary alphabets.
    # These are full enumerations, not sampled checks.
    for q, k, length in ((4, 2, 4), (4, 1, 8), (4, 3, 8), (5, 2, 6)):
        shell = BinaryShellRanker(length, q=q, k=k)
        assert shell.space_size == q ** length
        assert {shell.rank_digits(shell.unrank_digits(rank)) for rank in range(shell.space_size)} == set(range(shell.space_size))
        if q != 4:
            class FiveSymbolPermutation:
                alphabet = tuple("abcde")
                def order(self, prefix: Sequence[int]) -> Sequence[int]:
                    shift = (sum(prefix) + len(prefix)) % 5
                    return tuple((index + shift) % 5 for index in range(5))
            permutation: Permutation = FiveSymbolPermutation()
        else:
            permutation = RotatingPermutation()
        ranker = BabelRanker4096(length=length, k=k, permutation=permutation)
        for rank in range(ranker.space_size):
            page = ranker.unrank_page(rank)["page"]
            assert ranker.rank_page(page)["rank"] == rank


if __name__ == "__main__":
    _exhaustive_reduced_space_test()
    production = BabelRanker4096()
    for probe in (0, 1, production.space_size // 2, production.space_size - 1):
        page = production.unrank_page(probe)["page"]
        assert production.rank_page(page)["rank"] == probe
    print("Babel-1 shell ranker self-test: OK")
