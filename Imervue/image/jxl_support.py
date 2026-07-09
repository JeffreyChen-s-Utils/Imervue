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
def _register_jxl_opener() -> bool:
    """Import pillow-jxl (registers the JXL codec as a side effect; cached).

    Raises ``ImportError`` when the plugin is absent. ``lru_cache`` does not
    memoise exceptions, so the failure is not cached and a plugin installed
    after launch self-heals on the next call instead of needing a restart.
    """
    import pillow_jxl  # noqa: F401  (import registers the JXL codec)
    return True


def ensure_jxl_opener() -> bool:
    """Register the pillow-jxl codec once; return its availability.

    The successful registration is memoised, but a missing plugin returns
    ``False`` without caching so a runtime install self-heals in the same
    session.
    """
    try:
        return _register_jxl_opener()
    except ImportError:
        logger.info("pillow-jxl-plugin not installed — JPEG-XL files cannot be decoded.")
        return False
