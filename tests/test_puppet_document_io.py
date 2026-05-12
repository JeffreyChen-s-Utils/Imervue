"""Tests for the ``.puppet`` v1 file-format IO layer.

Per CLAUDE.md test discipline: happy / edge / error / boundary /
round-trip coverage for ``puppet/document_io.py``. No binary fixtures
checked in — each test materialises its own minimal puppet on
``tmp_path`` so the suite stays self-contained.
"""
from __future__ import annotations

import io
import json
import zipfile

import pytest

from puppet.document import (
    Deformer,
    Drawable,
    Expression,
    ExpressionParam,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    ParameterKey,
    PhysicsParticle,
    PhysicsRig,
    PoseGroup,
    PuppetDocument,
)
from puppet.document_io import (
    PuppetFormatError,
    SCHEMA_VERSION,
    from_zip_bytes,
    load_puppet,
    new_blank,
    save_puppet,
    to_zip_bytes,
)


# ---------------------------------------------------------------------------
# Tiny test PNG (1×1 transparent) — keeps fixtures small and Pillow-free.
# ---------------------------------------------------------------------------

_TINY_PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "8900000016624B47440000000000000000000000000000000000000000000000"
    "00FFA600007AC9000000097048597300000B1300000B13"
    "01009A9C180000000774494D4507E5050C0E2A2F"
    "F2C99B6F0000000A4944415408D763F8FFFF3F0005FE02FED832FA610000"
    "000049454E44AE426082"
)


def _build_full_doc() -> PuppetDocument:
    """Build a non-trivial puppet exercising every field — round-trip
    target for the happy-path and equality tests."""
    doc = PuppetDocument(size=(2048, 2048))
    doc.textures["textures/face.png"] = _TINY_PNG
    doc.drawables = [
        Drawable(
            id="face",
            texture="textures/face.png",
            vertices=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
            indices=[0, 1, 2, 0, 2, 3],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            draw_order=10,
            blend_mode="normal",
            clip_mask=None,
            visible=True,
            opacity=0.9,
        ),
    ]
    doc.deformers = [
        Deformer(
            id="head_rotation",
            type="rotation",
            parent=None,
            drawables=["face"],
            form={"anchor": [5.0, 5.0], "angle": 0.0},
        ),
    ]
    doc.parameters = [
        Parameter(
            id="ParamAngleX",
            min=-30.0,
            max=30.0,
            default=0.0,
            keys=[
                ParameterKey(value=-30.0, forms={"head_rotation": {"angle": -0.5}}),
                ParameterKey(value=0.0, forms={"head_rotation": {"angle": 0.0}}),
                ParameterKey(value=30.0, forms={"head_rotation": {"angle": 0.5}}),
            ],
        ),
    ]
    doc.pose_groups = [
        PoseGroup(id="weapons", drawables=["sword", "bow"]),
    ]
    doc.motions = [
        Motion(
            name="idle",
            duration=2.0,
            loop=True,
            tracks=[
                MotionTrack(
                    param_id="ParamAngleX",
                    segments=[
                        MotionSegment(
                            type="linear", p0=(0.0, 0.0), p1=(1.0, 30.0),
                        ),
                        MotionSegment(
                            type="cubic-bezier",
                            p0=(1.0, 30.0),
                            c0=(1.3, 30.0),
                            c1=(1.7, -30.0),
                            p1=(2.0, -30.0),
                        ),
                    ],
                ),
            ],
        ),
    ]
    doc.expressions = [
        Expression(
            name="smile",
            params=[
                ExpressionParam(id="ParamMouthSmile", value=1.0, mode="overwrite"),
                ExpressionParam(id="ParamCheek", value=0.5, mode="multiply"),
            ],
        ),
    ]
    doc.physics_rigs = [
        PhysicsRig(
            id="front_hair",
            input_param="ParamBodyAngleX",
            output_param="ParamHairFront",
            chain=[
                PhysicsParticle(mass=1.0, damping=0.7, spring=12.0),
                PhysicsParticle(mass=0.8, damping=0.7, spring=10.0),
            ],
            gravity=(0.0, -9.8),
        ),
    ]
    return doc


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip_preserves_all_fields(tmp_path):
    doc = _build_full_doc()
    out = tmp_path / "full.puppet"
    save_puppet(doc, out)
    assert out.exists()
    loaded = load_puppet(out)

    assert loaded.size == doc.size
    assert loaded.textures == doc.textures

    assert len(loaded.drawables) == 1
    d = loaded.drawables[0]
    assert d.id == "face"
    assert d.texture == "textures/face.png"
    assert d.vertices == doc.drawables[0].vertices
    assert d.indices == doc.drawables[0].indices
    assert d.uvs == doc.drawables[0].uvs
    assert d.draw_order == 10
    assert d.blend_mode == "normal"
    assert d.opacity == pytest.approx(0.9)

    assert loaded.deformers[0].type == "rotation"
    assert loaded.deformers[0].form == {"anchor": [5.0, 5.0], "angle": 0.0}

    p = loaded.parameters[0]
    assert p.min == pytest.approx(-30.0)
    assert p.max == pytest.approx(30.0)
    assert len(p.keys) == 3
    assert p.keys[0].forms == {"head_rotation": {"angle": -0.5}}

    assert loaded.pose_groups[0].id == "weapons"

    m = loaded.motions[0]
    assert m.name == "idle"
    assert m.loop is True
    assert m.duration == pytest.approx(2.0)
    assert len(m.tracks[0].segments) == 2
    assert m.tracks[0].segments[1].type == "cubic-bezier"

    e = loaded.expressions[0]
    assert e.name == "smile"
    assert e.params[0].mode == "overwrite"

    r = loaded.physics_rigs[0]
    assert r.id == "front_hair"
    assert len(r.chain) == 2
    assert r.gravity == (0.0, -9.8)


def test_in_memory_round_trip_matches_disk(tmp_path):
    doc = _build_full_doc()
    out = tmp_path / "mem.puppet"
    save_puppet(doc, out)
    on_disk = out.read_bytes()
    in_mem = to_zip_bytes(doc)
    # Both should round-trip to a doc that compares equal across fields
    assert load_puppet(out).drawables[0].id == from_zip_bytes(in_mem).drawables[0].id
    assert from_zip_bytes(on_disk).size == from_zip_bytes(in_mem).size


def test_save_creates_parent_directories(tmp_path):
    nested = tmp_path / "deep" / "nested" / "out.puppet"
    save_puppet(new_blank((512, 512)), nested)
    assert nested.exists()


# ---------------------------------------------------------------------------
# Schema validation — error paths
# ---------------------------------------------------------------------------


def _zip_with_manifest(manifest: dict, **extras: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("puppet.json", json.dumps(manifest))
        for path, data in extras.items():
            zf.writestr(path, data)
    return buf.getvalue()


def test_load_rejects_non_zip(tmp_path):
    p = tmp_path / "broken.puppet"
    p.write_bytes(b"not a zip")
    with pytest.raises(PuppetFormatError, match="not a zip archive"):
        load_puppet(p)


def test_load_rejects_missing_manifest(tmp_path):
    out = tmp_path / "no_manifest.puppet"
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("textures/face.png", _TINY_PNG)
    with pytest.raises(PuppetFormatError, match="missing puppet.json"):
        load_puppet(out)


def test_load_rejects_unknown_version(tmp_path):
    raw = _zip_with_manifest({
        "version": 99,
        "size": [512, 512],
        "drawables": [],
        "deformers": [],
        "parameters": [],
    })
    out = tmp_path / "future.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="schema version"):
        load_puppet(out)


def test_load_rejects_missing_required_top_level_key(tmp_path):
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [],   # OK
        "deformers": [],
        # parameters missing
    })
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="parameters"):
        load_puppet(out)


def test_load_rejects_drawable_with_unknown_blend_mode(tmp_path):
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [{
            "id": "d", "texture": "textures/x.png",
            "vertices": [[0.0, 0.0]],
            "indices": [],
            "uvs": [[0.0, 0.0]],
            "draw_order": 0,
            "blend_mode": "telekinesis",
        }],
        "deformers": [],
        "parameters": [],
    })
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="blend_mode"):
        load_puppet(out)


def test_load_rejects_drawable_with_indices_not_divisible_by_3(tmp_path):
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [{
            "id": "d", "texture": "textures/x.png",
            "vertices": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "indices": [0, 1, 2, 0],  # 4 entries — not a triangle list
            "uvs": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "draw_order": 0,
        }],
        "deformers": [],
        "parameters": [],
    })
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="not divisible by 3"):
        load_puppet(out)


def test_load_rejects_drawable_with_vertex_uv_length_mismatch(tmp_path):
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [{
            "id": "d", "texture": "textures/x.png",
            "vertices": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
            "indices": [0, 1, 2],
            "uvs": [[0.0, 0.0]],  # length 1, vertices length 3
            "draw_order": 0,
        }],
        "deformers": [],
        "parameters": [],
    })
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="length mismatch"):
        load_puppet(out)


def test_load_rejects_unknown_deformer_type(tmp_path):
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [],
        "deformers": [{
            "id": "x",
            "type": "skywarp",
            "drawables": [],
            "form": {},
        }],
        "parameters": [],
    })
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="skywarp"):
        load_puppet(out)


def test_load_rejects_unknown_segment_type(tmp_path):
    """Motion track segment type must be in the enum."""
    motion_raw = json.dumps({
        "version": SCHEMA_VERSION,
        "duration": 1.0,
        "tracks": [{
            "param_id": "X",
            "segments": [{"type": "wobble", "p0": [0.0, 0.0], "p1": [1.0, 1.0]}],
        }],
    })
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [],
        "deformers": [],
        "parameters": [],
        "motions": ["bad"],
    }, **{"motions/bad.json": motion_raw.encode("utf-8")})
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="wobble"):
        load_puppet(out)


def test_load_rejects_listed_motion_with_missing_file(tmp_path):
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [],
        "deformers": [],
        "parameters": [],
        "motions": ["missing"],
    })
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="missing"):
        load_puppet(out)


def test_load_rejects_malformed_motion_json(tmp_path):
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [],
        "deformers": [],
        "parameters": [],
        "motions": ["broken"],
    }, **{"motions/broken.json": b"{ this is not json"})
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="malformed JSON"):
        load_puppet(out)


def test_load_rejects_unknown_expression_mode(tmp_path):
    expr_raw = json.dumps({
        "version": SCHEMA_VERSION,
        "params": [{"id": "X", "value": 1.0, "mode": "telekinesis"}],
    })
    raw = _zip_with_manifest({
        "version": SCHEMA_VERSION,
        "size": [512, 512],
        "drawables": [],
        "deformers": [],
        "parameters": [],
        "expressions": ["bad"],
    }, **{"expressions/bad.json": expr_raw.encode("utf-8")})
    out = tmp_path / "bad.puppet"
    out.write_bytes(raw)
    with pytest.raises(PuppetFormatError, match="telekinesis"):
        load_puppet(out)


def test_load_missing_file_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_puppet(tmp_path / "no_such.puppet")


# ---------------------------------------------------------------------------
# Helper smoke
# ---------------------------------------------------------------------------


def test_new_blank_returns_empty_document():
    doc = new_blank((100, 200))
    assert doc.size == (100, 200)
    assert doc.drawables == []
    assert doc.deformers == []
    assert doc.parameters == []


def test_document_lookup_helpers():
    doc = _build_full_doc()
    assert doc.drawable("face") is not None
    assert doc.drawable("missing") is None
    assert doc.deformer("head_rotation") is not None
    assert doc.parameter("ParamAngleX") is not None
    assert doc.parameter("ParamMissing") is None


# ---------------------------------------------------------------------------
# Round-trip via ``to_zip_bytes`` keeps the pose / expressions / physics
# branches active so the writers don't bitrot.
# ---------------------------------------------------------------------------


def test_optional_blocks_omitted_when_empty():
    """A document without motions / expressions / physics / pose must
    still round-trip and the manifest must not carry empty placeholder
    keys (keeps git diffs clean for tiny puppets)."""
    doc = new_blank((128, 128))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            indices=[0, 1, 2],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            draw_order=0,
        ),
    ]
    raw = to_zip_bytes(doc)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        manifest = json.loads(zf.read("puppet.json"))
    for absent in ("motions", "expressions", "physics", "pose"):
        assert absent not in manifest, f"empty {absent} should be omitted"


# ---------------------------------------------------------------------------
# Bone weights round-trip
# ---------------------------------------------------------------------------


def _drawable_with_bone_weights(bone_weights):
    return Drawable(
        id="d", texture="textures/x.png",
        vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        indices=[0, 1, 2],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        draw_order=0,
        bone_weights=bone_weights,
    )


def test_bone_weights_round_trip():
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_bone_weights({
        "arm": [1.0, 0.6, 0.0],
        "torso": [0.0, 0.4, 1.0],
    })]
    restored = from_zip_bytes(to_zip_bytes(doc))
    assert restored.drawables[0].bone_weights == {
        "arm": [1.0, 0.6, 0.0],
        "torso": [0.0, 0.4, 1.0],
    }


def test_drawable_without_bone_weights_omits_field_in_json():
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_bone_weights(None)]
    raw = to_zip_bytes(doc)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        manifest = json.loads(zf.read("puppet.json"))
    assert "bone_weights" not in manifest["drawables"][0]


def test_load_rejects_bone_weights_with_wrong_length(tmp_path):
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_bone_weights({"arm": [1.0, 0.0, 0.5]})]
    raw = to_zip_bytes(doc)
    # Hand-edit the manifest to break the weight count, then re-zip.
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        manifest = json.loads(zf.read("puppet.json"))
        png = zf.read("textures/x.png")
    manifest["drawables"][0]["bone_weights"]["arm"] = [1.0, 0.0]  # too short
    bad_path = tmp_path / "bad.puppet"
    with zipfile.ZipFile(bad_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("puppet.json", json.dumps(manifest))
        zf.writestr("textures/x.png", png)
    with pytest.raises(PuppetFormatError, match="bone_weights"):
        load_puppet(bad_path)


# ---------------------------------------------------------------------------
# opacity_keys round-trip (parameter-driven cross-fade)
# ---------------------------------------------------------------------------


def _drawable_with_opacity_keys(opacity_keys):
    return Drawable(
        id="d", texture="textures/x.png",
        vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        indices=[0, 1, 2],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        draw_order=0,
        opacity_keys=opacity_keys,
    )


def test_opacity_keys_round_trip():
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_opacity_keys([
        {"parameter": "arm_swing", "stops": [
            {"value": -1.5, "alpha": 1.0},
            {"value": 0.0, "alpha": 0.0},
        ]},
    ])]
    restored = from_zip_bytes(to_zip_bytes(doc))
    keys = restored.drawables[0].opacity_keys
    assert keys is not None
    assert len(keys) == 1
    assert keys[0]["parameter"] == "arm_swing"
    assert keys[0]["stops"] == [
        {"value": -1.5, "alpha": 1.0},
        {"value": 0.0, "alpha": 0.0},
    ]


def test_drawable_without_opacity_keys_omits_field_in_json():
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_opacity_keys(None)]
    raw = to_zip_bytes(doc)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        manifest = json.loads(zf.read("puppet.json"))
    assert "opacity_keys" not in manifest["drawables"][0]


def test_load_rejects_opacity_keys_not_a_list(tmp_path):
    """opacity_keys must be a list — a dict typo should raise early."""
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_opacity_keys([
        {"parameter": "swing", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.0},
        ]},
    ])]
    raw = to_zip_bytes(doc)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        manifest = json.loads(zf.read("puppet.json"))
        png = zf.read("textures/x.png")
    manifest["drawables"][0]["opacity_keys"] = {"not": "a list"}
    bad_path = tmp_path / "bad.puppet"
    with zipfile.ZipFile(bad_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("puppet.json", json.dumps(manifest))
        zf.writestr("textures/x.png", png)
    with pytest.raises(PuppetFormatError, match="opacity_keys"):
        load_puppet(bad_path)


def test_load_rejects_opacity_keys_with_too_few_stops(tmp_path):
    """A curve with fewer than 2 stops has nothing to interpolate."""
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_opacity_keys([
        {"parameter": "swing", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.0},
        ]},
    ])]
    raw = to_zip_bytes(doc)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        manifest = json.loads(zf.read("puppet.json"))
        png = zf.read("textures/x.png")
    manifest["drawables"][0]["opacity_keys"][0]["stops"] = [
        {"value": 0.0, "alpha": 1.0},
    ]
    bad_path = tmp_path / "bad.puppet"
    with zipfile.ZipFile(bad_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("puppet.json", json.dumps(manifest))
        zf.writestr("textures/x.png", png)
    with pytest.raises(PuppetFormatError, match="stops"):
        load_puppet(bad_path)


def test_load_rejects_opacity_keys_with_missing_alpha(tmp_path):
    """A stop missing its alpha field is malformed."""
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_opacity_keys([
        {"parameter": "swing", "stops": [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.0},
        ]},
    ])]
    raw = to_zip_bytes(doc)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        manifest = json.loads(zf.read("puppet.json"))
        png = zf.read("textures/x.png")
    manifest["drawables"][0]["opacity_keys"][0]["stops"][1] = {"value": 1.0}
    bad_path = tmp_path / "bad.puppet"
    with zipfile.ZipFile(bad_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("puppet.json", json.dumps(manifest))
        zf.writestr("textures/x.png", png)
    with pytest.raises(PuppetFormatError, match="alpha"):
        load_puppet(bad_path)


def test_bone_rotation_deformer_round_trips():
    doc = new_blank((64, 64))
    doc.textures["textures/x.png"] = _TINY_PNG
    doc.drawables = [_drawable_with_bone_weights({"arm": [1.0, 1.0, 1.0]})]
    doc.deformers = [Deformer(
        id="arm_bone", type="bone_rotation", parent=None,
        drawables=["d"],
        form={"bone_id": "arm", "anchor": [10.0, 20.0], "angle": 0.0},
    )]
    restored = from_zip_bytes(to_zip_bytes(doc))
    deformer = restored.deformers[0]
    assert deformer.type == "bone_rotation"
    assert deformer.form["bone_id"] == "arm"
    assert deformer.form["anchor"] == [10.0, 20.0]
