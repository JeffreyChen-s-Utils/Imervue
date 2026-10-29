"""Format contracts for the native ``.imervue`` NPZ bundle.

Pins the exact archive members, the metadata JSON the writer emits, the
save -> load round trip of a representative document (layers, masks, groups,
named selections, selection, reference layer, panel layout, adjustments,
effects) and every error / tolerance branch of the loader on malformed input.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

import numpy as np
import pytest

from Imervue.paint.adjustments import Adjustment
from Imervue.paint.document import PaintDocument
from Imervue.paint.document_io import (
    FILE_EXTENSION,
    FORMAT_VERSION,
    load_document,
    load_document_from_buffer,
    save_document,
    save_document_to_buffer,
)
from Imervue.paint.layer_effects import LayerEffect
from Imervue.paint.manga_panels import PanelCell, PanelLayout

_H, _W = 6, 8
_LAYER_KEYS = (
    "name", "opacity", "blend_mode", "visible", "locked", "lock_alpha",
    "mask_enabled", "clip", "has_mask", "group", "adjustment", "effects",
    "tone", "binary", "blend_if", "vector_strokes", "color_label",
)


def _representative_document() -> PaintDocument:
    """Three layers, a mask, a group, a selection and a named selection."""
    doc = PaintDocument()
    base = np.zeros((_H, _W, 4), dtype=np.uint8)
    base[..., 0] = np.arange(_W, dtype=np.uint8)
    base[..., 3] = 255
    doc.load_image(base)
    doc.create_group("Inks", opacity=0.5, blend_mode="multiply", expanded=False)
    inked = doc.add_layer(name="Inked")
    inked.image[1:3, 2:5] = (9, 8, 7, 200)
    inked.opacity = 0.75
    inked.blend_mode = "screen"
    inked.color_label = "blue"
    inked.adjustment = Adjustment.from_dict({"kind": "hsv"})
    inked.effects = (LayerEffect.from_dict({"kind": "stroke"}),)
    doc.set_layer_group(1, group="Inks")
    doc.add_layer_mask(1, fill=128)
    top = doc.add_layer(name="Top")
    top.visible = False
    top.locked = True
    selection = np.zeros((_H, _W), dtype=bool)
    selection[0:2, 0:3] = True
    doc.set_selection(selection)
    doc.save_selection("corner")
    doc.set_reference_layer_index(0)
    doc.set_active_layer(1)
    doc.panel_layout = PanelLayout(_W, _H, (PanelCell(0, 0, 4, 3),), 1, 2)
    return doc


def _members(blob: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        return sorted(zf.namelist())


def _arrays(blob: bytes) -> dict[str, np.ndarray]:
    with np.load(io.BytesIO(blob), allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def _write_raw(tmp_path, arrays: dict, name: str = "raw") -> str:
    path = tmp_path / f"{name}{FILE_EXTENSION}"
    with open(path, "wb") as fh:
        np.savez_compressed(fh, **arrays)
    return str(path)


def _layer_meta(**overrides) -> dict:
    meta = {
        "name": "L", "opacity": 1.0, "blend_mode": "normal",
        "visible": True, "locked": False, "lock_alpha": False,
        "mask_enabled": True, "clip": False, "has_mask": False,
    }
    meta.update(overrides)
    return meta


def _metadata(**overrides) -> dict:
    meta = {
        "format_version": FORMAT_VERSION,
        "width": 4, "height": 3, "active_layer": 0,
        "layers": [_layer_meta()],
    }
    meta.update(overrides)
    return meta


def _image(h: int = 3, w: int = 4) -> np.ndarray:
    return np.full((h, w, 4), 7, dtype=np.uint8)


def _load_raw(tmp_path, metadata, **extra) -> PaintDocument:
    arrays = {"_metadata": np.array(json.dumps(metadata)), **extra}
    return load_document(_write_raw(tmp_path, arrays))


# ---------------------------------------------------------------------------
# Writer: archive members, metadata, array bytes
# ---------------------------------------------------------------------------


def test_archive_member_names_are_pinned():
    blob = save_document_to_buffer(_representative_document())
    assert _members(blob) == sorted([
        "_metadata.npy", "layer_0_image.npy", "layer_1_image.npy",
        "layer_1_mask.npy", "layer_2_image.npy", "named_selection_0.npy",
        "selection.npy",
    ])


def test_file_and_buffer_carry_the_same_members_and_arrays(tmp_path):
    doc = _representative_document()
    target = tmp_path / f"art{FILE_EXTENSION}"
    save_document(doc, target)
    on_disk = target.read_bytes()
    in_memory = save_document_to_buffer(doc)
    assert _members(on_disk) == _members(in_memory)
    disk_arrays, mem_arrays = _arrays(on_disk), _arrays(in_memory)
    for key, value in mem_arrays.items():
        assert np.array_equal(disk_arrays[key], value)
        assert disk_arrays[key].dtype == value.dtype


def test_metadata_json_is_pinned():
    arrays = _arrays(save_document_to_buffer(_representative_document()))
    assert arrays["_metadata"].ndim == 0
    meta = json.loads(str(arrays["_metadata"].item()))
    assert list(meta) == [
        "format_version", "width", "height", "active_layer", "layers",
        "groups", "named_selections", "panel_layout", "reference_layer",
    ]
    assert meta["format_version"] == 1
    assert (meta["width"], meta["height"]) == (_W, _H)
    assert meta["active_layer"] == 1
    assert meta["reference_layer"] == 0
    assert meta["named_selections"] == ["corner"]
    assert meta["groups"] == [{
        "name": "Inks", "visible": True, "opacity": 0.5,
        "blend_mode": "multiply", "locked": False, "expanded": False,
    }]
    assert meta["panel_layout"] == {
        "width": _W, "height": _H,
        "cells": [{"x": 0, "y": 0, "w": 4, "h": 3}],
        "gutter": 1, "border_width": 2,
    }
    assert [list(entry) for entry in meta["layers"]] == [list(_LAYER_KEYS)] * 3


def test_layer_metadata_entries_are_pinned():
    arrays = _arrays(save_document_to_buffer(_representative_document()))
    base, inked, top = json.loads(str(arrays["_metadata"].item()))["layers"]
    assert inked == {
        "name": "Inked", "opacity": 0.75, "blend_mode": "screen",
        "visible": True, "locked": False, "lock_alpha": False,
        "mask_enabled": True, "clip": False, "has_mask": True,
        "group": "Inks",
        "adjustment": Adjustment.from_dict({"kind": "hsv"}).to_dict(),
        "effects": [LayerEffect.from_dict({"kind": "stroke"}).to_dict()],
        "tone": None, "binary": None, "blend_if": None,
        "vector_strokes": None, "color_label": "blue",
    }
    assert base["has_mask"] is False and base["group"] is None
    assert base["adjustment"] is None and base["effects"] == []
    assert (top["visible"], top["locked"]) == (False, True)


def test_written_arrays_are_pinned_by_dtype_shape_and_hash():
    doc = _representative_document()
    arrays = _arrays(save_document_to_buffer(doc))
    for i, layer in enumerate(doc.layers()):
        image = arrays[f"layer_{i}_image"]
        assert image.dtype == np.uint8 and image.shape == (_H, _W, 4)
        assert (hashlib.sha256(image.tobytes()).hexdigest()
                == hashlib.sha256(layer.image.tobytes()).hexdigest())
    assert arrays["layer_1_mask"].dtype == np.uint8
    assert np.all(arrays["layer_1_mask"] == 128)
    assert arrays["selection"].dtype == np.bool_
    assert int(arrays["selection"].sum()) == 6
    assert np.array_equal(arrays["named_selection_0"], arrays["selection"])


def test_document_without_selection_or_extras_writes_minimal_members():
    doc = PaintDocument()
    doc.load_image(_image())
    blob = save_document_to_buffer(doc)
    assert _members(blob) == ["_metadata.npy", "layer_0_image.npy"]
    meta = json.loads(str(_arrays(blob)["_metadata"].item()))
    assert meta["groups"] == [] and meta["named_selections"] == []
    assert meta["panel_layout"] is None and meta["reference_layer"] is None


def test_save_rejects_an_empty_document():
    with pytest.raises(ValueError, match="no layers to write"):
        save_document_to_buffer(PaintDocument())


def test_save_rejects_a_document_with_unknown_shape(monkeypatch):
    doc = PaintDocument()
    doc.load_image(_image())
    monkeypatch.setattr(PaintDocument, "shape", property(lambda _self: None))
    with pytest.raises(ValueError, match="unknown shape"):
        save_document_to_buffer(doc)


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------


def test_representative_document_round_trips_through_buffer():
    doc = _representative_document()
    loaded = load_document_from_buffer(save_document_to_buffer(doc))
    assert [layer.name for layer in loaded.layers()] == ["Background", "Inked", "Top"]
    for want, got in zip(doc.layers(), loaded.layers(), strict=True):
        assert np.array_equal(want.image, got.image)
        assert (got.opacity, got.blend_mode, got.visible, got.locked) == (
            want.opacity, want.blend_mode, want.visible, want.locked)
        assert got.group == want.group
        assert got.adjustment == want.adjustment
        assert tuple(got.effects) == tuple(want.effects)
        assert got.color_label == want.color_label
    assert np.array_equal(loaded.layers()[1].mask, doc.layers()[1].mask)
    assert loaded.layers()[0].mask is None
    assert loaded.active_layer_index() == 1
    assert loaded.reference_layer_index() == 0
    assert loaded.group("Inks") == doc.group("Inks")
    assert loaded.list_named_selections() == ["corner"]
    assert np.array_equal(loaded.named_selection("corner"), doc.selection())
    assert np.array_equal(loaded.selection(), doc.selection())
    assert loaded.panel_layout == doc.panel_layout


def test_round_trip_is_stable_on_a_second_save(tmp_path):
    first = save_document_to_buffer(_representative_document())
    second = save_document_to_buffer(load_document_from_buffer(first))
    assert _members(first) == _members(second)
    one, two = _arrays(first), _arrays(second)
    for key in one:
        assert np.array_equal(one[key], two[key])


# ---------------------------------------------------------------------------
# Loader: hard errors
# ---------------------------------------------------------------------------


def test_load_rejects_a_missing_metadata_entry(tmp_path):
    path = _write_raw(tmp_path, {"layer_0_image": _image()})
    with pytest.raises(ValueError, match="missing the _metadata entry"):
        load_document(path)


def test_load_rejects_non_object_metadata(tmp_path):
    with pytest.raises(ValueError, match="metadata must be an object, got list"):
        _load_raw(tmp_path, [1, 2])


def test_load_rejects_a_one_dimensional_metadata_array(tmp_path):
    arrays = {"_metadata": np.array([json.dumps(_metadata())]),
              "layer_0_image": _image()}
    with pytest.raises(ValueError, match="not valid JSON"):
        load_document(_write_raw(tmp_path, arrays))


def test_load_rejects_missing_format_version(tmp_path):
    meta = _metadata()
    del meta["format_version"]
    with pytest.raises(ValueError, match="unsupported document format version None"):
        _load_raw(tmp_path, meta, layer_0_image=_image())


@pytest.mark.parametrize("layers", [None, [], "abc"])
def test_load_rejects_metadata_without_layers(tmp_path, layers):
    with pytest.raises(ValueError, match="document metadata has no layers"):
        _load_raw(tmp_path, _metadata(layers=layers))


def test_load_rejects_a_non_object_layer_entry(tmp_path):
    meta = _metadata(layers=[_layer_meta(), "oops"])
    with pytest.raises(ValueError, match="layer 1 metadata must be an object"):
        _load_raw(tmp_path, meta, layer_0_image=_image(), layer_1_image=_image())


def test_load_rejects_a_non_uint8_layer_image(tmp_path):
    with pytest.raises(ValueError, match="layer 0 dtype float32 must be uint8"):
        _load_raw(tmp_path, _metadata(),
                  layer_0_image=_image().astype(np.float32))


def test_load_reports_the_expected_layer_shape(tmp_path):
    with pytest.raises(ValueError, match=r"layer 0 shape \(3, 4, 3\) does not match "
                                         r"document \(3, 4, 4\)"):
        _load_raw(tmp_path, _metadata(), layer_0_image=_image()[..., :3])


def test_load_rejects_a_flagged_but_missing_mask(tmp_path):
    meta = _metadata(layers=[_layer_meta(has_mask=True)])
    with pytest.raises(ValueError, match="missing array 'layer_0_mask'"):
        _load_raw(tmp_path, meta, layer_0_image=_image())


def test_load_rejects_a_mask_of_the_wrong_shape(tmp_path):
    meta = _metadata(layers=[_layer_meta(has_mask=True)])
    with pytest.raises(ValueError, match=r"layer 0 mask shape \(2, 2\) does not match "
                                         r"document \(3, 4\)"):
        _load_raw(tmp_path, meta, layer_0_image=_image(),
                  layer_0_mask=np.zeros((2, 2), dtype=np.uint8))


def test_load_ignores_a_mask_array_when_metadata_says_none(tmp_path):
    doc = _load_raw(tmp_path, _metadata(), layer_0_image=_image(),
                    layer_0_mask=np.zeros((3, 4), dtype=np.uint8))
    assert doc.layers()[0].mask is None


def test_load_rejects_a_non_bool_selection(tmp_path):
    with pytest.raises(ValueError, match="selection dtype uint8 must be bool"):
        _load_raw(tmp_path, _metadata(), layer_0_image=_image(),
                  selection=np.zeros((3, 4), dtype=np.uint8))


def test_load_rejects_a_selection_of_the_wrong_shape(tmp_path):
    with pytest.raises(ValueError, match=r"selection shape \(4, 3\) does not match document"):
        _load_raw(tmp_path, _metadata(), layer_0_image=_image(),
                  selection=np.zeros((4, 3), dtype=bool))


def test_load_refuses_pickled_object_arrays(tmp_path):
    path = tmp_path / f"evil{FILE_EXTENSION}"
    with open(path, "wb") as fh:
        np.savez(fh, _metadata=np.array([{"x": 1}], dtype=object),
                 layer_0_image=_image())
    with pytest.raises(ValueError, match="allow_pickle"):
        load_document(path)


def test_load_rejects_malformed_panel_layout(tmp_path):
    with pytest.raises(ValueError, match="panel layout must be an object"):
        _load_raw(tmp_path, _metadata(panel_layout=[1]), layer_0_image=_image())


def test_load_propagates_a_non_numeric_layer_opacity(tmp_path):
    meta = _metadata(layers=[_layer_meta(opacity="loud")])
    with pytest.raises(ValueError, match="could not convert"):
        _load_raw(tmp_path, meta, layer_0_image=_image())


# ---------------------------------------------------------------------------
# Loader: tolerated legacy / damaged fields
# ---------------------------------------------------------------------------


def test_minimal_legacy_metadata_loads_with_defaults(tmp_path):
    meta = {"format_version": FORMAT_VERSION, "width": 4, "height": 3,
            "layers": [{}]}
    doc = _load_raw(tmp_path, meta, layer_0_image=_image())
    layer = doc.layers()[0]
    assert layer.name == "Layer 0"
    assert (layer.opacity, layer.blend_mode, layer.visible) == (1.0, "normal", True)
    assert (layer.locked, layer.mask_enabled, layer.clip, layer.lock_alpha) == (
        False, True, False, False)
    assert layer.group is None and layer.adjustment is None
    assert tuple(layer.effects) == ()
    assert layer.tone is None and layer.binary is None and layer.blend_if is None
    assert layer.vector_data is None and layer.color_label is None
    assert doc.active_layer_index() == 0
    assert doc.reference_layer_index() is None
    assert doc.list_named_selections() == []
    assert doc.selection() is None
    assert doc.panel_layout is None


def test_unknown_layer_blend_mode_falls_back_to_normal(tmp_path):
    meta = _metadata(layers=[_layer_meta(blend_mode="sparkle")])
    doc = _load_raw(tmp_path, meta, layer_0_image=_image())
    assert doc.layers()[0].blend_mode == "normal"


@pytest.mark.parametrize(("raw", "expected"), [(-5, 0), (99, 1), (1, 1)])
def test_active_layer_index_is_clamped(tmp_path, raw, expected):
    meta = _metadata(active_layer=raw, layers=[_layer_meta(), _layer_meta()])
    doc = _load_raw(tmp_path, meta, layer_0_image=_image(), layer_1_image=_image())
    assert doc.active_layer_index() == expected


@pytest.mark.parametrize("raw", [-1, 2, "0", 1.0, None])
def test_out_of_range_or_non_int_reference_layer_is_dropped(tmp_path, raw):
    meta = _metadata(reference_layer=raw, layers=[_layer_meta(), _layer_meta()])
    doc = _load_raw(tmp_path, meta, layer_0_image=_image(), layer_1_image=_image())
    assert doc.reference_layer_index() is None


def test_in_range_reference_layer_is_kept(tmp_path):
    meta = _metadata(reference_layer=1, layers=[_layer_meta(), _layer_meta()])
    doc = _load_raw(tmp_path, meta, layer_0_image=_image(), layer_1_image=_image())
    assert doc.reference_layer_index() == 1


def test_bad_adjustment_and_effects_are_dropped(tmp_path):
    meta = _metadata(layers=[_layer_meta(
        adjustment={"kind": "nope"},
        effects=[{"kind": "nope"}, "junk", {"kind": "drop_shadow"}],
    )])
    layer = _load_raw(tmp_path, meta, layer_0_image=_image()).layers()[0]
    assert layer.adjustment is None
    assert [eff.kind for eff in layer.effects] == ["drop_shadow"]


def test_non_list_effects_and_non_dict_adjustment_are_dropped(tmp_path):
    meta = _metadata(layers=[_layer_meta(adjustment="hsv", effects={"a": 1})])
    layer = _load_raw(tmp_path, meta, layer_0_image=_image()).layers()[0]
    assert layer.adjustment is None and tuple(layer.effects) == ()


def test_vector_strokes_skip_non_dict_entries(tmp_path):
    meta = _metadata(layers=[_layer_meta(vector_strokes=["junk", 3])])
    layer = _load_raw(tmp_path, meta, layer_0_image=_image()).layers()[0]
    assert layer.vector_data is not None
    assert layer.vector_data.strokes == []


def test_non_dict_blend_if_and_unknown_label_are_dropped(tmp_path):
    meta = _metadata(layers=[_layer_meta(blend_if=[1], color_label="plaid")])
    layer = _load_raw(tmp_path, meta, layer_0_image=_image()).layers()[0]
    assert layer.blend_if is None and layer.color_label is None


def test_empty_group_name_on_a_layer_becomes_none(tmp_path):
    meta = _metadata(layers=[_layer_meta(group="")])
    assert _load_raw(tmp_path, meta, layer_0_image=_image()).layers()[0].group is None


def test_group_registry_skips_damaged_entries(tmp_path):
    groups = [
        "junk",
        {"name": "   "},
        {"name": "Bad", "opacity": "heavy"},
        {"name": "Odd", "blend_mode": "sparkle", "opacity": 3},
        {"name": " Kept ", "visible": False, "locked": True},
    ]
    doc = _load_raw(tmp_path, _metadata(groups=groups), layer_0_image=_image())
    names = sorted(grp.name for grp in doc.groups())
    assert names == ["Kept", "Odd"]
    odd = doc.group("Odd")
    assert odd.blend_mode == "pass_through" and odd.opacity == pytest.approx(1.0)
    kept = doc.group("Kept")
    assert (kept.visible, kept.locked, kept.expanded) == (False, True, True)


def test_non_list_groups_load_as_empty(tmp_path):
    doc = _load_raw(tmp_path, _metadata(groups={"a": 1}), layer_0_image=_image())
    assert list(doc.groups()) == []


def test_named_selections_skip_missing_or_invalid_arrays(tmp_path):
    good = np.ones((3, 4), dtype=bool)
    doc = _load_raw(
        tmp_path, _metadata(named_selections=["gone", "wrong-dtype", "wrong-shape", 7]),
        layer_0_image=_image(),
        named_selection_1=np.ones((3, 4), dtype=np.uint8),
        named_selection_2=np.ones((4, 3), dtype=bool),
        named_selection_3=good,
    )
    assert doc.list_named_selections() == ["7"]
    assert np.array_equal(doc.named_selection("7"), good)


def test_non_list_named_selections_load_as_empty(tmp_path):
    doc = _load_raw(tmp_path, _metadata(named_selections="corner"),
                    layer_0_image=_image(),
                    named_selection_0=np.ones((3, 4), dtype=bool))
    assert doc.list_named_selections() == []
