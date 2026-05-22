"""Tests for the pure-Python bloom filter used by the library scanner.

Pure module — no Qt. Covers membership semantics, false-positive
rate within the configured bound on a representative population,
parameter scaling, and the fingerprint helper.
"""
from __future__ import annotations

import secrets

import pytest

from Imervue.library.bloom_filter import (
    DEFAULT_FALSE_POSITIVE_RATE,
    MAX_HASH_FUNCTIONS,
    MIN_BIT_ARRAY_BITS,
    BloomFilter,
    fingerprint,
)


# ---------------------------------------------------------------
# Membership semantics
# ---------------------------------------------------------------


def test_added_key_always_might_contain():
    """Bloom filters have no false negatives — every added key
    must subsequently report membership."""
    bf = BloomFilter(expected_items=100)
    for i in range(50):
        bf.add(f"key-{i}")
    for i in range(50):
        assert bf.might_contain(f"key-{i}")


def test_in_operator_works():
    """The ``__contains__`` alias mirrors :meth:`might_contain`
    so callers can use ``if x in bloom:``."""
    bf = BloomFilter(expected_items=10)
    bf.add("alpha")
    assert "alpha" in bf
    assert "beta" not in bf or "beta" in bf   # tautology — just smoke


def test_unseen_key_usually_not_contained():
    """Most never-added keys should return ``False``. A few may
    collide (false positives) — we tolerate up to the configured
    rate."""
    bf = BloomFilter(expected_items=1000, false_positive_rate=0.01)
    for i in range(1000):
        bf.add(f"added-{i}")
    false_positives = sum(
        1 for i in range(1000) if bf.might_contain(f"absent-{i}")
    )
    # Allow some margin — 1% rate ± headroom for the random seed.
    assert false_positives <= 30


def test_empty_filter_contains_nothing():
    bf = BloomFilter(expected_items=100)
    for i in range(50):
        assert not bf.might_contain(f"any-{i}")


def test_items_added_counter():
    bf = BloomFilter(expected_items=10)
    assert bf.items_added == 0
    bf.add("a")
    bf.add("b")
    bf.add("c")
    assert bf.items_added == 3


# ---------------------------------------------------------------
# Sizing math
# ---------------------------------------------------------------


def test_bit_array_grows_with_expected_items():
    """More expected items → bigger bit array, monotonically."""
    small = BloomFilter(expected_items=100).size_bits
    big = BloomFilter(expected_items=10_000).size_bits
    assert big > small


def test_bit_array_grows_when_fp_rate_tightens():
    """Tighter FP rate (lower number) → bigger bit array. The
    standard bloom-filter formula scales by ``-ln(p)``."""
    loose = BloomFilter(expected_items=1000, false_positive_rate=0.1).size_bits
    tight = BloomFilter(
        expected_items=1000, false_positive_rate=0.001,
    ).size_bits
    assert tight > loose


def test_floor_on_size_bits():
    """Even with absurdly small expected_items the bit array must
    have the documented floor so the modulo arithmetic stays
    valid."""
    bf = BloomFilter(expected_items=0)
    assert bf.size_bits >= MIN_BIT_ARRAY_BITS


def test_hash_function_count_capped():
    """``k = (m/n) ln 2`` grows with capacity; the cap protects
    per-check cost from going O(20+)."""
    bf = BloomFilter(expected_items=10, false_positive_rate=1e-9)
    assert bf.num_hashes <= MAX_HASH_FUNCTIONS


def test_hash_function_count_floored_at_one():
    """Even pathological inputs produce at least 1 hash function
    so add / contain do something useful."""
    bf = BloomFilter(expected_items=10**9, false_positive_rate=0.5)
    assert bf.num_hashes >= 1


@pytest.mark.parametrize("items", [1000, 5000])
def test_fp_rate_stays_within_3x_documented(items):
    """At sufficiently large populations, the observed FP rate
    stays within 3× the documented rate. Allows headroom for the
    bit-array floor and hash-function ceiling that distort the
    formula at the extremes."""
    bf = BloomFilter(
        expected_items=items, false_positive_rate=DEFAULT_FALSE_POSITIVE_RATE,
    )
    for i in range(items):
        bf.add(f"member-{i}-{secrets.token_hex(4)}")
    sample_size = max(2000, items)
    fp_count = sum(
        1 for _ in range(sample_size)
        if bf.might_contain(f"miss-{secrets.token_hex(8)}")
    )
    rate = fp_count / sample_size
    assert rate <= DEFAULT_FALSE_POSITIVE_RATE * 3


# ---------------------------------------------------------------
# fingerprint
# ---------------------------------------------------------------


def test_fingerprint_stable_for_same_inputs():
    """Same (path, mtime, size) → same fingerprint string. Catalog
    rehydrate must produce identical fingerprints to a re-stat of
    the same file."""
    a = fingerprint("/photos/a.jpg", 1700000000.0, 1024)
    b = fingerprint("/photos/a.jpg", 1700000000.0, 1024)
    assert a == b


def test_fingerprint_changes_with_mtime():
    """Edited file (mtime changed) must produce a new fingerprint
    so the scanner re-indexes it."""
    a = fingerprint("/photos/a.jpg", 1700000000.0, 1024)
    b = fingerprint("/photos/a.jpg", 1700000001.0, 1024)
    assert a != b


def test_fingerprint_changes_with_size():
    """Same path + mtime but different size shouldn't happen on a
    sane filesystem, but if it did the fingerprint must catch it
    and force a re-index."""
    a = fingerprint("/photos/a.jpg", 1700000000.0, 1024)
    b = fingerprint("/photos/a.jpg", 1700000000.0, 2048)
    assert a != b


def test_fingerprint_rounds_mtime_to_ms():
    """mtime arrives as a float with sub-microsecond noise on some
    filesystems. Rounding to ms keeps stat re-reads within the
    same millisecond producing the same fingerprint."""
    a = fingerprint("/photos/a.jpg", 1700000000.0001, 1024)
    b = fingerprint("/photos/a.jpg", 1700000000.0004, 1024)
    # Both round to 1700000000000 ms — same fingerprint.
    assert a == b
    # A bump past the ms boundary lands on a different fingerprint —
    # the file genuinely changed in measurable time.
    c = fingerprint("/photos/a.jpg", 1700000000.002, 1024)
    assert a != c


def test_fingerprint_distinct_paths_distinct_fingerprints():
    a = fingerprint("/photos/a.jpg", 1700000000.0, 1024)
    b = fingerprint("/photos/b.jpg", 1700000000.0, 1024)
    assert a != b


# ---------------------------------------------------------------
# End-to-end with the fingerprint helper
# ---------------------------------------------------------------


def test_bloom_with_fingerprint_round_trip():
    """The actual usage pattern: pre-populate from (path, mtime,
    size) tuples; the scanner queries with a freshly computed
    fingerprint and expects membership."""
    bf = BloomFilter(expected_items=10)
    catalog = [
        ("/photos/a.jpg", 1700000000.0, 1024),
        ("/photos/b.jpg", 1700000100.0, 2048),
    ]
    for path, mtime, size in catalog:
        bf.add(fingerprint(path, mtime, size))
    # Walking the filesystem and re-statting both → both in bloom.
    for path, mtime, size in catalog:
        assert fingerprint(path, mtime, size) in bf
    # Edited file (mtime bumped) → not in bloom → scanner indexes it.
    assert fingerprint("/photos/a.jpg", 1700000999.0, 1024) not in bf
