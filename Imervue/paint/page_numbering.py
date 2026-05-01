"""Auto page-number stamper for multi-page projects.

MediBang's "Comic Project" workflow lets the artist drop a page-
number stamp onto every page in one shot. This module is the pure
logic: take a :class:`PaintProject`, render the page index into a
small text layer at the requested corner of each page, and add that
layer to the page's document. Pure-Python / Pillow — Qt-free so the
verb runs in tests without a display server.

Numbering options:

* ``start_at`` — first page's printed number (default ``1``). Useful
  when binding multiple chapters or the cover sits as page 0.
* ``corner`` — one of :data:`PAGE_NUMBER_CORNERS`; selects which of
  the four corners receives the stamp.
* ``font_size`` / ``color`` — passed straight to the text renderer.
* ``margin`` — distance from the chosen corner in pixels.
* ``layer_name`` — the name added to the page's layer stack so the
  artist can find / hide / delete the stamps later.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.paint_project import PaintProject

PAGE_NUMBER_CORNERS = (
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
)
DEFAULT_PAGE_NUMBER_CORNER = "bottom_right"
DEFAULT_PAGE_NUMBER_LAYER = "Page Number"
DEFAULT_PAGE_NUMBER_MARGIN = 24
DEFAULT_PAGE_NUMBER_SIZE = 28


def stamp_page_numbers(
    project: PaintProject,
    *,
    start_at: int = 1,
    corner: str = DEFAULT_PAGE_NUMBER_CORNER,
    font_size: int = DEFAULT_PAGE_NUMBER_SIZE,
    color: tuple[int, int, int, int] = (0, 0, 0, 255),
    margin: int = DEFAULT_PAGE_NUMBER_MARGIN,
    layer_name: str = DEFAULT_PAGE_NUMBER_LAYER,
) -> int:
    """Add a page-number layer to every page in ``project``.

    Returns the number of pages stamped. Ignores empty pages (no
    shape) — they get skipped silently rather than raising, so a
    half-built project survives the verb.
    """
    if corner not in PAGE_NUMBER_CORNERS:
        raise ValueError(
            f"unknown corner {corner!r}; expected one of {PAGE_NUMBER_CORNERS}",
        )
    if int(margin) < 0:
        raise ValueError(f"margin must be >= 0, got {margin}")
    if int(font_size) < 1:
        raise ValueError(f"font_size must be >= 1, got {font_size}")
    if not str(layer_name).strip():
        raise ValueError("layer_name must be non-empty")

    stamped = 0
    for index, page in enumerate(project.pages):
        document = page.document
        shape = document.shape
        if shape is None:
            continue
        h, w = shape
        text = str(int(start_at) + index)
        stamp_layer = _render_page_number_layer(
            (h, w),
            text=text,
            corner=corner,
            font_size=font_size,
            color=color,
            margin=margin,
        )
        layer = document.add_layer(name=layer_name)
        np.copyto(layer.image, stamp_layer)
        document.invalidate_composite()
        stamped += 1
    return stamped


def _render_page_number_layer(
    canvas_shape: tuple[int, int],
    *,
    text: str,
    corner: str,
    font_size: int,
    color: tuple[int, int, int, int],
    margin: int,
) -> np.ndarray:
    """Build a fresh canvas-sized RGBA buffer with the number stamped.

    The text is rendered through :mod:`Imervue.paint.text_render` so
    the stamp inherits whatever font fallback that module uses; the
    rendered glyph buffer is then pasted at the requested corner with
    the documented margin.
    """
    from Imervue.paint.text_render import TextRenderOptions, render_text

    h_canvas, w_canvas = canvas_shape
    rgb_color = tuple(int(c) for c in color[:3])
    glyphs = render_text(TextRenderOptions(
        text=text,
        size=int(font_size),
        color=rgb_color,  # type: ignore[arg-type]
    ))
    if glyphs.size == 0:
        return np.zeros((h_canvas, w_canvas, 4), dtype=np.uint8)
    h_glyph, w_glyph = glyphs.shape[:2]
    dst_x, dst_y = _corner_offset(
        corner=corner,
        canvas=(h_canvas, w_canvas),
        glyph=(h_glyph, w_glyph),
        margin=int(margin),
    )
    out = np.zeros((h_canvas, w_canvas, 4), dtype=np.uint8)
    src_x0 = max(0, -dst_x)
    src_y0 = max(0, -dst_y)
    src_x1 = w_glyph - max(0, (dst_x + w_glyph) - w_canvas)
    src_y1 = h_glyph - max(0, (dst_y + h_glyph) - h_canvas)
    cdst_x0 = max(0, dst_x)
    cdst_y0 = max(0, dst_y)
    cdst_x1 = min(w_canvas, dst_x + w_glyph)
    cdst_y1 = min(h_canvas, dst_y + h_glyph)
    if cdst_x0 < cdst_x1 and cdst_y0 < cdst_y1:
        out[cdst_y0:cdst_y1, cdst_x0:cdst_x1] = (
            glyphs[src_y0:src_y1, src_x0:src_x1]
        )
    return out


def _corner_offset(
    *,
    corner: str,
    canvas: tuple[int, int],
    glyph: tuple[int, int],
    margin: int,
) -> tuple[int, int]:
    """Return the (x, y) destination for the glyph buffer's top-left."""
    h_canvas, w_canvas = canvas
    h_glyph, w_glyph = glyph
    if corner == "top_left":
        return (margin, margin)
    if corner == "top_right":
        return (w_canvas - w_glyph - margin, margin)
    if corner == "bottom_left":
        return (margin, h_canvas - h_glyph - margin)
    # bottom_right (default)
    return (w_canvas - w_glyph - margin, h_canvas - h_glyph - margin)
