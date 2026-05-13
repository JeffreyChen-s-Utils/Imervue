"""Live2D Cubism v3 file-format importers.

Reads ``.motion3.json``, ``.exp3.json`` and ``.model3.json`` and maps
them onto our :mod:`puppet.document` dataclasses. The binary mesh
container (``.moc3``) is intentionally out of scope — without it we
can't reconstruct the original drawables/deformers, but the metadata
formats are JSON and asset-portable, so a user can drop a Cubism
motion library onto their own PSD-imported rig as long as parameter
ids match.

Why this exists: Cubism's free templates (Hiyori / Haru / Mark) ship
with .motion3.json + .exp3.json + .model3.json bundles. Being able to
ingest those directly is the strongest "feels like Live2D" signal —
the user doesn't have to author every motion from zero.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from Imervue.puppet.document import (
    Expression,
    ExpressionParam,
    HitArea,
    Motion,
    MotionSegment,
    MotionTrack,
    PhysicsParticle,
    PhysicsRig,
    PoseGroup,
)


class CubismFormatError(ValueError):
    """Raised when a Cubism JSON file doesn't conform to the v3 schema
    or carries values we can't translate."""


# Cubism segment-type ids per the v3 spec.
_CUBISM_LINEAR: int = 0
_CUBISM_BEZIER: int = 1
_CUBISM_STEPPED: int = 2
_CUBISM_INVERSE_STEPPED: int = 3

_CUBISM_BLEND_TO_MODE: dict[str, str] = {
    "Add": "additive",
    "Multiply": "multiply",
    "Overwrite": "overwrite",
}


@dataclass
class CubismBundle:
    """Aggregate of everything the importer extracted from a
    ``.model3.json`` and its referenced files. The workspace folds
    this into a :class:`PuppetDocument` (or merges with the active
    document) once it's ready to apply the bundle."""

    motions: list[Motion] = field(default_factory=list)
    expressions: list[Expression] = field(default_factory=list)
    hit_areas: list[HitArea] = field(default_factory=list)
    physics_rigs: list[PhysicsRig] = field(default_factory=list)
    pose_groups: list[PoseGroup] = field(default_factory=list)
    display_names: dict[str, str] = field(default_factory=dict)
    parameter_groups: dict[str, list[str]] = field(default_factory=dict)
    """Cubism Groups list keyed by group name (``EyeBlink`` /
    ``LipSync`` are the standard ones). Each value is the list of
    parameter ids that group covers — drivers can use this to discover
    which params to drive without hardcoding ids per rig."""


# ---------------------------------------------------------------------------
# .motion3.json
# ---------------------------------------------------------------------------


def load_motion3(path: str | Path, *, name: str | None = None) -> Motion:
    """Parse one Cubism ``.motion3.json`` into our :class:`Motion`.

    ``name`` defaults to the file's stem (``idle_01.motion3.json`` →
    ``idle_01``) so the motion picker in the dock has a readable label.
    Non-``Parameter`` curves (``PartOpacity`` / ``Model``) are skipped —
    they target Cubism-specific state our runtime doesn't model.
    """
    p = Path(path)
    raw = _read_json(p)
    meta = raw.get("Meta") or {}
    motion_name = name or p.stem.removesuffix(".motion3")
    return Motion(
        name=motion_name,
        duration=float(meta.get("Duration", 0.0)),
        loop=bool(meta.get("Loop", False)),
        tracks=_parse_motion_curves(raw.get("Curves") or []),
        fade_in_duration=float(meta.get("FadeInTime", 0.0)),
        fade_out_duration=float(meta.get("FadeOutTime", 0.0)),
    )


def _parse_motion_curves(curves: list[dict]) -> list[MotionTrack]:
    tracks: list[MotionTrack] = []
    for curve in curves:
        if curve.get("Target") != "Parameter":
            continue
        param_id = curve.get("Id")
        segments_raw = curve.get("Segments")
        if not isinstance(param_id, str) or not isinstance(segments_raw, list):
            continue
        tracks.append(
            MotionTrack(
                param_id=param_id,
                segments=_parse_cubism_segments(segments_raw),
            ),
        )
    return tracks


def _parse_cubism_segments(raw: list[float]) -> list[MotionSegment]:
    """Walk Cubism's flat segment array. Format: ``[t0, v0, type, p1,
    p2, ...]`` where each segment consumes a type byte plus 2 (linear /
    stepped / inverse-stepped) or 6 (bezier) floats and the next
    segment continues from the previous segment's endpoint."""
    if len(raw) < 2:
        return []
    cursor = 2
    prev = (float(raw[0]), float(raw[1]))
    segments: list[MotionSegment] = []
    while cursor < len(raw):
        seg_type = int(raw[cursor])
        cursor += 1
        segment, prev, cursor = _consume_segment(raw, cursor, seg_type, prev)
        segments.append(segment)
    return segments


def _consume_segment(
    raw: list[float], cursor: int, seg_type: int, prev: tuple[float, float],
) -> tuple[MotionSegment, tuple[float, float], int]:
    if seg_type == _CUBISM_LINEAR:
        p1 = (float(raw[cursor]), float(raw[cursor + 1]))
        return MotionSegment(type="linear", p0=prev, p1=p1), p1, cursor + 2
    if seg_type == _CUBISM_BEZIER:
        c0 = (float(raw[cursor]), float(raw[cursor + 1]))
        c1 = (float(raw[cursor + 2]), float(raw[cursor + 3]))
        p1 = (float(raw[cursor + 4]), float(raw[cursor + 5]))
        return (
            MotionSegment(type="cubic-bezier", p0=prev, p1=p1, c0=c0, c1=c1),
            p1, cursor + 6,
        )
    if seg_type == _CUBISM_STEPPED:
        p1 = (float(raw[cursor]), float(raw[cursor + 1]))
        return MotionSegment(type="stepped", p0=prev, p1=p1), p1, cursor + 2
    if seg_type == _CUBISM_INVERSE_STEPPED:
        p1 = (float(raw[cursor]), float(raw[cursor + 1]))
        return MotionSegment(type="inverse-stepped", p0=prev, p1=p1), p1, cursor + 2
    raise CubismFormatError(f"unknown Cubism segment type {seg_type}")


# ---------------------------------------------------------------------------
# .exp3.json
# ---------------------------------------------------------------------------


def load_exp3(path: str | Path, *, name: str | None = None) -> Expression:
    """Parse one Cubism ``.exp3.json`` into our :class:`Expression`."""
    p = Path(path)
    raw = _read_json(p)
    if raw.get("Type") not in (None, "Live2D Expression"):
        raise CubismFormatError(
            f"{p} Type {raw.get('Type')!r} is not 'Live2D Expression'",
        )
    expression_name = name or p.stem.removesuffix(".exp3")
    return Expression(
        name=expression_name,
        params=[_parse_exp_param(p) for p in raw.get("Parameters") or []],
    )


def _parse_exp_param(raw: dict) -> ExpressionParam:
    cubism_blend = raw.get("Blend", "Add")
    mode = _CUBISM_BLEND_TO_MODE.get(cubism_blend)
    if mode is None:
        raise CubismFormatError(
            f"unknown Cubism expression Blend {cubism_blend!r}; "
            f"expected one of {list(_CUBISM_BLEND_TO_MODE)}",
        )
    return ExpressionParam(
        id=str(raw["Id"]),
        value=float(raw.get("Value", 0.0)),
        mode=mode,
    )


# ---------------------------------------------------------------------------
# .model3.json
# ---------------------------------------------------------------------------


def load_model3(path: str | Path) -> CubismBundle:
    """Read a Cubism ``.model3.json`` and resolve every referenced
    motion / expression file relative to its directory.

    Skips ``.moc3`` (binary mesh — not in scope) and texture lists
    (the user is applying these motions to their own rig). Returns a
    :class:`CubismBundle` the caller can fold into a
    :class:`PuppetDocument` via :func:`apply_bundle`.
    """
    p = Path(path)
    raw = _read_json(p)
    refs = raw.get("FileReferences") or {}
    base = p.parent
    bundle = CubismBundle()
    bundle.motions = _load_referenced_motions(base, refs.get("Motions") or {})
    bundle.expressions = _load_referenced_expressions(
        base, refs.get("Expressions") or [],
    )
    bundle.parameter_groups = _parse_groups(raw.get("Groups") or [])
    bundle.hit_areas = _parse_hit_areas(raw.get("HitAreas") or [])
    physics_ref = refs.get("Physics")
    if isinstance(physics_ref, str) and physics_ref:
        bundle.physics_rigs = load_physics3(base / physics_ref)
    pose_ref = refs.get("Pose")
    if isinstance(pose_ref, str) and pose_ref:
        bundle.pose_groups = load_pose3(base / pose_ref)
    display_ref = refs.get("DisplayInfo")
    if isinstance(display_ref, str) and display_ref:
        bundle.display_names = load_cdi3(base / display_ref)
    return bundle


def _load_referenced_motions(base: Path, motions_raw: dict) -> list[Motion]:
    out: list[Motion] = []
    for group_name, entries in motions_raw.items():
        if not isinstance(entries, list):
            continue
        for _index, entry in enumerate(entries):
            file_ref = entry.get("File") if isinstance(entry, dict) else None
            if not file_ref:
                continue
            motion_path = base / file_ref
            # Real Cubism rigs ship multiple motions per group sharing
            # the group name as a prefix in the file name (idle_01.motion3.json
            # etc.). Surfacing the file stem keeps that intent without
            # collapsing all of them under "Idle_0" / "Idle_1".
            real_name = Path(file_ref).stem.removesuffix(".motion3")
            motion = load_motion3(motion_path, name=f"{group_name}/{real_name}")
            motion.group = str(group_name)
            # FadeInTime / FadeOutTime on the model3 reference override
            # the motion3's own values when present — matches Cubism's
            # precedence rule.
            if isinstance(entry.get("FadeInTime"), (int, float)):
                motion.fade_in_duration = float(entry["FadeInTime"])
            if isinstance(entry.get("FadeOutTime"), (int, float)):
                motion.fade_out_duration = float(entry["FadeOutTime"])
            sound_ref = entry.get("Sound")
            if isinstance(sound_ref, str) and sound_ref:
                motion.sound_path = str(base / sound_ref)
            out.append(motion)
    return out


def _load_referenced_expressions(base: Path, exprs_raw: list) -> list[Expression]:
    out: list[Expression] = []
    for entry in exprs_raw:
        if not isinstance(entry, dict):
            continue
        file_ref = entry.get("File")
        if not file_ref:
            continue
        name = entry.get("Name") or Path(file_ref).stem.removesuffix(".exp3")
        out.append(load_exp3(base / file_ref, name=str(name)))
    return out


def _parse_groups(groups_raw: list) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for group in groups_raw:
        if not isinstance(group, dict):
            continue
        if group.get("Target") != "Parameter":
            continue
        name = group.get("Name")
        ids = group.get("Ids")
        if isinstance(name, str) and isinstance(ids, list):
            out[name] = [str(i) for i in ids]
    return out


def _parse_hit_areas(hit_raw: list) -> list[HitArea]:
    """Cubism ``HitAreas`` point at drawable ids that only exist inside
    the original ``.moc3``. We store the id anyway so the workspace
    can match them against rig drawables sharing the same name (often
    the case when the user names their PSD layers after the Cubism
    rig's part ids)."""
    out: list[HitArea] = []
    for entry in hit_raw:
        if not isinstance(entry, dict):
            continue
        drawable_id = entry.get("Id")
        name = entry.get("Name") or drawable_id
        if not isinstance(drawable_id, str):
            continue
        out.append(HitArea(id=str(name), drawables=[str(drawable_id)]))
    return out


# ---------------------------------------------------------------------------
# .physics3.json
# ---------------------------------------------------------------------------


def load_physics3(path: str | Path) -> list[PhysicsRig]:
    """Parse a Cubism ``.physics3.json`` into a list of
    :class:`PhysicsRig`.

    Cubism describes physics in much greater detail than our runtime
    (per-vertex Mobility / Delay / Acceleration / Radius, multiple
    Input/Output mappings, Normalization curves). We translate the
    shape rather than the dynamics: chain length comes from the
    Vertices array; the first ``Input.Source.Id`` and
    ``Output.Destination.Id`` become the rig's input/output params;
    each :class:`PhysicsParticle` uses our standard defaults. The
    result swings — just not pixel-identical to Cubism's runtime."""
    raw = _read_json(Path(path))
    settings = raw.get("PhysicsSettings") or []
    return [
        rig
        for entry in settings
        if (rig := _parse_physics_setting(entry)) is not None
    ]


def _parse_physics_setting(entry: dict) -> PhysicsRig | None:
    rig_id = entry.get("Id")
    inputs = entry.get("Input") or []
    outputs = entry.get("Output") or []
    vertices = entry.get("Vertices") or []
    if not isinstance(rig_id, str) or not inputs or not outputs or not vertices:
        return None
    input_param = _physics_endpoint_id(inputs[0], "Source")
    output_param = _physics_endpoint_id(outputs[0], "Destination")
    if input_param is None or output_param is None:
        return None
    return PhysicsRig(
        id=rig_id,
        input_param=input_param,
        output_param=output_param,
        chain=[_cubism_vertex_to_particle(v) for v in vertices],
    )


_DEFAULT_SPRING: float = 12.0


def _cubism_vertex_to_particle(vertex: dict) -> PhysicsParticle:
    """Map a Cubism physics vertex onto our particle dynamics.

    Cubism describes each vertex with four scalar coefficients:

    * ``Mobility`` ``[0, 1]`` — how much the particle responds to forces;
      we map this inversely onto damping (high mobility = low damping).
    * ``Delay`` ``[0, 1]`` — how slowly the particle catches up to its
      parent; we map this inversely onto spring stiffness (high delay =
      low spring, so the particle takes longer to converge).
    * ``Acceleration`` (non-negative) — boosts the spring on top of the
      delay-derived baseline so a heavy chain still has perceptible
      response.
    * ``Radius`` — rest distance from the parent vertex. We don't model
      per-particle radius in our Verlet integrator (all springs share
      ``REST_LENGTH``), but it influences ``mass``: bigger radius
      reads as a heavier inertia element.

    The mapping is a heuristic, not a faithful port of Cubism's
    proprietary integrator — but it captures the per-particle
    variation rather than collapsing everyone to the defaults."""
    mobility = _clamp01(vertex.get("Mobility", 1.0))
    delay = _clamp01(vertex.get("Delay", 1.0))
    acceleration = max(0.0, float(vertex.get("Acceleration", 1.0)))
    radius = max(0.0, float(vertex.get("Radius", 1.0)))
    damping = max(0.0, min(0.999, 1.0 - mobility * 0.9))
    spring = _DEFAULT_SPRING * (1.0 - delay * 0.8) * (0.5 + acceleration * 0.5)
    spring = max(0.5, min(30.0, spring))
    mass = max(0.25, min(4.0, 0.5 + radius * 0.5))
    return PhysicsParticle(mass=mass, damping=damping, spring=spring)


def _clamp01(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, v))


def _physics_endpoint_id(entry: dict, key: str) -> str | None:
    target = entry.get(key)
    if not isinstance(target, dict):
        return None
    if target.get("Target") != "Parameter":
        return None
    raw_id = target.get("Id")
    return str(raw_id) if isinstance(raw_id, str) else None


# ---------------------------------------------------------------------------
# .pose3.json
# ---------------------------------------------------------------------------


def load_pose3(path: str | Path) -> list[PoseGroup]:
    """Parse a Cubism ``.pose3.json`` into a list of :class:`PoseGroup`.

    Cubism's ``Groups`` field is a 2-D structure: each top-level entry
    is a mutually-exclusive set, each item inside it represents one
    alternative with its primary id plus a list of secondary
    ``Link`` ids. We collapse this to one :class:`PoseGroup` per
    mutex set whose ``drawables`` includes both the primary and any
    Link ids — when the runtime picks one primary as active, every
    drawable in its row gets shown together, which approximates
    Cubism's "show this part *and* its dependencies" behaviour."""
    raw = _read_json(Path(path))
    if raw.get("Type") not in (None, "Live2D Pose"):
        raise CubismFormatError(
            f"{path} Type {raw.get('Type')!r} is not 'Live2D Pose'",
        )
    groups_raw = raw.get("Groups") or []
    out: list[PoseGroup] = []
    for idx, group in enumerate(groups_raw):
        if not isinstance(group, list):
            continue
        drawables = _pose_group_drawables(group)
        if not drawables:
            continue
        out.append(PoseGroup(id=f"pose_group_{idx}", drawables=drawables))
    return out


def _pose_group_drawables(group: list) -> list[str]:
    drawables: list[str] = []
    for item in group:
        if not isinstance(item, dict):
            continue
        primary = item.get("Id")
        if isinstance(primary, str) and primary:
            drawables.append(primary)
        for link in item.get("Link") or []:
            if isinstance(link, str) and link:
                drawables.append(link)
    return drawables


# ---------------------------------------------------------------------------
# .cdi3.json
# ---------------------------------------------------------------------------


def load_cdi3(path: str | Path) -> dict[str, str]:
    """Parse a Cubism ``.cdi3.json`` display-info file into a
    ``{id: name}`` mapping covering parameters, parameter groups,
    and parts. The :class:`PuppetDocument.display_names` field
    consumes this directly."""
    raw = _read_json(Path(path))
    out: dict[str, str] = {}
    for section in ("Parameters", "ParameterGroups", "Parts"):
        for entry in raw.get(section) or []:
            if not isinstance(entry, dict):
                continue
            id_ = entry.get("Id")
            name = entry.get("Name")
            if isinstance(id_, str) and isinstance(name, str) and name:
                out[id_] = name
    return out


# ---------------------------------------------------------------------------
# Document merging
# ---------------------------------------------------------------------------


def apply_bundle(document, bundle: CubismBundle) -> None:
    """Fold ``bundle`` into ``document`` in-place: append motions /
    expressions / hit areas, deduping by name / id. Parameter groups
    aren't merged into the document (the document doesn't model them
    explicitly) — callers wanting them should read
    :attr:`CubismBundle.parameter_groups` directly."""
    existing_motions = {m.name for m in document.motions}
    for motion in bundle.motions:
        if motion.name not in existing_motions:
            document.motions.append(motion)
            existing_motions.add(motion.name)
    existing_expressions = {e.name for e in document.expressions}
    for expression in bundle.expressions:
        if expression.name not in existing_expressions:
            document.expressions.append(expression)
            existing_expressions.add(expression.name)
    existing_hits = {h.id for h in document.hit_areas}
    for hit in bundle.hit_areas:
        if hit.id not in existing_hits:
            document.hit_areas.append(hit)
            existing_hits.add(hit.id)
    existing_rigs = {r.id for r in document.physics_rigs}
    for rig in bundle.physics_rigs:
        if rig.id not in existing_rigs:
            document.physics_rigs.append(rig)
            existing_rigs.add(rig.id)
    existing_poses = {p.id for p in document.pose_groups}
    for group in bundle.pose_groups:
        if group.id not in existing_poses:
            document.pose_groups.append(group)
            existing_poses.add(group.id)
    if bundle.display_names:
        document.display_names.update(bundle.display_names)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CubismFormatError(f"{path}: malformed JSON ({exc})") from exc
