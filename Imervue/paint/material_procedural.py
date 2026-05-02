"""Procedural material generators — pure-numpy tile factories.

MediBang ships hundreds of bundled tones / textures / patterns; the
shipping size is one of its biggest selling points. Imervue takes
the opposite tack: every built-in material is generated on demand
from a tiny pure-numpy function, so the library is "alive" out of
the box without us shipping a single binary asset.

Each generator returns an ``HxWx4`` ``uint8`` RGBA tile. Tiles are
designed to be seamlessly tileable so the consumer can ``np.tile``
them across an arbitrary canvas without seams.
"""
from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

DEFAULT_TILE_SIZE = 128


# ---------------------------------------------------------------------------
# Halftone tones
# ---------------------------------------------------------------------------


def dot_tone(
    *,
    size: int = DEFAULT_TILE_SIZE,
    cell: int = 8,
    coverage: float = 0.35,
) -> np.ndarray:
    """Regular halftone dot grid — the classic manga screentone.

    ``cell`` is the on-grid spacing in pixels; ``coverage`` is the
    fraction of each cell filled by the dot (0..1). Returned tile is
    seamless along both axes because the dot pattern is grid-aligned
    and ``size`` is divided evenly into ``cell``-sized cells (the
    generator pads ``size`` up to the next multiple of ``cell``).
    """
    if size <= 0 or cell <= 0:
        raise ValueError(
            f"size and cell must be positive, got size={size} cell={cell}",
        )
    coverage = max(0.0, min(1.0, float(coverage)))
    # Round size up to a multiple of cell so the tile is exactly seamless.
    rounded = ((size + cell - 1) // cell) * cell
    tile = np.zeros((rounded, rounded, 4), dtype=np.uint8)
    radius = (cell * math.sqrt(coverage)) / 2.0
    yy, xx = np.indices((rounded, rounded))
    dx = (xx % cell) - cell / 2.0 + 0.5
    dy = (yy % cell) - cell / 2.0 + 0.5
    inside = (dx * dx + dy * dy) <= (radius * radius)
    tile[inside] = (0, 0, 0, 255)
    return tile[:size, :size]


def line_tone(
    *,
    size: int = DEFAULT_TILE_SIZE,
    spacing: int = 6,
    angle_deg: float = 45.0,
    thickness: int = 2,
) -> np.ndarray:
    """Parallel line halftone — thin opaque lines on a transparent ground.

    ``angle_deg`` rotates the lines clockwise; 0° = horizontal, 90° =
    vertical, 45° = the canonical "diagonal stripe" tone.
    """
    if size <= 0 or spacing <= 0 or thickness <= 0:
        raise ValueError(
            f"size, spacing, thickness must be positive; got {size},"
            f" {spacing}, {thickness}",
        )
    tile = np.zeros((size, size, 4), dtype=np.uint8)
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    yy, xx = np.indices((size, size)).astype(np.float32)
    # Distance perpendicular to the line direction.
    perp = xx * sin_a - yy * cos_a
    on_line = (np.mod(perp, spacing) < thickness)
    tile[on_line] = (0, 0, 0, 255)
    return tile


def gradient_tone(
    *,
    size: int = DEFAULT_TILE_SIZE,
    direction: str = "vertical",
) -> np.ndarray:
    """Smooth alpha gradient — top→bottom or left→right fade.

    Produces a black tile whose alpha rises linearly from 0 to 255 in
    the requested direction. Useful as a fade-to-black layer mask
    primitive, or a quick "dusk" overlay.
    """
    if direction not in ("vertical", "horizontal"):
        raise ValueError(
            f"direction must be 'vertical' or 'horizontal', got {direction!r}",
        )
    tile = np.zeros((size, size, 4), dtype=np.uint8)
    ramp = np.linspace(0, 255, size, dtype=np.uint8)
    if direction == "vertical":
        alpha = np.repeat(ramp[:, None], size, axis=1)
    else:
        alpha = np.repeat(ramp[None, :], size, axis=0)
    tile[..., 3] = alpha
    return tile


# ---------------------------------------------------------------------------
# Surface textures
# ---------------------------------------------------------------------------


def paper_noise(
    *,
    size: int = DEFAULT_TILE_SIZE,
    intensity: float = 0.12,
    seed: int = 0,
) -> np.ndarray:
    """Subtle paper-fibre noise — high-frequency luminance jitter.

    The tile is grey-on-grey by default so it can be multiply-blended
    over a coloured layer to fake a paper substrate without recolouring
    it. ``intensity`` is the standard deviation of the noise (0..1);
    keep it small (0.05–0.20) for a believable look.
    """
    intensity = max(0.0, min(1.0, float(intensity)))
    rng = np.random.default_rng(int(seed))
    base = 220
    noise = rng.normal(loc=0.0, scale=intensity * 60.0, size=(size, size))
    grey = np.clip(base + noise, 0, 255).astype(np.uint8)
    tile = np.zeros((size, size, 4), dtype=np.uint8)
    tile[..., 0] = grey
    tile[..., 1] = grey
    tile[..., 2] = grey
    tile[..., 3] = 255
    return tile


def checker_pattern(
    *,
    size: int = DEFAULT_TILE_SIZE,
    cell: int = 16,
) -> np.ndarray:
    """Two-tone checkerboard — handy as a transparency reference grid."""
    if cell <= 0:
        raise ValueError(f"cell must be positive, got {cell}")
    yy, xx = np.indices((size, size))
    is_dark = ((xx // cell) + (yy // cell)) % 2 == 0
    tile = np.full((size, size, 4), 255, dtype=np.uint8)
    tile[is_dark] = (200, 200, 200, 255)
    return tile


# ---------------------------------------------------------------------------
# Catalog — every built-in procedural material registered here gets
# surfaced in the MaterialDock. The default index reads this list.
# ---------------------------------------------------------------------------


def _wrap(generator: Callable, **kwargs) -> Callable[[], np.ndarray]:
    """Return a thunk that calls ``generator`` with the bound kwargs."""
    return lambda: generator(**kwargs)


# Each entry: (name, category, tags, provider, preview_size).
# Preview size is what the dock thumbnail renders; the consumer picks
# its own size when it actually tiles the material onto the canvas.
DEFAULT_PROCEDURAL_CATALOG: tuple[
    tuple[str, str, tuple[str, ...], Callable[[], np.ndarray]], ...
] = (
    ("Dot 30%", "tone", ("halftone", "dot", "light"),
     _wrap(dot_tone, cell=10, coverage=0.20)),
    ("Dot 50%", "tone", ("halftone", "dot", "medium"),
     _wrap(dot_tone, cell=8, coverage=0.40)),
    ("Dot 70%", "tone", ("halftone", "dot", "dark"),
     _wrap(dot_tone, cell=8, coverage=0.60)),
    ("Lines 45°", "tone", ("halftone", "line", "diagonal"),
     _wrap(line_tone, angle_deg=45.0)),
    ("Lines 90°", "tone", ("halftone", "line", "vertical"),
     _wrap(line_tone, angle_deg=90.0)),
    ("Gradient", "tone", ("fade", "gradient"),
     _wrap(gradient_tone)),
    ("Paper", "texture", ("paper", "noise", "fibre"),
     _wrap(paper_noise, intensity=0.10, seed=0)),
    ("Coarse paper", "texture", ("paper", "noise", "coarse"),
     _wrap(paper_noise, intensity=0.20, seed=1)),
    ("Checker", "pattern", ("checker", "grid"),
     _wrap(checker_pattern, cell=16)),
)


def tile_to_canvas(
    tile: np.ndarray, target_shape: tuple[int, int],
) -> np.ndarray:
    """Repeat ``tile`` to cover ``target_shape`` (h, w) and return RGBA.

    Tiles that already match ``target_shape`` are returned unchanged
    (no copy). Smaller tiles are repeated; the result is cropped to
    the exact target size so a tile that doesn't divide the canvas
    evenly still produces a flush fill.
    """
    if tile.ndim != 3 or tile.shape[2] != 4 or tile.dtype != np.uint8:
        raise ValueError(
            f"tile must be HxWx4 uint8 RGBA, got shape={tile.shape}"
            f" dtype={tile.dtype}",
        )
    h, w = target_shape
    if h <= 0 or w <= 0:
        raise ValueError(f"target_shape must be positive, got {target_shape}")
    th, tw = tile.shape[:2]
    if th == h and tw == w:
        return tile
    reps_y = (h + th - 1) // th
    reps_x = (w + tw - 1) // tw
    tiled = np.tile(tile, (reps_y, reps_x, 1))
    return tiled[:h, :w]
