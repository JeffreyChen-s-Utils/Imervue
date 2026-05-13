"""Tests for the puppet validator.

Every check has at least one happy-path (clean doc) and one
diagnostic case so the validator's matrix of rule codes stays
covered as the document schema grows. Reuses the dataclasses
directly — no Qt fixture needed."""
from __future__ import annotations

from Imervue.puppet.document import (
    Deformer,
    Drawable,
    Expression,
    HitArea,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    ParameterKey,
    Part,
    PoseGroup,
    PuppetDocument,
)
from Imervue.puppet.validator import Issue, severity_counts, validate


def _empty_drawable(id_: str = "x") -> Drawable:
    return Drawable(
        id=id_, texture=f"textures/{id_}.png",
        vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        indices=[0, 1, 2],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        draw_order=0,
    )


def _clean_doc() -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    drawable = _empty_drawable()
    doc.drawables = [drawable]
    doc.textures = {drawable.texture: b""}
    return doc


def _codes(issues: list[Issue]) -> set[str]:
    return {i.code for i in issues}


# ---------------------------------------------------------------------------
# Clean documents
# ---------------------------------------------------------------------------


def test_clean_doc_has_no_errors_or_warnings():
    issues = validate(_clean_doc())
    assert not any(i.severity == "error" for i in issues)
    assert not any(i.severity == "warning" for i in issues)


def test_severity_counts_aggregates_by_level():
    doc = _clean_doc()
    # Force one of each
    doc.drawables.append(_empty_drawable("dup"))
    doc.drawables.append(_empty_drawable("dup"))   # duplicate id
    doc.drawables[1].opacity = 2.0   # out of range warning
    counts = severity_counts(validate(doc))
    assert counts["error"] >= 1
    assert counts["warning"] >= 1


# ---------------------------------------------------------------------------
# Drawable checks
# ---------------------------------------------------------------------------


def test_duplicate_drawable_ids_flag_error():
    doc = _clean_doc()
    doc.drawables.append(_empty_drawable("x"))   # same id as the first
    doc.textures["textures/x.png"] = b""
    assert "duplicate_drawable_id" in _codes(validate(doc))


def test_drawable_opacity_out_of_range_is_warning():
    doc = _clean_doc()
    doc.drawables[0].opacity = 1.5
    issues = validate(doc)
    assert any(i.code == "drawable_opacity_out_of_range" for i in issues)


def test_clip_mask_pointing_at_unknown_drawable_is_error():
    doc = _clean_doc()
    doc.drawables[0].clip_mask = "no_such_drawable"
    assert "clip_mask_not_found" in _codes(validate(doc))


# ---------------------------------------------------------------------------
# Texture checks
# ---------------------------------------------------------------------------


def test_missing_texture_is_error():
    doc = _clean_doc()
    del doc.textures[doc.drawables[0].texture]
    assert "texture_missing" in _codes(validate(doc))


def test_unused_texture_is_info():
    doc = _clean_doc()
    doc.textures["textures/unused.png"] = b""
    codes = _codes(validate(doc))
    assert "texture_unused" in codes


# ---------------------------------------------------------------------------
# Deformer checks
# ---------------------------------------------------------------------------


def test_deformer_orphan_drawable_is_error():
    doc = _clean_doc()
    doc.deformers.append(Deformer(
        id="rot", type="rotation", parent=None,
        drawables=["nope"], form={"anchor": [0, 0], "angle": 0.0},
    ))
    assert "deformer_orphan_drawable" in _codes(validate(doc))


def test_deformer_orphan_parent_is_error():
    doc = _clean_doc()
    doc.deformers.append(Deformer(
        id="child", type="rotation", parent="missing_parent",
        drawables=["x"], form={"anchor": [0, 0], "angle": 0.0},
    ))
    assert "deformer_orphan_parent" in _codes(validate(doc))


def test_duplicate_deformer_ids_flag_error():
    doc = _clean_doc()
    for _ in range(2):
        doc.deformers.append(Deformer(
            id="rot", type="rotation", parent=None,
            drawables=["x"], form={"anchor": [0, 0], "angle": 0.0},
        ))
    assert "duplicate_deformer_id" in _codes(validate(doc))


# ---------------------------------------------------------------------------
# Parameter checks
# ---------------------------------------------------------------------------


def test_duplicate_parameter_id_is_error():
    doc = _clean_doc()
    doc.parameters = [
        Parameter(id="A", min=-1, max=1, default=0),
        Parameter(id="A", min=-1, max=1, default=0),
    ]
    assert "duplicate_parameter_id" in _codes(validate(doc))


def test_parameter_inverted_range_is_error():
    doc = _clean_doc()
    doc.parameters = [Parameter(id="A", min=1, max=-1, default=0)]
    assert "parameter_inverted_range" in _codes(validate(doc))


def test_default_outside_range_is_warning():
    doc = _clean_doc()
    doc.parameters = [Parameter(id="A", min=0, max=1, default=5)]
    assert "parameter_default_out_of_range" in _codes(validate(doc))


def test_keyform_outside_range_is_warning():
    doc = _clean_doc()
    doc.parameters = [
        Parameter(
            id="A", min=-1, max=1, default=0,
            keys=[ParameterKey(value=5.0, forms={})],
        ),
    ]
    assert "keyform_out_of_range" in _codes(validate(doc))


# ---------------------------------------------------------------------------
# Motion / pose / hit area / part / bone-weight
# ---------------------------------------------------------------------------


def test_motion_unknown_parameter_is_warning():
    doc = _clean_doc()
    doc.motions = [Motion(
        name="m", duration=1.0,
        tracks=[MotionTrack(
            param_id="ParamUnknown",
            segments=[MotionSegment(type="linear", p0=(0, 0), p1=(1, 1))],
        )],
    )]
    assert "motion_unknown_parameter" in _codes(validate(doc))


def test_pose_group_orphan_drawable_is_warning():
    doc = _clean_doc()
    doc.pose_groups = [PoseGroup(id="g", drawables=["ghost"])]
    assert "pose_group_orphan_drawable" in _codes(validate(doc))


def test_hit_area_orphan_expression_is_warning():
    doc = _clean_doc()
    doc.hit_areas = [HitArea(
        id="head", drawables=["x"], expression="missing_expression",
    )]
    doc.expressions = [Expression(name="smile")]
    assert "hit_area_orphan_expression" in _codes(validate(doc))


def test_part_orphan_drawable_is_warning():
    doc = _clean_doc()
    doc.parts = [Part(id="p", drawables=["ghost"])]
    assert "part_orphan_drawable" in _codes(validate(doc))


def test_bone_weights_not_normalised_is_warning():
    doc = _clean_doc()
    drawable = doc.drawables[0]
    # 3 vertices, only one bone, weights summing to 0.5 each → off by 0.5
    drawable.bone_weights = {"bone1": [0.5, 0.5, 0.5]}
    assert "bone_weights_not_normalised" in _codes(validate(doc))


def test_normalised_bone_weights_pass():
    doc = _clean_doc()
    drawable = doc.drawables[0]
    drawable.bone_weights = {"bone1": [1.0, 1.0, 1.0]}
    issues = validate(doc)
    assert "bone_weights_not_normalised" not in _codes(issues)
