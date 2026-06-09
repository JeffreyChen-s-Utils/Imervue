"""Tests for the Layer-menu effect-add bridge.

The renderer (drop_shadow / outer_glow / stroke) is exercised in
``test_paint_layer_effects.py`` already; this file pins the
workspace-level wiring so the user clicks the menu and the active
layer's ``effects`` tuple changes.
"""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.layer_effects import EFFECT_KINDS, LayerEffect
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


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
    return ws._layer_menu_bridge   # noqa: SLF001


# ---------------------------------------------------------------------------
# add_drop_shadow / add_outer_glow / add_stroke
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind,method_name", [
    ("drop_shadow", "add_drop_shadow"),
    ("outer_glow", "add_outer_glow"),
    ("stroke", "add_stroke"),
])
def test_add_effect_appends_to_layer(workspace, kind, method_name):
    document = workspace.canvas().document()
    layer = document.active_layer()
    assert layer.effects == ()
    getattr(_bridge(workspace), method_name)()
    assert len(layer.effects) == 1
    assert layer.effects[0].kind == kind


def test_add_drop_shadow_uses_default_params(workspace):
    _bridge(workspace).add_drop_shadow()
    effect = workspace.canvas().document().active_layer().effects[0]
    # Sanity: drop_shadow defaults to a non-zero offset and opacity.
    assert effect.params["opacity"] > 0
    assert effect.params["radius"] > 0


def test_add_same_kind_twice_replaces_not_stacks(workspace):
    """Clicking 'Add Drop Shadow' twice should not produce two
    shadow entries — the renderer takes only the first per kind."""
    _bridge(workspace).add_drop_shadow()
    _bridge(workspace).add_drop_shadow()
    effects = workspace.canvas().document().active_layer().effects
    drop_shadows = [e for e in effects if e.kind == "drop_shadow"]
    assert len(drop_shadows) == 1


def test_different_kinds_coexist(workspace):
    bridge = _bridge(workspace)
    bridge.add_drop_shadow()
    bridge.add_outer_glow()
    bridge.add_stroke()
    kinds = {e.kind for e in workspace.canvas().document().active_layer().effects}
    assert kinds == set(EFFECT_KINDS)


# ---------------------------------------------------------------------------
# clear_effects
# ---------------------------------------------------------------------------


def test_clear_effects_empties_tuple(workspace):
    bridge = _bridge(workspace)
    bridge.add_drop_shadow()
    bridge.add_stroke()
    assert len(workspace.canvas().document().active_layer().effects) == 2
    bridge.clear_effects()
    assert workspace.canvas().document().active_layer().effects == ()


def test_clear_effects_with_no_effects_is_noop(workspace):
    bridge = _bridge(workspace)
    assert workspace.canvas().document().active_layer().effects == ()
    bridge.clear_effects()  # must not crash


# ---------------------------------------------------------------------------
# Composite invalidation
# ---------------------------------------------------------------------------


def test_add_effect_invalidates_composite(workspace):
    document = workspace.canvas().document()
    document.composite()
    assert document._composite_cache is not None  # noqa: SLF001
    _bridge(workspace).add_drop_shadow()
    assert document._composite_cache is None  # noqa: SLF001


def test_clear_effects_invalidates_composite(workspace):
    document = workspace.canvas().document()
    _bridge(workspace).add_outer_glow()
    document.composite()
    assert document._composite_cache is not None  # noqa: SLF001
    _bridge(workspace).clear_effects()
    assert document._composite_cache is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# Defensive: methods cope when the active layer is gone
# ---------------------------------------------------------------------------


def test_add_effect_with_no_active_layer_is_noop(workspace):
    document = workspace.canvas().document()
    document._layers.clear()  # noqa: SLF001
    document._active_index = -1  # noqa: SLF001
    # All four bridge methods must tolerate the empty stack.
    _bridge(workspace).add_drop_shadow()
    _bridge(workspace).add_outer_glow()
    _bridge(workspace).add_stroke()
    _bridge(workspace).clear_effects()


# ---------------------------------------------------------------------------
# Effect actually shows up in the composite
# ---------------------------------------------------------------------------


def test_drop_shadow_changes_composite_pixels(workspace):
    """Add a shadow → composite differs from the no-effect baseline.

    Painted on a transparent layer with a small opaque disk so the
    shadow has room to peek out from behind it; a full-canvas opaque
    layer would have the shadow entirely behind the layer pixels and
    the composite would not change.
    """
    import numpy as np
    document = workspace.canvas().document()
    layer = document.active_layer()
    # Reset to fully transparent then stamp a disk in the centre.
    layer.image[...] = 0
    h, w = layer.image.shape[:2]
    yy, xx = np.indices((h, w))
    cy, cx = h / 2, w / 2
    inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= (min(h, w) / 8) ** 2
    layer.image[inside, 0] = 255
    layer.image[inside, 3] = 255
    document.invalidate_composite()
    baseline = document.composite().copy()
    workspace.canvas().document().set_layer_effects(
        effects=(LayerEffect(kind="drop_shadow", params={
            "offset_x": 8, "offset_y": 8, "radius": 4,
            "opacity": 0.7, "color": [0, 0, 0, 255],
        }),),
    )
    after = document.composite()
    assert not np.array_equal(baseline, after)
