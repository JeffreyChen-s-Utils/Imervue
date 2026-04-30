"""Tests for lock / clip / selection-from-alpha document helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import Layer, PaintDocument
from Imervue.paint.selection_ops import lock_alpha_mask


@pytest.fixture
def document_with_two_layers():
    doc = PaintDocument()
    base = np.full((8, 8, 4), 255, dtype=np.uint8)
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[2:5, 2:5, 3] = 200   # opaque blob
    above.image[..., :3] = (100, 50, 25)
    return doc


# ---------------------------------------------------------------------------
# Layer field defaults
# ---------------------------------------------------------------------------


def test_layer_lock_alpha_defaults_to_false():
    layer = Layer(name="L", image=np.zeros((4, 4, 4), dtype=np.uint8))
    assert layer.lock_alpha is False


# ---------------------------------------------------------------------------
# set_layer_locked
# ---------------------------------------------------------------------------


def test_set_layer_locked_toggles_flag(document_with_two_layers):
    doc = document_with_two_layers
    assert doc.set_layer_locked(locked=True) is True
    assert doc.active_layer().locked is True


def test_set_layer_locked_idempotent(document_with_two_layers):
    doc = document_with_two_layers
    doc.set_layer_locked(locked=True)
    assert doc.set_layer_locked(locked=True) is False


def test_set_layer_locked_explicit_index(document_with_two_layers):
    doc = document_with_two_layers
    doc.set_layer_locked(index=0, locked=True)
    assert doc.layer_at(0).locked is True
    assert doc.layer_at(1).locked is False


def test_set_layer_locked_empty_doc_returns_false():
    doc = PaintDocument()
    assert doc.set_layer_locked(locked=True) is False


# ---------------------------------------------------------------------------
# set_layer_lock_alpha
# ---------------------------------------------------------------------------


def test_set_layer_lock_alpha_toggles_flag(document_with_two_layers):
    doc = document_with_two_layers
    assert doc.set_layer_lock_alpha(lock_alpha=True) is True
    assert doc.active_layer().lock_alpha is True


def test_set_layer_lock_alpha_idempotent(document_with_two_layers):
    doc = document_with_two_layers
    doc.set_layer_lock_alpha(lock_alpha=False)
    assert doc.active_layer().lock_alpha is False


# ---------------------------------------------------------------------------
# set_layer_clip
# ---------------------------------------------------------------------------


def test_set_layer_clip_toggles_flag(document_with_two_layers):
    doc = document_with_two_layers
    assert doc.set_layer_clip(clip=True) is True
    assert doc.active_layer().clip is True


def test_set_layer_clip_idempotent(document_with_two_layers):
    doc = document_with_two_layers
    doc.set_layer_clip(clip=True)
    assert doc.set_layer_clip(clip=True) is False


# ---------------------------------------------------------------------------
# selection_from_layer_alpha
# ---------------------------------------------------------------------------


def test_selection_from_alpha_uses_active_layer(document_with_two_layers):
    doc = document_with_two_layers
    assert doc.selection_from_layer_alpha() is True
    sel = doc.selection()
    assert sel is not None
    assert sel.dtype == np.bool_
    # Selection matches the opaque blob at rows 2..5 cols 2..5.
    assert sel[3, 3]
    assert not sel[0, 0]


def test_selection_from_alpha_with_threshold(document_with_two_layers):
    doc = document_with_two_layers
    layer = doc.active_layer()
    layer.image[..., 3] = 50
    layer.image[6, 6, 3] = 200   # one strongly-opaque pixel
    doc.selection_from_layer_alpha(threshold=127)
    sel = doc.selection()
    assert sel[6, 6]
    assert not sel[0, 0]


def test_selection_from_alpha_idempotent_returns_false(document_with_two_layers):
    doc = document_with_two_layers
    doc.selection_from_layer_alpha()
    assert doc.selection_from_layer_alpha() is False


def test_selection_from_alpha_explicit_index(document_with_two_layers):
    doc = document_with_two_layers
    # The base layer (index 0) is fully opaque; selecting from it
    # should produce an all-True mask.
    doc.selection_from_layer_alpha(index=0)
    sel = doc.selection()
    assert sel.all()


# ---------------------------------------------------------------------------
# lock_alpha_mask helper
# ---------------------------------------------------------------------------


def test_lock_alpha_mask_no_selection_returns_alpha_region():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[1, 1, 3] = 100
    img[2, 2, 3] = 255
    mask = lock_alpha_mask(img, None)
    assert mask is not None
    assert mask[1, 1]
    assert mask[2, 2]
    assert not mask[0, 0]


def test_lock_alpha_mask_intersects_selection_and_alpha():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[1, 1, 3] = 100
    img[2, 2, 3] = 100
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[1, 1] = True
    mask = lock_alpha_mask(img, sel)
    assert mask is not None
    assert mask[1, 1]
    assert not mask[2, 2]   # in alpha but not in selection
    assert not mask[0, 0]


def test_lock_alpha_mask_rejects_shape_mismatch():
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    bad_sel = np.zeros((2, 2), dtype=np.bool_)
    with pytest.raises(ValueError, match="does not match"):
        lock_alpha_mask(img, bad_sel)


def test_lock_alpha_mask_rejects_rgb_only():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        lock_alpha_mask(rgb, None)
