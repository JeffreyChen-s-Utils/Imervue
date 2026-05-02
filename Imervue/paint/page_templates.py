"""Comic page templates — paper sizes + project presets.

A :class:`PageTemplate` is a named (width, height, dpi) triple plus an
optional default fill colour. The set covers the common paper sizes
manga/comic artists work at — JIS B5 / B4 (Japanese tankōbon and
single-print), ISO A4 / A5, plus a vertical-strip web-toon canvas
sized for mobile delivery.

Building a fresh project from a template returns a
:class:`Imervue.paint.paint_project.PaintProject` with one or more
blank pages already populated, so the user lands in a paintable state
without having to size the canvas by hand.

The pixel dimensions are computed from the template's physical size
(in millimetres) and DPI so a B5 manga at 600 DPI gives the print-
ready 4299×6071 buffer artists expect.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from Imervue.paint.document import PaintDocument
from Imervue.paint.paint_project import PaintProject, ProjectPage

# Internal cap so a corrupt / hostile template can't blow out RAM with
# a 100k×100k allocation. Far above any realistic print size; chosen
# to fit comfortably inside a single uint8 RGBA buffer (16 GiB max).
_MAX_PIXEL_DIMENSION = 16384


@dataclass(frozen=True)
class PageTemplate:
    """A named page format with paper size + DPI + default fill.

    ``width_mm`` / ``height_mm`` are the physical canvas size and
    ``dpi`` controls the pixel resolution. ``fill_rgba`` is the colour
    the seeded blank canvas is filled with — opaque white by default
    so artists see paper rather than transparency.
    """

    name: str
    width_mm: float
    height_mm: float
    dpi: int = 350
    fill_rgba: tuple[int, int, int, int] = (255, 255, 255, 255)

    @property
    def pixel_size(self) -> tuple[int, int]:
        """Return ``(width_px, height_px)`` rounded to nearest pixel."""
        w = int(round(self.width_mm * self.dpi / 25.4))
        h = int(round(self.height_mm * self.dpi / 25.4))
        return (max(1, w), max(1, h))


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

# DPI defaults: 350 for print-ready manga, 72 for web-strip delivery.
PAGE_TEMPLATES: tuple[PageTemplate, ...] = (
    PageTemplate(name="manga_b5", width_mm=182.0, height_mm=257.0, dpi=350),
    PageTemplate(name="manga_b4", width_mm=257.0, height_mm=364.0, dpi=350),
    PageTemplate(name="manga_a4", width_mm=210.0, height_mm=297.0, dpi=350),
    PageTemplate(name="manga_a5", width_mm=148.0, height_mm=210.0, dpi=350),
    PageTemplate(
        # 800×3200 px, the WEBTOON-platform standard for vertical strip.
        name="webtoon_strip",
        width_mm=800.0 * 25.4 / 72.0,
        height_mm=3200.0 * 25.4 / 72.0,
        dpi=72,
    ),
    PageTemplate(
        # Print-ready square — matches IG-friendly comic post size.
        name="square_2400",
        width_mm=2400.0 * 25.4 / 300.0,
        height_mm=2400.0 * 25.4 / 300.0,
        dpi=300,
    ),
)

DEFAULT_TEMPLATE_NAME = "manga_b5"


def template_by_name(name: str) -> PageTemplate:
    """Lookup a built-in template by name. Raises ``KeyError`` if missing.

    Use :func:`available_template_names` if you need a stable list to
    drive a UI dropdown.
    """
    for tpl in PAGE_TEMPLATES:
        if tpl.name == name:
            return tpl
    raise KeyError(f"unknown page template {name!r}")


def available_template_names() -> tuple[str, ...]:
    """Return the names in their canonical / UI order."""
    return tuple(tpl.name for tpl in PAGE_TEMPLATES)


# ---------------------------------------------------------------------------
# Page / project construction
# ---------------------------------------------------------------------------


def make_blank_page(
    template: PageTemplate, *, name: str = "Page",
) -> ProjectPage:
    """Create a single :class:`ProjectPage` filled per ``template``."""
    width_px, height_px = template.pixel_size
    if width_px > _MAX_PIXEL_DIMENSION or height_px > _MAX_PIXEL_DIMENSION:
        raise ValueError(
            f"template {template.name!r} produces oversize canvas "
            f"{width_px}×{height_px} (cap {_MAX_PIXEL_DIMENSION})",
        )
    arr = np.empty((height_px, width_px, 4), dtype=np.uint8)
    arr[..., :] = template.fill_rgba
    document = PaintDocument()
    document.load_image(arr)
    return ProjectPage(document=document, name=name)


def project_from_template(
    template: PageTemplate,
    *,
    page_count: int = 1,
    project_name: str = "Untitled Project",
    author: str = "",
) -> PaintProject:
    """Create a :class:`PaintProject` with ``page_count`` blank pages.

    ``page_count`` must be at least 1 — a project must always own at
    least one page (the model never lets the last page be removed).
    """
    if page_count < 1:
        raise ValueError(f"page_count must be >= 1, got {page_count!r}")
    pages = [
        make_blank_page(template, name=f"Page {i + 1}")
        for i in range(page_count)
    ]
    return PaintProject(
        name=project_name, author=author, pages=pages, active_page_index=0,
    )
