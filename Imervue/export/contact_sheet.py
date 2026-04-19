"""
Contact sheet PDF generator.

Lays out thumbnails of the supplied images in a grid, one page per chunk,
using ``QPdfWriter`` + ``QPainter`` so there is no runtime dependency on
reportlab or pillow for PDF output.

Keep the public surface small: ``ContactSheetOptions`` + ``generate_contact_sheet``.
The GUI dialog picks page size / grid and delegates here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QMarginsF, QSizeF, QRect
from PySide6.QtGui import QPdfWriter, QPainter, QImage, QPageSize, QPageLayout, QFont

logger = logging.getLogger("Imervue.export.contact_sheet")

# Common paper sizes — mapped to QPageSize IDs.
PAGE_SIZES: dict[str, QPageSize.PageSizeId] = {
    "A4": QPageSize.PageSizeId.A4,
    "A3": QPageSize.PageSizeId.A3,
    "Letter": QPageSize.PageSizeId.Letter,
    "Legal": QPageSize.PageSizeId.Legal,
}


@dataclass(frozen=True)
class ContactSheetOptions:
    rows: int = 5
    cols: int = 4
    page_size: str = "A4"  # key in PAGE_SIZES
    margin_mm: float = 10.0
    caption: bool = True
    title: str = ""
    dpi: int = 300


def _resolve_page_size(key: str) -> QPageSize.PageSizeId:
    return PAGE_SIZES.get(key, QPageSize.PageSizeId.A4)


def _load_thumbnail(path: str, max_side: int) -> QImage | None:
    """Load ``path`` as a QImage scaled so its long side <= ``max_side``."""
    img = QImage(path)
    if img.isNull():
        return None
    if max(img.width(), img.height()) <= max_side:
        return img
    return img.scaled(
        max_side, max_side,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _draw_title(painter: QPainter, rect: QRect, title: str) -> int:
    """Draw the page title at the top of ``rect``. Returns the title's height."""
    if not title:
        return 0
    font = QFont()
    font.setPointSize(14)
    font.setBold(True)
    painter.setFont(font)
    metrics = painter.fontMetrics()
    height = metrics.height() + 4
    painter.drawText(rect.left(), rect.top() + metrics.ascent(), title)
    return height


def _draw_cell(
    painter: QPainter,
    cell_rect: QRect,
    image_path: str,
    show_caption: bool,
) -> None:
    """Render one thumbnail + caption inside ``cell_rect``."""
    caption_h = 0
    if show_caption:
        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)
        caption_h = painter.fontMetrics().height() + 4
    image_rect = QRect(
        cell_rect.left(), cell_rect.top(),
        cell_rect.width(), cell_rect.height() - caption_h,
    )
    thumb = _load_thumbnail(image_path, max(image_rect.width(), image_rect.height()))
    if thumb is None:
        painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, "[missing]")
    else:
        scaled = thumb.scaled(
            image_rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = image_rect.left() + (image_rect.width() - scaled.width()) // 2
        y = image_rect.top() + (image_rect.height() - scaled.height()) // 2
        painter.drawImage(x, y, scaled)
    if show_caption:
        caption_rect = QRect(
            cell_rect.left(), image_rect.bottom() + 2,
            cell_rect.width(), caption_h - 2,
        )
        painter.drawText(
            caption_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine,
            Path(image_path).name,
        )


def _configure_pdf(writer: QPdfWriter, opts: ContactSheetOptions) -> None:
    writer.setResolution(opts.dpi)
    layout = QPageLayout()
    layout.setPageSize(QPageSize(_resolve_page_size(opts.page_size)))
    layout.setOrientation(QPageLayout.Orientation.Portrait)
    layout.setUnits(QPageLayout.Unit.Millimeter)
    layout.setMargins(QMarginsF(
        opts.margin_mm, opts.margin_mm, opts.margin_mm, opts.margin_mm))
    writer.setPageLayout(layout)


def generate_contact_sheet(
    images: list[str],
    output_path: str | Path,
    opts: ContactSheetOptions | None = None,
) -> Path:
    """Render ``images`` into a multi-page PDF contact sheet at ``output_path``."""
    if not images:
        raise ValueError("generate_contact_sheet requires at least one image")
    options = opts or ContactSheetOptions()
    if options.rows < 1 or options.cols < 1:
        raise ValueError("rows and cols must be >= 1")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    writer = QPdfWriter(str(out))
    _configure_pdf(writer, options)
    painter = QPainter(writer)
    try:
        _render_pages(painter, writer, images, options)
    finally:
        painter.end()
    logger.info("Contact sheet written: %s", out)
    return out


def _render_pages(
    painter: QPainter,
    writer: QPdfWriter,
    images: list[str],
    opts: ContactSheetOptions,
) -> None:
    per_page = opts.rows * opts.cols
    total_pages = (len(images) + per_page - 1) // per_page
    for page_idx in range(total_pages):
        if page_idx > 0:
            writer.newPage()
        start = page_idx * per_page
        chunk = images[start:start + per_page]
        page_rect = painter.viewport()
        title_h = _draw_title(painter, page_rect, opts.title) if page_idx == 0 else 0
        grid_rect = QRect(
            page_rect.left(), page_rect.top() + title_h,
            page_rect.width(), page_rect.height() - title_h,
        )
        cell_w = grid_rect.width() // opts.cols
        cell_h = grid_rect.height() // opts.rows
        for i, img_path in enumerate(chunk):
            row = i // opts.cols
            col = i % opts.cols
            cell_rect = QRect(
                grid_rect.left() + col * cell_w + 4,
                grid_rect.top() + row * cell_h + 4,
                cell_w - 8, cell_h - 8,
            )
            _draw_cell(painter, cell_rect, img_path, opts.caption)
