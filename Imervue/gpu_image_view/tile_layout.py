"""Tile-grid layout helpers for the GPU thumbnail wall.

Pure-Python helpers extracted from ``GPUImageView`` so the layout math and the
thumbnail-size-change decision are unit-testable without a live OpenGL context
or any Qt widget.

* :func:`tile_grid_layout` — turns the widget width, base tile size and the
  current screen's device-pixel-ratio into the ``(draw_scale, cell, cols)``
  triple the renderer needs. Treating the base tile / padding as *physical*
  pixel targets (dividing by ``dpr``) makes a thumbnail occupy the same
  physical size on every monitor regardless of its display scaling.
* :func:`plan_tile_size_change` — decides what should happen when the user
  picks a new thumbnail size from the menu, so the viewer stays in deep zoom
  instead of being kicked back to the grid.
"""
from __future__ import annotations

# Thumbnail sizes offered by the menu. ``None`` (full resolution) is handled
# separately because it is not an integer.
VALID_THUMBNAIL_SIZES = (128, 256, 512, 1024)
DEFAULT_THUMBNAIL_SIZE = 512


def resolve_thumbnail_size(stored, *, default: int = DEFAULT_THUMBNAIL_SIZE):
    """Validate a persisted thumbnail size read from user settings.

    ``None`` means the user picked the full-resolution option and is passed
    through. Anything that isn't a recognised size (corrupt / tampered value)
    falls back to *default* so a bad setting can't break the grid.
    """
    if stored is None:
        return None
    try:
        value = int(stored)
    except (TypeError, ValueError):
        return default
    return value if value in VALID_THUMBNAIL_SIZES else default


def is_active_thumbnail_choice(option, current) -> bool:
    """True if a menu *option* matches the viewer's *current* thumbnail size.

    The menu's full-resolution entry is the string ``"None"`` while the viewer
    stores ``None``; this bridges the two so the active radio item shows a
    checkmark even when full resolution is selected.
    """
    if option == "None":
        return current is None
    return option == current


def tile_grid_layout(
    view_width: float,
    base_tile: float,
    tile_scale: float,
    padding: float,
    dpr: float,
) -> tuple[float, float, int]:
    """Compute ``(draw_scale, cell, cols)`` for the thumbnail grid.

    ``base_tile`` and ``padding`` are treated as physical-pixel targets;
    dividing by ``dpr`` keeps a tile the same physical size on every monitor.
    On a ``dpr == 1`` screen this is a no-op, so the primary-monitor layout is
    unchanged. ``dpr`` values of zero or below are clamped to ``1.0`` so a bad
    probe can't trigger a division-by-zero.
    """
    safe_dpr = dpr if dpr > 0 else 1.0
    draw_scale = tile_scale / safe_dpr
    cell = base_tile * draw_scale + padding / safe_dpr
    cols = max(1, int(view_width // cell)) if cell > 0 else 1
    return draw_scale, cell, cols


def clamp_grid_offset(
    offset_y: float,
    count: int,
    cols: int,
    cell: float,
    tile_extent: float,
    view_height: float,
) -> float:
    """Clamp the thumbnail-wall vertical scroll offset to its content range.

    Tiles sit at ``y = row * cell + offset_y`` (a larger offset pushes the wall
    *down*). Without a bound the wheel / middle-drag scrolls the whole grid off
    into empty space — above the first row or below the last — leaving a blank
    screen with no cue that it over-scrolled. The offset is held in
    ``[view_height - content_height, 0]`` so the first row can't drop below the
    top edge and the last row can't lift above the bottom; a grid shorter than
    the viewport is pinned to the top (offset ``0``). An empty grid clamps to 0.
    """
    if count <= 0:
        return 0.0
    safe_cols = cols if cols > 0 else 1
    last_row = (count - 1) // safe_cols
    content_height = last_row * cell + tile_extent
    min_offset = min(0.0, view_height - content_height)
    return max(min_offset, min(0.0, offset_y))


def plan_tile_size_change(*, in_deep_zoom: bool, has_images: bool) -> str:
    """Decide how to react to a thumbnail-size change.

    Returns one of:

    * ``"none"`` — nothing is loaded, just store the new size.
    * ``"defer"`` — the viewer is in deep zoom; keep it there and rebuild the
      grid lazily when the user exits back to the wall.
    * ``"rebuild"`` — the viewer is on the grid; rebuild it now at the new size.
    """
    if not has_images:
        return "none"
    if in_deep_zoom:
        return "defer"
    return "rebuild"
