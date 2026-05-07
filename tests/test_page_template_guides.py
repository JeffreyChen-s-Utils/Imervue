"""Tests for the manga page templates that ship with frame guides."""
from __future__ import annotations

import numpy as np

from Imervue.paint.page_templates import (
    BLEED_GUIDE_RGBA,
    GUIDE_LAYER_NAME,
    PANEL_GUIDE_RGBA,
    PageTemplate,
    available_template_names,
    make_blank_page,
    render_layout_guides,
    template_by_name,
    _grid_panels,
)


def test_grid_panels_partition_canvas_with_gutters():
    panels = _grid_panels(2, 2, gutter=0.05)
    assert len(panels) == 4
    # Every coord stays inside the unit square.
    for poly in panels:
        for (x, y) in poly:
            assert 0.0 <= x <= 1.0
            assert 0.0 <= y <= 1.0


def test_layout_guide_rendering_writes_panel_outlines():
    """A trivial single-panel template draws a transparent buffer
    with a grey outline at the panel's normalised coordinates."""
    tpl = PageTemplate(
        name="single", width_mm=20.0, height_mm=20.0, dpi=72,
        panel_frames=(
            ((0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)),
        ),
    )
    arr = render_layout_guides(tpl)
    h, w = arr.shape[:2]
    assert arr.dtype == np.uint8
    assert arr.shape[2] == 4
    # The four corners well outside the panel must be transparent.
    assert arr[1, 1, 3] == 0
    assert arr[h - 2, w - 2, 3] == 0
    # Pixels along the panel's top edge must carry the guide colour.
    sample_y = int(round(0.25 * h))
    sample_x = int(round(0.5 * w))
    assert tuple(arr[sample_y, sample_x, :3]) == PANEL_GUIDE_RGBA[:3]
    assert arr[sample_y, sample_x, 3] > 0


def test_layout_guide_rendering_writes_bleed_line():
    """A template with bleed_mm > 0 draws a bleed rectangle inset
    from the canvas edge in the bleed-guide colour."""
    tpl = PageTemplate(
        name="bleed", width_mm=50.0, height_mm=50.0, dpi=72, bleed_mm=5.0,
    )
    arr = render_layout_guides(tpl)
    h, w = arr.shape[:2]
    inset = int(round(5.0 * 72 / 25.4))
    # Right at the bleed inset on the top edge.
    sample = arr[inset, w // 2, :3]
    assert tuple(sample) == BLEED_GUIDE_RGBA[:3]


def test_make_blank_page_no_guide_layer_when_template_plain():
    tpl = template_by_name("manga_b5")
    page = make_blank_page(tpl, name="One")
    # Plain B5 has only the paper layer.
    assert len(page.document.layers()) == 1


def test_make_blank_page_attaches_guide_layer_when_template_has_guides():
    tpl = template_by_name("manga_b5_2x3_grid")
    page = make_blank_page(tpl, name="Page A")
    layers = page.document.layers()
    assert len(layers) == 2
    assert layers[1].name == GUIDE_LAYER_NAME
    # Active layer must be the paper, not the guides — user paints
    # on the paper by default.
    assert page.document.active_layer_index() == 0
    # Guide layer carries the panel outlines = some opaque pixels.
    assert int(layers[1].image[..., 3].max()) > 0


def test_grid_template_panel_count_matches_grid_dimensions():
    tpl = template_by_name("manga_b5_2x3_grid")
    assert len(tpl.panel_frames) == 6
    splash = template_by_name("manga_b5_splash")
    assert len(splash.panel_frames) == 1


def test_built_in_template_list_includes_all_grid_variants():
    names = available_template_names()
    for required in (
        "manga_b5", "manga_b4", "manga_a4", "manga_a5",
        "webtoon_strip", "square_2400",
        "manga_b5_2x3_grid", "manga_b5_4koma",
        "manga_b5_splash", "manga_b5_6panel",
    ):
        assert required in names


def test_has_layout_guides_property_reflects_optional_fields():
    plain = PageTemplate(name="x", width_mm=10, height_mm=10)
    with_panels = PageTemplate(
        name="x", width_mm=10, height_mm=10,
        panel_frames=(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),),
    )
    with_bleed = PageTemplate(
        name="x", width_mm=10, height_mm=10, bleed_mm=2.0,
    )
    assert plain.has_layout_guides is False
    assert with_panels.has_layout_guides is True
    assert with_bleed.has_layout_guides is True
