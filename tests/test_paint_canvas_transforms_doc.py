"""Tests for whole-document flip / rotate verbs + Image-menu bridge."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.document import Layer, PaintDocument
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _seeded_document(h: int = 8, w: int = 8) -> PaintDocument:
    """Document with a known asymmetric per-pixel pattern so flips
    and rotations can be verified by checking specific corner cells."""
    doc = PaintDocument()
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 3] = 255
    arr[0, 0] = (255, 0, 0, 255)      # top-left red
    arr[0, w - 1] = (0, 255, 0, 255)  # top-right green
    arr[h - 1, 0] = (0, 0, 255, 255)  # bottom-left blue
    doc._layers.append(Layer(name="seed", image=arr))   # noqa: SLF001
    doc._active_index = 0   # noqa: SLF001
    return doc


# ---------------------------------------------------------------------------
# flip_horizontal — mirrors columns
# ---------------------------------------------------------------------------


def test_flip_horizontal_swaps_top_left_and_top_right():
    doc = _seeded_document(8, 8)
    assert doc.flip_horizontal() is True
    layer = doc.layer_at(0)
    # Top-left was red; after H-flip the top-LEFT position holds the
    # original top-RIGHT pixel (green).
    assert tuple(layer.image[0, 0]) == (0, 255, 0, 255)
    assert tuple(layer.image[0, 7]) == (255, 0, 0, 255)


def test_flip_horizontal_on_empty_document_returns_false():
    doc = PaintDocument()
    assert doc.flip_horizontal() is False


def test_flip_horizontal_flips_mask_too():
    doc = _seeded_document(4, 4)
    layer = doc.layer_at(0)
    layer.mask = np.zeros((4, 4), dtype=np.uint8)
    layer.mask[0, 0] = 200
    doc.flip_horizontal()
    # Mask sentinel moves from column 0 to column 3.
    assert int(layer.mask[0, 3]) == 200
    assert int(layer.mask[0, 0]) == 0


def test_flip_horizontal_flips_selection():
    doc = _seeded_document(4, 4)
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[1, 0] = True
    doc.set_selection(sel)
    doc.flip_horizontal()
    new_sel = doc.selection()
    assert bool(new_sel[1, 3])
    assert not bool(new_sel[1, 0])


def test_flip_horizontal_yields_contiguous_array():
    """np.fliplr returns a view; the verb must materialise a
    contiguous buffer so downstream GL upload + composite paths
    don't trip over a strided ndarray."""
    doc = _seeded_document()
    doc.flip_horizontal()
    layer = doc.layer_at(0)
    assert layer.image.flags["C_CONTIGUOUS"]


# ---------------------------------------------------------------------------
# flip_vertical
# ---------------------------------------------------------------------------


def test_flip_vertical_swaps_top_and_bottom():
    doc = _seeded_document(8, 8)
    assert doc.flip_vertical() is True
    layer = doc.layer_at(0)
    # Top-left (red) moves to bottom-left.
    assert tuple(layer.image[7, 0]) == (255, 0, 0, 255)
    # Bottom-left (blue) moves to top-left.
    assert tuple(layer.image[0, 0]) == (0, 0, 255, 255)


def test_flip_vertical_on_empty_document_returns_false():
    assert PaintDocument().flip_vertical() is False


# ---------------------------------------------------------------------------
# rotate_90_cw / ccw / 180
# ---------------------------------------------------------------------------


def test_rotate_90_cw_swaps_dimensions():
    doc = _seeded_document(4, 8)
    doc.rotate_90_cw()
    layer = doc.layer_at(0)
    assert layer.image.shape[:2] == (8, 4)


def test_rotate_90_cw_moves_top_left_to_top_right():
    """A 90° CW rotation moves the top-left pixel to the top-right."""
    doc = _seeded_document(4, 4)
    doc.rotate_90_cw()
    layer = doc.layer_at(0)
    assert tuple(layer.image[0, 3]) == (255, 0, 0, 255)


def test_rotate_90_ccw_moves_top_left_to_bottom_left():
    doc = _seeded_document(4, 4)
    doc.rotate_90_ccw()
    layer = doc.layer_at(0)
    assert tuple(layer.image[3, 0]) == (255, 0, 0, 255)


def test_rotate_90_cw_then_ccw_round_trips():
    doc = _seeded_document(4, 6)
    snapshot = doc.layer_at(0).image.copy()
    doc.rotate_90_cw()
    doc.rotate_90_ccw()
    assert np.array_equal(doc.layer_at(0).image, snapshot)


def test_rotate_180_equals_flip_h_then_v():
    doc_a = _seeded_document(4, 4)
    doc_b = _seeded_document(4, 4)
    doc_a.rotate_180()
    doc_b.flip_horizontal()
    doc_b.flip_vertical()
    assert np.array_equal(doc_a.layer_at(0).image, doc_b.layer_at(0).image)


def test_rotate_keeps_layer_count_unchanged():
    doc = _seeded_document()
    doc._layers.append(Layer(  # noqa: SLF001
        name="extra", image=np.zeros((8, 8, 4), dtype=np.uint8),
    ))
    before = doc.layer_count
    doc.rotate_90_cw()
    assert doc.layer_count == before


def test_rotate_90_on_empty_document_returns_false():
    assert PaintDocument().rotate_90_cw() is False
    assert PaintDocument().rotate_90_ccw() is False
    assert PaintDocument().rotate_180() is False


# ---------------------------------------------------------------------------
# Image menu bridge
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def _bridge(ws):
    return ws._image_menu_bridge   # noqa: SLF001


def test_bridge_flip_horizontal_calls_document_verb(workspace):
    layer = workspace.canvas().document().active_layer()
    layer.image[0, 0] = (255, 0, 0, 255)
    layer.image[0, -1] = (0, 255, 0, 255)
    _bridge(workspace).flip_horizontal()
    flipped = workspace.canvas().document().active_layer()
    assert tuple(flipped.image[0, 0]) == (0, 255, 0, 255)


def test_bridge_rotate_90_cw_swaps_dimensions(workspace):
    document = workspace.canvas().document()
    h_before, w_before = document.shape
    if h_before == w_before:
        # If the canvas happens to be square, the dim check is vacuous.
        # Crop to a non-square shape first so the rotation is observable.
        document.crop((0, 0, max(2, w_before // 2), h_before))
        h_before, w_before = document.shape
    _bridge(workspace).rotate_90_cw()
    h_after, w_after = workspace.canvas().document().shape
    assert (h_after, w_after) == (w_before, h_before)


def test_bridge_invalidates_composite(workspace):
    document = workspace.canvas().document()
    document.composite()
    assert document._composite_cache is not None  # noqa: SLF001
    _bridge(workspace).flip_horizontal()
    assert document._composite_cache is None  # noqa: SLF001


def test_image_menu_has_documented_actions(workspace):
    from Imervue.paint.paint_menu_bar import menu_for
    image_menu = menu_for(workspace, "image")
    # Image Size + sep + 2 flip + sep + 3 rotate = 8 entries (25b added Size).
    assert len(image_menu.actions()) == 8
