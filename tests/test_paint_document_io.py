"""Tests for native PaintDocument save / load."""
from __future__ import annotations

import json

import numpy as np
import pytest

from Imervue.paint.document import Layer, PaintDocument
from Imervue.paint.document_io import (
    FILE_EXTENSION,
    FORMAT_VERSION,
    load_document,
    save_document,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_doc(h=8, w=10, with_selection=False, with_mask=False):
    doc = PaintDocument()
    base = np.zeros((h, w, 4), dtype=np.uint8)
    base[..., :3] = (200, 100, 50)
    base[..., 3] = 255
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (10, 20, 30)
    above.image[..., 3] = 200
    above.opacity = 0.7
    above.blend_mode = "multiply"
    above.lock_alpha = True
    if with_mask:
        above.mask = np.full((h, w), 128, dtype=np.uint8)
        above.mask_enabled = True
    if with_selection:
        sel = np.zeros((h, w), dtype=np.bool_)
        sel[1:5, 1:5] = True
        doc.set_selection(sel)
    return doc


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_save_then_load_round_trips_layer_count(tmp_path):
    doc = _make_doc()
    path = tmp_path / f"doc{FILE_EXTENSION}"
    save_document(doc, path)
    loaded = load_document(path)
    assert loaded.layer_count == doc.layer_count


def test_save_then_load_preserves_layer_pixels(tmp_path):
    doc = _make_doc()
    path = tmp_path / f"doc{FILE_EXTENSION}"
    save_document(doc, path)
    loaded = load_document(path)
    for original, restored in zip(doc.layers(), loaded.layers(), strict=True):
        np.testing.assert_array_equal(original.image, restored.image)


def test_save_then_load_preserves_layer_metadata(tmp_path):
    doc = _make_doc()
    path = tmp_path / f"doc{FILE_EXTENSION}"
    save_document(doc, path)
    loaded = load_document(path)
    above_orig = doc.layers()[1]
    above_load = loaded.layers()[1]
    assert above_load.name == above_orig.name
    assert above_load.opacity == pytest.approx(above_orig.opacity)
    assert above_load.blend_mode == above_orig.blend_mode
    assert above_load.lock_alpha is True


def test_save_then_load_preserves_active_layer_index(tmp_path):
    doc = _make_doc()
    doc.set_active_layer(0)
    path = tmp_path / f"doc{FILE_EXTENSION}"
    save_document(doc, path)
    loaded = load_document(path)
    assert loaded.active_layer_index() == 0


def test_save_then_load_preserves_layer_mask(tmp_path):
    doc = _make_doc(with_mask=True)
    path = tmp_path / f"doc{FILE_EXTENSION}"
    save_document(doc, path)
    loaded = load_document(path)
    restored_mask = loaded.layers()[1].mask
    assert restored_mask is not None
    assert (restored_mask == 128).all()


def test_save_then_load_preserves_selection(tmp_path):
    doc = _make_doc(with_selection=True)
    path = tmp_path / f"doc{FILE_EXTENSION}"
    save_document(doc, path)
    loaded = load_document(path)
    sel_orig = doc.selection()
    sel_load = loaded.selection()
    assert sel_load is not None
    np.testing.assert_array_equal(sel_orig, sel_load)


def test_save_creates_parent_directory(tmp_path):
    doc = _make_doc()
    nested = tmp_path / "deep" / "in" / f"doc{FILE_EXTENSION}"
    save_document(doc, nested)
    assert nested.exists()


def test_save_overwrites_existing_file(tmp_path):
    doc1 = _make_doc()
    doc2 = _make_doc()
    doc2.add_layer(name="Extra")
    path = tmp_path / f"doc{FILE_EXTENSION}"
    save_document(doc1, path)
    save_document(doc2, path)
    loaded = load_document(path)
    assert loaded.layer_count == doc2.layer_count


# ---------------------------------------------------------------------------
# save_document — error paths
# ---------------------------------------------------------------------------


def test_save_empty_document_raises(tmp_path):
    doc = PaintDocument()
    with pytest.raises(ValueError, match="empty"):
        save_document(doc, tmp_path / f"empty{FILE_EXTENSION}")


# ---------------------------------------------------------------------------
# load_document — error paths
# ---------------------------------------------------------------------------


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_document(tmp_path / f"none{FILE_EXTENSION}")


def test_load_unknown_format_version_raises(tmp_path):
    """A file written with a future version must be rejected."""
    h, w = 4, 4
    img = np.zeros((h, w, 4), dtype=np.uint8)
    metadata = {
        "format_version": 999,
        "width": w,
        "height": h,
        "active_layer": 0,
        "layers": [{
            "name": "Layer", "opacity": 1.0, "blend_mode": "normal",
            "visible": True, "locked": False, "lock_alpha": False,
            "mask_enabled": True, "clip": False, "has_mask": False,
        }],
    }
    arrays = {
        "_metadata": np.array(json.dumps(metadata)),
        "layer_0_image": img,
    }
    path = tmp_path / f"future{FILE_EXTENSION}"
    with open(path, "wb") as fh:
        np.savez_compressed(fh, **arrays)
    with pytest.raises(ValueError, match="format version"):
        load_document(path)


def test_load_corrupt_metadata_raises(tmp_path):
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    arrays = {
        "_metadata": np.array("not valid json {"),
        "layer_0_image": img,
    }
    path = tmp_path / f"corrupt{FILE_EXTENSION}"
    with open(path, "wb") as fh:
        np.savez_compressed(fh, **arrays)
    with pytest.raises(ValueError, match="JSON"):
        load_document(path)


def test_load_missing_layer_image_raises(tmp_path):
    metadata = {
        "format_version": FORMAT_VERSION,
        "width": 4, "height": 4,
        "active_layer": 0,
        "layers": [{
            "name": "Layer", "opacity": 1.0, "blend_mode": "normal",
            "visible": True, "locked": False, "lock_alpha": False,
            "mask_enabled": True, "clip": False, "has_mask": False,
        }],
    }
    arrays = {"_metadata": np.array(json.dumps(metadata))}
    path = tmp_path / f"shy{FILE_EXTENSION}"
    with open(path, "wb") as fh:
        np.savez_compressed(fh, **arrays)
    with pytest.raises(ValueError, match="missing array"):
        load_document(path)


def test_load_metadata_layer_shape_mismatch_raises(tmp_path):
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    metadata = {
        "format_version": FORMAT_VERSION,
        "width": 8,    # claims 8 but image is 4
        "height": 8,
        "active_layer": 0,
        "layers": [{
            "name": "L", "opacity": 1.0, "blend_mode": "normal",
            "visible": True, "locked": False, "lock_alpha": False,
            "mask_enabled": True, "clip": False, "has_mask": False,
        }],
    }
    arrays = {
        "_metadata": np.array(json.dumps(metadata)),
        "layer_0_image": img,
    }
    path = tmp_path / f"mismatch{FILE_EXTENSION}"
    with open(path, "wb") as fh:
        np.savez_compressed(fh, **arrays)
    with pytest.raises(ValueError, match="does not match"):
        load_document(path)


# ---------------------------------------------------------------------------
# replace_state
# ---------------------------------------------------------------------------


def test_replace_state_swaps_layers():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    new_layers = [Layer(name="Fresh", image=np.full((4, 4, 4), 200, dtype=np.uint8))]
    doc.replace_state(layers=new_layers, active_index=0)
    assert doc.layer_count == 1
    assert doc.layers()[0].name == "Fresh"


def test_replace_state_clamps_active_index():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    new_layers = [
        Layer(name="A", image=np.zeros((4, 4, 4), dtype=np.uint8)),
        Layer(name="B", image=np.zeros((4, 4, 4), dtype=np.uint8)),
    ]
    doc.replace_state(layers=new_layers, active_index=99)
    assert doc.active_layer_index() == 1


def test_replace_state_rejects_empty_layers():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    with pytest.raises(ValueError, match="non-empty"):
        doc.replace_state(layers=[])


def test_replace_state_rejects_shape_mismatch_between_layers():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    new_layers = [
        Layer(name="A", image=np.zeros((4, 4, 4), dtype=np.uint8)),
        Layer(name="B", image=np.zeros((8, 8, 4), dtype=np.uint8)),
    ]
    with pytest.raises(ValueError, match="does not match"):
        doc.replace_state(layers=new_layers)


def test_replace_state_rejects_selection_shape_mismatch():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    new_layers = [Layer(name="A", image=np.zeros((4, 4, 4), dtype=np.uint8))]
    bad_sel = np.zeros((8, 8), dtype=np.bool_)
    with pytest.raises(ValueError, match="does not match"):
        doc.replace_state(layers=new_layers, selection=bad_sel)


def test_replace_state_rejects_non_bool_selection():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    new_layers = [Layer(name="A", image=np.zeros((4, 4, 4), dtype=np.uint8))]
    bad_sel = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="bool"):
        doc.replace_state(layers=new_layers, selection=bad_sel)


def test_replace_state_notifies_listeners():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    calls: list[int] = []
    doc.listen(lambda: calls.append(1))
    new_layers = [Layer(name="X", image=np.zeros((4, 4, 4), dtype=np.uint8))]
    doc.replace_state(layers=new_layers)
    assert calls
