"""Tests for pixel-grid + guide overlays."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from Imervue.paint.visual_guides import (
    DEFAULT_GRID_MAJOR_COLOR,
    GUIDE_ORIENTATIONS,
    Guide,
    GuideSet,
    GridSpec,
    render_overlay,
)


# ---------------------------------------------------------------------------
# Guide
# ---------------------------------------------------------------------------


def test_guide_orientations_set():
    assert set(GUIDE_ORIENTATIONS) == {"horizontal", "vertical"}


def test_guide_construction():
    g = Guide(orientation="vertical", position=50)
    assert g.position == 50


def test_guide_is_frozen():
    g = Guide(orientation="vertical", position=10)
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.position = 99  # type: ignore[misc]


def test_guide_rejects_unknown_orientation():
    with pytest.raises(ValueError, match="orientation"):
        Guide(orientation="diagonal", position=10)


def test_guide_rejects_oversized_color():
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        Guide(
            orientation="vertical", position=10,
            color=(300, 0, 0, 200),
        )


def test_guide_round_trip_via_dict():
    g = Guide(
        orientation="horizontal", position=42,
        color=(255, 0, 0, 200), visible=False,
    )
    rebuilt = Guide.from_dict(g.to_dict())
    assert rebuilt == g


def test_guide_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        Guide.from_dict("garbage")  # type: ignore[arg-type]  # NOSONAR — intentional negative-path test


def test_guide_from_dict_falls_back_for_unknown_orientation():
    rebuilt = Guide.from_dict({"orientation": "spiral", "position": 0})
    assert rebuilt.orientation == "vertical"


# ---------------------------------------------------------------------------
# GridSpec
# ---------------------------------------------------------------------------


def test_grid_spec_construction():
    g = GridSpec(minor_interval=10, major_every=5)
    assert g.minor_interval == 10
    assert g.major_every == 5


def test_grid_spec_rejects_undersized_minor():
    with pytest.raises(ValueError, match="minor_interval"):
        GridSpec(minor_interval=1)


def test_grid_spec_rejects_zero_major():
    with pytest.raises(ValueError, match="major_every"):
        GridSpec(minor_interval=10, major_every=0)


def test_grid_spec_round_trip_via_dict():
    g = GridSpec(
        minor_interval=20, major_every=4,
        minor_color=(100, 100, 100, 64),
        major_color=(255, 255, 255, 255),
    )
    rebuilt = GridSpec.from_dict(g.to_dict())
    assert rebuilt == g


def test_grid_spec_from_dict_clamps_oversized_interval():
    rebuilt = GridSpec.from_dict({"minor_interval": 999999})
    assert rebuilt.minor_interval <= 4096


def test_grid_spec_from_dict_falls_back_for_corrupt_color():
    rebuilt = GridSpec.from_dict({"minor_interval": 10, "major_color": "garbage"})
    assert rebuilt.major_color == DEFAULT_GRID_MAJOR_COLOR


# ---------------------------------------------------------------------------
# GuideSet
# ---------------------------------------------------------------------------


def test_guide_set_starts_empty():
    s = GuideSet()
    assert s.guides == []
    assert s.grid is None


def test_guide_set_add_remove():
    s = GuideSet()
    s.add_guide(Guide(orientation="vertical", position=10))
    assert len(s.guides) == 1
    assert s.remove_guide(0) is True
    assert s.guides == []


def test_guide_set_remove_out_of_range_returns_false():
    s = GuideSet()
    assert s.remove_guide(99) is False


def test_guide_set_clear_removes_grid_too():
    s = GuideSet(grid=GridSpec())
    s.add_guide(Guide(orientation="vertical", position=10))
    s.clear()
    assert s.guides == []
    assert s.grid is None


# ---------------------------------------------------------------------------
# render_overlay
# ---------------------------------------------------------------------------


def test_render_overlay_returns_canvas_sized_buffer():
    out = render_overlay((40, 60), GuideSet())
    assert out.shape == (40, 60, 4)
    assert out.dtype == np.uint8


def test_render_overlay_rejects_zero_canvas():
    with pytest.raises(ValueError, match="canvas_size"):
        render_overlay((0, 0), GuideSet())


def test_render_overlay_empty_guideset_is_blank():
    out = render_overlay((20, 20), GuideSet())
    assert out[..., 3].sum() == 0


def test_render_overlay_paints_vertical_guide():
    s = GuideSet()
    s.add_guide(Guide(orientation="vertical", position=10, color=(255, 0, 0, 200)))
    out = render_overlay((20, 30), s)
    # Column 10 has guide colour everywhere.
    assert (out[:, 10, 0] == 255).all()
    assert (out[:, 10, 3] == 200).all()
    # Other columns untouched.
    assert (out[:, 9, 3] == 0).all()


def test_render_overlay_paints_horizontal_guide():
    s = GuideSet()
    s.add_guide(Guide(orientation="horizontal", position=5, color=(0, 255, 0, 200)))
    out = render_overlay((20, 30), s)
    assert (out[5, :, 1] == 255).all()
    assert (out[6, :, 3] == 0).all()


def test_render_overlay_off_canvas_guide_is_clipped():
    s = GuideSet()
    s.add_guide(Guide(orientation="vertical", position=999))
    out = render_overlay((20, 30), s)
    assert out[..., 3].sum() == 0


def test_render_overlay_grid_paints_minor_lines():
    s = GuideSet(grid=GridSpec(minor_interval=10, major_every=5))
    out = render_overlay((50, 50), s)
    # Pick row 5 — between two grid rows so the horizontal pass
    # didn't overwrite the vertical pass's column lines.
    assert out[5, 10, 3] > 0     # minor grid line at col 10
    assert out[5, 11, 3] == 0    # between minor lines, untouched


def test_render_overlay_grid_major_color_at_major_interval():
    s = GuideSet(grid=GridSpec(
        minor_interval=10, major_every=5,
        minor_color=(0, 0, 0, 32),
        major_color=(255, 0, 0, 200),
    ))
    out = render_overlay((60, 60), s)
    # Sample row 5 (between two grid rows) — the vertical pass's
    # column colours stay readable there without horizontal overwrite.
    # x=0 is index 0 (major), x=10 is minor, x=50 is major (index 5).
    assert tuple(out[5, 0]) == (255, 0, 0, 200)
    assert tuple(out[5, 10]) == (0, 0, 0, 32)
    assert tuple(out[5, 50]) == (255, 0, 0, 200)


def test_render_overlay_invisible_grid_skipped():
    s = GuideSet(grid=GridSpec(minor_interval=10, visible=False))
    out = render_overlay((30, 30), s)
    assert out[..., 3].sum() == 0


def test_render_overlay_invisible_guide_skipped():
    s = GuideSet()
    s.add_guide(Guide(orientation="vertical", position=10, visible=False))
    out = render_overlay((20, 20), s)
    assert out[..., 3].sum() == 0


# ---------------------------------------------------------------------------
# Pixel grid + snap-to-pixel
# ---------------------------------------------------------------------------


def test_should_show_pixel_grid_threshold():
    from Imervue.paint.visual_guides import (
        PIXEL_GRID_MIN_ZOOM,
        should_show_pixel_grid,
    )
    assert not should_show_pixel_grid(1.0)
    assert not should_show_pixel_grid(PIXEL_GRID_MIN_ZOOM - 0.1)
    assert should_show_pixel_grid(PIXEL_GRID_MIN_ZOOM)
    assert should_show_pixel_grid(20.0)


def test_snap_to_pixel_rounds_to_nearest_centre():
    from Imervue.paint.visual_guides import snap_to_pixel
    # Pixel centres sit at integer + 0.5.
    assert snap_to_pixel(3.2, 4.7) == (3.5, 4.5)
    assert snap_to_pixel(0.0, 0.0) == (0.5, 0.5)


def test_snap_to_pixel_round_trip_at_centre():
    """A point already at a pixel centre should snap to itself."""
    from Imervue.paint.visual_guides import snap_to_pixel
    assert snap_to_pixel(7.5, 11.5) == (7.5, 11.5)


def test_snap_to_pixel_handles_negatives():
    from Imervue.paint.visual_guides import snap_to_pixel
    snapped = snap_to_pixel(-0.4, -2.7)
    assert snapped == (-0.5, -2.5)


# ---------------------------------------------------------------------------
# ToolState round-trip for snap_to_pixel
# ---------------------------------------------------------------------------


def test_tool_state_snap_to_pixel_default_is_false():
    from Imervue.paint.tool_state import ToolState
    state = ToolState()
    assert state.snap_to_pixel is False


def test_tool_state_snap_to_pixel_round_trips_via_dict():
    from Imervue.paint.tool_state import ToolState
    original = ToolState(snap_to_pixel=True)
    rebuilt = ToolState.from_dict(original.to_dict())
    assert rebuilt.snap_to_pixel is True


def test_tool_state_snap_to_pixel_default_when_missing():
    from Imervue.paint.tool_state import ToolState
    rebuilt = ToolState.from_dict({})
    assert rebuilt.snap_to_pixel is False


# ---------------------------------------------------------------------------
# Brush snap integration — pure logic via _snap
# ---------------------------------------------------------------------------


def test_brush_snap_pins_to_pixel_when_state_flag_on():
    from Imervue.paint.tool_dispatcher import BrushTool
    from Imervue.paint.tool_state import ToolState
    state = ToolState(snap_to_pixel=True)
    brush = BrushTool(state)
    snapped = brush._snap(3.2, 4.7)  # noqa: SLF001
    assert snapped == (3.5, 4.5)


def test_brush_snap_passes_through_when_state_flag_off():
    from Imervue.paint.tool_dispatcher import BrushTool
    from Imervue.paint.tool_state import ToolState
    state = ToolState(snap_to_pixel=False)
    brush = BrushTool(state)
    snapped = brush._snap(3.2, 4.7)  # noqa: SLF001
    assert snapped == (3.2, 4.7)
