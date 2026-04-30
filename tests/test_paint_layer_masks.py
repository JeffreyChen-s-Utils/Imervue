"""Tests for PaintDocument layer-mask helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import Layer, PaintDocument


@pytest.fixture
def document():
    doc = PaintDocument()
    base = np.full((8, 8, 4), 255, dtype=np.uint8)
    doc.load_image(base)
    return doc


# ---------------------------------------------------------------------------
# Layer.effective_mask
# ---------------------------------------------------------------------------


def test_effective_mask_none_when_no_mask():
    layer = Layer(name="L", image=np.zeros((4, 4, 4), dtype=np.uint8))
    assert layer.effective_mask is None


def test_effective_mask_returns_mask_when_enabled():
    layer = Layer(name="L", image=np.zeros((4, 4, 4), dtype=np.uint8))
    layer.mask = np.full((4, 4), 200, dtype=np.uint8)
    assert layer.effective_mask is not None
    assert layer.effective_mask[0, 0] == 200


def test_effective_mask_none_when_disabled():
    layer = Layer(name="L", image=np.zeros((4, 4, 4), dtype=np.uint8))
    layer.mask = np.full((4, 4), 200, dtype=np.uint8)
    layer.mask_enabled = False
    assert layer.effective_mask is None


# ---------------------------------------------------------------------------
# add_layer_mask
# ---------------------------------------------------------------------------


def test_add_layer_mask_creates_white_mask_by_default(document):
    assert document.add_layer_mask() is True
    layer = document.active_layer()
    assert layer is not None
    assert layer.mask is not None
    assert layer.mask.shape == (8, 8)
    assert layer.mask.dtype == np.uint8
    assert (layer.mask == 255).all()


def test_add_layer_mask_with_fill_zero_creates_hidden_mask(document):
    document.add_layer_mask(fill=0)
    assert (document.active_layer().mask == 0).all()


def test_add_layer_mask_replaces_existing_mask(document):
    document.add_layer_mask(fill=0)
    document.add_layer_mask(fill=255)
    assert (document.active_layer().mask == 255).all()


def test_add_layer_mask_re_enables_mask(document):
    document.add_layer_mask(fill=255)
    document.set_layer_mask_enabled(enabled=False)
    document.add_layer_mask(fill=128)
    assert document.active_layer().mask_enabled is True


def test_add_layer_mask_rejects_fill_above_255(document):
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        document.add_layer_mask(fill=300)


def test_add_layer_mask_empty_doc_returns_false():
    doc = PaintDocument()
    assert doc.add_layer_mask() is False


def test_add_layer_mask_explicit_index(document):
    document.add_layer(name="Above")
    document.add_layer_mask(index=0, fill=128)
    assert (document.layer_at(0).mask == 128).all()
    assert document.layer_at(1).mask is None   # still untouched


def test_add_layer_mask_out_of_range_raises(document):
    with pytest.raises(IndexError):
        document.add_layer_mask(index=10)


# ---------------------------------------------------------------------------
# add_layer_mask_from_selection
# ---------------------------------------------------------------------------


def test_mask_from_selection_uses_selection(document):
    sel = np.zeros((8, 8), dtype=np.bool_)
    sel[2:6, 2:6] = True
    document.set_selection(sel)
    document.add_layer_mask_from_selection()
    layer = document.active_layer()
    assert (layer.mask[2:6, 2:6] == 255).all()
    assert (layer.mask[:2, :] == 0).all()


def test_mask_from_selection_full_when_no_selection(document):
    document.add_layer_mask_from_selection()
    assert (document.active_layer().mask == 255).all()


def test_mask_from_selection_rejects_shape_mismatch(document):
    bad_sel = np.ones((4, 4), dtype=np.bool_)
    # Bypass set_selection's shape check by writing the field directly.
    document._selection = bad_sel  # noqa: SLF001
    with pytest.raises(ValueError, match="does not match"):
        document.add_layer_mask_from_selection()


# ---------------------------------------------------------------------------
# clear_layer_mask
# ---------------------------------------------------------------------------


def test_clear_layer_mask_removes_mask(document):
    document.add_layer_mask()
    assert document.clear_layer_mask() is True
    assert document.active_layer().mask is None


def test_clear_layer_mask_no_mask_returns_false(document):
    assert document.clear_layer_mask() is False


# ---------------------------------------------------------------------------
# invert_layer_mask
# ---------------------------------------------------------------------------


def test_invert_layer_mask_flips_values(document):
    document.add_layer_mask(fill=200)
    document.invert_layer_mask()
    assert (document.active_layer().mask == 55).all()


def test_invert_layer_mask_no_mask_returns_false(document):
    assert document.invert_layer_mask() is False


def test_invert_layer_mask_double_invert_restores_original(document):
    document.add_layer_mask(fill=200)
    document.invert_layer_mask()
    document.invert_layer_mask()
    assert (document.active_layer().mask == 200).all()


# ---------------------------------------------------------------------------
# apply_layer_mask
# ---------------------------------------------------------------------------


def test_apply_layer_mask_bakes_into_alpha(document):
    layer = document.active_layer()
    layer.image[..., 3] = 200
    document.add_layer_mask(fill=128)
    document.apply_layer_mask()
    # 200 * 128/255 ≈ 100.4 → 100
    expected = int(200 * 128 / 255.0)
    assert layer.mask is None
    assert abs(int(layer.image[0, 0, 3]) - expected) <= 1


def test_apply_layer_mask_with_zero_mask_zeroes_alpha(document):
    document.add_layer_mask(fill=0)
    document.apply_layer_mask()
    assert (document.active_layer().image[..., 3] == 0).all()


def test_apply_layer_mask_with_full_mask_preserves_alpha(document):
    layer = document.active_layer()
    layer.image[..., 3] = 200
    document.add_layer_mask(fill=255)
    document.apply_layer_mask()
    assert (document.active_layer().image[..., 3] == 200).all()


def test_apply_layer_mask_no_mask_returns_false(document):
    assert document.apply_layer_mask() is False


# ---------------------------------------------------------------------------
# set_layer_mask_enabled
# ---------------------------------------------------------------------------


def test_set_layer_mask_enabled_toggles_flag(document):
    document.add_layer_mask()
    assert document.set_layer_mask_enabled(enabled=False) is True
    assert document.active_layer().mask_enabled is False
    assert document.active_layer().effective_mask is None


def test_set_layer_mask_enabled_idempotent(document):
    document.add_layer_mask()
    assert document.set_layer_mask_enabled(enabled=True) is False


def test_set_layer_mask_enabled_preserves_mask_data(document):
    document.add_layer_mask(fill=200)
    document.set_layer_mask_enabled(enabled=False)
    document.set_layer_mask_enabled(enabled=True)
    assert (document.active_layer().mask == 200).all()


# ---------------------------------------------------------------------------
# Composite respects layer mask + enabled flag
# ---------------------------------------------------------------------------


def test_composite_skips_disabled_mask():
    doc = PaintDocument()
    base = np.full((4, 4, 4), 255, dtype=np.uint8)
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (50, 50, 50)
    above.image[..., 3] = 255
    above.mask = np.zeros((4, 4), dtype=np.uint8)   # would hide above
    above.mask_enabled = False
    doc.invalidate_composite()
    out = doc.composite()
    # With mask disabled, above shows through; centre pixel should be (50,50,50)
    assert out is not None
    assert tuple(out[2, 2, :3]) == (50, 50, 50)


def test_composite_applies_enabled_mask():
    doc = PaintDocument()
    base = np.full((4, 4, 4), 255, dtype=np.uint8)
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (50, 50, 50)
    above.image[..., 3] = 255
    above.mask = np.zeros((4, 4), dtype=np.uint8)
    above.mask_enabled = True
    doc.invalidate_composite()
    out = doc.composite()
    # With mask enabled and zero, above is hidden; pixel stays white.
    assert out is not None
    assert tuple(out[2, 2, :3]) == (255, 255, 255)
