"""Priority helpers for DeepZoom tile rendering."""
from __future__ import annotations

from math import hypot


def prioritize_tiles(
    tiles: list[tuple[int, int]],
    *,
    tile_size: int,
    scale_x: float,
    scale_y: float,
    offset_x: float,
    offset_y: float,
    canvas: tuple[int, int],
    cursor: tuple[float, float] | None = None,
) -> list[tuple[int, int]]:
    """Order visible tiles by likely importance.

    The viewport is already clipped before this helper runs. Within that
    visible set, tiles near the screen centre should arrive first; if the mouse
    is over the image, nearby tiles get an extra boost so zoom-after-hover feels
    more responsive.
    """
    if not tiles:
        return []
    cx = canvas[0] / 2
    cy = canvas[1] / 2
    cursor = cursor if cursor is not None else (cx, cy)

    def key(tile: tuple[int, int]) -> tuple[float, float]:
        tx, ty = tile
        sx = offset_x + (tx + 0.5) * tile_size * scale_x
        sy = offset_y + (ty + 0.5) * tile_size * scale_y
        center_distance = hypot(sx - cx, sy - cy)
        cursor_distance = hypot(sx - cursor[0], sy - cursor[1])
        return (center_distance * 0.65 + cursor_distance * 0.35, center_distance)

    return sorted(tiles, key=key)

