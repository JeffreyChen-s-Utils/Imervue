"""Per-frame parameter sampling + deformer composition.

The runtime composer is the bridge between the parameter-slider /
motion-track / physics-output values and the GL renderer's
per-vertex arrays. Pure-numpy + Qt-free so editor / playback / unit
tests share the same code path.

Pipeline per frame:

1. ``param_value_for_each_parameter`` — caller-supplied dict.
2. For each parameter, ``sample_parameter_forms`` finds the two
   adjacent keys, interpolates each deformer's form between them, and
   merges the results into a per-deformer override.
3. ``compose_drawable_vertices`` walks deformers in array order,
   applies each one whose ``drawables`` list contains the drawable,
   and returns the resulting vertex array.

The deformer order in ``document.deformers`` is the application
order; parents normally precede their children but the runtime
doesn't enforce that — the editor's responsibility.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from Imervue.puppet.deformers import (
    apply_rotation,
    apply_warp,
    blend_forms,
)
from Imervue.puppet.document import (
    Deformer,
    Drawable,
    Expression,
    Parameter,
    PuppetDocument,
)


# ---------------------------------------------------------------------------
# Parameter sampling
# ---------------------------------------------------------------------------


def sample_parameter_forms(
    parameter: Parameter, value: float,
) -> dict[str, dict[str, Any]]:
    """Return ``{deformer_id: form_override}`` interpolated at the
    given parameter value.

    Behaviour:
    * No keys → empty dict (parameter has no effect).
    * One key → that key's forms.
    * Below the lowest / above the highest key → clamp to the edge
      key's forms.
    * Otherwise → linear interpolation between the two surrounding
      keys, per-deformer, per-field.
    """
    keys = parameter.keys
    if not keys:
        return {}
    if len(keys) == 1:
        return _copy_forms(keys[0].forms)
    sorted_keys = sorted(keys, key=lambda k: k.value)
    if value <= sorted_keys[0].value:
        return _copy_forms(sorted_keys[0].forms)
    if value >= sorted_keys[-1].value:
        return _copy_forms(sorted_keys[-1].forms)
    for i in range(len(sorted_keys) - 1):
        a, b = sorted_keys[i], sorted_keys[i + 1]
        if a.value <= value <= b.value:
            t = 0.0 if b.value == a.value else (value - a.value) / (b.value - a.value)
            return _blend_forms_dicts(a.forms, b.forms, t)
    # Unreachable given the clamps above; defensive.
    return _copy_forms(sorted_keys[-1].forms)


def merge_parameter_samples(
    document: PuppetDocument, values: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """Aggregate every parameter's sampled forms into a single
    ``{deformer_id: merged_form}`` dict.

    When two parameters both override the same field on the same
    deformer the later parameter (in document.parameters order) wins.
    Most rigs avoid this by keying disjoint deformers per parameter,
    but the runtime stays defined either way.
    """
    out: dict[str, dict[str, Any]] = {}
    for param in document.parameters:
        if param.id not in values:
            continue
        sampled = sample_parameter_forms(param, float(values[param.id]))
        for def_id, form in sampled.items():
            existing = out.get(def_id)
            if existing is None:
                out[def_id] = dict(form)
            else:
                existing.update(form)
    return out


# ---------------------------------------------------------------------------
# Deformer composition
# ---------------------------------------------------------------------------


def compose_drawable_vertices(
    drawable: Drawable,
    deformers: list[Deformer],
    overrides: dict[str, dict[str, Any]],
) -> np.ndarray:
    """Apply every deformer that targets ``drawable`` to its neutral
    vertices and return the deformed Nx2 array.

    ``overrides`` is the merged-parameter output from
    :func:`merge_parameter_samples`. A deformer not present in
    ``overrides`` runs with its authored neutral form (= identity in
    practice, since neutral forms produce identity transforms).
    """
    verts = np.asarray(drawable.vertices, dtype=np.float64)
    for deformer in deformers:
        if drawable.id not in deformer.drawables:
            continue
        form = _form_for(deformer, overrides)
        verts = _apply_deformer(deformer.type, verts, form)
    return verts.astype(np.float32, copy=False)


def compose_all_drawables(
    document: PuppetDocument, values: dict[str, float],
) -> dict[str, np.ndarray]:
    """Convenience: run :func:`compose_drawable_vertices` for every
    drawable in ``document``, returning a ``{drawable_id: verts}`` map.
    Caller is the canvas's per-frame paint."""
    overrides = merge_parameter_samples(document, values)
    return {
        d.id: compose_drawable_vertices(d, document.deformers, overrides)
        for d in document.drawables
    }


def default_parameter_values(document: PuppetDocument) -> dict[str, float]:
    """Map every parameter to its default value — used by the canvas
    to seed the parameter-values dict on document load."""
    return {p.id: float(p.default) for p in document.parameters}


# ---------------------------------------------------------------------------
# Expression overlay
# ---------------------------------------------------------------------------


def apply_expression(
    values: dict[str, float], expression: Expression,
) -> dict[str, float]:
    """Apply ``expression``'s param overrides on top of ``values`` and
    return a new dict. Original values dict is not mutated.

    Modes per the v1 schema:
    * ``additive`` — final = base + value
    * ``multiply`` — final = base × value
    * ``overwrite`` — final = value (ignores base)
    """
    out = dict(values)
    for pp in expression.params:
        base = float(out.get(pp.id, 0.0))
        if pp.mode == "additive":
            out[pp.id] = base + float(pp.value)
        elif pp.mode == "multiply":
            out[pp.id] = base * float(pp.value)
        elif pp.mode == "overwrite":
            out[pp.id] = float(pp.value)
        else:
            out[pp.id] = base
    return out


def apply_expressions(
    values: dict[str, float], expressions: list[Expression],
) -> dict[str, float]:
    """Compose multiple expressions in list order (last writer wins on
    overlapping params)."""
    out = dict(values)
    for expr in expressions:
        out = apply_expression(out, expr)
    return out


# ---------------------------------------------------------------------------
# Pose visibility
# ---------------------------------------------------------------------------


def resolve_pose_visibility(
    document: PuppetDocument, active_per_group: dict[str, str],
) -> dict[str, bool]:
    """Build ``{drawable_id: visible}`` honouring pose-group exclusivity.

    For every group, the drawable named in ``active_per_group[group_id]``
    is visible and the rest of the group is hidden. Drawables not part
    of any group keep their authored ``visible`` flag.

    A group whose ``active_per_group`` entry is missing or invalid
    keeps its first member visible — matches the v1 schema's "exactly
    one drawable per group is shown" contract.
    """
    out = {d.id: bool(d.visible) for d in document.drawables}
    for group in document.pose_groups:
        active = active_per_group.get(group.id)
        if active not in group.drawables:
            active = group.drawables[0] if group.drawables else None
        for member in group.drawables:
            out[member] = (member == active)
    return out


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


_DEFORMER_FUNCS = {
    "rotation": apply_rotation,
    "warp": apply_warp,
}


def _apply_deformer(
    type_: str, vertices: np.ndarray, form: dict[str, Any],
) -> np.ndarray:
    fn = _DEFORMER_FUNCS.get(type_)
    if fn is None:
        return vertices
    return fn(vertices, form)


def _form_for(
    deformer: Deformer, overrides: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return the deformer's form merged with any parameter override.

    The deformer's authored form is the neutral pose; parameter keys
    deliver partial deltas, so we layer the override on top of the
    neutral form rather than replacing it. That keeps the warp's
    ``rows`` / ``cols`` / ``bounds`` constants (which never appear in
    parameter overrides) intact while ``angle`` / ``grid`` are
    overwritten per-frame.
    """
    base = dict(deformer.form)
    delta = overrides.get(deformer.id)
    if delta:
        base.update(delta)
    return base


def _copy_forms(forms: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {k: dict(v) for k, v in forms.items()}


def _blend_forms_dicts(
    a: dict[str, dict[str, Any]],
    b: dict[str, dict[str, Any]],
    t: float,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for def_id, form_a in a.items():
        form_b = b.get(def_id)
        if form_b is None:
            out[def_id] = dict(form_a)
        else:
            out[def_id] = blend_forms(form_a, form_b, t)
    for def_id, form_b in b.items():
        if def_id not in out:
            out[def_id] = dict(form_b)
    return out
