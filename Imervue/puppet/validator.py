"""Static health-check for :class:`PuppetDocument`.

Walks the document and reports problems that would otherwise only
surface at runtime: deformers targeting non-existent drawables, two
parameters sharing an id, bone weights that don't normalise, keyforms
outside their parameter range, missing textures, dangling clip-mask
references, …

Pure-Python — no Qt — so the workspace dialog is a thin wrapper on
:func:`validate` and tests can assert directly on the returned
:class:`Issue` records. The output is intentionally a flat list (not
a tree) so the UI can sort by severity / type / file location without
restructuring the data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from Imervue.puppet.document import PuppetDocument

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Issue:
    """One validation finding.

    * ``severity`` — ``error`` for things that will cause runtime
      failures (missing texture, deformer targeting a non-drawable),
      ``warning`` for likely bugs that won't crash but produce wrong
      output (keyform outside parameter range), ``info`` for stylistic
      / convention hints (unused expression, parameter with no keys).
    * ``code`` — short stable identifier so dashboards can group by
      rule, exactly like a linter rule id.
    * ``message`` — human-readable description, formatted in English.
    * ``location`` — best-effort pointer into the document (e.g.
      ``"deformer:rot1"`` / ``"parameter:ParamAngleX:keys[2]"``).
    """

    severity: Severity
    code: str
    message: str
    location: str = ""


def validate(document: PuppetDocument) -> list[Issue]:
    """Run every check against ``document`` and return the union of
    findings. Order matches the check order so the report reads
    top-down by category."""
    issues: list[Issue] = []
    _check_drawables(document, issues)
    _check_textures(document, issues)
    _check_deformers(document, issues)
    _check_parameters(document, issues)
    _check_motions(document, issues)
    _check_pose_groups(document, issues)
    _check_hit_areas(document, issues)
    _check_parts(document, issues)
    _check_bone_weights(document, issues)
    return issues


# ---------------------------------------------------------------------------
# Per-category checks
# ---------------------------------------------------------------------------


def _check_drawables(document: PuppetDocument, issues: list[Issue]) -> None:
    seen: set[str] = set()
    for drawable in document.drawables:
        if drawable.id in seen:
            issues.append(Issue(
                "error", "duplicate_drawable_id",
                f"two drawables share id {drawable.id!r}",
                f"drawable:{drawable.id}",
            ))
        seen.add(drawable.id)
        if not 0.0 <= drawable.opacity <= 1.0:
            issues.append(Issue(
                "warning", "drawable_opacity_out_of_range",
                f"opacity {drawable.opacity} outside [0, 1]",
                f"drawable:{drawable.id}",
            ))
        if drawable.clip_mask and not _drawable_exists(document, drawable.clip_mask):
            issues.append(Issue(
                "error", "clip_mask_not_found",
                f"clip_mask {drawable.clip_mask!r} not in document",
                f"drawable:{drawable.id}",
            ))


def _check_textures(document: PuppetDocument, issues: list[Issue]) -> None:
    referenced = {d.texture for d in document.drawables}
    available = set(document.textures.keys())
    for missing in sorted(referenced - available):
        issues.append(Issue(
            "error", "texture_missing",
            f"texture {missing!r} referenced by a drawable but absent from textures map",
            f"texture:{missing}",
        ))
    for unused in sorted(available - referenced):
        issues.append(Issue(
            "info", "texture_unused",
            f"texture {unused!r} bundled but no drawable references it",
            f"texture:{unused}",
        ))


def _check_deformers(document: PuppetDocument, issues: list[Issue]) -> None:
    seen: set[str] = set()
    for deformer in document.deformers:
        if deformer.id in seen:
            issues.append(Issue(
                "error", "duplicate_deformer_id",
                f"two deformers share id {deformer.id!r}",
                f"deformer:{deformer.id}",
            ))
        seen.add(deformer.id)
        for drawable_id in deformer.drawables:
            if not _drawable_exists(document, drawable_id):
                issues.append(Issue(
                    "error", "deformer_orphan_drawable",
                    f"deformer targets drawable {drawable_id!r} which isn't in the document",
                    f"deformer:{deformer.id}",
                ))
        if deformer.parent and deformer.parent not in {d.id for d in document.deformers}:
            issues.append(Issue(
                "error", "deformer_orphan_parent",
                f"parent {deformer.parent!r} not in document deformers",
                f"deformer:{deformer.id}",
            ))


def _check_parameters(document: PuppetDocument, issues: list[Issue]) -> None:
    seen: set[str] = set()
    for param in document.parameters:
        if param.id in seen:
            issues.append(Issue(
                "error", "duplicate_parameter_id",
                f"two parameters share id {param.id!r}",
                f"parameter:{param.id}",
            ))
        seen.add(param.id)
        if param.min > param.max:
            issues.append(Issue(
                "error", "parameter_inverted_range",
                f"min ({param.min}) > max ({param.max})",
                f"parameter:{param.id}",
            ))
        if not param.min <= param.default <= param.max:
            issues.append(Issue(
                "warning", "parameter_default_out_of_range",
                f"default ({param.default}) outside [{param.min}, {param.max}]",
                f"parameter:{param.id}",
            ))
        for index, key in enumerate(param.keys):
            if not param.min <= key.value <= param.max:
                issues.append(Issue(
                    "warning", "keyform_out_of_range",
                    f"key {index} value {key.value} outside parameter range",
                    f"parameter:{param.id}:keys[{index}]",
                ))
        if not param.keys:
            issues.append(Issue(
                "info", "parameter_has_no_keys",
                f"parameter {param.id!r} has no keyforms — slider moves nothing",
                f"parameter:{param.id}",
            ))


def _check_motions(document: PuppetDocument, issues: list[Issue]) -> None:
    seen: set[str] = set()
    param_ids = {p.id for p in document.parameters}
    for motion in document.motions:
        if motion.name in seen:
            issues.append(Issue(
                "error", "duplicate_motion_name",
                f"two motions share name {motion.name!r}",
                f"motion:{motion.name}",
            ))
        seen.add(motion.name)
        if motion.duration <= 0:
            issues.append(Issue(
                "warning", "motion_zero_duration",
                f"motion {motion.name!r} has duration {motion.duration}",
                f"motion:{motion.name}",
            ))
        for track in motion.tracks:
            if track.param_id not in param_ids:
                issues.append(Issue(
                    "warning", "motion_unknown_parameter",
                    f"track targets parameter {track.param_id!r} not in document",
                    f"motion:{motion.name}",
                ))


def _check_pose_groups(document: PuppetDocument, issues: list[Issue]) -> None:
    for group in document.pose_groups:
        for drawable_id in group.drawables:
            if not _drawable_exists(document, drawable_id):
                issues.append(Issue(
                    "warning", "pose_group_orphan_drawable",
                    f"pose group lists drawable {drawable_id!r} which isn't in the document",
                    f"pose_group:{group.id}",
                ))


def _check_hit_areas(document: PuppetDocument, issues: list[Issue]) -> None:
    motion_names = {m.name for m in document.motions}
    motion_groups = {m.group for m in document.motions if m.group}
    expression_names = {e.name for e in document.expressions}
    for area in document.hit_areas:
        for drawable_id in area.drawables:
            if not _drawable_exists(document, drawable_id):
                issues.append(Issue(
                    "warning", "hit_area_orphan_drawable",
                    f"hit area drawable {drawable_id!r} not in document",
                    f"hit_area:{area.id}",
                ))
        if area.motion and area.motion not in motion_names | motion_groups:
            issues.append(Issue(
                "warning", "hit_area_orphan_motion",
                f"hit area motion {area.motion!r} matches no motion name or group",
                f"hit_area:{area.id}",
            ))
        if area.expression and area.expression not in expression_names:
            issues.append(Issue(
                "warning", "hit_area_orphan_expression",
                f"hit area expression {area.expression!r} not in document",
                f"hit_area:{area.id}",
            ))


def _check_parts(document: PuppetDocument, issues: list[Issue]) -> None:
    part_ids = {p.id for p in document.parts}
    for part in document.parts:
        for drawable_id in part.drawables:
            if not _drawable_exists(document, drawable_id):
                issues.append(Issue(
                    "warning", "part_orphan_drawable",
                    f"part drawable {drawable_id!r} not in document",
                    f"part:{part.id}",
                ))
        for child_id in part.children:
            if child_id not in part_ids:
                issues.append(Issue(
                    "warning", "part_orphan_child",
                    f"part child {child_id!r} isn't a Part in this document",
                    f"part:{part.id}",
                ))


def _check_bone_weights(document: PuppetDocument, issues: list[Issue]) -> None:
    """LBS expects per-vertex weights across all bones to sum to ``1``.
    The runtime renormalises silently but mismatches usually indicate
    an authoring error (a half-painted weight map) so we flag them at
    the ``warning`` level."""
    for drawable in document.drawables:
        if not drawable.bone_weights:
            continue
        n_vertices = len(drawable.vertices)
        if not n_vertices:
            continue
        sums = [0.0] * n_vertices
        for weights in drawable.bone_weights.values():
            for i in range(min(n_vertices, len(weights))):
                sums[i] += float(weights[i])
        bad_indices = [i for i, total in enumerate(sums) if abs(total - 1.0) > 0.05]
        if not bad_indices:
            continue
        sample = bad_indices[:5]
        issues.append(Issue(
            "warning", "bone_weights_not_normalised",
            f"{len(bad_indices)} vertex weights don't sum to ~1.0 "
            f"(first offsets: {sample})",
            f"drawable:{drawable.id}",
        ))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _drawable_exists(document: PuppetDocument, drawable_id: str) -> bool:
    return any(d.id == drawable_id for d in document.drawables)


def severity_counts(issues: list[Issue]) -> dict[str, int]:
    """Group findings by severity — handy for a one-line summary at
    the top of the report dialog."""
    out: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        out[issue.severity] = out.get(issue.severity, 0) + 1
    return out
