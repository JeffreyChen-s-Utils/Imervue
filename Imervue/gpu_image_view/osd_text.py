"""Text the viewer's OSD and Debug HUD show — pure string formatting.

The overlay painter draws these lines; building them needs no Qt and no GL
context, so they live here and are unit-tested directly (project pattern: pure
logic next to the Qt shell, see ``architecture_explore.md`` §10).
"""
from __future__ import annotations

import os
from pathlib import Path

_BYTES_PER_KB = 1024
_BYTES_PER_MB = 1024 * 1024


def human_file_size(path: str) -> str:
    """Return a human-readable size for ``path``, or "—" when unavailable."""
    try:
        size_bytes = os.path.getsize(path)
    except OSError:
        return "—"
    if size_bytes >= _BYTES_PER_MB:
        return f"{size_bytes / _BYTES_PER_MB:.2f} MB"
    return f"{size_bytes / _BYTES_PER_KB:.1f} KB"


def favorites_set(favorites) -> set:
    """Coerce a stored favorites value (set/list/None) into a set."""
    if isinstance(favorites, set):
        return favorites
    try:
        return set(favorites)
    except TypeError:
        return set()


def osd_lines(path: str, width: int, height: int) -> list[str]:
    """Build the three OSD text lines for ``path`` at ``width`` x ``height``."""
    suffix = Path(path).suffix.lstrip(".").upper() or "—"
    return [
        Path(path).name,
        f"{width} × {height}",
        f"{suffix}   {human_file_size(path)}",
    ]


def debug_hud_lines(stats: dict) -> list[str]:
    """Build the Debug-HUD text lines from a stats dict.

    Keys: vram_usage, vram_limit, tile_tex, tile_cache, prefetch,
    prefetch_workers, active_threads, max_threads, generation, zoom.
    """
    vram_mb = stats["vram_usage"] / _BYTES_PER_MB
    limit_mb = stats["vram_limit"] / _BYTES_PER_MB
    pct = (stats["vram_usage"] / stats["vram_limit"] * 100) if stats["vram_limit"] else 0
    return [
        f"VRAM  {vram_mb:6.1f} / {limit_mb:6.1f} MB  ({pct:4.1f}%)",
        f"Tile tex   {stats['tile_tex']:4d}   cache {stats['tile_cache']:4d}",
        f"Prefetch   {stats['prefetch']:4d}   workers {stats['prefetch_workers']}",
        f"Threads    {stats['active_threads']:4d} / {stats['max_threads']}",
        f"Gen {stats['generation']}   Zoom {stats['zoom'] * 100:.1f}%",
    ]


def _exif_to_float(value) -> float | None:
    """Coerce an EXIF value (IFDRational / (num, den) / number) to a float."""
    if value is None:
        return None
    try:
        if isinstance(value, tuple | list) and len(value) == 2:
            num, den = value
            return num / den if den else None
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _format_exposure(value) -> str | None:
    seconds = _exif_to_float(value)
    if seconds is None or seconds <= 0:
        return None
    if seconds >= 1:  # NOSONAR S2583 - FP: _exif_to_float can return (0, 1), e.g. 1/200s
        return f"{seconds:g}s"
    return f"1/{round(1 / seconds)}s"


def _format_iso(value) -> str | None:
    if isinstance(value, tuple | list) and value:
        value = value[0]
    try:
        return f"ISO {int(value)}"
    except (TypeError, ValueError):
        return None


def format_exif_osd_lines(exif: dict) -> list[str]:
    """Build compact OSD lines (exposure / f-number / ISO / focal + lens).

    Returns an empty list when no shooting data is present, so non-photo images
    leave the OSD unchanged. Each field is skipped individually when missing or
    malformed, so partial EXIF still yields a useful line.
    """
    if not exif:
        return []
    fnumber = _exif_to_float(exif.get("FNumber"))
    focal = _exif_to_float(exif.get("FocalLength"))
    fields = [
        _format_exposure(exif.get("ExposureTime")),
        f"f/{fnumber:g}" if fnumber and fnumber > 0 else None,
        _format_iso(exif.get("ISOSpeedRatings")),
        f"{round(focal)}mm" if focal and focal > 0 else None,
    ]
    primary = [field for field in fields if field]
    lines = ["   ".join(primary)] if primary else []
    lens = exif.get("LensModel")
    if lens and str(lens).strip():
        lines.append(str(lens).strip())
    return lines
