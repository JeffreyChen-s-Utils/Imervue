"""Tests for the puppet bone-weight normalise / repair helpers."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.puppet.bone_weights import (
    is_normalised,
    needs_repair,
    normalize_bone_weights,
    normalize_drawable_weights,
    per_vertex_sums,
)


# ---------------------------------------------------------------------------
# per_vertex_sums
# ---------------------------------------------------------------------------


def test_per_vertex_sums_adds_across_bones():
    weights = {"a": [0.3, 0.6], "b": [0.7, 0.4]}
    assert per_vertex_sums(weights, 2) == pytest.approx([1.0, 1.0])


def test_per_vertex_sums_tolerates_short_lists():
    weights = {"a": [0.5]}  # only one entry but two vertices
    assert per_vertex_sums(weights, 2) == pytest.approx([0.5, 0.0])


# ---------------------------------------------------------------------------
# is_normalised
# ---------------------------------------------------------------------------


def test_is_normalised_true_when_each_vertex_sums_to_one():
    assert is_normalised({"a": [0.25, 1.0], "b": [0.75, 0.0]}, 2)


def test_is_normalised_false_when_a_vertex_is_off():
    assert not is_normalised({"a": [0.5, 0.6]}, 2)


def test_is_normalised_allows_uninfluenced_vertices():
    # Vertex 1 has zero total influence — LBS leaves it at rest, that's fine.
    assert is_normalised({"a": [1.0, 0.0]}, 2)


# ---------------------------------------------------------------------------
# needs_repair
# ---------------------------------------------------------------------------


def test_needs_repair_flags_negative_weight():
    assert needs_repair({"a": [1.2, 1.0], "b": [-0.2, 0.0]}, 2)


def test_needs_repair_flags_wrong_length():
    assert needs_repair({"a": [1.0]}, 3)


def test_needs_repair_flags_unnormalised_sum():
    assert needs_repair({"a": [0.4, 0.4]}, 2)


def test_needs_repair_false_for_clean_map():
    assert not needs_repair({"a": [0.5, 1.0], "b": [0.5, 0.0]}, 2)


# ---------------------------------------------------------------------------
# normalize_bone_weights
# ---------------------------------------------------------------------------


def test_normalize_makes_each_vertex_sum_to_one():
    out = normalize_bone_weights({"a": [0.3, 0.2], "b": [0.3, 0.2]}, 2)
    sums = per_vertex_sums(out, 2)
    assert sums == pytest.approx([1.0, 1.0])


def test_normalize_clamps_negative_weights():
    out = normalize_bone_weights({"a": [2.0, 1.0], "b": [-1.0, 0.0]}, 2)
    assert out["b"][0] == pytest.approx(0.0)
    assert out["a"][0] == pytest.approx(1.0)  # only positive weight remains


def test_normalize_pads_and_truncates_to_vertex_count():
    out = normalize_bone_weights({"a": [1.0]}, 3)
    assert len(out["a"]) == 3
    out2 = normalize_bone_weights({"a": [1.0, 1.0, 1.0]}, 2)
    assert len(out2["a"]) == 2


def test_normalize_leaves_uninfluenced_vertex_at_zero():
    out = normalize_bone_weights({"a": [1.0, 0.0]}, 2)
    assert out["a"][1] == pytest.approx(0.0)


def test_normalize_does_not_mutate_input():
    src = {"a": [2.0, 0.0]}
    normalize_bone_weights(src, 2)
    assert src == {"a": [2.0, 0.0]}


def test_normalize_fixes_rounding_drift():
    # The classic "exported from Blender at 3 dp so it sums to 0.999" case.
    out = normalize_bone_weights({"a": [0.333, 0.5], "b": [0.666, 0.5]}, 2)
    assert per_vertex_sums(out, 2)[0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# normalize_drawable_weights (in place, duck-typed)
# ---------------------------------------------------------------------------


def test_drawable_repair_normalises_in_place():
    drawable = SimpleNamespace(
        vertices=[(0, 0), (1, 1)], bone_weights={"a": [0.4, 0.4], "b": [0.4, 0.4]},
    )
    assert normalize_drawable_weights(drawable) is True
    assert per_vertex_sums(drawable.bone_weights, 2) == pytest.approx([1.0, 1.0])


def test_drawable_repair_skips_clean_map():
    drawable = SimpleNamespace(
        vertices=[(0, 0), (1, 1)], bone_weights={"a": [0.5, 1.0], "b": [0.5, 0.0]},
    )
    assert normalize_drawable_weights(drawable) is False


def test_drawable_repair_skips_when_no_weights():
    assert normalize_drawable_weights(
        SimpleNamespace(vertices=[(0, 0)], bone_weights=None)) is False
    assert normalize_drawable_weights(
        SimpleNamespace(vertices=[], bone_weights={"a": [1.0]})) is False
