"""JPEG-XL decode/encode support via the optional ``pillow-jxl-plugin``.

JPEG-XL (.jxl) is a modern still format that stock Pillow can't handle.
``pillow-jxl-plugin`` registers a Pillow codec on import, after which the
normal raster load/save paths handle ``.jxl`` transparently.

The dependency is optional; when it is absent ``.jxl`` files simply fail to
load (graceful, per-image) rather than breaking startup. Mirrors
:mod:`Imervue.image.heif_support`.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("Imervue.image.jxl_support")

JXL_EXTENSIONS: frozenset[str] = frozenset({".jxl"})


def is_jxl_path(path: str) -> bool:
    """Return True when ``path`` has a JPEG-XL extension."""
    return Path(path).suffix.lower() in JXL_EXTENSIONS


@lru_cache(maxsize=1)
def ensure_jxl_opener() -> bool:
    """Register the pillow-jxl codec once; return its availability.

    Importing ``pillow_jxl`` registers the JXL open/save handlers as a side
    effect. Memoised, and returns ``False`` (cached) when the plugin is absent.
    """
    try:
        import pillow_jxl  # noqa: F401  (import registers the JXL codec)
    except ImportError:
        logger.info("pillow-jxl-plugin not installed — JPEG-XL files cannot be decoded.")
        return False
    return True
