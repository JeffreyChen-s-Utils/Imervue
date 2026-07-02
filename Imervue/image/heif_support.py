"""HEIF / AVIF decode support via the optional ``pillow-heif`` backend.

iPhone photos default to HEIC and modern screenshots increasingly use AVIF;
neither is decodable by stock Pillow. ``pillow-heif`` registers a Pillow
opener so the normal raster load path handles both transparently — a single
``register_heif_opener()`` call covers HEIF *and* AVIF in pillow-heif 1.x.

The dependency is optional (it bundles libheif binaries we don't want to force
on every install). When it is absent these files simply fail to load and the
browser shows a one-time install hint, rather than the app refusing to start.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("Imervue.image.heif_support")

HEIF_EXTENSIONS: frozenset[str] = frozenset({".heic", ".heif", ".hif", ".avif"})


def is_heif_path(path: str) -> bool:
    """Return True when ``path`` has a HEIF/AVIF extension."""
    return Path(path).suffix.lower() in HEIF_EXTENSIONS


@lru_cache(maxsize=1)
def _register_heif_opener() -> bool:
    """Import pillow-heif and register its Pillow opener (cached on success).

    Raises ``ImportError`` when the backend is absent. ``lru_cache`` does not
    memoise exceptions, so the failure is *not* cached: a backend installed
    after launch (via the in-app pip installer) is re-probed on the next call
    instead of being stuck at the cached failure until restart.
    """
    import pillow_heif
    pillow_heif.register_heif_opener()
    return True


def ensure_heif_opener() -> bool:
    """Register the pillow-heif opener once; return its availability.

    The successful registration is memoised, but a missing backend returns
    ``False`` without caching so callers degrade gracefully now and self-heal
    if ``pillow-heif`` is installed later in the same session.
    """
    try:
        return _register_heif_opener()
    except ImportError:
        logger.info("pillow-heif not installed — HEIC/AVIF files cannot be decoded.")
        return False


def needs_heif_hint(paths: list[str], opener_available: bool) -> bool:
    """True when a HEIF/AVIF file is present but no decoder is available."""
    if opener_available:
        return False
    return any(is_heif_path(p) for p in paths)
