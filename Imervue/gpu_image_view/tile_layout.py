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
