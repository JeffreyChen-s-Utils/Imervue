"""Pure-Python bloom filter for fast "have I seen this fingerprint?" checks.

The scanner walks ``library_roots`` on every refresh and historically
re-indexed every file — for a 100k-image catalog where nothing has
changed that's 100k pointless SQL upserts (cheap individually,
several seconds in aggregate) plus 100k pHash recomputations (each
one a Pillow decode + DCT — *very* not cheap).

Workflow:

1. Scanner-start hydrates a :class:`BloomFilter` from the existing
   catalog (one row per image: ``(path, mtime, size)`` → fingerprint).
2. For each file the scanner walks, compute its fingerprint with
   :func:`fingerprint` and check :meth:`BloomFilter.might_contain`.
3. ``False`` → definitely a new / changed file; index it.
4. ``True``  → probably unchanged. Fall back to one exact SQL
   lookup to disambiguate; if mtime + size still match, skip the
   pHash recomputation entirely.

A bloom filter only has false positives (member-set says "yes" for
a non-member), never false negatives, so the worst case for an
unchanged library is one SQL roundtrip per file vs the previous
"one upsert + one pHash" per file. Best case (lots of unchanged
files) is one bloom check per file — orders of magnitude faster.

This is pure Python — no external bloom-filter dep. The math is
small enough to ship verbatim.
"""
from __future__ import annotations

import hashlib
import math

DEFAULT_FALSE_POSITIVE_RATE: float = 0.01
"""1 % false-positive rate. The fall-back is "do the SQL lookup"
which is still cheap; tighter rates would inflate the bit array
without proportional benefit."""

MIN_BIT_ARRAY_BITS: int = 64
"""Floor so a brand-new empty catalog still has a usable filter
(zero-sized bit array would divide by zero)."""

MAX_HASH_FUNCTIONS: int = 16
"""Cap on the number of derived hashes. The formula
``k = (m / n) * ln(2)`` grows with capacity; past ~16 the
diminishing returns aren't worth the per-check cost."""


def _optimal_size_bits(expected_items: int, false_positive_rate: float) -> int:
    """Compute the bit-array size required for the requested
    capacity / FP rate. Standard bloom-filter math:
    ``m = -n * ln(p) / (ln 2)^2``."""
    n = max(1, int(expected_items))
    p = max(1e-9, min(0.5, float(false_positive_rate)))
    bits = -n * math.log(p) / (math.log(2) ** 2)
    return max(MIN_BIT_ARRAY_BITS, int(math.ceil(bits)))


def _optimal_num_hashes(size_bits: int, expected_items: int) -> int:
    """Compute the optimal number of hash functions:
    ``k = (m / n) * ln 2``. Floored at 1, capped at
    :data:`MAX_HASH_FUNCTIONS` to keep per-check cost bounded."""
    n = max(1, int(expected_items))
    raw = (size_bits / n) * math.log(2)
    return max(1, min(MAX_HASH_FUNCTIONS, int(round(raw))))


class BloomFilter:
    """Compact bloom filter backed by a Python ``bytearray``.

    Use case: probabilistic membership. ``might_contain(key)`` may
    return ``True`` for non-members (≤ configured FP rate) but
    NEVER returns ``False`` for an added member. Callers that need
    certainty must follow up with an exact lookup.

    The hash is derived from a single SHA-256 over the key; the
    output is sliced into ``k`` independent hash values via
    "double-hashing" — ``h_i(x) = (h1 + i * h2) mod m``. Cheaper
    than running k separate hash functions and statistically
    equivalent for filter membership.
    """

    def __init__(
        self,
        expected_items: int = 1_000,
        false_positive_rate: float = DEFAULT_FALSE_POSITIVE_RATE,
    ) -> None:
        self._size_bits = _optimal_size_bits(expected_items, false_positive_rate)
        self._num_hashes = _optimal_num_hashes(self._size_bits, expected_items)
        self._bytes = bytearray((self._size_bits + 7) // 8)
        self._items_added: int = 0

    @property
    def size_bits(self) -> int:
        return self._size_bits

    @property
    def num_hashes(self) -> int:
        return self._num_hashes

    @property
    def items_added(self) -> int:
        return self._items_added

    def add(self, key: str) -> None:
        """Mark ``key`` as a member. Subsequent
        :meth:`might_contain` calls return ``True`` for this key."""
        for bit in self._bit_positions(key):
            self._bytes[bit >> 3] |= 1 << (bit & 7)
        self._items_added += 1

    def might_contain(self, key: str) -> bool:
        """Probabilistic membership. ``False`` is definitive;
        ``True`` may be a false positive (rate ≈ configured FP)."""
        return all(
            self._bytes[bit >> 3] & (1 << (bit & 7))
            for bit in self._bit_positions(key)
        )

    def __contains__(self, key: str) -> bool:
        return self.might_contain(key)

    def _bit_positions(self, key: str):
        """Yield ``num_hashes`` bit positions for ``key``. Double-
        hashing reuses one SHA-256 output to derive k independent
        positions — cheap enough that callers can afford a check
        per file."""
        digest = hashlib.sha256(key.encode("utf-8"), usedforsecurity=False).digest()
        # Take 16-byte halves as two 64-bit integers.
        h1 = int.from_bytes(digest[:8], "big")
        h2 = int.from_bytes(digest[8:16], "big")
        # ``h2 == 0`` would collapse all derived positions to the
        # same bit — make sure it's non-zero. The shift below is
        # the standard fix in bloom-filter literature.
        if h2 == 0:
            h2 = 1
        for i in range(self._num_hashes):
            yield (h1 + i * h2) % self._size_bits


def fingerprint(path: str, mtime: float, size: int) -> str:
    """Stable string fingerprint of a file's identity in the
    catalog. The scanner builds this from each candidate file and
    looks it up in a bloom filter populated from the existing
    catalog rows.

    Format: ``"<path>|<mtime>|<size>"``. mtime is rounded to
    millisecond precision so two stat reads on the same file
    don't disagree on a floating-point tail."""
    return f"{path}|{round(float(mtime) * 1000)}|{int(size)}"
