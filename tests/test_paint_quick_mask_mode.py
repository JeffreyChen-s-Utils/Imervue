"""Tests for the Quick Mask toggle (24e).

The pure overlay helpers (``quick_mask_overlay``,
``selection_from_quick_mask``) already have their own tests; this
module focuses on the new toggle-mode hand-off (``enter_mode`` /
``exit_mode``) and the workspace-level wiring through the Edit menu.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.quick_mask import (
    QUICK_MASK_PROXY_RGB,
    QuickMaskState,
    enter_mode,
    exit_mode,
    make_proxy_buffer,
    selection_from_proxy,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _layer(h: int = 8, w: int = 8) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = (50, 100, 150)
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# make_proxy_buffer
# ---------------------------------------------------------------------------


def test_proxy_buffer_has_red_tint_and_zero_alpha_when_no_selection():
    buf = make_proxy_buffer((4, 4), None)
    assert buf.shape == (4, 4, 4)
    assert buf.dtype == np.uint8
    # RGB pre-baked at the documented overlay tint.
    assert tuple(buf[0, 0, :3]) == QUICK_MASK_PROXY_RGB
    # Alpha is zero — nothing is selected yet.
    assert (buf[..., 3] == 0).all()


def test_proxy_buffer_alpha_tracks_selection():
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[0, 0] = True
    sel[2, 2] = True
    buf = make_proxy_buffer((4, 4), sel)
    assert int(buf[0, 0, 3]) == 255
    assert int(buf[2, 2, 3]) == 255
    assert int(buf[1, 1, 3]) == 0


def test_proxy_buffer_rejects_shape_mismatch():
    sel = np.zeros((2, 4), dtype=np.bool_)
    with pytest.raises(ValueError):
        make_proxy_buffer((4, 4), sel)


def test_proxy_buffer_rejects_zero_dimensions():
    with pytest.raises(ValueError):
        make_proxy_buffer((0, 4), None)


# ---------------------------------------------------------------------------
# selection_from_proxy
# ---------------------------------------------------------------------------


def test_selection_round_trips_via_default_threshold():
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[0, 0] = True
    buf = make_proxy_buffer((4, 4), sel)
    out = selection_from_proxy(buf)
    np.testing.assert_array_equal(out, sel)


def test_selection_threshold_governs_partial_alpha():
    """Pixels with alpha 64 should NOT count at default threshold but
    DO count at threshold=32."""
    buf = np.zeros((2, 2, 4), dtype=np.uint8)
    buf[0, 0, 3] = 64
    high = selection_from_proxy(buf, threshold=128)
    low = selection_from_proxy(buf, threshold=32)
    assert high[0, 0] is np.False_ or not bool(high[0, 0])
    assert bool(low[0, 0])


def test_selection_from_proxy_rejects_non_rgba():
    bad = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        selection_from_proxy(bad)


def test_selection_from_proxy_rejects_out_of_range_threshold():
    buf = np.zeros((2, 2, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        selection_from_proxy(buf, threshold=300)


# ---------------------------------------------------------------------------
# enter_mode / exit_mode round-trip
# ---------------------------------------------------------------------------


def test_enter_mode_snapshot_preserves_layer_image():
    layer = _layer()
    state = enter_mode(layer, None, layer_index=2)
    assert state.layer_index == 2
    np.testing.assert_array_equal(state.original_image, layer)
    # The snapshot must be a copy, not an alias.
    layer[0, 0] = 0
    assert int(state.original_image[0, 0, 0]) != 0


def test_enter_mode_buffer_inherits_selection():
    layer = _layer(4, 4)
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[0, 0] = True
    state = enter_mode(layer, sel)
    assert int(state.buffer[0, 0, 3]) == 255
    assert int(state.buffer[1, 1, 3]) == 0


def test_enter_mode_rejects_non_rgba_layer():
    bad = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        enter_mode(bad, None)


def test_exit_mode_round_trips_unchanged_buffer_to_input_selection():
    layer = _layer(4, 4)
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[1, 1] = True
    state = enter_mode(layer, sel, layer_index=0)
    restored, derived = exit_mode(state)
    np.testing.assert_array_equal(restored, layer)
    np.testing.assert_array_equal(derived, sel)


def test_exit_mode_picks_up_painted_alpha_changes():
    """Simulate the user painting on the proxy by writing alpha
    directly; exit_mode must surface those pixels in the new
    selection."""
    layer = _layer(8, 8)
    state = enter_mode(layer, None)
    # Paint a 2×2 square in the middle.
    state.buffer[3:5, 3:5, 3] = 255
    _, sel = exit_mode(state)
    assert sel[3, 3] is np.True_ or bool(sel[3, 3])
    assert not bool(sel[0, 0])


# ---------------------------------------------------------------------------
# Workspace toggle
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_workspace_starts_with_quick_mask_off(workspace):
    assert workspace.is_quick_mask_active() is False


def test_enter_quick_mask_swaps_layer_image(workspace):
    canvas = workspace.canvas()
    document = canvas.document()
    layer = document.active_layer()
    original_image_id = id(layer.image)
    assert workspace.enter_quick_mask() is True
    assert workspace.is_quick_mask_active()
    # Layer's image was replaced with the proxy buffer.
    assert id(layer.image) != original_image_id


def test_exit_quick_mask_restores_image_and_writes_selection(workspace):
    canvas = workspace.canvas()
    document = canvas.document()
    layer = document.active_layer()
    snapshot = layer.image.copy()
    workspace.enter_quick_mask()
    # Paint a small region into the proxy alpha.
    layer.image[2:6, 2:6, 3] = 255
    assert workspace.exit_quick_mask() is True
    assert workspace.is_quick_mask_active() is False
    # Original pixels restored.
    np.testing.assert_array_equal(layer.image, snapshot)
    # Selection now matches the painted region.
    selection = canvas.current_selection()
    assert selection is not None
    assert bool(selection[3, 3])
    assert not bool(selection[0, 0])


def test_enter_twice_is_noop(workspace):
    assert workspace.enter_quick_mask() is True
    assert workspace.enter_quick_mask() is False


def test_exit_when_inactive_is_noop(workspace):
    assert workspace.exit_quick_mask() is False


def test_edit_menu_toggle_flips_state(workspace):
    bridge = workspace._edit_menu_bridge   # noqa: SLF001
    assert workspace.is_quick_mask_active() is False
    bridge.toggle_quick_mask()
    assert workspace.is_quick_mask_active() is True
    bridge.toggle_quick_mask()
    assert workspace.is_quick_mask_active() is False


def test_edit_menu_action_check_state_follows(workspace):
    bridge = workspace._edit_menu_bridge   # noqa: SLF001
    bridge.toggle_quick_mask()
    assert bridge._quick_mask_action.isChecked() is True   # noqa: SLF001
    bridge.toggle_quick_mask()
    assert bridge._quick_mask_action.isChecked() is False   # noqa: SLF001


# ---------------------------------------------------------------------------
# QuickMaskState shape exposure
# ---------------------------------------------------------------------------


def test_state_shape_property_returns_buffer_shape():
    layer = _layer(3, 5)
    state = enter_mode(layer, None)
    assert state.shape == (3, 5)


def test_quick_mask_state_dataclass_fields():
    state = QuickMaskState(
        layer_index=0,
        original_image=np.zeros((2, 2, 4), dtype=np.uint8),
        buffer=np.zeros((2, 2, 4), dtype=np.uint8),
    )
    assert state.layer_index == 0
    assert state.original_image.shape == (2, 2, 4)
    assert state.buffer.shape == (2, 2, 4)
