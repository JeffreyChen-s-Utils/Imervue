"""Tests for the brush cursor ring renderer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.brush_cursor import (
    cursor_bbox,
    render_cursor_ring,
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_render_cursor_ring_rejects_zero_canvas():
    with pytest.raises(ValueError, match="canvas_size"):
        render_cursor_ring((0, 0), 0, 0, 5)


def test_render_cursor_ring_rejects_negative_radius():
    with pytest.raises(ValueError, match="radius"):
        render_cursor_ring((20, 20), 10, 10, -1)


def test_render_cursor_ring_rejects_oversized_radius():
    with pytest.raises(ValueError, match="radius"):
        render_cursor_ring((20, 20), 10, 10, 99999)


def test_render_cursor_ring_rejects_zero_thickness():
    with pytest.raises(ValueError, match="thickness"):
        render_cursor_ring((20, 20), 10, 10, 5, thickness=0)


def test_render_cursor_ring_rejects_oversized_thickness():
    with pytest.raises(ValueError, match="thickness"):
        render_cursor_ring((20, 20), 10, 10, 5, thickness=100)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def test_render_cursor_ring_returns_canvas_sized_buffer():
    out = render_cursor_ring((30, 40), 20, 15, 5)
    assert out.shape == (30, 40, 4)
    assert out.dtype == np.uint8


def test_render_cursor_ring_centre_not_painted():
    """The ring is hollow — the centre pixel stays transparent."""
    out = render_cursor_ring((40, 40), 20, 20, 8)
    assert out[20, 20, 3] == 0


def test_render_cursor_ring_paints_at_radius():
    """A pixel at exactly ``radius`` from the centre lies on the ring."""
    out = render_cursor_ring((40, 40), 20, 20, 8)
    # (28, 20) is 8 pixels right of centre.
    assert out[20, 28, 3] > 0


def test_render_cursor_ring_outside_radius_unpainted():
    out = render_cursor_ring((40, 40), 20, 20, 5)
    # Far edge of canvas, well outside the ring.
    assert out[0, 0, 3] == 0


def test_render_cursor_ring_thicker_paints_more():
    thin = render_cursor_ring((40, 40), 20, 20, 8, thickness=1)
    thick = render_cursor_ring((40, 40), 20, 20, 8, thickness=4)
    assert (thick[..., 3] > 0).sum() > (thin[..., 3] > 0).sum()


def test_render_cursor_ring_inner_radius_paints_second_circle():
    no_inner = render_cursor_ring((40, 40), 20, 20, 8)
    with_inner = render_cursor_ring(
        (40, 40), 20, 20, 8, inner_radius=4,
    )
    assert (with_inner[..., 3] > 0).sum() > (no_inner[..., 3] > 0).sum()


def test_render_cursor_ring_inner_geq_outer_raises():
    with pytest.raises(ValueError, match="inner_radius"):
        render_cursor_ring((40, 40), 20, 20, 4, inner_radius=8)


def test_render_cursor_ring_zero_radius_no_inner_returns_empty():
    out = render_cursor_ring((20, 20), 10, 10, 0)
    assert out[..., 3].sum() == 0


def test_render_cursor_ring_color_applied():
    out = render_cursor_ring(
        (40, 40), 20, 20, 8, color=(255, 100, 50, 200),
    )
    ys, xs = np.nonzero(out[..., 3] > 0)
    sample = out[ys[0], xs[0]]
    assert tuple(sample) == (255, 100, 50, 200)


def test_render_cursor_ring_off_canvas_centre_clipped():
    """Drawing a ring whose centre is outside the canvas still paints
    the visible portion without raising."""
    out = render_cursor_ring((20, 20), -5, -5, 10)
    # Some pixels in the top-left quadrant might be on-ring.
    assert out.shape == (20, 20, 4)


# ---------------------------------------------------------------------------
# cursor_bbox
# ---------------------------------------------------------------------------


def test_cursor_bbox_contains_ring():
    bbox = cursor_bbox(20, 20, 8)
    x, _, w, _ = bbox
    # All of (12, 28) on the x axis must lie within the box.
    assert x <= 12
    assert x + w >= 28


def test_cursor_bbox_grows_with_thickness():
    thin = cursor_bbox(20, 20, 8, thickness=1)
    thick = cursor_bbox(20, 20, 8, thickness=10)
    assert thick[2] > thin[2]
    assert thick[3] > thin[3]


def test_cursor_bbox_shrinks_with_smaller_radius():
    big = cursor_bbox(20, 20, 16)
    small = cursor_bbox(20, 20, 4)
    assert big[2] > small[2]


# ---------------------------------------------------------------------------
# Quick-mask cursor colour
# ---------------------------------------------------------------------------


def test_cursor_color_uses_foreground_when_not_quick_mask():
    from Imervue.paint.brush_cursor import cursor_color_for_state
    color = cursor_color_for_state((10, 20, 30))
    assert color == (10, 20, 30, 200)


def test_cursor_color_overrides_to_quick_mask_red():
    """Quick-mask flips the cursor to the mask-edit red so the user
    has a visual cue that strokes mutate the selection, not the
    layer pixels."""
    from Imervue.paint.brush_cursor import (
        QUICK_MASK_CURSOR_COLOR,
        cursor_color_for_state,
    )
    color = cursor_color_for_state((0, 0, 0), quick_mask_active=True)
    assert color == QUICK_MASK_CURSOR_COLOR


def test_cursor_color_honours_custom_alpha():
    from Imervue.paint.brush_cursor import cursor_color_for_state
    color = cursor_color_for_state((100, 100, 100), foreground_alpha=64)
    assert color == (100, 100, 100, 64)


def test_cursor_color_quick_mask_ignores_alpha_arg():
    """When quick mask is active the cursor must use the documented
    quick-mask colour regardless of the foreground alpha argument."""
    from Imervue.paint.brush_cursor import (
        QUICK_MASK_CURSOR_COLOR,
        cursor_color_for_state,
    )
    color = cursor_color_for_state(
        (100, 100, 100), quick_mask_active=True, foreground_alpha=10,
    )
    assert color == QUICK_MASK_CURSOR_COLOR


# ---------------------------------------------------------------------------
# ToolState round-trip for quick_mask_active
# ---------------------------------------------------------------------------


def test_tool_state_quick_mask_active_default_is_false():
    from Imervue.paint.tool_state import ToolState
    assert ToolState().quick_mask_active is False


def test_tool_state_quick_mask_active_round_trips_via_dict():
    from Imervue.paint.tool_state import ToolState
    original = ToolState(quick_mask_active=True)
    rebuilt = ToolState.from_dict(original.to_dict())
    assert rebuilt.quick_mask_active is True


def test_tool_state_quick_mask_active_default_when_missing():
    from Imervue.paint.tool_state import ToolState
    assert ToolState.from_dict({}).quick_mask_active is False


# ---------------------------------------------------------------------------
# QPixmap brush cursor — Medibang-style size preview
# ---------------------------------------------------------------------------


def test_make_brush_cursor_returns_pixmap_and_centred_hotspot(qapp):
    from Imervue.paint.brush_cursor import make_brush_cursor
    pixmap, hot_x, hot_y = make_brush_cursor(32)
    assert not pixmap.isNull()
    # Hot-spot is at the centre so the next dab lands under the
    # pointer rather than at the bitmap origin.
    assert hot_x == pixmap.width() // 2
    assert hot_y == pixmap.height() // 2


def test_make_brush_cursor_pixmap_includes_margin(qapp):
    """Bitmap is slightly larger than the requested diameter so the
    antialiased ring isn't clipped at the edge."""
    from Imervue.paint.brush_cursor import make_brush_cursor
    pixmap, _, _ = make_brush_cursor(32)
    assert pixmap.width() >= 32
    assert pixmap.width() == pixmap.height()
    assert pixmap.width() <= 32 + 6   # tight margin, not bloated


def test_make_brush_cursor_below_minimum_raises(qapp):
    from Imervue.paint.brush_cursor import (
        BRUSH_CURSOR_MIN_PX,
        make_brush_cursor,
    )
    with pytest.raises(ValueError):
        make_brush_cursor(BRUSH_CURSOR_MIN_PX - 1)


def test_make_brush_cursor_above_maximum_raises(qapp):
    from Imervue.paint.brush_cursor import (
        BRUSH_CURSOR_MAX_PX,
        make_brush_cursor,
    )
    with pytest.raises(ValueError):
        make_brush_cursor(BRUSH_CURSOR_MAX_PX + 1)


def test_make_brush_cursor_eraser_variant_differs_from_brush(qapp):
    """Eraser cursor adds a slash so the user can tell at a glance
    they're erasing, not painting. That visual difference must show
    in the bitmap pixel hash."""
    from Imervue.paint.brush_cursor import make_brush_cursor
    brush_pix, _, _ = make_brush_cursor(64, eraser=False)
    eraser_pix, _, _ = make_brush_cursor(64, eraser=True)
    brush_image = brush_pix.toImage()
    eraser_image = eraser_pix.toImage()
    # Find at least one differing pixel — the slash adds opaque ink
    # somewhere the brush variant left transparent.
    differs = False
    for y in range(brush_image.height()):
        for x in range(brush_image.width()):
            if brush_image.pixel(x, y) != eraser_image.pixel(x, y):
                differs = True
                break
        if differs:
            break
    assert differs


def test_set_brush_size_cursor_falls_back_when_diameter_too_small(qapp):
    """A 1-pixel ring at 100 % zoom is illegible — the canvas should
    drop to the per-tool ``Qt.CursorShape`` fallback."""
    from Imervue.paint.canvas import PaintCanvas
    canvas = PaintCanvas()
    try:
        canvas.set_brush_size_cursor(1, 1.0, kind="brush")
        # Crosshair (per ``cursor_for_tool('brush')``) — not a pixmap.
        assert canvas.cursor().pixmap().isNull()
    finally:
        canvas.deleteLater()


def test_set_brush_size_cursor_falls_back_when_diameter_too_large(qapp):
    from Imervue.paint.brush_cursor import BRUSH_CURSOR_MAX_PX
    from Imervue.paint.canvas import PaintCanvas
    canvas = PaintCanvas()
    try:
        canvas.set_brush_size_cursor(BRUSH_CURSOR_MAX_PX + 100, 1.0, kind="brush")
        assert canvas.cursor().pixmap().isNull()
    finally:
        canvas.deleteLater()


def test_set_brush_size_cursor_in_range_uses_pixmap(qapp):
    from Imervue.paint.canvas import PaintCanvas
    canvas = PaintCanvas()
    try:
        canvas.set_brush_size_cursor(32, 1.0, kind="brush")
        # In-range diameter → the cursor carries a non-null pixmap.
        assert not canvas.cursor().pixmap().isNull()
    finally:
        canvas.deleteLater()


def test_set_brush_size_cursor_zoom_scales_diameter(qapp):
    """Zooming in should grow the on-screen ring even though the
    canvas-space brush size is unchanged. The pixmap dimensions are
    a usable proxy for the diameter."""
    from Imervue.paint.canvas import PaintCanvas
    canvas = PaintCanvas()
    try:
        canvas.set_brush_size_cursor(32, 1.0, kind="brush")
        small_w = canvas.cursor().pixmap().width()
        canvas.set_brush_size_cursor(32, 4.0, kind="brush")
        big_w = canvas.cursor().pixmap().width()
        assert big_w > small_w
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Workspace integration — cursor reacts to tool / brush / zoom changes
# ---------------------------------------------------------------------------


@pytest.fixture
def _workspace(qapp):
    from Imervue.paint import tool_state as ts
    from Imervue.paint.paint_workspace import PaintWorkspace
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    ws = PaintWorkspace()
    yield ws
    ws.stop_autosave()
    ws.deleteLater()
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def test_workspace_brush_tool_uses_pixmap_cursor(_workspace):
    _workspace.state().set_tool("brush")
    _workspace.state().set_brush(size=32)
    pixmap = _workspace.canvas().cursor().pixmap()
    assert not pixmap.isNull()


def test_workspace_move_tool_uses_qt_shape_not_pixmap(_workspace):
    """The move tool falls back to Qt's ``SizeAllCursor`` — that
    system glyph is already the documented affordance for "drag to
    reposition" so we don't override it with a custom pixmap."""
    _workspace.state().set_tool("move")
    pixmap = _workspace.canvas().cursor().pixmap()
    assert pixmap.isNull()


def test_workspace_brush_size_change_resizes_cursor(_workspace):
    _workspace.state().set_tool("brush")
    _workspace.state().set_brush(size=16)
    small = _workspace.canvas().cursor().pixmap().width()
    _workspace.state().set_brush(size=128)
    big = _workspace.canvas().cursor().pixmap().width()
    assert big > small


def test_workspace_brush_size_change_ignored_for_non_ring_tool(_workspace):
    """A brush-size change while the move tool is active must not
    re-set the cursor to a ring — the move tool stays on its
    ``SizeAllCursor`` shape."""
    _workspace.state().set_tool("move")
    _workspace.state().set_brush(size=64)
    pixmap = _workspace.canvas().cursor().pixmap()
    assert pixmap.isNull()


def test_workspace_eraser_tool_uses_eraser_variant(_workspace):
    """Eraser cursor differs from the brush variant — verifies the
    workspace forwarded the ``kind="eraser"`` hint to the canvas."""
    _workspace.state().set_tool("brush")
    _workspace.state().set_brush(size=64)
    brush_pixmap = _workspace.canvas().cursor().pixmap()
    _workspace.state().set_tool("eraser")
    eraser_pixmap = _workspace.canvas().cursor().pixmap()
    assert brush_pixmap.toImage() != eraser_pixmap.toImage()


def test_workspace_clone_stamp_uses_brush_ring(_workspace):
    """Clone stamp paints with ``state.brush.size`` so it joins the
    ring-cursor family."""
    _workspace.state().set_tool("clone_stamp")
    _workspace.state().set_brush(size=48)
    pixmap = _workspace.canvas().cursor().pixmap()
    assert not pixmap.isNull()


# ---------------------------------------------------------------------------
# Per-tool icon cursor — a custom QPixmap for every "non-ring" tool
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool", [
    "eyedropper", "fill", "gradient", "bezier_pen",
    "select_rect", "select_lasso", "select_wand", "select_quick",
    "zoom",
])
def test_make_tool_cursor_returns_pixmap_for_iconed_tools(qapp, tool):
    """Every drawing tool that doesn't paint with ``brush.size`` still
    deserves a descriptive icon — verifies the registry covers it."""
    from Imervue.paint.brush_cursor import make_tool_cursor
    result = make_tool_cursor(tool)
    assert result is not None
    pixmap, hot_x, hot_y = result
    assert not pixmap.isNull()
    assert 0 <= hot_x < pixmap.width()
    assert 0 <= hot_y < pixmap.height()


@pytest.mark.parametrize("tool", [
    "brush", "eraser", "smudge", "blur", "clone_stamp",
    "move", "hand", "text",
])
def test_make_tool_cursor_returns_none_for_ring_or_qt_tools(qapp, tool):
    """Brush-family tools use the size ring instead of a static icon;
    move / hand / text use Qt's built-in cursor shapes that already
    look correct."""
    from Imervue.paint.brush_cursor import make_tool_cursor
    assert make_tool_cursor(tool) is None


def test_tool_icons_are_visually_distinct(qapp):
    """Two different drawing tools must render different icons —
    otherwise the user can't tell them apart from the cursor alone."""
    from Imervue.paint.brush_cursor import make_tool_cursor
    seen = []
    for tool in ("eyedropper", "fill", "gradient", "bezier_pen", "zoom"):
        pixmap, _, _ = make_tool_cursor(tool)
        seen.append(pixmap.toImage())
    # Pairwise compare — every pair differs at least one pixel.
    for i, a in enumerate(seen):
        for b in seen[i + 1:]:
            assert a != b


def test_workspace_eyedropper_tool_uses_custom_icon(_workspace):
    """Picking the eyedropper now sets a tool-icon pixmap, not the
    plain ``PointingHandCursor`` we used to fall back to."""
    _workspace.state().set_tool("eyedropper")
    pixmap = _workspace.canvas().cursor().pixmap()
    assert not pixmap.isNull()


def test_workspace_zoom_tool_uses_custom_icon(_workspace):
    _workspace.state().set_tool("zoom")
    pixmap = _workspace.canvas().cursor().pixmap()
    assert not pixmap.isNull()


def test_workspace_text_tool_keeps_qt_shape(_workspace):
    """``text`` falls back to Qt's IBeam — no custom pixmap because
    the system shape is already the documented affordance."""
    _workspace.state().set_tool("text")
    pixmap = _workspace.canvas().cursor().pixmap()
    assert pixmap.isNull()
