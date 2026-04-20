"""
Adobe ``.cube`` LUT reader and applier.

Supports LUT_1D_SIZE and LUT_3D_SIZE cube files up to 64³ (DaVinci Resolve,
Adobe, Capture One, and most free LUT packs export in this format).
Parsing is tolerant of comments (``# …``), blank lines, and different
newline styles.

Applying a 3D LUT uses trilinear interpolation via NumPy advanced indexing
— fast enough for 4K previews on a laptop (~80 ms for a 1920×1280 image
with a 33³ LUT). Results are cached per path so repeated apply() calls
during a develop session don't re-parse the file.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

logger = logging.getLogger("Imervue.lut")

_MAX_CUBE_SIZE = 64


@dataclass(frozen=True)
class CubeLut:
    """Parsed ``.cube`` LUT in either 1D (N, 3) or 3D (N, N, N, 3) form."""

    size: int
    table: np.ndarray   # float32, values in [0, 1]
    domain_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    domain_max: tuple[float, float, float] = (1.0, 1.0, 1.0)
    is_3d: bool = True


def parse_cube(path: str | Path) -> CubeLut:
    """Parse a ``.cube`` LUT file. Raises ``ValueError`` on bad syntax."""
    p = Path(path)
    size = 0
    is_3d = True
    domain_min = [0.0, 0.0, 0.0]
    domain_max = [1.0, 1.0, 1.0]
    values: list[tuple[float, float, float]] = []
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            upper = line.upper()
            if upper.startswith("TITLE"):
                continue
            if upper.startswith("LUT_3D_SIZE"):
                size = int(line.split()[1])
                is_3d = True
            elif upper.startswith("LUT_1D_SIZE"):
                size = int(line.split()[1])
                is_3d = False
            elif upper.startswith("DOMAIN_MIN"):
                domain_min = [float(x) for x in line.split()[1:4]]
            elif upper.startswith("DOMAIN_MAX"):
                domain_max = [float(x) for x in line.split()[1:4]]
            else:
                parts = line.split()
                if len(parts) != 3:
                    continue
                try:
                    values.append(tuple(float(p) for p in parts))  # type: ignore[misc]
                except ValueError as err:
                    raise ValueError(f"bad LUT row: {line!r}") from err
    if size <= 0:
        raise ValueError("missing LUT_1D_SIZE / LUT_3D_SIZE header")
    if size > _MAX_CUBE_SIZE:
        raise ValueError(f"LUT size {size} exceeds maximum {_MAX_CUBE_SIZE}")
    expected = size ** 3 if is_3d else size
    if len(values) != expected:
        raise ValueError(
            f"expected {expected} rows, got {len(values)} (size={size}, 3D={is_3d})"
        )
    arr = np.asarray(values, dtype=np.float32)
    table = arr.reshape((size, size, size, 3)) if is_3d else arr.reshape((size, 3))
    return CubeLut(
        size=size,
        table=table,
        domain_min=tuple(domain_min),  # type: ignore[arg-type]
        domain_max=tuple(domain_max),  # type: ignore[arg-type]
        is_3d=is_3d,
    )


@lru_cache(maxsize=8)
def _load_cached(path: str, mtime_ns: int) -> CubeLut:
    return parse_cube(path)


def _load_with_mtime_cache(path: str) -> CubeLut:
    try:
        mtime_ns = Path(path).stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    return _load_cached(path, mtime_ns)


def _apply_3d(arr: np.ndarray, lut: CubeLut) -> np.ndarray:
    """Trilinear interpolation of RGB values through a 3D LUT."""
    rgb = arr[..., :3].astype(np.float32) / 255.0
    dmin = np.array(lut.domain_min, dtype=np.float32)
    dmax = np.array(lut.domain_max, dtype=np.float32)
    span = np.maximum(dmax - dmin, 1e-6)
    rgb = np.clip((rgb - dmin) / span, 0.0, 1.0)
    n = lut.size - 1
    scaled = rgb * n
    idx_lo = np.floor(scaled).astype(np.int32)
    idx_hi = np.minimum(idx_lo + 1, n)
    frac = scaled - idx_lo

    r0, g0, b0 = idx_lo[..., 0], idx_lo[..., 1], idx_lo[..., 2]
    r1, g1, b1 = idx_hi[..., 0], idx_hi[..., 1], idx_hi[..., 2]
    fr, fg, fb = frac[..., 0:1], frac[..., 1:2], frac[..., 2:3]

    # .cube files store rows with R varying fastest, then G, then B. After
    # reshape((size, size, size, 3)) in default C-order the axes are
    # (B, G, R, rgb), so we index as table[b, g, r].
    c000 = lut.table[b0, g0, r0]
    c100 = lut.table[b0, g0, r1]
    c010 = lut.table[b0, g1, r0]
    c110 = lut.table[b0, g1, r1]
    c001 = lut.table[b1, g0, r0]
    c101 = lut.table[b1, g0, r1]
    c011 = lut.table[b1, g1, r0]
    c111 = lut.table[b1, g1, r1]

    c00 = c000 * (1 - fr) + c100 * fr
    c10 = c010 * (1 - fr) + c110 * fr
    c01 = c001 * (1 - fr) + c101 * fr
    c11 = c011 * (1 - fr) + c111 * fr
    c0 = c00 * (1 - fg) + c10 * fg
    c1 = c01 * (1 - fg) + c11 * fg
    result = c0 * (1 - fb) + c1 * fb
    return np.clip(result, 0.0, 1.0)


def _apply_1d(arr: np.ndarray, lut: CubeLut) -> np.ndarray:
    """Per-channel 1D LUT via linear interpolation."""
    rgb = arr[..., :3].astype(np.float32) / 255.0
    out = np.empty_like(rgb)
    n = lut.size - 1
    xs = np.linspace(0.0, 1.0, lut.size)
    for c in range(3):
        out[..., c] = np.interp(rgb[..., c], xs, lut.table[:, c])
    _ = n  # keep lint happy; size encoded in xs
    return np.clip(out, 0.0, 1.0)


def apply_cube_lut(
    arr: np.ndarray, path: str | Path, intensity: float = 1.0,
) -> np.ndarray:
    """Apply a ``.cube`` LUT to an HxWx4 RGBA uint8 image.

    ``intensity`` blends between the original (0.0) and the fully-applied
    LUT (1.0). The alpha channel is left untouched.
    """
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("apply_cube_lut expects HxWx4 RGBA uint8")
    intensity = float(max(0.0, min(1.0, intensity)))
    if intensity <= 0.0 or math.isclose(intensity, 0.0):
        return arr
    lut = _load_with_mtime_cache(str(path))
    applied = _apply_3d(arr, lut) if lut.is_3d else _apply_1d(arr, lut)
    original = arr[..., :3].astype(np.float32) / 255.0
    blended = original * (1.0 - intensity) + applied * intensity
    np.clip(blended, 0.0, 1.0, out=blended)
    out = arr.copy()
    out[..., :3] = (blended * 255.0 + 0.5).astype(np.uint8)
    return out


def clear_cache() -> None:
    """Drop the in-process parsed-LUT cache. Used by tests."""
    _load_cached.cache_clear()
