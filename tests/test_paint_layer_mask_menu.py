"""Tests for the layer-mask Layer-menu actions.

The model verbs (``add_layer_mask``, ``clear_layer_mask`` etc.) are
already covered by the document tests; this file pins down the
bridge that maps menu actions onto those verbs and refreshes the
canvas afterwards.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def _bridge(ws):
    return ws._layer_menu_bridge  # noqa: SLF001


# ---------------------------------------------------------------------------
# add_mask + variants
# ---------------------------------------------------------------------------


def test_add_mask_attaches_white_mask_to_active_layer(workspace):
    document = workspace.canvas().document()
    layer = document.active_layer()
    assert layer.mask is None
    _bridge(workspace).add_mask()
    assert layer.mask is not None
    # Default fill is fully visible (255) so the layer keeps showing.
    assert (layer.mask == 255).all()


def test_add_mask_replaces_existing_mask(workspace):
    document = workspace.canvas().document()
    layer = document.active_layer()
    document.add_layer_mask()
    layer.mask[:] = 0
    _bridge(workspace).add_mask()
    # Should have re-initialised to fully visible.
    assert (layer.mask == 255).all()


def test_add_mask_from_selection_uses_active_selection(workspace):
    document = workspace.canvas().document()
    h, w = document.shape
    mask = np.zeros((h, w), dtype=np.bool_)
    mask[: h // 2, : w // 2] = True
    workspace.canvas().set_selection(mask)
    _bridge(workspace).add_mask_from_selection()
    layer = document.active_layer()
    assert layer.mask is not None
    # Selected region → 255, rest → 0.
    assert (layer.mask[: h // 2, : w // 2] == 255).all()
    assert (layer.mask[h // 2:, w // 2:] == 0).all()


def test_add_mask_from_selection_with_no_selection_full_visible(workspace):
    document = workspace.canvas().document()
    workspace.canvas().set_selection(None)
    _bridge(workspace).add_mask_from_selection()
    assert (document.active_layer().mask == 255).all()


# ---------------------------------------------------------------------------
# delete_mask
# ---------------------------------------------------------------------------


def test_delete_mask_removes_existing_mask(workspace):
    document = workspace.canvas().document()
    document.add_layer_mask()
    assert document.active_layer().mask is not None
    _bridge(workspace).delete_mask()
    assert document.active_layer().mask is None


def test_delete_mask_with_no_mask_is_noop(workspace):
    document = workspace.canvas().document()
    layer = document.active_layer()
    assert layer.mask is None
    _bridge(workspace).delete_mask()  # must not crash
    assert layer.mask is None


# ---------------------------------------------------------------------------
# invert_mask
# ---------------------------------------------------------------------------


def test_invert_mask_bitwise_flips_values(workspace):
    document = workspace.canvas().document()
    document.add_layer_mask(fill=64)
    _bridge(workspace).invert_mask()
    # Every pixel was 64; should now be 255 - 64 == 191.
    assert (document.active_layer().mask == 191).all()


def test_invert_mask_with_no_mask_is_noop(workspace):
    _bridge(workspace).invert_mask()  # must not crash


# ---------------------------------------------------------------------------
# apply_mask — bakes mask into alpha and clears the mask
# ---------------------------------------------------------------------------


def test_apply_mask_bakes_into_alpha(workspace):
    document = workspace.canvas().document()
    layer = document.active_layer()
    # Make the layer fully opaque first.
    layer.image[..., 3] = 255
    document.add_layer_mask(fill=128)
    _bridge(workspace).apply_mask()
    # alpha *= 128/255 → ~128
    assert layer.mask is None
    assert int(layer.image[0, 0, 3]) in range(127, 130)


def test_apply_mask_with_no_mask_is_noop(workspace):
    _bridge(workspace).apply_mask()  # must not crash


# ---------------------------------------------------------------------------
# Composite uses the mask
# ---------------------------------------------------------------------------


def test_composite_respects_layer_mask(workspace):
    """A 0-fill mask must hide the layer entirely; a 255-fill mask
    must leave the composite unchanged."""
    document = workspace.canvas().document()
    layer = document.active_layer()
    layer.image[..., :3] = (200, 0, 0)
    layer.image[..., 3] = 255
    composite_visible = document.composite().copy()
    document.add_layer_mask(fill=0)
    document.invalidate_composite()
    composite_hidden = document.composite()
    assert not np.array_equal(composite_visible, composite_hidden)
