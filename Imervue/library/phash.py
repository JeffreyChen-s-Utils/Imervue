"""
Perceptual hash (64-bit DCT pHash) for similar-image search.

Independent of imagehash / PyPI dependencies — uses PIL for I/O + NumPy for
the DCT. Hashing a 32×32 luma block into a 64-bit signature typically catches
resize, recompress, and small colour shifts while staying hostile to crops.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger("Imervue.phash")

_HASH_SIZE = 8      # Result is _HASH_SIZE * _HASH_SIZE bits (64).
_SAMPLE_SIZE = 32   # DCT input resolution.

# SQLite's INTEGER column stores signed 64-bit values, but a perceptual hash is
# naturally unsigned and its top bit (the DC-vs-median term) is set for
# essentially every real photo — so the raw value lands in [2**63, 2**64) and
# sqlite3 raises OverflowError when it is bound. ``to_signed64`` reinterprets the
# identical 64 bits as a two's-complement signed integer for storage; ``hamming``
# masks both operands back to 64 unsigned bits so a hash read back from the DB
# (signed) compares identically to one freshly computed in memory (unsigned).
_U64_MASK = (1 << 64) - 1
_SIGN_BIT = 1 << 63


def _dct_1d(a: np.ndarray) -> np.ndarray:
    """Plain DCT-II along the last axis — avoids a scipy dependency."""
    n = a.shape[-1]
    k = np.arange(n)
    # Build the DCT matrix once per call; vectorised across rows / columns.
    factors = np.cos(np.pi / n * (k + 0.5)[:, None] * k[None, :])
    return a @ factors.T


def compute_phash(path: str | Path) -> int | None:
    """Return a 64-bit perceptual hash of ``path`` or None on failure."""
    try:
        with Image.open(path) as im:
            sampled = im.convert("L").resize(
                (_SAMPLE_SIZE, _SAMPLE_SIZE), Image.Resampling.LANCZOS
            )
            arr = np.asarray(sampled, dtype=np.float32)
    except Exception as exc:  # noqa: BLE001 — pillow throws a zoo of types here
        logger.debug("phash failed for %s: %s", path, exc)
        return None

    dct = _dct_1d(_dct_1d(arr).T).T
    block = dct[:_HASH_SIZE, :_HASH_SIZE]
    # Exclude the DC (0,0) term so overall brightness doesn't dominate.
    values = block.flatten()
    mean = float(np.median(values[1:]))
    bits = values > mean
    result = 0
    for bit in bits:
        result = (result << 1) | int(bool(bit))
    return result


def to_signed64(value: int) -> int:
    """Reinterpret an unsigned 64-bit hash as a signed 64-bit int for SQLite.

    SQLite cannot bind a Python int outside the signed 64-bit range, and a pHash
    with its high bit set exceeds it. Two's-complement reinterpretation keeps the
    identical bit pattern while fitting the storable range.
    """
    value &= _U64_MASK
    return value - (1 << 64) if value & _SIGN_BIT else value


def hamming(a: int, b: int) -> int:
    """Return the number of differing bits between two 64-bit hashes.

    Masks to 64 unsigned bits so a hash stored in SQLite as a signed
    two's-complement integer compares identically to a freshly computed
    unsigned one.
    """
    return bin((int(a) ^ int(b)) & _U64_MASK).count("1")
