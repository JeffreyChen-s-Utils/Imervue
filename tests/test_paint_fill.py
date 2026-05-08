"""Tests for the flood fill bucket algorithm and its dispatcher hook."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.fill import FillResult, flood_fill
from Imervue.paint.tool_dispatcher import FillTool
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def chequer_canvas():
    """16×16 canvas with a black square inset on white background."""
    arr = np.full((16, 16, 4), 255, dtype=np.uint8)
    arr[4:12, 4:12, :3] = 0    # black square in the middle
    return arr


# ---------------------------------------------------------------------------
# flood_fill — input validation
# ---------------------------------------------------------------------------


def test_fill_rejects_non_rgba(sample_rgb_array):
    with pytest.raises(ValueError):
        flood_fill(sample_rgb_array, 0, 0, (255, 0, 0))


def test_fill_seed_off_canvas_returns_empty(chequer_canvas):
    out = flood_fill(chequer_canvas, -1, -1, (255, 0, 0))
    assert out.is_empty


def test_fill_clamps_negative_tolerance(chequer_canvas):
    a = flood_fill(chequer_canvas.copy(), 0, 0, (255, 0, 0), tolerance=0)
    b = flood_fill(chequer_canvas.copy(), 0, 0, (255, 0, 0), tolerance=-50)
    assert a.pixels_filled == b.pixels_filled


def test_fill_clamps_huge_tolerance(chequer_canvas):
    a = flood_fill(chequer_canvas.copy(), 0, 0, (255, 0, 0), tolerance=255)
    b = flood_fill(chequer_canvas.copy(), 0, 0, (255, 0, 0), tolerance=10_000)
    assert a.pixels_filled == b.pixels_filled


# ---------------------------------------------------------------------------
# Contiguous fill
# ---------------------------------------------------------------------------


def test_contiguous_fill_only_floods_seed_region(chequer_canvas):
    canvas = chequer_canvas.copy()
    out = flood_fill(canvas, 0, 0, (200, 0, 0), tolerance=0, contiguous=True)
    # White ring around the square is filled red.
    assert canvas[0, 0, 0] == 200
    # Inner black square untouched.
    assert canvas[6, 6, 0] == 0
    assert out.pixels_filled == (16 * 16) - (8 * 8)


def test_contiguous_fill_inside_returns_only_inner_square(chequer_canvas):
    canvas = chequer_canvas.copy()
    out = flood_fill(canvas, 6, 6, (0, 0, 200), tolerance=0, contiguous=True)
    assert out.pixels_filled == 8 * 8
    assert canvas[0, 0, 2] == 255   # outer ring untouched
    assert canvas[6, 6, 2] == 200


def test_contiguous_fill_records_full_alpha(chequer_canvas):
    canvas = chequer_canvas.copy()
    canvas[..., 3] = 0
    flood_fill(canvas, 0, 0, (50, 50, 50), tolerance=0)
    assert canvas[0, 0, 3] == 255


def test_contiguous_fill_isolated_seed_pixel():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[0, 0, 0] = 100
    out = flood_fill(canvas, 0, 0, (10, 20, 30), tolerance=0)
    # Only one pixel matched (R=100); others have R=0.
    assert out.pixels_filled == 1


# ---------------------------------------------------------------------------
# Global fill
# ---------------------------------------------------------------------------


def test_global_fill_paints_disconnected_islands():
    canvas = np.full((6, 6, 4), 255, dtype=np.uint8)
    canvas[1, 1, :3] = (10, 10, 10)
    canvas[4, 4, :3] = (10, 10, 10)
    out = flood_fill(canvas, 1, 1, (200, 0, 0), tolerance=0, contiguous=False)
    assert out.pixels_filled == 2
    assert canvas[1, 1, 0] == 200
    assert canvas[4, 4, 0] == 200


def test_global_fill_with_tolerance_picks_up_near_matches():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[0, 0, :3] = (100, 100, 100)
    canvas[3, 3, :3] = (110, 110, 110)
    out = flood_fill(canvas, 0, 0, (200, 0, 0), tolerance=15, contiguous=False)
    assert out.pixels_filled == 2


# ---------------------------------------------------------------------------
# FillResult
# ---------------------------------------------------------------------------


def test_fill_result_empty_property():
    assert FillResult(0, 0, 0, 0, 0).is_empty is True
    assert FillResult(0, 0, 4, 4, 16).is_empty is False


# ---------------------------------------------------------------------------
# FillTool dispatcher
# ---------------------------------------------------------------------------


def test_fill_tool_runs_on_press(chequer_canvas):
    state = ts.load_tool_state()
    state.set_foreground((255, 0, 0))
    state.set_fill(tolerance=0, contiguous=True)
    tool = FillTool(state)
    evt = PointerEvent(phase="press", x=0, y=0, button=1, modifiers=0, pressure=1.0)
    canvas = chequer_canvas.copy()
    assert tool.handle(evt, canvas) is True
    assert canvas[0, 0, 0] == 255


def test_fill_tool_ignores_move(chequer_canvas):
    state = ts.load_tool_state()
    tool = FillTool(state)
    evt = PointerEvent(phase="move", x=0, y=0, button=1, modifiers=0, pressure=1.0)
    canvas = chequer_canvas.copy()
    assert tool.handle(evt, canvas) is False


# ---------------------------------------------------------------------------
# ToolState fill round-trip
# ---------------------------------------------------------------------------


def test_set_fill_persists_to_dict():
    state = ts.load_tool_state()
    state.set_fill(tolerance=128, contiguous=False, sample_all_layers=True)
    raw = user_setting_dict["paint_state"]
    assert raw["fill"]["tolerance"] == 128
    assert raw["fill"]["contiguous"] is False
    assert raw["fill"]["sample_all_layers"] is True


def test_set_fill_round_trips_via_to_from_dict():
    state = ts.load_tool_state()
    state.set_fill(tolerance=64, contiguous=False)
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.fill.tolerance == 64
    assert rebuilt.fill.contiguous is False


def test_set_fill_clamps_tolerance_above_max():
    state = ts.load_tool_state()
    state.set_fill(tolerance=ts.FILL_TOLERANCE_MAX + 100)
    assert state.fill.tolerance == ts.FILL_TOLERANCE_MAX


def test_set_fill_idempotent_returns_false():
    state = ts.load_tool_state()
    state.set_fill(tolerance=64)
    assert state.set_fill(tolerance=64) is False


def test_set_fill_rejects_unknown_attribute():
    state = ts.load_tool_state()
    with pytest.raises(ValueError):
        state.set_fill(magic_wand_size=8)


# ---------------------------------------------------------------------------
# Reference-layer fill — bucket samples a separate buffer for boundaries
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_target_canvas():
    """Fully-transparent 16x16 RGBA buffer — like a blank colour layer."""
    return np.zeros((16, 16, 4), dtype=np.uint8)


@pytest.fixture
def lineart_reference():
    """White 16x16 with an opaque-black ring around a transparent inner.

    The reference looks like a comic-style closed region: a black
    pen-stroke loop on a transparent canvas. The inside (rows/cols
    5..10) and the outside (rows/cols < 4 or > 11) are both
    transparent and connected only via the ink ring — but the ink
    has alpha 255 on top of a placeholder colour, so a fill seeded
    inside the ring should NOT escape across the ink.
    """
    ref = np.zeros((16, 16, 4), dtype=np.uint8)
    # outer + inner are transparent (alpha 0)
    # ring rows / cols 4 and 11 painted black + opaque
    ref[4:12, 4, :] = (0, 0, 0, 255)
    ref[4:12, 11, :] = (0, 0, 0, 255)
    ref[4, 4:12, :] = (0, 0, 0, 255)
    ref[11, 4:12, :] = (0, 0, 0, 255)
    return ref


def test_reference_fill_paints_target_inside_ring(
    empty_target_canvas, lineart_reference,
):
    canvas = empty_target_canvas.copy()
    out = flood_fill(
        canvas, 7, 7, (255, 0, 0),
        tolerance=0, contiguous=True,
        reference_image=lineart_reference,
    )
    # Inside the ring is fully painted red; the ink ring itself stays
    # untouched on the target canvas.
    assert canvas[7, 7, 0] == 255
    assert canvas[7, 7, 3] == 255
    assert canvas[4, 4, 3] == 0   # ink-ring pixel on the target is still empty
    # 6x6 inside, minus pixels that fell on the ring border itself.
    assert out.pixels_filled == 6 * 6


def test_reference_fill_does_not_cross_opaque_ink(
    empty_target_canvas, lineart_reference,
):
    canvas = empty_target_canvas.copy()
    flood_fill(
        canvas, 0, 0, (0, 200, 0),
        tolerance=0, contiguous=True,
        reference_image=lineart_reference,
    )
    # Outside the ring is filled green; inside stays empty because the
    # ink ring blocks the flood.
    assert canvas[0, 0, 1] == 200
    assert canvas[7, 7, 3] == 0


def test_reference_fill_rejects_shape_mismatch(empty_target_canvas):
    bad = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        flood_fill(
            empty_target_canvas, 0, 0, (1, 2, 3),
            reference_image=bad,
        )


def test_reference_fill_rejects_wrong_channel_count(empty_target_canvas):
    bad = np.zeros((16, 16, 2), dtype=np.uint8)
    with pytest.raises(ValueError):
        flood_fill(
            empty_target_canvas, 0, 0, (1, 2, 3),
            reference_image=bad,
        )


def test_reference_fill_accepts_rgb_reference(empty_target_canvas):
    """A 3-channel reference is also valid — alpha is implicit-opaque."""
    ref = np.full((16, 16, 3), 255, dtype=np.uint8)
    ref[7, 7] = (0, 0, 0)
    canvas = empty_target_canvas.copy()
    out = flood_fill(
        canvas, 0, 0, (10, 20, 30),
        tolerance=0, contiguous=True,
        reference_image=ref,
    )
    # White everywhere except the single black pixel — fill covers
    # 16*16 - 1 pixels.
    assert out.pixels_filled == 16 * 16 - 1


# ---------------------------------------------------------------------------
# Expand (anti-overflow) — dilate fill mask by N px before painting
# ---------------------------------------------------------------------------


def test_expand_grows_fill_into_anti_aliased_halo():
    canvas = np.full((10, 10, 4), 255, dtype=np.uint8)
    canvas[..., 3] = 255
    # Anti-aliased halo: a ring of grey-150 around a black core.
    canvas[3:7, 3:7, :3] = 0      # opaque black core
    canvas[2:8, 2:8, 0] = np.where(
        canvas[2:8, 2:8, 0] == 0, 0, 150,
    )
    out = flood_fill(
        canvas.copy(), 3, 3, (200, 0, 0),
        tolerance=0, contiguous=True, expand=0,
    )
    out_expanded = flood_fill(
        canvas.copy(), 3, 3, (200, 0, 0),
        tolerance=0, contiguous=True, expand=2,
    )
    # Expanding strictly grows the fill region (or leaves it equal at the
    # canvas border).
    assert out_expanded.pixels_filled > out.pixels_filled


def test_expand_zero_is_noop(chequer_canvas):
    a = flood_fill(
        chequer_canvas.copy(), 0, 0, (200, 0, 0),
        tolerance=0, contiguous=True, expand=0,
    )
    b = flood_fill(
        chequer_canvas.copy(), 0, 0, (200, 0, 0),
        tolerance=0, contiguous=True,
    )
    assert a.pixels_filled == b.pixels_filled


def test_expand_rejects_negative():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        flood_fill(canvas, 0, 0, (1, 2, 3), expand=-1)


def test_expand_rejects_above_max():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    from Imervue.paint.fill import MAX_EXPAND
    with pytest.raises(ValueError):
        flood_fill(canvas, 0, 0, (1, 2, 3), expand=MAX_EXPAND + 1)


def test_expand_clipped_by_selection():
    """Expanded mask must still respect the active selection."""
    canvas = np.full((10, 10, 4), 255, dtype=np.uint8)
    canvas[..., :3] = 0   # black canvas — global match within tolerance 0
    selection = np.zeros((10, 10), dtype=np.bool_)
    selection[2:5, 2:5] = True   # only a 3x3 region is selectable
    flood_fill(
        canvas, 3, 3, (200, 0, 0),
        tolerance=0, contiguous=False, expand=4,
        selection=selection,
    )
    # Outside the selection must remain untouched even though dilation
    # would otherwise spill across it.
    assert canvas[0, 0, 0] == 0   # untouched
    assert canvas[3, 3, 0] == 200 # filled inside the selection


# ---------------------------------------------------------------------------
# FillTool dispatcher honours the new options
# ---------------------------------------------------------------------------


def test_fill_tool_uses_reference_provider_when_enabled(
    empty_target_canvas, lineart_reference,
):
    state = ts.load_tool_state()
    state.set_foreground((0, 100, 200))
    state.set_fill(tolerance=0, contiguous=True, use_reference_layer=True)
    tool = FillTool(
        state,
        selection_provider=lambda: None,
        reference_provider=lambda: lineart_reference,
    )
    canvas = empty_target_canvas.copy()
    evt = PointerEvent(
        phase="press", x=7, y=7, button=1, modifiers=0, pressure=1.0,
    )
    assert tool.handle(evt, canvas) is True
    assert canvas[7, 7, 0] == 0
    assert canvas[7, 7, 2] == 200


def test_fill_tool_ignores_reference_when_flag_off(
    empty_target_canvas, lineart_reference,
):
    """Reference is only consulted while ``use_reference_layer`` is on."""
    state = ts.load_tool_state()
    state.set_foreground((0, 100, 200))
    state.set_fill(tolerance=0, contiguous=True, use_reference_layer=False)
    tool = FillTool(
        state,
        selection_provider=lambda: None,
        reference_provider=lambda: lineart_reference,
    )
    canvas = empty_target_canvas.copy()
    evt = PointerEvent(
        phase="press", x=7, y=7, button=1, modifiers=0, pressure=1.0,
    )
    # Without a reference the empty target floods entirely with the
    # foreground colour.
    assert tool.handle(evt, canvas) is True
    assert canvas[0, 0, 2] == 200


def test_fill_settings_round_trip_includes_new_fields():
    state = ts.load_tool_state()
    state.set_fill(expand_px=5, use_reference_layer=True)
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.fill.expand_px == 5
    assert rebuilt.fill.use_reference_layer is True


def test_fill_settings_clamps_expand_above_max():
    state = ts.load_tool_state()
    state.set_fill(expand_px=ts.FILL_EXPAND_MAX + 99)
    assert state.fill.expand_px == ts.FILL_EXPAND_MAX


def test_fill_settings_clamps_expand_below_zero():
    state = ts.load_tool_state()
    state.set_fill(expand_px=-5)
    assert state.fill.expand_px == ts.FILL_EXPAND_MIN


# ---------------------------------------------------------------------------
# Color Drop — morphological closing of broken-line gaps
# ---------------------------------------------------------------------------


@pytest.fixture
def gappy_lineart_canvas():
    """20x20 canvas with a closed black box that has a 1px gap on the
    right wall — a regular flood from inside leaks straight out.
    """
    arr = np.full((20, 20, 4), 255, dtype=np.uint8)
    # Top, bottom, left walls fully closed.
    arr[5, 5:16, :3] = 0
    arr[14, 5:16, :3] = 0
    arr[5:15, 5, :3] = 0
    # Right wall has a 1-pixel hole at row 9.
    arr[5:9, 15, :3] = 0
    arr[10:15, 15, :3] = 0
    return arr


def test_regular_fill_leaks_through_gap(gappy_lineart_canvas):
    canvas = gappy_lineart_canvas.copy()
    flood_fill(canvas, 8, 9, (200, 0, 0), tolerance=0, contiguous=True)
    # The leak reaches the canvas's far edge.
    assert (canvas[0, 0, 0] == 200) or (canvas[19, 19, 0] == 200)


def test_gap_close_contains_fill_inside_box(gappy_lineart_canvas):
    canvas = gappy_lineart_canvas.copy()
    flood_fill(
        canvas, 8, 9, (200, 0, 0),
        tolerance=0, contiguous=True, gap_close=2,
    )
    # Outside the box stays white.
    assert canvas[0, 0, 0] == 255
    assert canvas[19, 19, 0] == 255
    # Inside the box is painted.
    assert canvas[8, 9, 0] == 200


def test_gap_close_zero_is_noop():
    """Without gap_close the fill behaves exactly like the existing path."""
    canvas = np.full((10, 10, 4), 255, dtype=np.uint8)
    canvas[..., :3] = 0
    a = canvas.copy()
    b = canvas.copy()
    out_a = flood_fill(a, 0, 0, (200, 0, 0), tolerance=0, gap_close=0)
    out_b = flood_fill(b, 0, 0, (200, 0, 0), tolerance=0)
    assert out_a.pixels_filled == out_b.pixels_filled


def test_gap_close_rejects_negative():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        flood_fill(canvas, 0, 0, (1, 2, 3), gap_close=-1)


def test_gap_close_rejects_above_max():
    from Imervue.paint.fill import MAX_GAP_CLOSE
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        flood_fill(canvas, 0, 0, (1, 2, 3), gap_close=MAX_GAP_CLOSE + 1)


def test_gap_close_too_small_does_not_close_wide_gap():
    """A gap wider than ``2 * gap_close`` must remain open — the
    documented trade-off of the dilation-based bridge."""
    arr = np.full((20, 20, 4), 255, dtype=np.uint8)
    arr[5, 5:16, :3] = 0
    arr[14, 5:16, :3] = 0
    arr[5:15, 5, :3] = 0
    # 5-pixel-wide gap on the right wall: only rows 5..8 + 14 of col
    # 15 are inked; rows 9..13 are open. gap_close=1 dilates by 1 on
    # each side which can't bridge 5 pixels.
    arr[5:9, 15, :3] = 0
    arr[14, 15, :3] = 0
    canvas = arr.copy()
    flood_fill(
        canvas, 8, 9, (200, 0, 0),
        tolerance=0, contiguous=True, gap_close=1,
    )
    # Leak still happens because the gap is too wide for a 1-px close.
    assert (canvas[0, 0, 0] == 200) or (canvas[19, 19, 0] == 200)


def test_fill_settings_round_trip_includes_gap_close():
    state = ts.load_tool_state()
    state.set_fill(gap_close_px=4)
    rebuilt = ts.ToolState.from_dict(state.to_dict())
    assert rebuilt.fill.gap_close_px == 4


def test_fill_settings_clamps_gap_close_above_max():
    state = ts.load_tool_state()
    state.set_fill(gap_close_px=ts.FILL_GAP_CLOSE_MAX + 50)
    assert state.fill.gap_close_px == ts.FILL_GAP_CLOSE_MAX


def test_fill_settings_clamps_gap_close_below_zero():
    state = ts.load_tool_state()
    state.set_fill(gap_close_px=-5)
    assert state.fill.gap_close_px == ts.FILL_GAP_CLOSE_MIN


def test_fill_tool_uses_gap_close_setting(gappy_lineart_canvas):
    state = ts.load_tool_state()
    state.set_foreground((100, 0, 0))
    state.set_fill(tolerance=0, contiguous=True, gap_close_px=2)
    tool = FillTool(state)
    canvas = gappy_lineart_canvas.copy()
    evt = PointerEvent(
        phase="press", x=8, y=9, button=1, modifiers=0, pressure=1.0,
    )
    assert tool.handle(evt, canvas) is True
    # Outside the box stays white — gap_close prevented the leak.
    assert canvas[0, 0, 0] == 255


# ---------------------------------------------------------------------------
# Alpha-boundary respect — eraser leaves lingering RGB; the bucket
# must not bleed across the alpha=0 / alpha>0 transition or it would
# repaint the strokes the user just erased.
# ---------------------------------------------------------------------------


def test_fill_does_not_bleed_across_erased_region():
    """Seed on an opaque pixel; an erased band on the same RGB must
    block the flood instead of letting the bucket repaint the
    eraser's leftovers."""
    arr = np.zeros((4, 8, 4), dtype=np.uint8)
    arr[..., :3] = (200, 50, 50)
    arr[..., 3] = 255              # all opaque red
    # Erase a 4-pixel-wide vertical band in the middle.
    arr[:, 3:5, 3] = 0
    flood_fill(arr, 0, 0, (10, 20, 30), tolerance=0, contiguous=True)
    # Left half is repainted; the erased middle band stays untouched
    # (alpha 0, RGB still red); the right half is unreached.
    assert (arr[:, 0:3, :3] == (10, 20, 30)).all()
    assert (arr[:, 3:5, 0] == 200).all()       # erased RGB preserved
    assert (arr[:, 3:5, 3] == 0).all()         # still erased
    assert (arr[:, 5:8, :3] == (200, 50, 50)).all()  # right half untouched


def test_fill_seed_on_erased_pixel_fills_only_transparent_region():
    """Seeding the bucket on an alpha=0 pixel must restrict the flood
    to the connected transparent region — opaque neighbours act as a
    wall even when they share the lingering RGB."""
    arr = np.zeros((4, 6, 4), dtype=np.uint8)
    arr[..., :3] = (123, 45, 67)
    arr[..., 3] = 255
    # Erase a 2x2 hole in the middle.
    arr[1:3, 2:4, 3] = 0
    flood_fill(arr, 2, 1, (250, 250, 250), tolerance=0, contiguous=True)
    # Hole is now opaque white; surrounding still original red.
    assert (arr[1:3, 2:4, :3] == (250, 250, 250)).all()
    assert (arr[1:3, 2:4, 3] == 255).all()
    # Outside the hole is unchanged.
    assert (arr[0, :, :3] == (123, 45, 67)).all()


def test_fill_global_mode_also_respects_alpha_boundary():
    """Non-contiguous fill (whole-canvas match) must also drop the
    erased pixels from the candidate set, otherwise the bucket would
    repaint them as a side-effect of matching their lingering RGB."""
    arr = np.zeros((3, 6, 4), dtype=np.uint8)
    arr[..., :3] = (200, 200, 200)
    arr[..., 3] = 255
    arr[:, 2:4, 3] = 0
    flood_fill(arr, 0, 0, (5, 10, 15), tolerance=0, contiguous=False)
    # The erased band keeps alpha 0 and RGB stays as it was.
    assert (arr[:, 2:4, 3] == 0).all()
    assert (arr[:, 2:4, 0] == 200).all()
    # Visible pixels became the new colour.
    assert (arr[:, 0:2, :3] == (5, 10, 15)).all()
    assert (arr[:, 4:6, :3] == (5, 10, 15)).all()


def test_fill_blank_layer_seed_fills_entire_layer():
    """Filling a freshly-cleared layer (every pixel alpha=0) from any
    seed point still floods the whole canvas — the alpha gate keeps
    the candidate set on the transparent side, which IS the entire
    canvas, so no regression for the new-layer case."""
    arr = np.zeros((5, 5, 4), dtype=np.uint8)
    flood_fill(arr, 2, 2, (0, 128, 255), tolerance=0, contiguous=True)
    assert (arr[..., :3] == (0, 128, 255)).all()
    assert (arr[..., 3] == 255).all()
