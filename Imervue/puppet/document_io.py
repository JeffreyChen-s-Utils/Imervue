"""Load / save the ``.puppet`` zip container.

Pure-Python — no Qt, no GL. Round-trips through the dataclasses in
``document.py``. Strict schema validation on load with clear error
messages so corrupt files don't silently produce broken puppets.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from Imervue.puppet.document import (
    BLEND_MODES,
    DEFORMER_TYPES,
    EXPRESSION_MODES,
    SCHEMA_VERSION,
    SEGMENT_TYPES,
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


class PuppetFormatError(ValueError):
    """Raised when a ``.puppet`` archive doesn't conform to the v1 schema."""


_PUPPET_JSON = "puppet.json"
_PHYSICS_JSON = "physics.json"
_TEXTURES_DIR = "textures/"
_MOTIONS_DIR = "motions/"
_EXPRESSIONS_DIR = "expressions/"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def load_puppet(path: str | Path) -> PuppetDocument:
    """Open ``path`` (a ``.puppet`` zip), parse it, return a document.

    Raises :class:`PuppetFormatError` for any schema violation.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if not zipfile.is_zipfile(p):
        raise PuppetFormatError(f"{p} is not a zip archive")
    with zipfile.ZipFile(p, "r") as zf:
        return _load_from_zip(zf)


def save_puppet(doc: PuppetDocument, path: str | Path) -> None:
    """Write ``doc`` to ``path`` as a ``.puppet`` zip archive.

    Overwrites if the file already exists. Creates parent directories
    on demand.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_PUPPET_JSON, _puppet_json_bytes(doc))
        for tex_path, tex_bytes in doc.textures.items():
            zf.writestr(tex_path, tex_bytes)
        for motion in doc.motions:
            zf.writestr(
                f"{_MOTIONS_DIR}{motion.name}.json",
                _motion_json_bytes(motion),
            )
        for expr in doc.expressions:
            zf.writestr(
                f"{_EXPRESSIONS_DIR}{expr.name}.json",
                _expression_json_bytes(expr),
            )
        if doc.physics_rigs:
            zf.writestr(_PHYSICS_JSON, _physics_json_bytes(doc.physics_rigs))


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_from_zip(zf: zipfile.ZipFile) -> PuppetDocument:
    if _PUPPET_JSON not in zf.namelist():
        raise PuppetFormatError(f"missing {_PUPPET_JSON}")
    manifest = _read_json(zf, _PUPPET_JSON)
    _check_version(manifest)

    doc = PuppetDocument(
        size=_parse_size(manifest.get("size")),
        drawables=[_parse_drawable(d) for d in _require_list(manifest, "drawables")],
        deformers=[_parse_deformer(d) for d in _require_list(manifest, "deformers")],
        parameters=[_parse_parameter(p) for p in _require_list(manifest, "parameters")],
    )
    pose = manifest.get("pose")
    if pose is not None:
        doc.pose_groups = [_parse_pose_group(g) for g in pose.get("groups", [])]

    doc.textures = _load_textures(zf)
    doc.motions = _load_motions(zf, manifest.get("motions") or [])
    doc.expressions = _load_expressions(zf, manifest.get("expressions") or [])
    if manifest.get("physics"):
        doc.physics_rigs = _load_physics(zf, manifest["physics"])
    return doc


def _check_version(manifest: dict) -> None:
    version = manifest.get("version")
    if version != SCHEMA_VERSION:
        raise PuppetFormatError(
            f"unsupported puppet schema version {version!r}; expected {SCHEMA_VERSION}"
        )


def _parse_size(raw: Any) -> tuple[int, int]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise PuppetFormatError(f"size must be [w, h], got {raw!r}")
    return (int(raw[0]), int(raw[1]))


def _parse_drawable(raw: dict) -> Drawable:
    _require_keys(raw, ("id", "texture", "vertices", "indices", "uvs", "draw_order"), "drawable")
    blend = raw.get("blend_mode", "normal")
    if blend not in BLEND_MODES:
        raise PuppetFormatError(f"drawable {raw['id']!r} blend_mode {blend!r} not in {BLEND_MODES}")
    indices = list(raw["indices"])
    if len(indices) % 3 != 0:
        raise PuppetFormatError(
            f"drawable {raw['id']!r} indices length {len(indices)} not divisible by 3"
        )
    if len(raw["vertices"]) != len(raw["uvs"]):
        raise PuppetFormatError(
            f"drawable {raw['id']!r} vertices/uvs length mismatch"
        )
    return Drawable(
        id=str(raw["id"]),
        texture=str(raw["texture"]),
        vertices=[(float(x), float(y)) for x, y in raw["vertices"]],
        indices=[int(i) for i in indices],
        uvs=[(float(u), float(v)) for u, v in raw["uvs"]],
        draw_order=int(raw["draw_order"]),
        blend_mode=blend,
        clip_mask=raw.get("clip_mask"),
        visible=bool(raw.get("visible", True)),
        opacity=float(raw.get("opacity", 1.0)),
    )


def _parse_deformer(raw: dict) -> Deformer:
    _require_keys(raw, ("id", "type", "drawables", "form"), "deformer")
    if raw["type"] not in DEFORMER_TYPES:
        raise PuppetFormatError(
            f"deformer {raw['id']!r} type {raw['type']!r} not in {DEFORMER_TYPES}"
        )
    return Deformer(
        id=str(raw["id"]),
        type=raw["type"],
        parent=raw.get("parent"),
        drawables=[str(d) for d in raw["drawables"]],
        form=dict(raw["form"]),
    )


def _parse_parameter(raw: dict) -> Parameter:
    _require_keys(raw, ("id", "min", "max", "default"), "parameter")
    keys_raw = raw.get("keys", [])
    keys = [
        ParameterKey(
            value=float(k["value"]),
            forms={str(k_id): dict(form) for k_id, form in (k.get("forms") or {}).items()},
        )
        for k in keys_raw
    ]
    return Parameter(
        id=str(raw["id"]),
        min=float(raw["min"]),
        max=float(raw["max"]),
        default=float(raw["default"]),
        keys=keys,
    )


def _parse_pose_group(raw: dict) -> PoseGroup:
    _require_keys(raw, ("id", "drawables"), "pose group")
    return PoseGroup(
        id=str(raw["id"]),
        drawables=[str(d) for d in raw["drawables"]],
    )


def _load_textures(zf: zipfile.ZipFile) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for name in zf.namelist():
        if name.startswith(_TEXTURES_DIR) and not name.endswith("/"):
            with zf.open(name) as fp:
                out[name] = fp.read()
    return out


def _load_motions(zf: zipfile.ZipFile, names: list[str]) -> list[Motion]:
    out: list[Motion] = []
    for name in names:
        path = f"{_MOTIONS_DIR}{name}.json"
        if path not in zf.namelist():
            raise PuppetFormatError(f"motion {name!r} listed but {path} missing")
        raw = _read_json(zf, path)
        out.append(_parse_motion(name, raw))
    return out


def _parse_motion(name: str, raw: dict) -> Motion:
    _require_keys(raw, ("duration", "tracks"), f"motion {name}")
    return Motion(
        name=name,
        duration=float(raw["duration"]),
        loop=bool(raw.get("loop", False)),
        tracks=[_parse_track(t) for t in raw["tracks"]],
    )


def _parse_track(raw: dict) -> MotionTrack:
    _require_keys(raw, ("param_id", "segments"), "motion track")
    return MotionTrack(
        param_id=str(raw["param_id"]),
        segments=[_parse_segment(s) for s in raw["segments"]],
    )


def _parse_segment(raw: dict) -> MotionSegment:
    seg_type = raw.get("type")
    if seg_type not in SEGMENT_TYPES:
        raise PuppetFormatError(f"segment type {seg_type!r} not in {SEGMENT_TYPES}")
    return MotionSegment(
        type=seg_type,
        p0=_xy(raw["p0"]),
        p1=_xy(raw["p1"]),
        c0=_xy(raw["c0"]) if "c0" in raw else None,
        c1=_xy(raw["c1"]) if "c1" in raw else None,
    )


def _load_expressions(zf: zipfile.ZipFile, names: list[str]) -> list[Expression]:
    out: list[Expression] = []
    for name in names:
        path = f"{_EXPRESSIONS_DIR}{name}.json"
        if path not in zf.namelist():
            raise PuppetFormatError(f"expression {name!r} listed but {path} missing")
        raw = _read_json(zf, path)
        out.append(_parse_expression(name, raw))
    return out


def _parse_expression(name: str, raw: dict) -> Expression:
    return Expression(
        name=name,
        params=[_parse_expr_param(p) for p in raw.get("params", [])],
    )


def _parse_expr_param(raw: dict) -> ExpressionParam:
    _require_keys(raw, ("id", "value"), "expression param")
    mode = raw.get("mode", "additive")
    if mode not in EXPRESSION_MODES:
        raise PuppetFormatError(f"expression mode {mode!r} not in {EXPRESSION_MODES}")
    return ExpressionParam(id=str(raw["id"]), value=float(raw["value"]), mode=mode)


def _load_physics(zf: zipfile.ZipFile, path: str) -> list[PhysicsRig]:
    if path not in zf.namelist():
        raise PuppetFormatError(f"physics path {path!r} missing in archive")
    raw = _read_json(zf, path)
    return [_parse_physics_rig(r) for r in raw.get("rigs", [])]


def _parse_physics_rig(raw: dict) -> PhysicsRig:
    _require_keys(raw, ("id", "input_param", "output_param", "chain"), "physics rig")
    chain = [
        PhysicsParticle(
            mass=float(p.get("mass", 1.0)),
            damping=float(p.get("damping", 0.7)),
            spring=float(p.get("spring", 12.0)),
        )
        for p in raw["chain"]
    ]
    gravity = raw.get("gravity", [0.0, -9.8])
    return PhysicsRig(
        id=str(raw["id"]),
        input_param=str(raw["input_param"]),
        output_param=str(raw["output_param"]),
        chain=chain,
        gravity=(float(gravity[0]), float(gravity[1])),
    )


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------


def _puppet_json_bytes(doc: PuppetDocument) -> bytes:
    payload = {
        "version": SCHEMA_VERSION,
        "size": [int(doc.size[0]), int(doc.size[1])],
        "drawables": [_drawable_to_json(d) for d in doc.drawables],
        "deformers": [_deformer_to_json(d) for d in doc.deformers],
        "parameters": [_parameter_to_json(p) for p in doc.parameters],
    }
    if doc.pose_groups:
        payload["pose"] = {"groups": [_pose_to_json(g) for g in doc.pose_groups]}
    if doc.motions:
        payload["motions"] = [m.name for m in doc.motions]
    if doc.expressions:
        payload["expressions"] = [e.name for e in doc.expressions]
    if doc.physics_rigs:
        payload["physics"] = _PHYSICS_JSON
    return _dumps(payload)


def _drawable_to_json(d: Drawable) -> dict:
    out = {
        "id": d.id,
        "texture": d.texture,
        "vertices": [list(v) for v in d.vertices],
        "indices": list(d.indices),
        "uvs": [list(uv) for uv in d.uvs],
        "draw_order": d.draw_order,
        "blend_mode": d.blend_mode,
        "visible": d.visible,
        "opacity": d.opacity,
    }
    if d.clip_mask is not None:
        out["clip_mask"] = d.clip_mask
    return out


def _deformer_to_json(d: Deformer) -> dict:
    return {
        "id": d.id,
        "type": d.type,
        "parent": d.parent,
        "drawables": list(d.drawables),
        "form": dict(d.form),
    }


def _parameter_to_json(p: Parameter) -> dict:
    return {
        "id": p.id,
        "min": p.min,
        "max": p.max,
        "default": p.default,
        "keys": [
            {"value": k.value, "forms": {k_id: dict(form) for k_id, form in k.forms.items()}}
            for k in p.keys
        ],
    }


def _pose_to_json(g: PoseGroup) -> dict:
    return {"id": g.id, "drawables": list(g.drawables)}


def _motion_json_bytes(motion: Motion) -> bytes:
    payload = {
        "version": SCHEMA_VERSION,
        "duration": motion.duration,
        "loop": motion.loop,
        "tracks": [
            {
                "param_id": t.param_id,
                "segments": [_segment_to_json(s) for s in t.segments],
            }
            for t in motion.tracks
        ],
    }
    return _dumps(payload)


def _segment_to_json(s: MotionSegment) -> dict:
    out: dict = {
        "type": s.type,
        "p0": list(s.p0),
        "p1": list(s.p1),
    }
    if s.c0 is not None:
        out["c0"] = list(s.c0)
    if s.c1 is not None:
        out["c1"] = list(s.c1)
    return out


def _expression_json_bytes(expr: Expression) -> bytes:
    payload = {
        "version": SCHEMA_VERSION,
        "params": [
            {"id": p.id, "value": p.value, "mode": p.mode}
            for p in expr.params
        ],
    }
    return _dumps(payload)


def _physics_json_bytes(rigs: list[PhysicsRig]) -> bytes:
    payload = {
        "version": SCHEMA_VERSION,
        "rigs": [
            {
                "id": r.id,
                "input_param": r.input_param,
                "output_param": r.output_param,
                "chain": [
                    {"mass": p.mass, "damping": p.damping, "spring": p.spring}
                    for p in r.chain
                ],
                "gravity": list(r.gravity),
            }
            for r in rigs
        ],
    }
    return _dumps(payload)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(zf: zipfile.ZipFile, path: str) -> dict:
    with zf.open(path) as fp:
        try:
            return json.loads(fp.read().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PuppetFormatError(f"{path}: malformed JSON ({exc})") from exc


def _require_keys(raw: dict, keys: tuple[str, ...], label: str) -> None:
    missing = [k for k in keys if k not in raw]
    if missing:
        raise PuppetFormatError(f"{label} missing required keys: {missing}")


def _require_list(manifest: dict, key: str) -> list:
    val = manifest.get(key)
    if not isinstance(val, list):
        raise PuppetFormatError(f"manifest key {key!r} must be a list")
    return val


def _xy(raw: Any) -> tuple[float, float]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise PuppetFormatError(f"expected [x, y] pair, got {raw!r}")
    return (float(raw[0]), float(raw[1]))


def _dumps(payload: dict) -> bytes:
    """Stable, human-readable JSON for git diffs."""
    return json.dumps(
        payload, indent=2, sort_keys=False, ensure_ascii=False,
    ).encode("utf-8")


# Convenience used by Phase 3+'s "Import PNG → puppet" path: build a
# minimal one-drawable, no-deformer document around an existing texture.

def new_blank(size: tuple[int, int] = (1024, 1024)) -> PuppetDocument:
    """Return an empty puppet of ``size`` — no drawables yet. Used as
    the seed for editor sessions starting from scratch."""
    return PuppetDocument(size=size)


# Used internally by ``save_puppet`` callers and the test fixtures.
def to_zip_bytes(doc: PuppetDocument) -> bytes:
    """Serialise ``doc`` to an in-memory zip and return the bytes. Mirrors
    ``save_puppet`` but without touching disk — handy for tests and for
    embedding a puppet inside another container later."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_PUPPET_JSON, _puppet_json_bytes(doc))
        for tex_path, tex_bytes in doc.textures.items():
            zf.writestr(tex_path, tex_bytes)
        for motion in doc.motions:
            zf.writestr(
                f"{_MOTIONS_DIR}{motion.name}.json",
                _motion_json_bytes(motion),
            )
        for expr in doc.expressions:
            zf.writestr(
                f"{_EXPRESSIONS_DIR}{expr.name}.json",
                _expression_json_bytes(expr),
            )
        if doc.physics_rigs:
            zf.writestr(_PHYSICS_JSON, _physics_json_bytes(doc.physics_rigs))
    return buf.getvalue()


def from_zip_bytes(data: bytes) -> PuppetDocument:
    """Inverse of :func:`to_zip_bytes`."""
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        return _load_from_zip(zf)
