"""Pure-Python tests for the editor authoring operations.

No Qt fixture needed — every entry point is a function on a
:class:`PuppetDocument` and returns ``True`` on success.
"""
from __future__ import annotations

import pytest

from Imervue.puppet.document import (
    Drawable,
    PuppetDocument,
)
from Imervue.puppet.operations import (
    add_parameter,
    add_rotation_deformer,
    add_warp_deformer,
    remove_deformer,
    remove_key,
    remove_parameter,
    set_key_at_value,
    snapshot_current_forms,
)


def _doc_with_drawable() -> PuppetDocument:
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
            draw_order=0,
        ),
    ]
    return doc


# ---------------------------------------------------------------------------
# Deformers
# ---------------------------------------------------------------------------


def test_add_rotation_deformer_targets_all_drawables_by_default():
    doc = _doc_with_drawable()
    assert add_rotation_deformer(doc, "rot1") is True
    d = doc.deformer("rot1")
    assert d is not None
    assert d.type == "rotation"
    assert d.drawables == ["x"]
    assert d.form["angle"] == pytest.approx(0.0)
    # anchor defaults to canvas centre
    assert d.form["anchor"] == [50.0, 50.0]


def test_add_rotation_deformer_rejects_duplicate_id():
    doc = _doc_with_drawable()
    add_rotation_deformer(doc, "rot1")
    assert add_rotation_deformer(doc, "rot1") is False
    assert len(doc.deformers) == 1


def test_add_warp_deformer_defaults_cover_canvas():
    doc = _doc_with_drawable()
    assert add_warp_deformer(doc, "warp1") is True
    d = doc.deformer("warp1")
    assert d.type == "warp"
    assert d.form["bounds"] == [0.0, 0.0, 100.0, 100.0]
    assert d.form["rows"] == 5
    assert d.form["cols"] == 5


def test_add_warp_deformer_with_custom_bounds_and_dimensions():
    doc = _doc_with_drawable()
    add_warp_deformer(
        doc, "warp", bounds=(10.0, 20.0, 90.0, 80.0), rows=3, cols=4,
    )
    d = doc.deformer("warp")
    assert d.form["bounds"] == [10.0, 20.0, 90.0, 80.0]
    assert d.form["rows"] == 3
    assert d.form["cols"] == 4


def test_remove_deformer_drops_keys_referencing_it():
    doc = _doc_with_drawable()
    add_rotation_deformer(doc, "rot")
    add_parameter(doc, "P", min_value=0.0, max_value=1.0, default=0.0)
    set_key_at_value(doc, "P", 1.0, {"rot": {"angle": 0.5}})
    assert remove_deformer(doc, "rot") is True
    assert doc.deformer("rot") is None
    # Key for that deformer dropped
    assert doc.parameter("P").keys[0].forms == {}


def test_remove_unknown_deformer_returns_false():
    doc = _doc_with_drawable()
    assert remove_deformer(doc, "ghost") is False


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


def test_add_parameter_defaults():
    doc = _doc_with_drawable()
    assert add_parameter(doc, "ParamAngleX") is True
    p = doc.parameter("ParamAngleX")
    assert p.min == pytest.approx(-1.0)
    assert p.max == pytest.approx(1.0)
    assert p.default == pytest.approx(0.0)
    assert p.keys == []


def test_add_parameter_rejects_duplicate_id():
    doc = _doc_with_drawable()
    add_parameter(doc, "P")
    assert add_parameter(doc, "P") is False
    assert len(doc.parameters) == 1


def test_add_parameter_rejects_inverted_range():
    doc = _doc_with_drawable()
    with pytest.raises(ValueError, match="must be <="):
        add_parameter(doc, "P", min_value=1.0, max_value=-1.0)


def test_add_parameter_rejects_default_outside_range():
    doc = _doc_with_drawable()
    with pytest.raises(ValueError, match="within"):
        add_parameter(doc, "P", min_value=0.0, max_value=1.0, default=5.0)


def test_remove_parameter():
    doc = _doc_with_drawable()
    add_parameter(doc, "P")
    assert remove_parameter(doc, "P") is True
    assert doc.parameter("P") is None
    assert remove_parameter(doc, "Q") is False


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------


def test_set_key_appends_new_key_in_sorted_order():
    doc = _doc_with_drawable()
    add_parameter(doc, "P", min_value=-1.0, max_value=1.0)
    set_key_at_value(doc, "P", 1.0, {"d": {"angle": 1.0}})
    set_key_at_value(doc, "P", -1.0, {"d": {"angle": -1.0}})
    set_key_at_value(doc, "P", 0.0, {"d": {"angle": 0.0}})
    keys = doc.parameter("P").keys
    assert [k.value for k in keys] == [-1.0, 0.0, 1.0]


def test_set_key_replaces_existing_at_same_value():
    doc = _doc_with_drawable()
    add_parameter(doc, "P")
    set_key_at_value(doc, "P", 0.0, {"d": {"angle": 0.0}})
    set_key_at_value(doc, "P", 0.0, {"d": {"angle": 0.5}})
    keys = doc.parameter("P").keys
    assert len(keys) == 1
    assert keys[0].forms == {"d": {"angle": 0.5}}


def test_set_key_rejects_value_outside_range():
    doc = _doc_with_drawable()
    add_parameter(doc, "P", min_value=0.0, max_value=1.0)
    with pytest.raises(ValueError, match="outside"):
        set_key_at_value(doc, "P", 2.0, {})


def test_set_key_unknown_parameter_returns_false():
    doc = _doc_with_drawable()
    assert set_key_at_value(doc, "missing", 0.0, {}) is False


def test_remove_key_drops_matching_value():
    doc = _doc_with_drawable()
    add_parameter(doc, "P", min_value=-1.0, max_value=1.0)
    set_key_at_value(doc, "P", 0.5, {"d": {"x": 1.0}})
    set_key_at_value(doc, "P", -0.5, {"d": {"x": -1.0}})
    assert remove_key(doc, "P", 0.5) is True
    keys = doc.parameter("P").keys
    assert [k.value for k in keys] == [-0.5]


def test_remove_key_no_match_returns_false():
    doc = _doc_with_drawable()
    add_parameter(doc, "P")
    assert remove_key(doc, "P", 0.0) is False


# ---------------------------------------------------------------------------
# snapshot_current_forms
# ---------------------------------------------------------------------------


def test_snapshot_returns_independent_copies():
    doc = _doc_with_drawable()
    add_rotation_deformer(doc, "rot")
    snap = snapshot_current_forms(doc)
    assert "rot" in snap
    snap["rot"]["angle"] = 999.0
    assert doc.deformer("rot").form["angle"] == pytest.approx(0.0)   # unaffected by mutation


def test_snapshot_empty_for_no_deformers():
    doc = _doc_with_drawable()
    assert snapshot_current_forms(doc) == {}
