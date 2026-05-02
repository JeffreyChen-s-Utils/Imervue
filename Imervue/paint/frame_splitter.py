"""Interactive frame-splitter for the manga panel layout.

The manga_panels module produced regular grids and irregular row
layouts. Real comic pages, though, are built progressively — the
artist starts with a single panel and cuts it down into smaller ones
as the action demands. This module exposes the cut operation:

* :func:`split_panel` — given a single :class:`PanelCell`, an axis
  and a split position, return the two sub-panels.
* :func:`split_layout` — apply a split to a specific cell of a
  :class:`PanelLayout` and return a fresh layout with the split
  baked in.
* :func:`find_cell_at` — given a canvas-space ``(x, y)`` point,
  identify which cell of a layout contains it (used by the UI to
  resolve "the user clicked here, which panel is that?").

Pure math; Qt-free. Splits inherit the layout's gutter so the new
sub-panels are spaced consistently with the rest of the page.
"""
from __future__ import annotations

from Imervue.paint.manga_panels import PanelCell, PanelLayout

SPLIT_AXES = ("horizontal", "vertical")


def split_panel(
    cell: PanelCell,
    *,
    axis: str,
    split_at: int,
    gutter: int = 0,
) -> tuple[PanelCell, PanelCell]:
    """Split ``cell`` into two sub-panels.

    * ``axis="horizontal"`` — split with a horizontal cut at
      ``split_at`` (a y-coordinate in canvas space). Returns
      ``(top, bottom)``.
    * ``axis="vertical"`` — split with a vertical cut at ``split_at``
      (an x-coordinate). Returns ``(left, right)``.

    ``split_at`` must lie strictly inside the cell — at least 1 px
    away from each edge — otherwise one of the sub-panels would be
    empty. ``gutter`` is the number of empty pixels between the two
    sub-panels (each side gives up gutter/2 per the row-spec
    convention used in :func:`Imervue.paint.manga_panels.panel_grid`,
    so a gutter of 8 yields a 4-px gap on each side of the cut line).
    """
    if axis not in SPLIT_AXES:
        raise ValueError(
            f"unknown split axis {axis!r}; expected one of {SPLIT_AXES}",
        )
    if gutter < 0:
        raise ValueError(f"gutter must be >= 0, got {gutter}")

    if axis == "horizontal":
        return _split_horizontal(cell, split_at, gutter)
    return _split_vertical(cell, split_at, gutter)


def _split_horizontal(
    cell: PanelCell, split_at: int, gutter: int,
) -> tuple[PanelCell, PanelCell]:
    half = gutter // 2
    other_half = gutter - half
    top_h = int(split_at) - cell.y - half
    bottom_y = int(split_at) + other_half
    bottom_h = (cell.y + cell.h) - bottom_y
    if top_h <= 0 or bottom_h <= 0:
        raise ValueError(
            f"horizontal split at y={split_at} with gutter={gutter} "
            f"produces zero-height sub-panel inside cell {cell!r}",
        )
    top = PanelCell(x=cell.x, y=cell.y, w=cell.w, h=top_h)
    bottom = PanelCell(x=cell.x, y=bottom_y, w=cell.w, h=bottom_h)
    return top, bottom


def _split_vertical(
    cell: PanelCell, split_at: int, gutter: int,
) -> tuple[PanelCell, PanelCell]:
    half = gutter // 2
    other_half = gutter - half
    left_w = int(split_at) - cell.x - half
    right_x = int(split_at) + other_half
    right_w = (cell.x + cell.w) - right_x
    if left_w <= 0 or right_w <= 0:
        raise ValueError(
            f"vertical split at x={split_at} with gutter={gutter} "
            f"produces zero-width sub-panel inside cell {cell!r}",
        )
    left = PanelCell(x=cell.x, y=cell.y, w=left_w, h=cell.h)
    right = PanelCell(x=right_x, y=cell.y, w=right_w, h=cell.h)
    return left, right


def split_layout(
    layout: PanelLayout,
    cell_index: int,
    *,
    axis: str,
    split_at: int,
    gutter: int | None = None,
) -> PanelLayout:
    """Return a new layout with the cell at ``cell_index`` split.

    If ``gutter`` is None the layout's own ``gutter`` value is used
    so the new sub-panels are spaced consistently with the rest of
    the page. The returned layout's ``gutter`` and ``border_width``
    are preserved.
    """
    if not 0 <= cell_index < len(layout.cells):
        raise IndexError(
            f"cell_index {cell_index} out of range for layout with "
            f"{len(layout.cells)} cells",
        )
    g = layout.gutter if gutter is None else int(gutter)
    target = layout.cells[cell_index]
    a, b = split_panel(target, axis=axis, split_at=split_at, gutter=g)
    new_cells = list(layout.cells)
    new_cells[cell_index:cell_index + 1] = [a, b]
    return PanelLayout(
        width=layout.width,
        height=layout.height,
        cells=tuple(new_cells),
        gutter=layout.gutter,
        border_width=layout.border_width,
    )


def find_cell_at(layout: PanelLayout, x: int, y: int) -> int | None:
    """Return the index of the cell containing ``(x, y)``, or ``None``
    if the point falls in a gutter / outside the layout."""
    for i, cell in enumerate(layout.cells):
        if cell.x <= x < cell.x + cell.w and cell.y <= y < cell.y + cell.h:
            return i
    return None
