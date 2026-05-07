"""Comic page templates — paper sizes + project presets.

A :class:`PageTemplate` is a named (width, height, dpi) triple plus an
optional default fill colour. The set covers the common paper sizes
manga/comic artists work at — JIS B5 / B4 (Japanese tankōbon and
single-print), ISO A4 / A5, plus a vertical-strip web-toon canvas
sized for mobile delivery.

Templates can also carry **layout guides**: a list of panel-frame
polygons in fractional canvas coordinates and an optional bleed inset
(in millimetres) that gets converted to pixels at template DPI. When
either is non-empty, ``make_blank_page`` rasterises the guides into a
non-active "Guides" layer so the artist sees the panel grid + bleed
margins from the moment the page opens. The guide layer is alpha-
masked thin grey lines, so painting over them works normally — the
guides act as a visual reference, not a clip.

Building a fresh project from a template returns a
:class:`Imervue.paint.paint_project.PaintProject` with one or more
blank pages already populated, so the user lands in a paintable state
without having to size the canvas by hand.

The pixel dimensions are computed from the template's physical size
(in millimetres) and DPI so a B5 manga at 600 DPI gives the print-
ready 4299×6071 buffer artists expect.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from Imervue.paint.document import PaintDocument
from Imervue.paint.paint_project import PaintProject, ProjectPage

# Internal cap so a corrupt / hostile template can't blow out RAM with
# a 100k×100k allocation. Far above any realistic print size; chosen
# to fit comfortably inside a single uint8 RGBA buffer (16 GiB max).
_MAX_PIXEL_DIMENSION = 16384


PanelPolygon = tuple[tuple[float, float], ...]
BLEED_GUIDE_RGBA = (200, 60, 60, 200)
PANEL_GUIDE_RGBA = (140, 140, 140, 220)
GUIDE_LAYER_NAME = "Guides"


@dataclass(frozen=True)
class PageTemplate:
    """A named page format with paper size + DPI + default fill.

    ``width_mm`` / ``height_mm`` are the physical canvas size and
    ``dpi`` controls the pixel resolution. ``fill_rgba`` is the colour
    the seeded blank canvas is filled with — opaque white by default
    so artists see paper rather than transparency.

    ``panel_frames`` lists panel-border polygons in *fractional*
    canvas coordinates (each ``(x, y)`` in ``[0.0, 1.0]``) so the
    same template renders cleanly at any DPI. ``bleed_mm`` is the
    inset from the canvas edge to the bleed line; 0 disables the
    bleed guide. ``guide_thickness_mm`` controls outline weight.
    """

    name: str
    width_mm: float
    height_mm: float
    dpi: int = 350
    fill_rgba: tuple[int, int, int, int] = (255, 255, 255, 255)
    panel_frames: tuple[PanelPolygon, ...] = field(default_factory=tuple)
    bleed_mm: float = 0.0
    guide_thickness_mm: float = 0.5

    @property
    def pixel_size(self) -> tuple[int, int]:
        """Return ``(width_px, height_px)`` rounded to nearest pixel."""
        w = int(round(self.width_mm * self.dpi / 25.4))
        h = int(round(self.height_mm * self.dpi / 25.4))
        return (max(1, w), max(1, h))

    @property
    def has_layout_guides(self) -> bool:
        return bool(self.panel_frames) or self.bleed_mm > 0


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

def _grid_panels(rows: int, cols: int, *, gutter: float = 0.025) -> tuple[PanelPolygon, ...]:
    """Build a uniform grid of rectangular panel polygons.

    ``gutter`` is the gap between panels as a fraction of canvas size.
    Coordinates are normalised so the same grid scales to any DPI.
    """
    panels: list[PanelPolygon] = []
    cell_w = (1.0 - gutter * (cols + 1)) / cols
    cell_h = (1.0 - gutter * (rows + 1)) / rows
    for r in range(rows):
        for c in range(cols):
            x0 = gutter + c * (cell_w + gutter)
            y0 = gutter + r * (cell_h + gutter)
            x1 = x0 + cell_w
            y1 = y0 + cell_h
            panels.append((
                (x0, y0), (x1, y0), (x1, y1), (x0, y1),
            ))
    return tuple(panels)


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
    # --- panel-grid manga templates: pre-drawn frames + bleed line ----
    PageTemplate(
        name="manga_b5_2x3_grid",
        width_mm=182.0, height_mm=257.0, dpi=350,
        panel_frames=_grid_panels(rows=3, cols=2),
        bleed_mm=3.0,
    ),
    PageTemplate(
        name="manga_b5_4koma",
        width_mm=182.0, height_mm=257.0, dpi=350,
        panel_frames=_grid_panels(rows=4, cols=1, gutter=0.04),
        bleed_mm=3.0,
    ),
    PageTemplate(
        name="manga_b5_splash",
        width_mm=182.0, height_mm=257.0, dpi=350,
        panel_frames=(
            ((0.06, 0.06), (0.94, 0.06), (0.94, 0.94), (0.06, 0.94)),
        ),
        bleed_mm=3.0,
    ),
    PageTemplate(
        name="manga_b5_6panel",
        width_mm=182.0, height_mm=257.0, dpi=350,
        panel_frames=_grid_panels(rows=3, cols=2, gutter=0.02),
        bleed_mm=3.0,
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
    if template.has_layout_guides:
        guide_image = render_layout_guides(template)
        guide_layer = document.add_layer(name=GUIDE_LAYER_NAME)
        np.copyto(guide_layer.image, guide_image)
        # Drop activity back to the main paper layer so the user
        # paints there by default; the guides stay above as overlay.
        document.set_active_layer(0)
    return ProjectPage(document=document, name=name)


def render_layout_guides(template: PageTemplate) -> np.ndarray:
    """Rasterise panel frames + bleed line for ``template``.

    Returns a HxWx4 RGBA buffer the size of ``template.pixel_size``,
    transparent everywhere except the guide strokes. Drawn with
    Pillow so anti-aliasing is consistent with the rest of the
    paint stack.
    """
    from PIL import Image, ImageDraw

    width_px, height_px = template.pixel_size
    img = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    line_px = max(1, int(round(template.guide_thickness_mm * template.dpi / 25.4)))

    if template.bleed_mm > 0:
        inset = int(round(template.bleed_mm * template.dpi / 25.4))
        draw.rectangle(
            (inset, inset, width_px - inset - 1, height_px - inset - 1),
            outline=BLEED_GUIDE_RGBA, width=line_px,
        )

    for panel in template.panel_frames:
        coords = [
            (int(round(px * width_px)), int(round(py * height_px)))
            for (px, py) in panel
        ]
        # Draw closed polygon outline. PIL's ``polygon`` ignores
        # ``width`` for the outline in older versions, so we draw
        # explicit line segments to honour ``line_px`` everywhere.
        for i in range(len(coords)):
            a = coords[i]
            b = coords[(i + 1) % len(coords)]
            draw.line([a, b], fill=PANEL_GUIDE_RGBA, width=line_px)

    return np.asarray(img, dtype=np.uint8).copy()


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
