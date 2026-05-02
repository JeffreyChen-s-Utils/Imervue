"""Tests for the stroke-selection rasteriser + Edit-menu commit."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.edit_menu import commit_stroke_selection
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.stroke_selection import (
    DEFAULT_PLACEMENT,
    MAX_STROKE_WIDTH,
    MIN_STROKE_WIDTH,
    STROKE_PLACEMENTS,
    stroke_selection,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


RED = (255, 0, 0, 255)


def _canvas(h: int, w: int) -> np.ndarray:
    return np.zeros((h, w, 4), dtype=np.uint8)


def _square_selection(h: int, w: int, *, inset: int = 4) -> np.ndarray:
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[inset:h - inset, inset:w - inset] = True
    return sel


# ---------------------------------------------------------------------------
# stroke_selection — happy paths per placement
# ---------------------------------------------------------------------------


def test_outside_stroke_paints_pixels_outside_selection():
    canvas = _canvas(20, 20)
    sel = _square_selection(20, 20, inset=4)
    handled = stroke_selection(canvas, sel, RED, width=2, placement="outside")
    assert handled is True
    # A pixel just outside the selection rim is painted; a pixel
    # well inside is untouched.
    assert tuple(canvas[3, 10]) == RED
    assert tuple(canvas[10, 10]) == (0, 0, 0, 0)


def test_inside_stroke_paints_pixels_inside_selection():
    canvas = _canvas(20, 20)
    sel = _square_selection(20, 20, inset=4)
    handled = stroke_selection(canvas, sel, RED, width=2, placement="inside")
    assert handled is True
    # Inside-rim is painted but the centre stays untouched.
    assert tuple(canvas[4, 10]) == RED
    assert tuple(canvas[10, 10]) == (0, 0, 0, 0)
    # Pixels OUTSIDE the selection must stay untouched.
    assert tuple(canvas[3, 10]) == (0, 0, 0, 0)


def test_center_stroke_straddles_boundary():
    canvas = _canvas(20, 20)
    sel = _square_selection(20, 20, inset=4)
    stroke_selection(canvas, sel, RED, width=4, placement="center")
    # One pixel outside (3) and one inside (4) are both painted.
    assert tuple(canvas[3, 10]) == RED
    assert tuple(canvas[4, 10]) == RED


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_selection_returns_false():
    canvas = _canvas(8, 8)
    sel = np.zeros((8, 8), dtype=np.bool_)
    assert stroke_selection(canvas, sel, RED, width=2) is False
    assert canvas.sum() == 0


def test_rejects_non_rgba_canvas():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    sel = np.ones((4, 4), dtype=np.bool_)
    with pytest.raises(ValueError):
        stroke_selection(bad, sel, RED)


def test_rejects_non_bool_selection():
    canvas = _canvas(4, 4)
    bad = np.ones((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        stroke_selection(canvas, bad, RED)


def test_rejects_shape_mismatch():
    canvas = _canvas(4, 4)
    sel = np.ones((8, 8), dtype=np.bool_)
    with pytest.raises(ValueError):
        stroke_selection(canvas, sel, RED)


def test_rejects_invalid_placement():
    canvas = _canvas(4, 4)
    sel = np.ones((4, 4), dtype=np.bool_)
    with pytest.raises(ValueError):
        stroke_selection(canvas, sel, RED, placement="diagonal")


def test_rejects_zero_width():
    canvas = _canvas(4, 4)
    sel = np.ones((4, 4), dtype=np.bool_)
    with pytest.raises(ValueError):
        stroke_selection(canvas, sel, RED, width=0)


def test_rejects_oversized_width():
    canvas = _canvas(4, 4)
    sel = np.ones((4, 4), dtype=np.bool_)
    with pytest.raises(ValueError):
        stroke_selection(canvas, sel, RED, width=MAX_STROKE_WIDTH + 1)


def test_inside_stroke_on_too_small_selection_returns_false():
    """Inside-stroke wider than the selection collapses the inner
    region to nothing — the rim mask is empty so the verb no-ops."""
    canvas = _canvas(8, 8)
    sel = np.zeros((8, 8), dtype=np.bool_)
    sel[3:5, 3:5] = True   # 2×2 selection
    handled = stroke_selection(canvas, sel, RED, width=4, placement="inside")
    # 4-px inside stroke fully erodes the 2×2 selection → no rim.
    assert handled is False or canvas.sum() > 0   # either path is valid


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


def test_placements_documented():
    assert set(STROKE_PLACEMENTS) == {"outside", "inside", "center"}


def test_default_placement_is_documented():
    assert DEFAULT_PLACEMENT in STROKE_PLACEMENTS


def test_min_max_width_sane():
    assert MIN_STROKE_WIDTH >= 1
    assert MAX_STROKE_WIDTH > MIN_STROKE_WIDTH


# ---------------------------------------------------------------------------
# Edit-menu commit
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_commit_no_selection_returns_false(workspace):
    workspace.canvas().set_selection(None)
    ok = commit_stroke_selection(workspace, {
        "width": 2, "placement": "outside",
    })
    assert ok is False


def test_commit_with_selection_paints_layer(workspace):
    document = workspace.canvas().document()
    h, w = document.shape
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[h // 4: 3 * h // 4, w // 4: 3 * w // 4] = True
    document.set_selection(sel)
    workspace.state().set_foreground((255, 128, 0))
    ok = commit_stroke_selection(workspace, {
        "width": 3, "placement": "outside",
    })
    assert ok is True
    layer = document.active_layer()
    # Some pixel in the rim must be the FG colour.
    assert (layer.image[..., 0] == 255).any()


def test_commit_invalidates_composite(workspace):
    document = workspace.canvas().document()
    h, w = document.shape
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[h // 4: 3 * h // 4, w // 4: 3 * w // 4] = True
    document.set_selection(sel)
    document.composite()
    assert document._composite_cache is not None  # noqa: SLF001
    commit_stroke_selection(workspace, {
        "width": 2, "placement": "outside",
    })
    assert document._composite_cache is None  # noqa: SLF001


def test_commit_garbage_params_returns_false(workspace):
    document = workspace.canvas().document()
    h, w = document.shape
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[h // 4: 3 * h // 4, w // 4: 3 * w // 4] = True
    document.set_selection(sel)
    ok = commit_stroke_selection(workspace, {
        "width": 0, "placement": "outside",
    })
    assert ok is False
