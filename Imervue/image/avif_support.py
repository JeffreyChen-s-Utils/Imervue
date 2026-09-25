"""AVIF through Pillow's own AVIF plugin — no extra package.

Pillow's wheels read and write AVIF since 11.3 (libavif with dav1d to decode
and aom to encode), and pillow-heif 1.0 dropped its AVIF opener for that
reason: installing pillow-heif never helps an AVIF file. A Pillow without
libavif (built from source, or the Windows ARM64 wheel) has no AVIF plugin;
:func:`avif_available` says which one is running.
"""
from __future__ import annotations

from PIL import features

AVIF_EXTENSIONS: frozenset[str] = frozenset({".avif"})


def avif_available() -> bool:
    """True when this Pillow was built with libavif and can read and write AVIF."""
    return bool(features.check("avif"))
