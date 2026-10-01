"""Tests for the .puppet format's JSON Schemas, the schema checker and the conformance check."""
from __future__ import annotations

import copy
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

from Imervue.puppet.document import Deformer, Motion, MotionSegment, MotionTrack
from Imervue.puppet.document_io import new_blank, save_puppet, to_zip_bytes
from Imervue.puppet.format_schema import (
    MEDIA_TYPE,
    PUPPET_SCHEMA,
    SCHEMA_NAMES,
    SCHEMA_URLS,
    SCHEMAS,
    check_puppet_file,
    schema_errors,
    schema_text,
    write_schema_files,
)
from Imervue.puppet.schema_check import validate
from test_puppet_document_io import _build_full_doc

_ROOT = Path(__file__).resolve().parents[1]


def _archive(data: bytes) -> zipfile.ZipFile:
    import io
    return zipfile.ZipFile(io.BytesIO(data))


def _manifest(doc) -> dict:
    return json.loads(_archive(to_zip_bytes(doc)).read("puppet.json"))


def _zip(tmp_path, manifest: dict, entries: dict | None = None) -> Path:
    path = tmp_path / "t.puppet"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("puppet.json", json.dumps(manifest))
        for name, value in (entries or {}).items():
            zf.writestr(name, value if isinstance(value, bytes) else json.dumps(value))
    return path


def _rigged_doc():
    doc = _build_full_doc()
    doc.deformers += [
        Deformer(id="w", type="warp", parent=None, drawables=[], form={
            "rows": 2, "cols": 2, "grid": [[[0, 0], [1, 0]], [[0, 1], [1, 1]]],
            "bounds": [0, 0, 1, 1]}),
        Deformer(id="b", type="bone_rotation", parent=None, drawables=[],
                 form={"bone_id": "arm", "anchor": [0.0, 0.0], "angle": 0.0}),
    ]
    doc.motions.append(Motion(name="blink", duration=1.0, tracks=[MotionTrack(
        param_id="ParamEyeLOpen", segments=[MotionSegment(
            type="cubic-bezier", p0=(0.0, 1.0), p1=(1.0, 0.0), c0=(0.3, 1.0), c1=(0.6, 0.0))])],
        group="Idle"))
    return doc


# --- what Imervue writes conforms ---------------------------------------------

@pytest.mark.parametrize("make", [new_blank, _build_full_doc, _rigged_doc])
def test_every_file_imervue_writes_conforms(make):
    archive = _archive(to_zip_bytes(make()))
    assert schema_errors(archive) == []


def test_a_png_import_conforms(tmp_path):
    from PIL import Image

    from Imervue.puppet.auto_mesh import puppet_from_png
    png = tmp_path / "a.png"
    Image.new("RGBA", (64, 64), (200, 10, 10, 255)).save(png)
    assert schema_errors(_archive(to_zip_bytes(puppet_from_png(png, cell_size=16)))) == []


def test_the_schemas_name_their_published_urls():
    for name in SCHEMA_NAMES:
        assert SCHEMAS[name]["$id"] == SCHEMA_URLS[name]
        assert SCHEMAS[name]["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_the_published_schema_files_are_the_generated_ones():
    """docs/schemas/ is generated: python -m Imervue.puppet.format_schema docs/schemas."""
    for name in SCHEMA_NAMES:
        published = (_ROOT / "docs" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8")
        assert published.replace("\r\n", "\n") == schema_text(name)


def test_write_schema_files(tmp_path):
    written = write_schema_files(tmp_path / "out")
    assert [p.name for p in written] == [f"{n}.schema.json" for n in SCHEMA_NAMES]
    assert json.loads(written[0].read_text(encoding="utf-8")) == SCHEMAS["puppet"]


# --- what the schemas reject --------------------------------------------------

def _broken(mutate) -> list[str]:
    manifest = _manifest(_rigged_doc())
    mutate(manifest)
    return validate(manifest, PUPPET_SCHEMA)


@pytest.mark.parametrize(("mutate", "fragment"), [
    (lambda m: m.pop("drawables"), "missing required key 'drawables'"),
    (lambda m: m.update(version=2), "$.version: must be 1"),
    (lambda m: m.update(extra=1), "$.extra: unknown key"),
    (lambda m: m["drawables"][0].update(blend_mode="screen"), "is not one of"),
    (lambda m: m["drawables"][0].update(opacity=1.5), "above the maximum 1"),
    (lambda m: m["drawables"][0].update(vertices=[[0, 0, 0]]), "at most 2 items"),
    (lambda m: m["drawables"][0]["indices"].append(-1), "below the minimum 0"),
    (lambda m: m["deformers"][0]["form"].pop("anchor"), ".form: missing required key 'anchor'"),
    (lambda m: m["deformers"][-2]["form"].pop("bounds"), "missing required key 'bounds'"),
    (lambda m: m["deformers"][-1]["form"].pop("bone_id"), "missing required key 'bone_id'"),
    (lambda m: m.update(size=[0, 10]), "below the minimum 1"),
    (lambda m: m.update(display_names={"a": 3}), "$.display_names.a: expected string"),
])
def test_the_schema_reports_what_breaks_the_format(mutate, fragment):
    errors = _broken(mutate)
    assert any(fragment in e for e in errors), errors


def test_a_boolean_is_not_a_version():
    assert _broken(lambda m: m.update(version=True)) == ["$.version: expected integer, got boolean"]


# --- the schema checker's keywords ----------------------------------------------

@pytest.mark.parametrize(("instance", "schema", "expected"), [
    (3, {"type": "integer"}, []),
    (3.5, {"type": "integer"}, ["$: expected integer, got number"]),
    (True, {"type": "number"}, ["$: expected number, got boolean"]),
    (None, {"type": ["string", "null"]}, []),
    ("a", {"enum": ["b"]}, ["$: 'a' is not one of ['b']"]),
    ("", {"type": "string", "minLength": 1}, ["$: shorter than 1 characters"]),
    ([1], {"type": "array", "minItems": 2}, ["$: needs at least 2 items, has 1"]),
    ({"a": 1}, {"type": "object", "additionalProperties": {"type": "string"}},
     ["$.a: expected string, got integer"]),
    ({"a": 1}, {"type": "object", "properties": {"a": {"type": "integer"}},
                "additionalProperties": False}, []),
    (5, {"anyOf": [{"type": "string"}, {"type": "boolean"}]}, ["$: matches none of the allowed shapes"]),
    (5, {"allOf": [{"minimum": 6}, {"maximum": 4}]},
     ["$: 5 is below the minimum 6", "$: 5 is above the maximum 4"]),
    ({"t": "x", "v": 1}, {"if": {"properties": {"t": {"const": "x"}}},
                          "then": {"properties": {"v": {"type": "string"}}}},
     ["$.v: expected string, got integer"]),
    ({"t": "y", "v": 1}, {"if": {"properties": {"t": {"const": "x"}}},
                          "then": {"properties": {"v": {"type": "string"}}}}, []),
])
def test_schema_check_keywords(instance, schema, expected):
    assert validate(instance, schema) == expected


def test_schema_check_follows_local_refs_only():
    schema = {"$defs": {"n": {"type": "number"}}, "items": {"$ref": "#/$defs/n"}, "type": "array"}
    assert validate([1, "x"], schema) == ["$[1]: expected number, got string"]
    with pytest.raises(ValueError, match="local references"):
        validate(1, {"$ref": "https://example.com/s.json"})


# --- the conformance check ----------------------------------------------------------

def test_a_good_file_is_valid(tmp_path):
    path = tmp_path / "good.puppet"
    save_puppet(_rigged_doc(), path)
    report = check_puppet_file(path)
    assert report["valid"] and report["version"] == 1
    assert report["schema_errors"] == [] and report["load_error"] is None
    assert all({"severity", "code", "message", "location"} <= set(i) for i in report["issues"])


def test_a_rig_error_makes_it_invalid(tmp_path):
    doc = _rigged_doc()
    doc.textures.clear()                      # every drawable's texture is now missing
    path = tmp_path / "no_tex.puppet"
    save_puppet(doc, path)
    report = check_puppet_file(path)
    assert not report["valid"]
    assert any(i["code"] == "texture_missing" and i["severity"] == "error" for i in report["issues"])


def test_a_listed_motion_that_is_missing(tmp_path):
    manifest = _manifest(new_blank())
    manifest["motions"] = ["idle"]
    report = check_puppet_file(_zip(tmp_path, manifest))
    assert "motions/idle.json: listed but missing from the archive" in report["schema_errors"]
    assert "motion 'idle' listed" in report["load_error"]
    assert not report["valid"]


def test_a_companion_file_breaking_its_schema(tmp_path):
    manifest = _manifest(new_blank())
    manifest["expressions"] = ["smile"]
    report = check_puppet_file(_zip(tmp_path, manifest,
                                    {"expressions/smile.json": {"params": [{"id": "a"}]}}))
    assert any(e.startswith("expressions/smile.json .params[0]: missing required key 'value'")
               for e in report["schema_errors"]), report["schema_errors"]


def test_a_companion_that_is_not_json(tmp_path):
    manifest = _manifest(new_blank())
    manifest["physics"] = "physics.json"
    report = check_puppet_file(_zip(tmp_path, manifest, {"physics.json": b"\xff not json"}))
    assert any(e.startswith("physics.json: not valid UTF-8 JSON") for e in report["schema_errors"])


def test_a_file_that_is_no_zip(tmp_path):
    path = tmp_path / "bogus.puppet"
    path.write_bytes(b"not a zip")
    report = check_puppet_file(path)
    assert report["load_error"].startswith("not a readable zip archive")
    assert report["valid"] is False and report["version"] is None


def test_a_newer_format_version_is_reported(tmp_path):
    manifest = _manifest(new_blank())
    manifest["version"] = 3
    report = check_puppet_file(_zip(tmp_path, manifest))
    assert report["version"] == 3
    assert "format v3, newer than the v1" in report["load_error"]
    assert "puppet.json .version: must be 1" in report["schema_errors"]


def test_a_manifest_that_is_not_an_object(tmp_path):
    path = tmp_path / "list.puppet"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("puppet.json", "[1, 2]")
    report = check_puppet_file(path)
    assert report["schema_errors"] == ["puppet.json : expected object, got array"]
    assert report["load_error"]


# --- MCP / CLI ------------------------------------------------------------------------

def test_the_mcp_tools(tmp_path):
    from Imervue.mcp_server.tools import puppet_schema, puppet_validate
    path = tmp_path / "p.puppet"
    save_puppet(_rigged_doc(), path)
    assert puppet_validate(str(path))["valid"]
    assert puppet_schema("motion")["schema"] == SCHEMAS["motion"]
    assert puppet_schema()["url"] == SCHEMA_URLS["puppet"]
    with pytest.raises(ValueError, match="name must be one of"):
        puppet_schema("pose")


def test_the_cli_validates_and_prints_a_schema(tmp_path, capsys):
    from Imervue.cli import main
    path = tmp_path / "p.puppet"
    save_puppet(_rigged_doc(), path)
    assert main(["puppet-validate", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["valid"] is True
    assert main(["puppet-schema", "--name", "expression"]) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == SCHEMAS["expression"]


# --- the stdlib reference reader ---------------------------------------------------------

def _reference_reader():
    spec = importlib.util.spec_from_file_location(
        "read_puppet", _ROOT / "docs" / "examples" / "read_puppet.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_reference_reader_reads_what_imervue_writes(tmp_path):
    reader = _reference_reader()
    assert reader.MEDIA_TYPE == MEDIA_TYPE
    path = tmp_path / "p.puppet"
    save_puppet(_rigged_doc(), path)
    puppet = reader.read_puppet(str(path))
    assert puppet["manifest"]["version"] == 1
    assert set(puppet["motions"]) == {m.name for m in _rigged_doc().motions}
    assert puppet["textures"] and puppet["physics"] is not None
    assert "drawables" in reader.summary(puppet)


def test_the_reference_reader_refuses_other_files(tmp_path):
    reader = _reference_reader()
    wrong_type = tmp_path / "other.puppet"
    with zipfile.ZipFile(wrong_type, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("puppet.json", "{}")
    with pytest.raises(ValueError, match="not a .puppet"):
        reader.read_puppet(str(wrong_type))
    manifest = copy.deepcopy(_manifest(new_blank()))
    manifest["version"] = 2
    with pytest.raises(ValueError, match="version 2"):
        reader.read_puppet(str(_zip(tmp_path, manifest)))
