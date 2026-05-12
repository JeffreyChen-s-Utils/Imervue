"""Tests for the auto-symmetrize helpers."""
from __future__ import annotations

import pytest

from puppet.document import Deformer, Drawable, PuppetDocument
from puppet.symmetrize import (
    auto_mirror_pair,
    mirror_drawable,
    mirror_id,
    mirror_rotation_deformer,
)


def _drawable(id_: str, vertices: list[tuple[float, float]]) -> Drawable:
    n = len(vertices)
    return Drawable(
        id=id_, texture=f"textures/{id_}.png",
        vertices=vertices,
        indices=list(range(n)) if n >= 3 else [],
        uvs=[(0.0, 0.0)] * n,
        draw_order=0,
    )


# ---------------------------------------------------------------------------
# mirror_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source,expected", [
    ("eye_l", "eye_r"),
    ("eye_r", "eye_l"),
    ("eye_left", "eye_right"),
    ("eye_right", "eye_left"),
    ("l_eye", "r_eye"),
    ("r_eye", "l_eye"),
    ("left_arm", "right_arm"),
    ("right_arm", "left_arm"),
])
def test_mirror_id_known_token_swap(source, expected):
    assert mirror_id(source) == expected


def test_mirror_id_falls_back_to_mirrored_suffix():
    assert mirror_id("head") == "head_mirrored"


# ---------------------------------------------------------------------------
# mirror_drawable
# ---------------------------------------------------------------------------


def test_mirror_drawable_reflects_vertices_about_axis():
    drawable = _drawable("eye_l", [(2.0, 0.0), (4.0, 0.0), (3.0, 1.0)])
    mirrored = mirror_drawable(drawable, axis_x=5.0)
    assert mirrored.vertices == [(8.0, 0.0), (6.0, 0.0), (7.0, 1.0)]


def test_mirror_drawable_reverses_triangle_winding():
    drawable = _drawable("eye_l", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])
    mirrored = mirror_drawable(drawable, axis_x=2.0)
    assert mirrored.indices == [0, 2, 1]


def test_mirror_drawable_defaults_new_id_to_mirror_id():
    drawable = _drawable("eye_l", [(0.0, 0.0)])
    mirrored = mirror_drawable(drawable, axis_x=1.0)
    assert mirrored.id == "eye_r"


def test_mirror_drawable_keeps_uvs_untouched():
    drawable = _drawable("x", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])
    drawable.uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
    mirrored = mirror_drawable(drawable, axis_x=10.0)
    assert mirrored.uvs == drawable.uvs


def test_mirror_drawable_explicit_new_id_overrides_heuristic():
    drawable = _drawable("eye_l", [(0.0, 0.0)])
    mirrored = mirror_drawable(drawable, axis_x=1.0, new_id="custom")
    assert mirrored.id == "custom"


# ---------------------------------------------------------------------------
# mirror_rotation_deformer
# ---------------------------------------------------------------------------


def test_mirror_rotation_deformer_flips_anchor_x_and_negates_angle():
    deformer = Deformer(
        id="rot_l", type="rotation", parent=None,
        drawables=["eye_l"], form={"anchor": [3.0, 5.0], "angle": 0.5},
    )
    mirrored = mirror_rotation_deformer(deformer, axis_x=5.0)
    assert mirrored.form["anchor"] == [7.0, 5.0]
    assert mirrored.form["angle"] == pytest.approx(-0.5)
    assert mirrored.id == "rot_r"


def test_mirror_rotation_deformer_rejects_non_rotation_type():
    deformer = Deformer(
        id="warp", type="warp", parent=None,
        drawables=["x"], form={"rows": 5, "cols": 5},
    )
    with pytest.raises(ValueError):
        mirror_rotation_deformer(deformer, axis_x=0.0)


# ---------------------------------------------------------------------------
# auto_mirror_pair — composite
# ---------------------------------------------------------------------------


def test_auto_mirror_pair_registers_mirrored_drawable():
    doc = PuppetDocument(size=(10, 10))
    doc.drawables = [_drawable("eye_l", [(2.0, 0.0), (4.0, 0.0), (3.0, 1.0)])]
    out = auto_mirror_pair(doc, "eye_l")
    assert out is not None
    assert out.id == "eye_r"
    # Mirror about canvas centre x=5.0
    assert out.vertices == [(8.0, 0.0), (6.0, 0.0), (7.0, 1.0)]
    # Document now carries both
    assert [d.id for d in doc.drawables] == ["eye_l", "eye_r"]


def test_auto_mirror_pair_returns_none_when_source_missing():
    doc = PuppetDocument(size=(10, 10))
    assert auto_mirror_pair(doc, "ghost") is None


def test_auto_mirror_pair_returns_none_when_target_id_exists():
    doc = PuppetDocument(size=(10, 10))
    doc.drawables = [
        _drawable("eye_l", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]),
        _drawable("eye_r", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]),
    ]
    # Default mirror id 'eye_r' already exists
    assert auto_mirror_pair(doc, "eye_l") is None


def test_auto_mirror_pair_explicit_axis():
    doc = PuppetDocument(size=(10, 10))
    doc.drawables = [_drawable("eye_l", [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])]
    out = auto_mirror_pair(doc, "eye_l", axis_x=20.0)
    assert out is not None
    assert out.vertices == [(40.0, 0.0), (39.0, 0.0), (39.0, 1.0)]
