"""Rasterise text into an RGBA numpy array via QPainter.

The Qt API is the most reliable way to get correctly-shaped, hinted
glyphs that match the OS's font set — pure-numpy approaches require
shipping a font atlas and a layout engine, which is well out of
scope. Keeping the rasteriser in its own module isolates the Qt
dependency so the rest of the paint logic stays Qt-free.

A single :class:`TextRenderOptions` carries every parameter; the
:func:`render_text` helper sizes the output canvas to the bounding
rect of the text and writes it onto a fully transparent background
ready to be alpha-composited onto the active layer.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
)

DEFAULT_FAMILY = "Arial"
SIZE_MIN = 4
SIZE_MAX = 600


@dataclass(frozen=True)
class TextRenderOptions:
    """Parameters for :func:`render_text`.

    ``vertical`` switches to manga-style top-to-bottom text where
    each glyph is stacked under the previous one. ``line_spacing``
    multiplies the natural line height; values < 1 tighten the
    columns / lines, values > 1 loosen them. The default ``1.0``
    matches the font's natural metrics.
    """

    text: str
    family: str = DEFAULT_FAMILY
    size: int = 36
    color: tuple[int, int, int] = (0, 0, 0)
    bold: bool = False
    italic: bool = False
    vertical: bool = False
    line_spacing: float = 1.0


def render_text(options: TextRenderOptions) -> np.ndarray:
    """Render ``options.text`` into an HxWx4 uint8 RGBA buffer.

    The buffer is sized to the text's bounding rect with a small
    padding margin so descenders and italic slants don't get clipped.
    Returns an empty ``(0, 0, 4)`` array if the text is empty.

    With ``options.vertical`` set, glyphs stack top-to-bottom
    centred on a single column whose width is the widest glyph plus
    padding — matching raster paint apps's manga vertical text mode.
    """
    text = options.text
    if not text:
        return np.empty((0, 0, 4), dtype=np.uint8)

    if options.vertical:
        return _render_vertical(options)

    size = max(SIZE_MIN, min(SIZE_MAX, int(options.size)))
    font = QFont(options.family or DEFAULT_FAMILY)
    font.setPixelSize(size)
    font.setBold(bool(options.bold))
    font.setItalic(bool(options.italic))

    metrics = QFontMetricsF(font)
    bbox = metrics.tightBoundingRect(text)
    pad = max(2, size // 8)
    width = max(1, int(bbox.width()) + pad * 2)
    height = max(1, int(bbox.height()) + pad * 2)

    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setFont(font)
    painter.setPen(QColor(*options.color))
    # Place the baseline so the glyphs sit inside the padded rect.
    baseline_y = pad - int(bbox.top())
    painter.drawText(pad, baseline_y, text)
    painter.end()

    return _qimage_to_rgba(image)


def _render_vertical(options: TextRenderOptions) -> np.ndarray:
    """Stack each glyph in ``options.text`` top-to-bottom into one
    centred column. Each glyph rasterises through the same Qt path
    as the horizontal renderer."""
    text = options.text
    size = max(SIZE_MIN, min(SIZE_MAX, int(options.size)))
    font = QFont(options.family or DEFAULT_FAMILY)
    font.setPixelSize(size)
    font.setBold(bool(options.bold))
    font.setItalic(bool(options.italic))

    metrics = QFontMetricsF(font)
    pad = max(2, size // 8)
    line_spacing = max(0.1, float(options.line_spacing))
    line_height = max(1, int(metrics.height() * line_spacing))

    glyph_buffers: list[np.ndarray] = []
    max_width = 1
    for char in text:
        bbox = metrics.tightBoundingRect(char)
        cw = max(1, int(bbox.width()) + pad * 2)
        ch = max(1, int(bbox.height()) + pad * 2)
        max_width = max(max_width, cw)
        image = QImage(cw, ch, QImage.Format.Format_RGBA8888)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(font)
        painter.setPen(QColor(*options.color))
        baseline_y = pad - int(bbox.top())
        painter.drawText(pad, baseline_y, char)
        painter.end()
        glyph_buffers.append(_qimage_to_rgba(image))

    total_height = max(line_height * len(glyph_buffers), 1)
    out = np.zeros((total_height, max_width, 4), dtype=np.uint8)
    y_cursor = 0
    for buf in glyph_buffers:
        bh, bw = buf.shape[:2]
        x_offset = max(0, (max_width - bw) // 2)
        # Vertically centre the glyph within its line slot so the
        # column reads with consistent baseline-style alignment.
        y_offset = max(0, (line_height - bh) // 2)
        target_h = min(bh, total_height - y_cursor - y_offset)
        if target_h > 0:
            out[
                y_cursor + y_offset:y_cursor + y_offset + target_h,
                x_offset:x_offset + bw,
            ] = buf[:target_h]
        y_cursor += line_height
    return out


def composite_onto(
    canvas: np.ndarray, rendered: np.ndarray, x: int, y: int,
    *, selection: np.ndarray | None = None,
) -> None:
    """Alpha-blend a rendered text bitmap onto an HxWx4 canvas in place.

    ``(x, y)`` is the top-left corner of the text's padded rect on the
    canvas. Pixels outside the canvas are clipped automatically. If a
    selection mask is given the blend is restricted to True pixels.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    if rendered.size == 0 or rendered.shape[0] == 0 or rendered.shape[1] == 0:
        return
    if rendered.ndim != 3 or rendered.shape[2] != 4 or rendered.dtype != np.uint8:
        raise ValueError(
            f"rendered text must be HxWx4 uint8 RGBA, got {rendered.shape} {rendered.dtype}",
        )

    rh, rw = rendered.shape[:2]
    h, w = canvas.shape[:2]
    cx0 = max(0, x)
    cy0 = max(0, y)
    cx1 = min(w, x + rw)
    cy1 = min(h, y + rh)
    if cx1 <= cx0 or cy1 <= cy0:
        return

    rx0 = cx0 - x
    ry0 = cy0 - y
    rx1 = rx0 + (cx1 - cx0)
    ry1 = ry0 + (cy1 - cy0)

    src = rendered[ry0:ry1, rx0:rx1].astype(np.float32) / 255.0
    dst = canvas[cy0:cy1, cx0:cx1].astype(np.float32) / 255.0

    a = src[..., 3:4]
    if selection is not None:
        if selection.shape != canvas.shape[:2]:
            raise ValueError(
                f"selection shape {selection.shape} does not match "
                f"canvas {canvas.shape[:2]}",
            )
        sel_slice = selection[cy0:cy1, cx0:cx1].astype(np.float32)[..., None]
        a = a * sel_slice
    out_rgb = src[..., :3] * a + dst[..., :3] * (1.0 - a)
    out_a = a[..., 0] + dst[..., 3] * (1.0 - a[..., 0])

    canvas[cy0:cy1, cx0:cx1, :3] = np.clip(out_rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    canvas[cy0:cy1, cx0:cx1, 3] = np.clip(out_a * 255.0, 0.0, 255.0).astype(np.uint8)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _qimage_to_rgba(image: QImage) -> np.ndarray:
    """Convert a QImage in Format_RGBA8888 to an HxWx4 uint8 numpy array."""
    if image.format() != QImage.Format.Format_RGBA8888:
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = image.width()
    height = image.height()
    # PySide6's constBits() already returns a sized memoryview.
    raw = bytes(image.constBits())
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(
        height, image.bytesPerLine() // 4, 4,
    )
    # Trim any per-row padding that QImage may have appended.
    return np.ascontiguousarray(arr[:, :width, :])
