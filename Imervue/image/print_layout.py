"""Print layout — compose multiple images onto printable pages as PDF.

Supports standard page sizes (A4 / A3 / Letter / Legal), configurable
margins, gutter between cells, and optional crop marks. One page per
NxM grid; images are scaled to fit while preserving aspect ratio.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("Imervue.print_layout")

# Page sizes in points (1 pt = 1/72 in).
PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A4": (595.28, 841.89),
    "A3": (841.89, 1190.55),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
}

_DEFAULT_MARGIN_PT = 36.0   # 0.5 inch
_DEFAULT_GUTTER_PT = 12.0
_MARK_LENGTH_PT = 12.0


@dataclass
class PrintLayout:
    page_size: str = "A4"
    landscape: bool = False
    rows: int = 2
    cols: int = 2
    margin_pt: float = _DEFAULT_MARGIN_PT
    gutter_pt: float = _DEFAULT_GUTTER_PT
    crop_marks: bool = False
    image_paths: list[str] = field(default_factory=list)


def _page_dimensions(layout: PrintLayout) -> tuple[float, float]:
    w, h = PAGE_SIZES.get(layout.page_size, PAGE_SIZES["A4"])
    return (h, w) if layout.landscape else (w, h)


def _draw_crop_marks(canvas, x: float, y: float, w: float, h: float) -> None:
    from reportlab.lib.colors import black
    canvas.setStrokeColor(black)
    canvas.setLineWidth(0.3)
    m = _MARK_LENGTH_PT
    for (cx, cy) in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        canvas.line(cx - m, cy, cx - 2, cy)
        canvas.line(cx + 2, cy, cx + m, cy)
        canvas.line(cx, cy - m, cx, cy - 2)
        canvas.line(cx, cy + 2, cx, cy + m)


def _cell_geometry(
    layout: PrintLayout, page_w: float, page_h: float,
) -> tuple[float, float, float, float]:
    """Return (x0, y0, cell_w, cell_h) for the first cell."""
    rows = max(1, layout.rows)
    cols = max(1, layout.cols)
    inner_w = page_w - 2 * layout.margin_pt - (cols - 1) * layout.gutter_pt
    inner_h = page_h - 2 * layout.margin_pt - (rows - 1) * layout.gutter_pt
    cell_w = max(1.0, inner_w / cols)
    cell_h = max(1.0, inner_h / rows)
    return layout.margin_pt, layout.margin_pt, cell_w, cell_h


def export_print_pdf(layout: PrintLayout, output_path: str | Path) -> Path:
    """Write a multi-page PDF with *layout*'s images tiled on each page.

    Raises ImportError if reportlab is not installed.
    """
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.utils import ImageReader

    page_w, page_h = _page_dimensions(layout)
    out_path = Path(output_path)
    c = pdf_canvas.Canvas(str(out_path), pagesize=(page_w, page_h))

    rows = max(1, layout.rows)
    cols = max(1, layout.cols)
    per_page = rows * cols
    x0, y0, cell_w, cell_h = _cell_geometry(layout, page_w, page_h)

    for page_idx in range(0, max(1, len(layout.image_paths)), per_page):
        batch = layout.image_paths[page_idx:page_idx + per_page]
        for i, img_path in enumerate(batch):
            r = i // cols
            col = i % cols
            # ReportLab origin is bottom-left; rows drawn top to bottom.
            cx = x0 + col * (cell_w + layout.gutter_pt)
            cy = page_h - layout.margin_pt - (r + 1) * cell_h - r * layout.gutter_pt
            try:
                img = ImageReader(str(img_path))
                iw, ih = img.getSize()
                scale = min(cell_w / iw, cell_h / ih)
                dw, dh = iw * scale, ih * scale
                dx = cx + (cell_w - dw) / 2.0
                dy = cy + (cell_h - dh) / 2.0
                c.drawImage(img, dx, dy, dw, dh,
                            preserveAspectRatio=True, mask="auto")
            except (OSError, ValueError) as err:
                logger.warning("Skipping %s: %s", img_path, err)
                continue
            if layout.crop_marks:
                _draw_crop_marks(c, cx, cy, cell_w, cell_h)
        c.showPage()
    c.save()
    return out_path
