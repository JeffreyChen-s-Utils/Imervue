"""Pure-numpy manga panel layout helpers.

Manga pages divide the canvas into rectangular panels separated by
gutters. This module computes the panel rects for both regular
``rows × cols`` grids and irregular row-spec layouts (e.g.
``[1, 2, 1]`` for a one-tall / two-cells / one-tall page), plus a
helper that draws the panel borders into an HxWx4 RGBA canvas.

Workflow: build a :class:`PanelLayout` via :func:`panel_grid` or
:func:`panel_rows` (or hand-construct one for fully bespoke pages),
then either:

* read the inner rects via ``layout.cells`` to decide where art goes,
* call :func:`draw_panel_borders` to stamp the gutters into a canvas.

Pure numpy / dataclass; Qt-free so the helpers can run without a
display server in unit tests.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PanelCell:
    """One panel rectangle in image coordinates (top-left origin)."""

    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class PanelLayout:
    """Result of a panel layout computation.

    ``cells`` are returned in reading order — left-to-right within a
    row, top-to-bottom across rows. Manga readers in Japan flow
    right-to-left; the UI layer can reverse cells per-row to honour
    that without changing the layout algebra here.
    """

    width: int
    height: int
    cells: tuple[PanelCell, ...]
    gutter: int
    border_width: int


def panel_grid(
    width: int,
    height: int,
    rows: int,
    cols: int,
    *,
    gutter: int = 16,
    border_width: int = 4,
    margin: int = 0,
) -> PanelLayout:
    """Compute a regular ``rows × cols`` panel layout.

    The page is divided into ``rows × cols`` equal-sized cells
    separated by gutters of ``gutter`` pixels. ``margin`` adds a
    uniform outer padding around the whole grid. ``border_width`` is
    carried through to the layout so a later
    :func:`draw_panel_borders` call knows how thick to stamp.
    """
    _validate_inputs(width, height, gutter, border_width, margin)
    if rows <= 0 or cols <= 0:
        raise ValueError(f"rows/cols must be positive, got {rows}x{cols}")
    inner_w = width - 2 * margin
    inner_h = height - 2 * margin
    if inner_w <= 0 or inner_h <= 0:
        raise ValueError(
            f"image too small for margin={margin}: "
            f"inner area {inner_w}x{inner_h}",
        )
    cell_w = (inner_w - (cols - 1) * gutter) / cols
    cell_h = (inner_h - (rows - 1) * gutter) / rows
    if cell_w <= 0 or cell_h <= 0:
        raise ValueError(
            f"gutter={gutter} / margin={margin} too large for {width}x{height}",
        )
    cells: list[PanelCell] = []
    for r in range(rows):
        for c in range(cols):
            cells.append(_cell(margin, c, r, cell_w, cell_h, gutter))
    return PanelLayout(
        width=width, height=height, cells=tuple(cells),
        gutter=gutter, border_width=border_width,
    )


def panel_rows(
    width: int,
    height: int,
    row_specs: Sequence[int],
    *,
    gutter: int = 16,
    border_width: int = 4,
    margin: int = 0,
) -> PanelLayout:
    """Compute an irregular layout — N rows, each with the cell count
    given by ``row_specs``.

    Row heights are equal; cell widths within a row are equal too.
    A typical 4-koma layout is ``[1, 1, 1, 1]``; a variable manga
    page might use ``[1, 2, 1]`` to mix a wide establishing shot
    with a busier middle row.
    """
    _validate_inputs(width, height, gutter, border_width, margin)
    if not row_specs:
        raise ValueError("row_specs must list at least one row")
    if any(c <= 0 for c in row_specs):
        raise ValueError(f"every row must have >=1 cells, got {list(row_specs)}")
    rows = len(row_specs)
    inner_w = width - 2 * margin
    inner_h = height - 2 * margin
    if inner_w <= 0 or inner_h <= 0:
        raise ValueError(
            f"image too small for margin={margin}: "
            f"inner area {inner_w}x{inner_h}",
        )
    cell_h = (inner_h - (rows - 1) * gutter) / rows
    if cell_h <= 0:
        raise ValueError(
            f"gutter={gutter} too large vertically for {height}px / {rows} rows",
        )
    cells: list[PanelCell] = []
    for r, cols in enumerate(row_specs):
        cell_w = (inner_w - (cols - 1) * gutter) / cols
        if cell_w <= 0:
            raise ValueError(
                f"gutter={gutter} too large for row {r} with {cols} cells",
            )
        for c in range(cols):
            cells.append(_cell(margin, c, r, cell_w, cell_h, gutter))
    return PanelLayout(
        width=width, height=height, cells=tuple(cells),
        gutter=gutter, border_width=border_width,
    )


def draw_panel_borders(
    canvas: np.ndarray,
    layout: PanelLayout,
    *,
    color: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Draw a frame around every panel cell, in-place.

    The frame has thickness ``layout.border_width`` and is drawn just
    *inside* each cell's rectangle so the gutter between cells stays
    untouched. The border alpha is fully opaque.
    """
    _check_canvas(canvas)
    border_width = layout.border_width
    if border_width <= 0:
        return
    h, w = canvas.shape[:2]
    fill = (color[0], color[1], color[2], 255)
    for cell in layout.cells:
        x0 = max(0, cell.x)
        y0 = max(0, cell.y)
        x1 = min(w, cell.x + cell.w)
        y1 = min(h, cell.y + cell.h)
        if x1 <= x0 or y1 <= y0:
            continue
        # Top / bottom horizontal strips, then left / right vertical
        # strips. Min() in the slice ends defends against a cell that
        # is thinner than ``border_width`` (no double-write at the
        # border crossover).
        canvas[y0:min(y0 + border_width, y1), x0:x1] = fill
        canvas[max(y1 - border_width, y0):y1, x0:x1] = fill
        canvas[y0:y1, x0:min(x0 + border_width, x1)] = fill
        canvas[y0:y1, max(x1 - border_width, x0):x1] = fill


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_inputs(
    width: int, height: int, gutter: int, border_width: int, margin: int,
) -> None:
    if width <= 0 or height <= 0:
        raise ValueError(f"page size must be positive, got {width}x{height}")
    if gutter < 0 or border_width < 0 or margin < 0:
        raise ValueError(
            f"gutter / border_width / margin must be >=0, got "
            f"{gutter}/{border_width}/{margin}",
        )


def _cell(
    margin: int, col: int, row: int, cell_w: float, cell_h: float, gutter: int,
) -> PanelCell:
    x = int(round(margin + col * (cell_w + gutter)))
    y = int(round(margin + row * (cell_h + gutter)))
    return PanelCell(x=x, y=y, w=int(round(cell_w)), h=int(round(cell_h)))


def _check_canvas(canvas: np.ndarray) -> None:
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
