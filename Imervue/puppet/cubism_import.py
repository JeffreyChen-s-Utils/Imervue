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

from dataclasses import dataclass, field
from pathlib import Path

from Imervue.puppet.cubism_import_common import CubismFormatError, _read_json
from Imervue.puppet.cubism_import_model import (
    _load_motion_entry,
    _load_referenced_expressions,
    _load_referenced_motions,
    _parse_groups,
    _parse_hit_areas,
)
from Imervue.puppet.cubism_import_motion import (
    _CUBISM_BEZIER,
    _CUBISM_LINEAR,
    _consume_segment,
    load_exp3,
    load_motion3,
)
from Imervue.puppet.cubism_import_parts import load_cdi3, load_pose3
from Imervue.puppet.cubism_import_physics import load_physics3
from Imervue.puppet.document import (
    Expression,
    HitArea,
    Motion,
    PhysicsRig,
    PoseGroup,
)

__all__ = [
    "_CUBISM_BEZIER",
    "_CUBISM_LINEAR",
    "CubismBundle",
    "CubismFormatError",
    "_consume_segment",
    "_load_motion_entry",
    "_read_json",
    "apply_bundle",
    "load_cdi3",
    "load_exp3",
    "load_model3",
    "load_motion3",
    "load_physics3",
    "load_pose3",
]


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


# ---------------------------------------------------------------------------
# Document merging
# ---------------------------------------------------------------------------


def _merge_by_attr(target: list, incoming: list, attr: str) -> None:
    """Append every item from ``incoming`` whose ``attr`` value isn't
    already present in ``target``. Same dedupe-on-attribute pattern
    motions / expressions / hit areas / physics / poses all use."""
    seen = {getattr(item, attr) for item in target}
    for item in incoming:
        key = getattr(item, attr)
        if key not in seen:
            target.append(item)
            seen.add(key)


def apply_bundle(document, bundle: CubismBundle) -> None:
    """Fold ``bundle`` into ``document`` in-place: append motions /
    expressions / hit areas, deduping by name / id. Parameter groups
    aren't merged into the document (the document doesn't model them
    explicitly) — callers wanting them should read
    :attr:`CubismBundle.parameter_groups` directly."""
    _merge_by_attr(document.motions, bundle.motions, "name")
    _merge_by_attr(document.expressions, bundle.expressions, "name")
    _merge_by_attr(document.hit_areas, bundle.hit_areas, "id")
    _merge_by_attr(document.physics_rigs, bundle.physics_rigs, "id")
    _merge_by_attr(document.pose_groups, bundle.pose_groups, "id")
    if bundle.display_names:
        document.display_names.update(bundle.display_names)
