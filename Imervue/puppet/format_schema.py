"""Machine-readable definition of the ``.puppet`` format (v1) and a conformance check.

The four JSON Schemas (draft 2020-12) describe the JSON files inside a
``.puppet`` archive — ``puppet.json``, ``motions/<name>.json``,
``expressions/<name>.json`` and ``physics.json`` — as ``Imervue/puppet/FORMAT.md``
specifies them. They are published as ``docs/schemas/<name>.schema.json``
(regenerate with ``python -m Imervue.puppet.format_schema docs/schemas``) under
the ``$id`` URLs in :data:`SCHEMA_URLS`; a writer puts that URL in each file's
``$schema`` key so editors can check the file as it is typed.

:func:`check_puppet_file` is the conformance check behind the CLI's
``puppet-validate`` and the MCP ``puppet_validate`` tool: the schemas, then the
loader's structural rules (index ranges, matching lengths, listed files present),
then the rig checks of :mod:`Imervue.puppet.validator`.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from Imervue.puppet.document import (
    BLEND_MODES,
    DEFORMER_TYPES,
    EXPRESSION_MODES,
    SCHEMA_VERSION,
    SEGMENT_TYPES,
)
from Imervue.puppet.schema_check import validate

#: IANA-style media type; stored uncompressed as the archive's first entry, ``mimetype``.
MEDIA_TYPE = "application/vnd.imervue.puppet+zip"
MIMETYPE_ENTRY = "mimetype"
SCHEMA_BASE_URL = "https://raw.githubusercontent.com/JeffreyChen-s-Utils/Imervue/main/docs/schemas/"
SCHEMA_NAMES = ("puppet", "motion", "expression", "physics")
SCHEMA_URLS = {name: f"{SCHEMA_BASE_URL}{name}.schema.json" for name in SCHEMA_NAMES}
_DRAFT = "https://json-schema.org/draft/2020-12/schema"
# The member that names a document's schema, in the schemas and in every file written.
SCHEMA_FIELD = "$schema"

_STRING = {"type": "string", "minLength": 1}
_NUMBER = {"type": "number"}
_UNIT = {"type": "number", "minimum": 0, "maximum": 1}
_NON_NEGATIVE = {"type": "number", "minimum": 0}
_STRINGS = {"type": "array", "items": _STRING}
_XY = {"type": "array", "items": _NUMBER, "minItems": 2, "maxItems": 2}
_RGB = {"type": "array", "items": _NUMBER, "minItems": 3, "maxItems": 3}
_XY_LIST = {"type": "array", "items": {"$ref": "#/$defs/xy"}}
_VERSION = {"type": "integer", "const": SCHEMA_VERSION}
_SCHEMA_KEY = {"type": "string"}
_FORMS = {"type": "object", "additionalProperties": {"type": "object"}}


def _object(required: tuple[str, ...], properties: dict[str, Any], *,
            closed: bool = True) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "required": list(required),
                              "properties": properties}
    if closed:
        schema["additionalProperties"] = False
    return schema


def _curve(stop: dict[str, Any]) -> dict[str, Any]:
    """An opacity / colour key: a parameter and at least two stops."""
    return {"type": "array", "items": _object(("parameter", "stops"), {
        "parameter": _STRING,
        "stops": {"type": "array", "minItems": 2, "items": stop},
    })}


def _drawable() -> dict[str, Any]:
    return _object(("id", "texture", "vertices", "indices", "uvs", "draw_order"), {
        "id": _STRING,
        "texture": _STRING,
        "vertices": _XY_LIST,
        "indices": {"type": "array", "items": {"type": "integer", "minimum": 0}},
        "uvs": _XY_LIST,
        "draw_order": {"type": "integer"},
        "blend_mode": {"enum": list(BLEND_MODES)},
        "clip_mask": {"type": ["string", "null"]},
        "visible": {"type": "boolean"},
        "opacity": _UNIT,
        "bone_weights": {"type": "object", "additionalProperties": {
            "type": "array", "items": _NUMBER}},
        "opacity_keys": _curve(_object(("value", "alpha"),
                                       {"value": _NUMBER, "alpha": _NUMBER})),
        "multiply_color": _RGB,
        "multiply_color_keys": _curve(_object(("value", "color"),
                                              {"value": _NUMBER, "color": _RGB})),
        "vertex_morphs": {"type": "array", "items": _object(("parameter",), {
            "parameter": _STRING, "delta_at_min": _XY_LIST, "delta_at_max": _XY_LIST})},
    })


def _forms() -> dict[str, Any]:
    rotation = _object(("anchor", "angle"), {"anchor": _XY, "angle": _NUMBER}, closed=False)
    warp = _object(("rows", "cols", "grid", "bounds"), {
        "rows": {"type": "integer"},
        "cols": {"type": "integer"},
        "grid": {"type": "array", "items": {"anyOf": [{"$ref": "#/$defs/xy"}, _XY_LIST]}},
        "bounds": {"type": "array", "items": _NUMBER, "minItems": 4, "maxItems": 4},
    }, closed=False)
    bone = _object(("bone_id", "anchor", "angle"), {
        "bone_id": _STRING, "anchor": _XY, "angle": _NUMBER}, closed=False)
    return {"rotation": rotation, "warp": warp, "bone_rotation": bone}


def _deformer() -> dict[str, Any]:
    schema = _object(("id", "type", "drawables", "form"), {
        "id": _STRING,
        "type": {"enum": list(DEFORMER_TYPES)},
        "parent": {"type": ["string", "null"]},
        "drawables": _STRINGS,
        "form": {"type": "object"},
    })
    schema["allOf"] = [
        {"if": {"properties": {"type": {"const": kind}}},
         "then": {"properties": {"form": {"$ref": f"#/$defs/{kind}_form"}}}}
        for kind in DEFORMER_TYPES
    ]
    return schema


def _puppet_defs() -> dict[str, Any]:
    forms = _forms()
    return {
        "xy": _XY,
        "drawable": _drawable(),
        "deformer": _deformer(),
        **{f"{kind}_form": form for kind, form in forms.items()},
        "parameter": _object(("id", "min", "max", "default"), {
            "id": _STRING, "min": _NUMBER, "max": _NUMBER, "default": _NUMBER,
            "keys": {"type": "array", "items": _object(("value",), {
                "value": _NUMBER, "forms": _FORMS})},
        }),
        "parameter_blend": _object(("id", "parameters", "keys"), {
            "id": _STRING,
            "parameters": {**_STRINGS, "minItems": 1},
            "keys": {"type": "array", "items": _object(("coords",), {
                "coords": {"type": "array", "items": _NUMBER}, "forms": _FORMS})},
        }),
        "part": _object(("id",), {
            "id": _STRING, "drawables": _STRINGS, "children": _STRINGS,
            "visible": {"type": "boolean"}, "opacity": _UNIT,
        }),
        "hit_area": _object(("id", "drawables"), {
            "id": _STRING, "drawables": _STRINGS, "motion": _STRING, "expression": _STRING,
        }),
        "pose_group": _object(("id", "drawables"), {"id": _STRING, "drawables": _STRINGS}),
    }


def _array_of(definition: str) -> dict[str, Any]:
    return {"type": "array", "items": {"$ref": f"#/$defs/{definition}"}}


def _document(name: str, title: str, body: dict[str, Any]) -> dict[str, Any]:
    return {SCHEMA_FIELD: _DRAFT, "$id": SCHEMA_URLS[name], "title": title, **body}


PUPPET_SCHEMA: dict[str, Any] = _document("puppet", ".puppet puppet.json (v1)", {
    **_object(("version", "size", "drawables", "deformers", "parameters"), {
        SCHEMA_FIELD: _SCHEMA_KEY,
        "version": _VERSION,
        "size": {"type": "array", "items": {"type": "integer", "minimum": 1},
                 "minItems": 2, "maxItems": 2},
        "drawables": _array_of("drawable"),
        "deformers": _array_of("deformer"),
        "parameters": _array_of("parameter"),
        "motions": _STRINGS,
        "expressions": _STRINGS,
        "pose": _object((), {"groups": _array_of("pose_group")}),
        "physics": _STRING,
        "hit_areas": _array_of("hit_area"),
        "parameter_blends": _array_of("parameter_blend"),
        "parts": _array_of("part"),
        "display_names": {"type": "object", "additionalProperties": {"type": "string"}},
    }),
    "$defs": _puppet_defs(),
})

MOTION_SCHEMA: dict[str, Any] = _document("motion", ".puppet motions/<name>.json (v1)", {
    **_object(("duration", "tracks"), {
        SCHEMA_FIELD: _SCHEMA_KEY,
        "version": _VERSION,
        "duration": _NON_NEGATIVE,
        "loop": {"type": "boolean"},
        "tracks": {"type": "array", "items": _object(("param_id", "segments"), {
            "param_id": _STRING,
            "segments": {"type": "array", "items": _object(("type", "p0", "p1"), {
                "type": {"enum": list(SEGMENT_TYPES)},
                "p0": _XY, "p1": _XY, "c0": _XY, "c1": _XY,
            })},
        })},
        "fade_in_duration": _NON_NEGATIVE,
        "fade_out_duration": _NON_NEGATIVE,
        "sound_path": _STRING,
        "group": _STRING,
    }),
})

EXPRESSION_SCHEMA: dict[str, Any] = _document(
    "expression", ".puppet expressions/<name>.json (v1)", {
    **_object((), {
        SCHEMA_FIELD: _SCHEMA_KEY,
        "version": _VERSION,
        "params": {"type": "array", "items": _object(("id", "value"), {
            "id": _STRING, "value": _NUMBER, "mode": {"enum": list(EXPRESSION_MODES)},
        })},
    }),
})

PHYSICS_SCHEMA: dict[str, Any] = _document("physics", ".puppet physics.json (v1)", {
    **_object(("rigs",), {
        SCHEMA_FIELD: _SCHEMA_KEY,
        "version": _VERSION,
        "rigs": {"type": "array", "items": _object(("id", "input_param", "output_param", "chain"), {
            "id": _STRING, "input_param": _STRING, "output_param": _STRING,
            "chain": {"type": "array", "items": _object((), {
                "mass": _NUMBER, "damping": _NUMBER, "spring": _NUMBER})},
            "gravity": _XY,
        })},
    }),
})

SCHEMAS: dict[str, dict[str, Any]] = {
    "puppet": PUPPET_SCHEMA, "motion": MOTION_SCHEMA,
    "expression": EXPRESSION_SCHEMA, "physics": PHYSICS_SCHEMA,
}


def schema_text(name: str) -> str:
    """The published JSON text of schema *name* (one of :data:`SCHEMA_NAMES`)."""
    return json.dumps(SCHEMAS[name], indent=2, ensure_ascii=False) + "\n"


def write_schema_files(folder: str | Path) -> list[Path]:
    """Write ``<name>.schema.json`` for every schema into *folder*; returns the paths."""
    target = Path(folder)
    # *folder* is where the user running ``puppet-schema --out`` asked the files to go.
    target.mkdir(parents=True, exist_ok=True)  # NOSONAR
    written = []
    for name in SCHEMA_NAMES:
        path = target / f"{name}.schema.json"
        # A fixed file name inside that folder.
        path.write_text(schema_text(name), encoding="utf-8", newline="\n")  # NOSONAR
        written.append(path)
    return written


# --------------------------------------------------------------------------- conformance

def _json_entry(archive: zipfile.ZipFile, name: str) -> tuple[Any, str | None]:
    """``(value, None)``, or ``(None, error)`` when the entry is missing or not JSON."""
    if name not in archive.namelist():
        return None, f"{name}: listed but missing from the archive"
    try:
        return json.loads(archive.read(name).decode("utf-8")), None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{name}: not valid UTF-8 JSON ({exc})"


def _names(manifest: dict, key: str) -> list[str]:
    value = manifest.get(key)
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _companions(manifest: dict) -> list[tuple[str, str]]:
    """``(entry, schema name)`` for every file ``puppet.json`` points at."""
    entries = [(f"motions/{n}.json", "motion") for n in _names(manifest, "motions")]
    entries += [(f"expressions/{n}.json", "expression") for n in _names(manifest, "expressions")]
    physics = manifest.get("physics")
    if isinstance(physics, str) and physics:
        entries.append((physics, "physics"))
    return entries


def schema_errors(archive: zipfile.ZipFile) -> list[str]:
    """Every schema violation in the archive's JSON files, each prefixed by its entry."""
    manifest, error = _json_entry(archive, "puppet.json")
    if error is not None:
        return [error]
    errors = [f"puppet.json {e[1:]}" for e in validate(manifest, PUPPET_SCHEMA)]
    if not isinstance(manifest, dict):
        return errors
    for entry, schema in _companions(manifest):
        value, error = _json_entry(archive, entry)
        if error is not None:
            errors.append(error)
            continue
        errors.extend(f"{entry} {e[1:]}" for e in validate(value, SCHEMAS[schema]))
    return errors


def check_puppet_file(path: str | Path) -> dict[str, Any]:
    """Check *path* against the v1 format: schemas, loader rules, then rig consistency.

    Returns ``{"path", "valid", "version", "schema_errors", "load_error",
    "issues"}``; ``issues`` are the rig checks' findings as dicts. ``valid`` is
    true when nothing breaks the format and no rig check reports an error.
    """
    from Imervue.puppet.document_io import PuppetFormatError, load_puppet
    from Imervue.puppet.validator import validate as check_rig
    report: dict[str, Any] = {"path": str(path), "valid": False, "version": None,
                              "schema_errors": [], "load_error": None, "issues": []}
    try:
        with zipfile.ZipFile(path) as archive:
            report["schema_errors"] = schema_errors(archive)
            manifest, _ = _json_entry(archive, "puppet.json")
        if isinstance(manifest, dict):
            report["version"] = manifest.get("version")
        document = load_puppet(path)
    except (OSError, zipfile.BadZipFile) as exc:
        report["load_error"] = f"not a readable zip archive: {exc}"
        return report
    except PuppetFormatError as exc:
        report["load_error"] = str(exc)
        return report
    report["issues"] = [
        {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location}
        for i in check_rig(document)
    ]
    report["valid"] = not report["schema_errors"] and not any(
        i["severity"] == "error" for i in report["issues"])
    return report


if __name__ == "__main__":
    write_schema_files(sys.argv[1] if len(sys.argv) > 1 else "docs/schemas")
