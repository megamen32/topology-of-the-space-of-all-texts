"""Exact experimental addresses for two generated half-pages of alphabet indices.

Callers supply two versioned, deterministic predictors. Each takes and returns
one fixed-size byte string. Each byte is one of Babel's 256 symbol indices.
Running the module tests the addressing algebra without language-model weights.
"""
from __future__ import annotations

from collections.abc import Callable
from hashlib import shake_256
from random import Random


class GenerativeAddress:
    def __init__(
        self,
        half_length: int,
        opening: Callable[[bytes], bytes],
        continuation: Callable[[bytes], bytes],
    ):
        if half_length < 1:
            raise ValueError("half_length must be positive")
        self.half_length = half_length
        self.opening = opening
        self.continuation = continuation

    def _xor_prediction(self, value: bytes, prediction: bytes) -> bytes:
        if not isinstance(prediction, bytes) or len(prediction) != self.half_length:
            raise ValueError("a predictor must return one full half-page of symbol indices")
        return bytes(a ^ b for a, b in zip(value, prediction))

    def unrank(self, address: int) -> bytes:
        if address < 0 or address.bit_length() > 16 * self.half_length:
            raise ValueError("address outside the page space")
        digits = address.to_bytes(2 * self.half_length, "big")
        left, seed = digits[:self.half_length], digits[self.half_length:]
        opening = self._xor_prediction(left, self.opening(seed))
        ending = self._xor_prediction(seed, self.continuation(opening))
        return opening + ending

    def rank(self, page: bytes) -> int:
        if len(page) != 2 * self.half_length:
            raise ValueError("expected one full page of symbol indices")
        opening, ending = page[:self.half_length], page[self.half_length:]
        seed = self._xor_prediction(ending, self.continuation(opening))
        left = self._xor_prediction(opening, self.opening(seed))
        return int.from_bytes(left + seed, "big")


def _self_test() -> None:
    # Hashes stand in for deterministic predictors. Their output tests arithmetic.
    def opening(seed: bytes) -> bytes:
        return shake_256(b"opening" + seed).digest(len(seed))

    def continuation(first: bytes) -> bytes:
        return shake_256(b"continuation" + first).digest(len(first))

    small = GenerativeAddress(1, opening, continuation)
    for address in range(256 ** 2):
        assert small.rank(small.unrank(address)) == address
        page = address.to_bytes(2, "big")
        assert small.unrank(small.rank(page)) == page

    half = 2048
    full = GenerativeAddress(half, opening, continuation)
    rng = Random(20261120)
    for bits in (0, 1, 8, 9, 64, 65, 1024, 16384, 16385, 24576, 32768):
        for address in (rng.getrandbits(bits), (1 << bits) - 1):
            page = full.unrank(address)
            assert full.rank(page) == address
            if bits <= 8 * half:
                seed = address.to_bytes(half, "big")
                reference = opening(seed) + continuation(opening(seed))
                guaranteed = 2 * half - (bits + 7) // 8
                assert page[:guaranteed] == reference[:guaranteed]
    for _ in range(32):
        page = rng.randbytes(2 * half)
        assert full.unrank(full.rank(page)) == page

    # Even a predictor that always emits the same page is allowed. It gives 32
    # distinct early pages with identical first 4095 symbols: a diversity control.
    def constant(_: bytes) -> bytes:
        return bytes([42]) * half

    collapsed = GenerativeAddress(half, constant, constant)
    early = [collapsed.unrank(i) for i in range(32)]
    assert len(set(early)) == 32 and len({page[:-1] for page in early}) == 1
    assert all(collapsed.rank(page) == i for i, page in enumerate(early))
    print("65,536 two-symbol pages checked in both directions")
    print("4,096-symbol pages: round trips, address boundaries and prefix bounds passed")
    print("Constant generator: 32 distinct early pages share the first 4,095 symbols")


if __name__ == "__main__":
    _self_test()
