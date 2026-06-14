"""Keyboard focus-cursor helpers for the GPU thumbnail wall.

Pure-Python helpers extracted from ``GPUImageView`` so the focus-cursor
movement, the scroll-to-reveal math, and the focused-tile rectangle are
unit-testable without a live OpenGL context or any Qt widget. The view owns
the ``focused_tile_index`` state; the keyboard handler calls these to move it
and keep it on screen, and the grid renderer calls :func:`focus_tile_rect` to
locate the highlight.

The wall lays tiles out by a *flat* index that wraps across rows, so Left /
Right step one tile (wrapping at row edges, like a file manager) while Up /
Down move a whole row. A larger ``grid_offset_y`` pushes tiles *down*, matching
the renderer's ``y = row * cell + grid_offset_y`` placement.
"""
from __future__ import annotations

# Sentinel for "no tile is focused yet" — the highlight only appears once the
# user starts keyboard-browsing, so mouse-only users never see a stray ring.
NO_FOCUS = -1

# Arrow directions, kept as plain strings so this module stays Qt-free; the
# key handler maps ``Qt.Key.Key_*`` onto them.
LEFT = "left"
RIGHT = "right"
UP = "up"
DOWN = "down"

_HORIZONTAL = (LEFT, RIGHT)


def _candidate_index(current: int, direction: str, cols: int) -> int:
    """Raw next index for *direction*, before any bounds checking."""
    deltas = {LEFT: -1, RIGHT: 1, UP: -cols, DOWN: cols}
    return current + deltas.get(direction, 0)


def next_focus_index(current: int, direction: str, cols: int, count: int) -> int:
    """Return the focused index after an arrow press.

    *current* is the currently focused index (``NO_FOCUS`` when none). The first
    arrow press while nothing is focused lands on the first tile. Left / right
    step one tile and clamp at the very ends; up / down move a full row and stay
    put when that would leave the grid, so the cursor never wraps off the edge
    or vanishes. A non-positive *cols* is treated as a single column.
    """
    if count <= 0:
        return NO_FOCUS
    safe_cols = cols if cols > 0 else 1
    if current < 0 or current >= count:
        return 0
    candidate = _candidate_index(current, direction, safe_cols)
    if direction in _HORIZONTAL:
        return max(0, min(count - 1, candidate))
    # Vertical: only move when the target row actually has a tile.
    return candidate if 0 <= candidate < count else current


def scroll_offset_to_reveal(
    focus_index: int,
    cols: int,
    cell: float,
    tile_extent: float,
    grid_offset_y: float,
    view_height: float,
) -> float:
    """Return the grid Y offset that brings the focused tile fully on screen.

    Tiles sit at ``y = row * cell + grid_offset_y``. When the focused tile is
    above the top or below the bottom edge, shift the offset just enough to
    reveal it (top-aligning when it would not otherwise fit); otherwise return
    the offset unchanged so a mouse-set scroll position is preserved.
    """
    if focus_index < 0:
        return grid_offset_y
    safe_cols = cols if cols > 0 else 1
    row = focus_index // safe_cols
    tile_top = row * cell + grid_offset_y
    tile_bottom = tile_top + tile_extent
    if tile_top < 0:
        return grid_offset_y - tile_top
    if tile_bottom > view_height:
        return grid_offset_y - (tile_bottom - view_height)
    return grid_offset_y


def focus_tile_rect(
    focus_index: int,
    cols: int,
    cell: float,
    tile_extent: float,
    grid_offset_x: float,
    grid_offset_y: float,
) -> tuple[float, float, float, float] | None:
    """Return ``(x0, y0, x1, y1)`` of the focused tile, or ``None`` if unfocused."""
    if focus_index < 0:
        return None
    safe_cols = cols if cols > 0 else 1
    row, col = divmod(focus_index, safe_cols)
    x0 = col * cell + grid_offset_x
    y0 = row * cell + grid_offset_y
    return x0, y0, x0 + tile_extent, y0 + tile_extent
