"""Command line of the frozen-build ``_runner.py``.

Reads the positional argv the subprocess workers build (see the usage in
``_runner``'s module docstring): the required fields, then the optional ones
with their defaults, in argv order, so a malformed number raises before any
detector loads. Also puts the external Python's site-packages on
``sys.path``. Loaded as a sibling file by the external Python; keep it free of
Qt, Imervue and third-party imports.
"""
from __future__ import annotations

import sys
from typing import NamedTuple

if __package__:   # imported as part of the plugin package (tests)
    from safety_review._constants import MIN_CONFIDENCE, SHAPE_RECT, STYLE_MOSAIC
else:             # run as a script next to its siblings
    from _constants import MIN_CONFIDENCE, SHAPE_RECT, STYLE_MOSAIC


class _SingleOptions(NamedTuple):
    """Single mode's argv: ``<input> <output> <block_size> <padding> [...]``."""
    input_path: str
    output_path: str
    block_size: int
    padding: int
    det_mode: str
    confidence: float
    expand_pct: int
    style: str
    categories: frozenset[str] | None
    shape: str


class _BatchOptions(NamedTuple):
    """Batch mode's argv: ``<json_paths> <output_dir> <block_size> <padding> <overwrite> [...]``."""
    json_paths: str
    output_dir: str
    block_size: int
    padding: int
    overwrite: bool
    det_mode: str
    confidence: float
    expand_pct: int
    style: str
    categories: frozenset[str] | None
    source_root: str
    only_censored: bool
    shape: str
    failed_dir: str
    scan_root: str
    merge_regions: bool


def _parse_categories(cats_str):
    """Parse comma-separated categories string → frozenset or None."""
    if not cats_str:
        return None
    return frozenset(c.strip() for c in cats_str.split(",") if c.strip())


def _bootstrap_site_packages(site_packages: str) -> None:
    if site_packages and site_packages not in sys.path:
        sys.path.insert(0, site_packages)


def _single_options(args) -> _SingleOptions:
    """Read single mode's fields from *args* (``args[2:]``; length checked by the caller)."""
    input_path, output_path = args[2], args[3]
    block_size, padding = int(args[4]), int(args[5])
    det_mode = args[6] if len(args) > 6 else "real"
    confidence = float(args[7]) if len(args) > 7 else MIN_CONFIDENCE
    expand_pct = int(args[8]) if len(args) > 8 else 0
    style = args[9] if len(args) > 9 else STYLE_MOSAIC
    categories = _parse_categories(args[10]) if len(args) > 10 else None
    shape = args[11] if len(args) > 11 else SHAPE_RECT
    return _SingleOptions(
        input_path=input_path, output_path=output_path,
        block_size=block_size, padding=padding, det_mode=det_mode,
        confidence=confidence, expand_pct=expand_pct, style=style,
        categories=categories, shape=shape)


def _batch_options(args) -> _BatchOptions:
    """Read batch mode's fields from *args* (``args[2:]``; length checked by the caller)."""
    json_paths, output_dir = args[2], args[3]
    block_size, padding = int(args[4]), int(args[5])
    overwrite = args[6].lower() == "true"
    det_mode = args[7] if len(args) > 7 else "real"
    confidence = float(args[8]) if len(args) > 8 else MIN_CONFIDENCE
    expand_pct = int(args[9]) if len(args) > 9 else 0
    style = args[10] if len(args) > 10 else STYLE_MOSAIC
    categories = _parse_categories(args[11]) if len(args) > 11 else None
    source_root = args[12] if len(args) > 12 else ""
    only_censored = args[13].lower() == "true" if len(args) > 13 else False
    shape = args[14] if len(args) > 14 else SHAPE_RECT
    failed_dir = args[15] if len(args) > 15 else ""
    scan_root = args[16] if len(args) > 16 else ""
    merge_regions = args[17].lower() != "false" if len(args) > 17 else True
    return _BatchOptions(
        json_paths=json_paths, output_dir=output_dir, block_size=block_size,
        padding=padding, overwrite=overwrite, det_mode=det_mode,
        confidence=confidence, expand_pct=expand_pct, style=style,
        categories=categories, source_root=source_root,
        only_censored=only_censored, shape=shape, failed_dir=failed_dir,
        scan_root=scan_root, merge_regions=merge_regions)
