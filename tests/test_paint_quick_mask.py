"""Tests for the quick mask helpers + named selection storage."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.quick_mask import (
    quick_mask_overlay,
    selection_from_quick_mask,
)


# ---------------------------------------------------------------------------
# quick_mask_overlay
# ---------------------------------------------------------------------------


def _selection(h, w, y0, y1, x0, x1):
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[y0:y1, x0:x1] = True
    return sel


def test_overlay_paints_unselected_pixels_by_default():
    sel = _selection(8, 8, 2, 6, 2, 6)
    out = quick_mask_overlay(sel)
    # Inside selection — overlay alpha is 0.
    assert out[3, 3, 3] == 0
    # Outside selection — overlay alpha matches the requested default.
    assert out[0, 0, 3] > 0


def test_overlay_uses_custom_color_and_alpha():
    sel = _selection(4, 4, 0, 2, 0, 2)
    out = quick_mask_overlay(sel, color=(0, 200, 0), alpha=64)
    # Pixels outside the selection get the custom colour + alpha.
    assert tuple(out[3, 3]) == (0, 200, 0, 64)


def test_overlay_invert_false_paints_selected_region():
    sel = _selection(4, 4, 0, 2, 0, 2)
    out = quick_mask_overlay(sel, invert=False)
    # Inside selection — overlay applied.
    assert out[0, 0, 3] > 0
    # Outside selection — overlay zero.
    assert out[3, 3, 3] == 0


def test_overlay_full_selection_invert_true_returns_empty():
    sel = np.ones((4, 4), dtype=np.bool_)
    out = quick_mask_overlay(sel, invert=True)
    assert out[..., 3].sum() == 0


def test_overlay_rejects_non_bool_selection():
    with pytest.raises(ValueError, match="bool"):
        quick_mask_overlay(np.zeros((4, 4), dtype=np.uint8))


def test_overlay_rejects_alpha_above_255():
    sel = _selection(4, 4, 0, 2, 0, 2)
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        quick_mask_overlay(sel, alpha=300)


# ---------------------------------------------------------------------------
# selection_from_quick_mask
# ---------------------------------------------------------------------------


def test_round_trip_overlay_to_selection():
    original = _selection(8, 8, 2, 6, 2, 6)
    overlay = quick_mask_overlay(original)
    rebuilt = selection_from_quick_mask(overlay)
    np.testing.assert_array_equal(rebuilt, original)


def test_selection_from_quick_mask_invert_false():
    original = _selection(8, 8, 0, 4, 0, 4)
    overlay = quick_mask_overlay(original, invert=False)
    rebuilt = selection_from_quick_mask(overlay, invert=False)
    np.testing.assert_array_equal(rebuilt, original)


def test_selection_from_quick_mask_threshold_filters_low_alpha():
    overlay = np.zeros((4, 4, 4), dtype=np.uint8)
    overlay[1, 1, 3] = 50
    overlay[2, 2, 3] = 200
    rebuilt = selection_from_quick_mask(overlay, threshold=100)
    # Threshold 100 skips alpha=50, keeps alpha=200.
    # Default invert=True means painted pixels become *un*selected.
    assert not rebuilt[2, 2]
    assert rebuilt[1, 1]
    assert rebuilt[0, 0]   # never painted, still selected


def test_selection_from_quick_mask_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        selection_from_quick_mask(rgb)


# ---------------------------------------------------------------------------
# PaintDocument named selections
# ---------------------------------------------------------------------------


@pytest.fixture
def document_with_selection():
    doc = PaintDocument()
    base = np.zeros((8, 8, 4), dtype=np.uint8)
    doc.load_image(base)
    sel = _selection(8, 8, 2, 6, 2, 6)
    doc.set_selection(sel)
    return doc


def test_save_and_load_named_selection(document_with_selection):
    doc = document_with_selection
    assert doc.save_selection("body") is True
    doc.set_selection(None)
    assert doc.load_selection("body") is True
    sel = doc.selection()
    assert sel is not None
    assert sel[3, 3] is np.True_ or sel[3, 3] is True


def test_save_selection_without_active_returns_false():
    doc = PaintDocument()
    base = np.zeros((4, 4, 4), dtype=np.uint8)
    doc.load_image(base)
    assert doc.save_selection("body") is False


def test_save_selection_blank_name_raises(document_with_selection):
    doc = document_with_selection
    with pytest.raises(ValueError, match="non-empty"):
        doc.save_selection("   ")


def test_load_unknown_selection_returns_false(document_with_selection):
    assert document_with_selection.load_selection("ghost") is False


def test_delete_named_selection(document_with_selection):
    doc = document_with_selection
    doc.save_selection("body")
    assert doc.delete_named_selection("body") is True
    assert doc.list_named_selections() == []


def test_delete_unknown_selection_returns_false(document_with_selection):
    assert document_with_selection.delete_named_selection("ghost") is False


def test_list_named_selections_returns_all_names(document_with_selection):
    doc = document_with_selection
    doc.save_selection("body")
    doc.set_selection(_selection(8, 8, 0, 2, 0, 2))
    doc.save_selection("head")
    assert set(doc.list_named_selections()) == {"body", "head"}


def test_named_selection_returns_independent_copy(document_with_selection):
    doc = document_with_selection
    doc.save_selection("body")
    snapshot = doc.named_selection("body")
    snapshot[0, 0] = True   # type: ignore[index]
    second = doc.named_selection("body")
    assert second is not None
    assert not second[0, 0]


def test_save_load_named_selection_persists_through_document_io(tmp_path):
    from Imervue.paint.document_io import load_document, save_document
    doc = PaintDocument()
    doc.load_image(np.zeros((6, 8, 4), dtype=np.uint8))
    doc.set_selection(_selection(6, 8, 1, 4, 1, 5))
    doc.save_selection("body")
    doc.set_selection(None)
    path = tmp_path / "named.imervue"
    save_document(doc, path)
    loaded = load_document(path)
    assert "body" in loaded.list_named_selections()
    loaded.load_selection("body")
    sel = loaded.selection()
    assert sel is not None
    assert sel.shape == (6, 8)
    assert sel[2, 2]
    assert not sel[0, 0]
