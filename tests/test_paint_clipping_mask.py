"""Tests for clipping mask compositing + the Layer-menu toggle."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.compositing import composite_stack
from Imervue.paint.document import Layer
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _solid_rgba(h: int, w: int, color: tuple[int, int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = color[0]
    arr[..., 1] = color[1]
    arr[..., 2] = color[2]
    arr[..., 3] = color[3]
    return arr


def _alpha_disk(h: int, w: int, color: tuple[int, int, int]) -> np.ndarray:
    """Layer with a centred opaque disk on a transparent background."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    yy, xx = np.indices((h, w))
    cy, cx = h / 2.0, w / 2.0
    inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= (min(h, w) / 4) ** 2
    arr[inside, 0] = color[0]
    arr[inside, 1] = color[1]
    arr[inside, 2] = color[2]
    arr[inside, 3] = 255
    return arr


# ---------------------------------------------------------------------------
# composite_stack — clip honoured
# ---------------------------------------------------------------------------


def test_clipped_layer_only_visible_where_base_layer_is_opaque():
    """A red layer above a green disk, marked clip=True, must only
    show the red where the disk is. Pixels outside the disk on the
    upper layer are clipped to the base's transparency."""
    h, w = 32, 32
    base = Layer(name="disk", image=_alpha_disk(h, w, (0, 200, 0)))
    above = Layer(
        name="red", image=_solid_rgba(h, w, (255, 0, 0, 255)), clip=True,
    )
    out = composite_stack([base, above], (h, w))
    # Outside the disk, the base alpha is 0 → red layer is clipped
    # away → composite alpha at corner is 0.
    assert out[0, 0, 3] == 0
    # Centre of the disk shows the red on top of the green base.
    assert out[h // 2, w // 2, 0] == 255
    assert out[h // 2, w // 2, 3] == 255


def test_clip_false_does_not_clip():
    """Same setup but clip=False — the red fully covers the canvas."""
    h, w = 32, 32
    base = Layer(name="disk", image=_alpha_disk(h, w, (0, 200, 0)))
    above = Layer(
        name="red", image=_solid_rgba(h, w, (255, 0, 0, 255)), clip=False,
    )
    out = composite_stack([base, above], (h, w))
    # Now every pixel shows red (full coverage).
    assert (out[..., 0] == 255).all()


def test_clip_at_bottom_of_stack_renders_unclipped():
    """A clipping layer with no base below it must still render
    (graceful fallback rather than disappearing)."""
    h, w = 16, 16
    only = Layer(
        name="orphan", image=_solid_rgba(h, w, (100, 100, 100, 255)),
        clip=True,
    )
    out = composite_stack([only], (h, w))
    # Without a base, the layer is just composited normally.
    assert (out[..., 0] == 100).all()


def test_multiple_clipping_layers_share_one_base():
    """Two consecutive clip=True layers should both clip to the same
    non-clipped base below — Photoshop's clipping group convention."""
    h, w = 32, 32
    base = Layer(name="disk", image=_alpha_disk(h, w, (0, 0, 0)))
    red = Layer(
        name="red", image=_solid_rgba(h, w, (255, 0, 0, 80)), clip=True,
    )
    blue = Layer(
        name="blue", image=_solid_rgba(h, w, (0, 0, 255, 80)), clip=True,
    )
    out = composite_stack([base, red, blue], (h, w))
    # Outside the disk, both clipped layers contribute nothing.
    assert out[0, 0, 3] == 0


def test_non_clip_layer_resets_clip_base():
    """After a non-clipped layer, subsequent clip layers should clip
    to the new base, not the old one."""
    h, w = 16, 16
    base_a = Layer(name="a", image=_alpha_disk(h, w, (255, 0, 0)))
    full_b = Layer(
        name="b", image=_solid_rgba(h, w, (0, 200, 0, 255)),
    )
    clip_c = Layer(
        name="c", image=_solid_rgba(h, w, (0, 0, 255, 255)), clip=True,
    )
    out = composite_stack([base_a, full_b, clip_c], (h, w))
    # Layer b covers the whole canvas, so clip_c (clipped to b) is
    # also visible everywhere. Corner alpha should be opaque.
    assert out[0, 0, 3] == 255
    assert out[0, 0, 2] == 255   # the blue won


# ---------------------------------------------------------------------------
# Layer-menu toggle
# ---------------------------------------------------------------------------


def test_toggle_clip_flips_active_layer_flag(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        layer = document.active_layer()
        assert layer.clip is False
        bridge = ws._layer_menu_bridge   # noqa: SLF001
        bridge.toggle_clipping_mask()
        assert document.active_layer().clip is True
        bridge.toggle_clipping_mask()
        assert document.active_layer().clip is False
    finally:
        ws.deleteLater()


def test_toggle_clip_invalidates_composite(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document.composite()
        assert document._composite_cache is not None  # noqa: SLF001
        ws._layer_menu_bridge.toggle_clipping_mask()  # noqa: SLF001
        assert document._composite_cache is None  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_toggle_clip_with_no_active_layer_is_noop(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document._layers.clear()  # noqa: SLF001
        document._active_index = -1  # noqa: SLF001
        # Must not raise.
        ws._layer_menu_bridge.toggle_clipping_mask()  # noqa: SLF001
    finally:
        ws.deleteLater()
