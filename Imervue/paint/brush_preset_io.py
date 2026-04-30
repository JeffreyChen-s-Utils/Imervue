"""Import / export for brush presets — portable JSON + foreign formats.

Two file shapes are supported:

* ``.imv-brush`` — Imervue's native, JSON-encoded portable format.
  One file per preset (or one bundle file per group). The schema is
  the same dict :meth:`BrushPreset.from_dict` accepts plus a small
  envelope (``format`` / ``version``) so future format upgrades can
  detect old files cleanly.
* ``.mdp`` — MediBang's brush-preset format. The on-disk layout is
  proprietary and undocumented in detail, but enough fields appear in
  ASCII near the file header to extract the brush name, size, and
  hardness for a useful round-trip. Anything we can't parse falls
  back to a sensible default rather than raising — the user gets a
  best-effort import they can adjust by hand instead of a hard error.

The reader is intentionally schema-tolerant. A library bundle that
ships dozens of presets shouldn't fail to load just because one row
is malformed — the bad row is dropped with a logger warning and the
rest still come through.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from pathlib import Path

from Imervue.paint.brush_presets import BrushPreset
from Imervue.paint.tool_state import BRUSH_SIZE_MAX, BRUSH_SIZE_MIN

logger = logging.getLogger("Imervue.paint.brush_preset_io")

IMERVUE_FORMAT_TAG = "imv-brush"
IMERVUE_FORMAT_VERSION = 1
IMERVUE_BRUSH_EXTENSION = ".imv-brush"
MEDIBANG_BRUSH_EXTENSION = ".mdp"

# Cap so a hostile / corrupted bundle can't blow out RAM via a 100k-
# preset list. 4096 is far above any realistic library size.
MAX_PRESETS_PER_BUNDLE = 4096


# ---------------------------------------------------------------------------
# .imv-brush — single preset
# ---------------------------------------------------------------------------


def export_preset(preset: BrushPreset, path: str | Path) -> Path:
    """Write a single :class:`BrushPreset` to ``path`` as JSON.

    Returns the resolved on-disk path so callers can chain into a
    "show in folder" action without re-stat'ing.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": IMERVUE_FORMAT_TAG,
        "version": IMERVUE_FORMAT_VERSION,
        "preset": preset.to_dict(),
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target.resolve()


def import_preset(path: str | Path) -> BrushPreset:
    """Read a single ``.imv-brush`` file. Raises on malformed input."""
    raw = _read_json(path)
    if raw.get("format") != IMERVUE_FORMAT_TAG:
        raise ValueError(
            f"{path}: not an {IMERVUE_FORMAT_TAG} file "
            f"(format={raw.get('format')!r})",
        )
    body = raw.get("preset")
    if not isinstance(body, dict):
        raise ValueError(f"{path}: missing 'preset' object")
    return BrushPreset.from_dict(body)


# ---------------------------------------------------------------------------
# .imv-brush — bundle
# ---------------------------------------------------------------------------


def export_bundle(presets: Iterable[BrushPreset], path: str | Path) -> Path:
    """Write a list of presets to a single ``.imv-brush`` bundle.

    Bundles use the same envelope as a single preset but the body is
    a ``presets`` list rather than a ``preset`` object. The reader
    auto-detects which shape is on disk so callers don't have to keep
    track.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": IMERVUE_FORMAT_TAG,
        "version": IMERVUE_FORMAT_VERSION,
        "presets": [p.to_dict() for p in presets],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target.resolve()


def import_bundle(path: str | Path) -> list[BrushPreset]:
    """Read a multi-preset bundle, dropping malformed rows silently.

    Single-preset files are accepted too (the result is a one-element
    list) so callers can use this when they don't know the bundle
    shape ahead of time.
    """
    raw = _read_json(path)
    if raw.get("format") != IMERVUE_FORMAT_TAG:
        raise ValueError(
            f"{path}: not an {IMERVUE_FORMAT_TAG} file "
            f"(format={raw.get('format')!r})",
        )
    rows = raw.get("presets")
    if rows is None:
        # Single-preset envelope — wrap into a one-element list.
        body = raw.get("preset")
        if not isinstance(body, dict):
            raise ValueError(f"{path}: missing 'presets' or 'preset'")
        return [BrushPreset.from_dict(body)]
    if not isinstance(rows, list):
        raise ValueError(f"{path}: 'presets' must be a list")
    out: list[BrushPreset] = []
    for index, row in enumerate(rows[:MAX_PRESETS_PER_BUNDLE]):
        if not isinstance(row, dict):
            logger.warning("%s: dropping non-dict preset at index %d", path, index)
            continue
        try:
            out.append(BrushPreset.from_dict(row))
        except (TypeError, ValueError) as exc:
            logger.warning(
                "%s: dropping malformed preset at index %d (%s)",
                path, index, exc,
            )
    return out


# ---------------------------------------------------------------------------
# .mdp — MediBang brush preset (read-only, best-effort)
# ---------------------------------------------------------------------------


# MediBang's format puts ASCII strings near the header for the brush
# name and tag; numeric parameters are sprinkled between length-
# prefixed records. We sniff for a handful of tag tokens and pull the
# associated values out by regex. Anything we can't find is replaced
# with the BrushPreset default so the user always gets *something*.
_MDP_NAME_PATTERN = re.compile(rb"name[\x00- ]+([\x20-\x7E]{1,64})")
_MDP_SIZE_PATTERN = re.compile(rb"size[\x00- ]+(\d{1,4})")
_MDP_HARDNESS_PATTERN = re.compile(rb"hardness[\x00- ]+(\d+(?:\.\d+)?)")
_MDP_OPACITY_PATTERN = re.compile(rb"opacity[\x00- ]+(\d+(?:\.\d+)?)")


def import_medibang_preset(path: str | Path) -> BrushPreset:
    """Best-effort read of a MediBang ``.mdp`` brush preset.

    Returns a :class:`BrushPreset` with whatever fields could be
    recovered. The format isn't fully documented; callers should
    treat this as a "first pass" and adjust the resulting preset
    afterwards.
    """
    blob = Path(path).read_bytes()
    name = _extract_match(_MDP_NAME_PATTERN, blob, fallback=Path(path).stem)
    size_raw = _extract_match(_MDP_SIZE_PATTERN, blob, fallback="12")
    hardness_raw = _extract_match(_MDP_HARDNESS_PATTERN, blob, fallback="0.8")
    opacity_raw = _extract_match(_MDP_OPACITY_PATTERN, blob, fallback="1.0")
    try:
        size = max(BRUSH_SIZE_MIN, min(BRUSH_SIZE_MAX, int(size_raw)))
    except ValueError:
        size = 12
    try:
        hardness = max(0.0, min(1.0, float(hardness_raw)))
    except ValueError:
        hardness = 0.8
    try:
        opacity = max(0.0, min(1.0, float(opacity_raw)))
    except ValueError:
        opacity = 1.0
    return BrushPreset(
        name=name or Path(path).stem,
        size=size,
        hardness=hardness,
        opacity=opacity,
    )


# ---------------------------------------------------------------------------
# Directory loader
# ---------------------------------------------------------------------------


def load_directory(root: str | Path) -> list[BrushPreset]:
    """Scan ``root`` and load every ``.imv-brush`` / ``.mdp`` it finds.

    Subdirectories are walked recursively. Order is filename-sorted
    so the loaded list is reproducible across runs (important for the
    UI tab ordering). Malformed files are skipped with a logger
    warning rather than crashing the whole load.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return []
    out: list[BrushPreset] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        try:
            if path.suffix == IMERVUE_BRUSH_EXTENSION:
                out.extend(import_bundle(path))
            elif path.suffix == MEDIBANG_BRUSH_EXTENSION:
                out.append(import_medibang_preset(path))
        except (OSError, ValueError) as exc:
            logger.warning("skipping %s: %s", path, exc)
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_json(path: str | Path) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be an object")
    return raw


def _extract_match(pattern: re.Pattern[bytes], blob: bytes, *, fallback: str) -> str:
    match = pattern.search(blob)
    if match is None:
        return fallback
    try:
        return match.group(1).decode("ascii", errors="replace").strip()
    except UnicodeDecodeError:
        return fallback
