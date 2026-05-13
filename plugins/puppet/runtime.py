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

from puppet.deformers import (
    apply_rotation,
    apply_skeleton_lbs,
    apply_warp,
    blend_forms,
)
from puppet.document import (
    BlendKey,
    Deformer,
    Drawable,
    Expression,
    Parameter,
    ParameterBlend,
    Part,
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

    Multi-axis :class:`ParameterBlend` groups are sampled after the
    single-parameter keys so a blend can override the per-axis result
    when both target the same deformer — matches Live2D's "the more
    specific keyform wins" intuition.
    """
    out: dict[str, dict[str, Any]] = {}
    for param in document.parameters:
        if param.id not in values:
            continue
        sampled = sample_parameter_forms(param, float(values[param.id]))
        _merge_form_dicts_into(out, sampled)
    for blend in document.parameter_blends:
        sampled = sample_blend_forms(blend, values)
        _merge_form_dicts_into(out, sampled)
    return out


def _merge_form_dicts_into(
    target: dict[str, dict[str, Any]],
    additions: dict[str, dict[str, Any]],
) -> None:
    for def_id, form in additions.items():
        existing = target.get(def_id)
        if existing is None:
            target[def_id] = dict(form)
        else:
            existing.update(form)


def sample_blend_forms(
    blend: ParameterBlend, values: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """N-D linear sample of ``blend`` at the current parameter values.

    Returns ``{deformer_id: form_override}``. Empty when the blend has
    no keys or no parameters, when none of the named parameters have
    values, or when no axis has at least one key value to interpolate
    against (e.g. all keys share the same coord on every axis).

    Algorithm: for each axis, find the bracketing pair of distinct key
    coords around the current parameter value (clamping to the edge
    coord when out of range). Build the ``2 ** N`` corner keys at the
    cartesian product of those brackets, then progressively reduce
    along each axis using :func:`blend_forms`.
    """
    if not blend.parameters or not blend.keys:
        return {}
    coords_by_axis = [sorted({k.coords[i] for k in blend.keys})
                      for i in range(len(blend.parameters))]
    brackets = _bracket_per_axis(blend, values, coords_by_axis)
    if brackets is None:
        return {}
    return _reduce_corners(blend, brackets)


def _bracket_per_axis(
    blend: ParameterBlend,
    values: dict[str, float],
    coords_by_axis: list[list[float]],
) -> list[tuple[float, float, float]] | None:
    """For each axis, return ``(lo, hi, t)`` where ``t in [0, 1]`` is
    the position of the parameter value between ``lo`` and ``hi``.

    Returns ``None`` when there isn't enough information to sample (an
    axis with no keys or with all-equal coords yields no interpolation
    direction; ``None`` lets the caller bail cleanly)."""
    out: list[tuple[float, float, float]] = []
    for axis_index, axis_coords in enumerate(coords_by_axis):
        if not axis_coords:
            return None
        param_id = blend.parameters[axis_index]
        value = float(values.get(param_id, axis_coords[0]))
        if value <= axis_coords[0]:
            out.append((axis_coords[0], axis_coords[0], 0.0))
            continue
        if value >= axis_coords[-1]:
            out.append((axis_coords[-1], axis_coords[-1], 1.0))
            continue
        lo, hi = axis_coords[0], axis_coords[-1]
        for i in range(len(axis_coords) - 1):
            if axis_coords[i] <= value <= axis_coords[i + 1]:
                lo, hi = axis_coords[i], axis_coords[i + 1]
                break
        span = hi - lo
        t = 0.0 if span == 0 else (value - lo) / span
        out.append((lo, hi, t))
    return out


def _reduce_corners(
    blend: ParameterBlend,
    brackets: list[tuple[float, float, float]],
) -> dict[str, dict[str, Any]]:
    """Walk the ``2 ** N`` cartesian-product corners of the bracket box
    and N-D-linearly blend the deformer forms into a single override
    dict. Missing corners are skipped — their absence shows up as
    "no override for that deformer at that corner", which the rest of
    the pipeline already tolerates.
    """
    corners = _collect_corner_keys(blend, brackets)
    if not corners:
        return {}
    # Walk axes from last to first so the early reductions collapse the
    # innermost varying dimension first — the order of axis reduction
    # doesn't change the result for linear interpolation but doing
    # high-to-low keeps the integer-key arithmetic obvious.
    n_axes = len(brackets)
    for axis in range(n_axes - 1, -1, -1):
        t = brackets[axis][2]
        next_corners: dict[tuple[int, ...], dict[str, dict[str, Any]]] = {}
        for key, form_map in corners.items():
            head, tail = key[:axis], key[axis + 1:]
            sub_key = head + tail
            if key[axis] == 0:
                pair_key = head + (1,) + tail
                pair_form = corners.get(pair_key)
                blended = (
                    _blend_form_maps(form_map, pair_form, t)
                    if pair_form is not None else form_map
                )
            else:
                pair_key = head + (0,) + tail
                if pair_key in corners:
                    # Already merged when we processed the 0-side key.
                    continue
                blended = form_map
            next_corners[sub_key] = blended
        corners = next_corners
    return next(iter(corners.values()))


def _collect_corner_keys(
    blend: ParameterBlend,
    brackets: list[tuple[float, float, float]],
) -> dict[tuple[int, ...], dict[str, dict[str, Any]]]:
    """Find the :class:`BlendKey` for every cartesian-product corner of
    the bracket. Returns ``{(0|1, 0|1, ...): forms}``.
    """
    coord_lookup: dict[tuple[float, ...], BlendKey] = {}
    for key in blend.keys:
        coord_lookup[tuple(float(c) for c in key.coords)] = key
    n_axes = len(brackets)
    out: dict[tuple[int, ...], dict[str, dict[str, Any]]] = {}
    for mask in range(1 << n_axes):
        coords = tuple(
            brackets[axis][1 if (mask >> axis) & 1 else 0]
            for axis in range(n_axes)
        )
        match = coord_lookup.get(coords)
        if match is None:
            continue
        bits = tuple((mask >> axis) & 1 for axis in range(n_axes))
        out[bits] = _copy_forms(match.forms)
    return out


def _blend_form_maps(
    a: dict[str, dict[str, Any]],
    b: dict[str, dict[str, Any]] | None,
    t: float,
) -> dict[str, dict[str, Any]]:
    """Pairwise blend of two ``{deformer_id: form}`` maps at parameter
    ``t``. Forms missing from one side pass through unchanged from the
    other — so a corner that only covers some deformers still
    contributes its overrides at the appropriate weight."""
    if b is None:
        return {k: dict(v) for k, v in a.items()}
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


# ---------------------------------------------------------------------------
# Deformer composition
# ---------------------------------------------------------------------------


def apply_vertex_morphs(
    rest_vertices: np.ndarray,
    morphs: list[dict] | None,
    parameter_values: dict[str, float],
    parameters_by_id: dict[str, Parameter],
) -> np.ndarray:
    """Apply :attr:`Drawable.vertex_morphs` linearly between the
    parameter's default and its min / max extremes.

    For each morph: when the parameter sits at its default value the
    morph contributes zero; values between default and the relevant
    extreme blend linearly toward ``delta_at_min`` or ``delta_at_max``.
    Out-of-range values clamp to the corresponding extreme. Missing
    parameters (or morphs targeting unknown parameters) silently
    skip — keeps a partial document well-defined.

    Hot path for Cubism-converted rigs: a 307-drawable / 2965-morph
    March 7th model gets ~10000 calls per second through this. The
    deltas get cached as numpy arrays in private morph-dict keys so
    the first call pays the conversion cost and every subsequent
    call is a pure vector ``add`` — ~100× faster than the per-vertex
    Python loop that lived here before."""
    if not morphs:
        return rest_vertices
    out = rest_vertices.copy()
    for morph in morphs:
        param_id = morph.get("parameter")
        if not isinstance(param_id, str):
            continue
        parameter = parameters_by_id.get(param_id)
        if parameter is None:
            continue
        value = float(parameter_values.get(param_id, parameter.default))
        if value < parameter.default:
            span = parameter.default - parameter.min
            if span <= 0:
                continue
            t = max(0.0, min(1.0, (parameter.default - value) / span))
            deltas = _morph_delta_array(morph, "delta_at_min", "_np_delta_at_min")
        elif value > parameter.default:
            span = parameter.max - parameter.default
            if span <= 0:
                continue
            t = max(0.0, min(1.0, (value - parameter.default) / span))
            deltas = _morph_delta_array(morph, "delta_at_max", "_np_delta_at_max")
        else:
            continue
        if deltas is None or deltas.size == 0:
            continue
        n = min(deltas.shape[0], out.shape[0])
        # Vectorised add — replaces the per-vertex Python loop.
        out[:n] += deltas[:n] * t
    return out


def _morph_delta_array(
    morph: dict, raw_key: str, cache_key: str,
) -> np.ndarray | None:
    """Lazy-cache the numpy version of a morph's delta list on the
    morph dict itself. Keys prefixed ``_np_`` are stripped during
    serialisation so they never reach disk."""
    cached = morph.get(cache_key)
    if cached is not None:
        return cached
    raw = morph.get(raw_key)
    if not raw:
        return None
    arr = np.asarray(raw, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 2)
    morph[cache_key] = arr
    return arr


def compose_drawable_vertices(
    drawable: Drawable,
    deformers: list[Deformer],
    overrides: dict[str, dict[str, Any]],
    *,
    parameter_values: dict[str, float] | None = None,
    parameters_by_id: dict[str, Parameter] | None = None,
    sorted_deformers: list[Deformer] | None = None,
) -> np.ndarray:
    """Apply every deformer that targets ``drawable`` to its neutral
    vertices and return the deformed Nx2 array.

    ``overrides`` is the merged-parameter output from
    :func:`merge_parameter_samples`. A deformer not present in
    ``overrides`` runs with its authored neutral form (= identity in
    practice, since neutral forms produce identity transforms).

    All ``bone_rotation`` deformers targeting this drawable are
    aggregated into a single LBS pass that runs against the rest
    vertices — that's what makes opposing-bone weights cancel correctly
    instead of stacking sequentially. Other deformer types are then
    applied in FK order: a topological sort by ``Deformer.parent``
    ensures a parent rotation/warp always runs before its children,
    even when the document lists them in a different order.

    Performance note: ``sorted_deformers`` lets a batch caller pass
    in the topologically-sorted deformer list once instead of
    recomputing it per drawable. ``compose_all_drawables`` already
    does this — only direct callers need to pass it.
    """
    rest = _rest_vertices_array(drawable)
    # Cubism-style vertex morphs run *before* any deformer pipeline —
    # they replace the rest pose with the parameter-deformed pose
    # that .moc3 conversion captured, then deformers (if any) layer on
    # top.
    if drawable.vertex_morphs and parameter_values is not None and parameters_by_id is not None:
        rest = apply_vertex_morphs(rest, drawable.vertex_morphs, parameter_values, parameters_by_id)
    if sorted_deformers is None:
        sorted_deformers = topologically_sorted_deformers(deformers)
    bone_deformers: list[Deformer] = []
    other_deformers: list[Deformer] = []
    for deformer in sorted_deformers:
        if drawable.id not in deformer.drawables:
            continue
        if deformer.type == "bone_rotation":
            bone_deformers.append(deformer)
        else:
            other_deformers.append(deformer)
    if not bone_deformers and not other_deformers:
        # Fast path: morphs already produced the final vertex set,
        # no deformer chain to layer on top. Skips the redundant
        # bone-LBS branch + the float32 cast since rest is already
        # float32 from ``_rest_vertices_array``.
        return rest
    verts = _compose_bone_lbs(rest, drawable, bone_deformers, overrides)
    for deformer in other_deformers:
        form = _form_for(deformer, overrides)
        verts = _apply_deformer(deformer.type, verts, form)
    return verts.astype(np.float32, copy=False)


def _rest_vertices_array(drawable: Drawable) -> np.ndarray:
    """Lazy-cache the numpy float32 form of a drawable's rest vertices.

    ``Drawable.vertices`` is a list of ``(x, y)`` tuples — fine for
    serialisation but pricey to re-pack into a numpy array every frame.
    For a 307-drawable rig at 60 fps the conversion alone burned ~3 ms
    of every paint. Cache it as a private attribute so subsequent
    frames just return the array pointer."""
    cached = getattr(drawable, "_np_rest_vertices", None)
    if cached is not None:
        return cached
    arr = np.asarray(drawable.vertices, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 2)
    drawable._np_rest_vertices = arr   # noqa: SLF001 — private cache slot
    return arr


def topologically_sorted_deformers(
    deformers: list[Deformer],
) -> list[Deformer]:
    """Return ``deformers`` in an order where each deformer appears
    after its :attr:`Deformer.parent`.

    Cycles (a malformed document where two deformers list each other
    as parent) are broken by stopping the walk at the second visit —
    the first-seen order wins, the runtime stays defined.
    """
    by_id = {d.id: d for d in deformers}
    visited: set[str] = set()
    ordered: list[Deformer] = []

    def _visit(deformer: Deformer, in_progress: set[str]) -> None:
        if deformer.id in visited or deformer.id in in_progress:
            return
        in_progress.add(deformer.id)
        parent_id = deformer.parent
        if parent_id and parent_id in by_id:
            _visit(by_id[parent_id], in_progress)
        in_progress.discard(deformer.id)
        if deformer.id not in visited:
            visited.add(deformer.id)
            ordered.append(deformer)

    for deformer in deformers:
        _visit(deformer, set())
    return ordered


def _compose_bone_lbs(
    rest: np.ndarray,
    drawable: Drawable,
    bone_deformers: list[Deformer],
    overrides: dict[str, dict[str, Any]],
) -> np.ndarray:
    """Build the bones list + weights map from the drawable's
    bone_weights and the bone_rotation deformers, then run one LBS
    pass. Returns the rest vertices unchanged when no bones drive this
    drawable, which keeps the cost negligible for non-skinned rigs."""
    if not bone_deformers or not drawable.bone_weights:
        return rest
    bones: list[dict[str, Any]] = []
    weights_per_bone: dict[str, np.ndarray] = {}
    for deformer in bone_deformers:
        form = _form_for(deformer, overrides)
        bone_id = form.get("bone_id")
        if bone_id is None:
            continue
        weights = drawable.bone_weights.get(bone_id)
        if weights is None:
            continue
        bones.append({
            "bone_id": bone_id,
            "anchor": form.get("anchor", (0.0, 0.0)),
            "angle": float(form.get("angle", 0.0)),
        })
        weights_per_bone[bone_id] = np.asarray(weights, dtype=rest.dtype)
    if not bones:
        return rest
    return apply_skeleton_lbs(rest, bones, weights_per_bone)


def compose_all_drawables(
    document: PuppetDocument, values: dict[str, float],
) -> dict[str, np.ndarray]:
    """Convenience: run :func:`compose_drawable_vertices` for every
    drawable in ``document``, returning a ``{drawable_id: verts}`` map.
    Caller is the canvas's per-frame paint."""
    overrides = merge_parameter_samples(document, values)
    parameters_by_id = {p.id: p for p in document.parameters}
    sorted_deformers = topologically_sorted_deformers(document.deformers)
    return {
        d.id: compose_drawable_vertices(
            d, document.deformers, overrides,
            parameter_values=values, parameters_by_id=parameters_by_id,
            sorted_deformers=sorted_deformers,
        )
        for d in document.drawables
    }


def default_parameter_values(document: PuppetDocument) -> dict[str, float]:
    """Map every parameter to its default value — used by the canvas
    to seed the parameter-values dict on document load."""
    return {p.id: float(p.default) for p in document.parameters}


# ---------------------------------------------------------------------------
# Drawable opacity — parameter-driven cross-fade
# ---------------------------------------------------------------------------


def resolve_drawable_opacity(
    drawable: Drawable, values: dict[str, float],
) -> float:
    """Compute the effective alpha multiplier for ``drawable`` given the
    current parameter ``values``.

    Multiplies the static ``drawable.opacity`` with each
    ``opacity_keys`` curve sampled at its parameter value. Stops are
    interpolated linearly; values outside the stop range clamp to the
    nearest stop. A drawable without ``opacity_keys`` returns
    ``drawable.opacity`` unchanged.

    Used for cross-fading between pose variants (e.g. an arm at neutral
    swing fades out while an arm at full drop fades in)."""
    out = float(drawable.opacity)
    if not drawable.opacity_keys:
        return max(0.0, min(1.0, out))
    for entry in drawable.opacity_keys:
        param = entry.get("parameter")
        stops = entry.get("stops") or []
        if not isinstance(param, str) or not param or not stops:
            continue
        sample = float(values.get(param, 0.0))
        out *= _sample_opacity_stops(stops, sample)
        if out <= 0.0:
            return 0.0
    return max(0.0, min(1.0, out))


def resolve_drawable_color(
    drawable: Drawable, values: dict[str, float],
) -> tuple[float, float, float]:
    """Return the per-frame ``(r, g, b)`` multiply tint for ``drawable``.

    Combines the static :attr:`Drawable.multiply_color` with every
    :attr:`Drawable.multiply_color_keys` curve sampled at its parameter
    value. Multiple curves multiply channel-wise so two curves each
    tinting by ``(1, 0.5, 0.5)`` compose to ``(1, 0.25, 0.25)``.

    Mirrors :func:`resolve_drawable_opacity` so the canvas applies one
    consistent pattern for parameter-driven channel multipliers."""
    r, g, b = drawable.multiply_color
    if not drawable.multiply_color_keys:
        return (r, g, b)
    for entry in drawable.multiply_color_keys:
        param = entry.get("parameter")
        stops = entry.get("stops") or []
        if not isinstance(param, str) or not param or not stops:
            continue
        sample = float(values.get(param, 0.0))
        sr, sg, sb = _sample_color_stops(stops, sample)
        r *= sr
        g *= sg
        b *= sb
    return (max(0.0, r), max(0.0, g), max(0.0, b))


def _sample_color_stops(
    stops: list[dict], value: float,
) -> tuple[float, float, float]:
    sorted_stops = sorted(stops, key=lambda s: float(s["value"]))
    if value <= float(sorted_stops[0]["value"]):
        return tuple(float(c) for c in sorted_stops[0]["color"])
    if value >= float(sorted_stops[-1]["value"]):
        return tuple(float(c) for c in sorted_stops[-1]["color"])
    for i in range(len(sorted_stops) - 1):
        a, b = sorted_stops[i], sorted_stops[i + 1]
        av, bv = float(a["value"]), float(b["value"])
        if av <= value <= bv:
            if bv == av:
                return tuple(float(c) for c in a["color"])
            t = (value - av) / (bv - av)
            ac = [float(c) for c in a["color"]]
            bc = [float(c) for c in b["color"]]
            return tuple(ac[i] * (1.0 - t) + bc[i] * t for i in range(3))
    return tuple(float(c) for c in sorted_stops[-1]["color"])


def _sample_opacity_stops(stops: list[dict], value: float) -> float:
    sorted_stops = sorted(stops, key=lambda s: float(s["value"]))
    if value <= float(sorted_stops[0]["value"]):
        return float(sorted_stops[0]["alpha"])
    if value >= float(sorted_stops[-1]["value"]):
        return float(sorted_stops[-1]["alpha"])
    for i in range(len(sorted_stops) - 1):
        a, b = sorted_stops[i], sorted_stops[i + 1]
        av, bv = float(a["value"]), float(b["value"])
        if av <= value <= bv:
            if bv == av:
                return float(a["alpha"])
            t = (value - av) / (bv - av)
            return float(a["alpha"]) * (1.0 - t) + float(b["alpha"]) * t
    return float(sorted_stops[-1]["alpha"])


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


def resolve_part_state(
    document: PuppetDocument,
) -> dict[str, tuple[bool, float]]:
    """Walk the Part tree and return ``{drawable_id: (visible, opacity)}``.

    A drawable inherits the AND of every ancestor's ``visible`` flag
    and the product of every ancestor's ``opacity``. Drawables not
    listed under any Part get ``(True, 1.0)`` so a document without a
    Part tree behaves exactly like before.

    Each drawable's own ``visible`` and ``opacity`` are *not* combined
    here — those live on the drawable itself and the caller still
    consults them. ``resolve_part_state`` only contributes the
    hierarchy-level multiplier."""
    out: dict[str, tuple[bool, float]] = {
        d.id: (True, 1.0) for d in document.drawables
    }
    if not document.parts:
        return out
    by_id = {part.id: part for part in document.parts}
    parents = _find_root_parts(document.parts)
    for root in parents:
        _walk_part(root, by_id, parent_visible=True, parent_opacity=1.0, out=out)
    return out


def _find_root_parts(parts: list[Part]) -> list[Part]:
    """Roots are Parts not referenced as a child of any other Part —
    they sit at the top of the tree."""
    referenced: set[str] = set()
    for part in parts:
        referenced.update(part.children)
    return [p for p in parts if p.id not in referenced]


def _walk_part(
    part: Part,
    by_id: dict[str, Part],
    *,
    parent_visible: bool,
    parent_opacity: float,
    out: dict[str, tuple[bool, float]],
    visited: set[str] | None = None,
) -> None:
    """Depth-first traverse. ``visited`` guards against cycles (a
    malformed document where Part A lists Part B as a child and vice
    versa would otherwise stack-overflow)."""
    if visited is None:
        visited = set()
    if part.id in visited:
        return
    visited.add(part.id)
    effective_visible = parent_visible and bool(part.visible)
    effective_opacity = float(parent_opacity) * float(part.opacity)
    for drawable_id in part.drawables:
        if drawable_id not in out:
            continue
        prev_visible, prev_opacity = out[drawable_id]
        out[drawable_id] = (
            prev_visible and effective_visible,
            prev_opacity * effective_opacity,
        )
    for child_id in part.children:
        child = by_id.get(child_id)
        if child is None:
            continue
        _walk_part(
            child, by_id,
            parent_visible=effective_visible,
            parent_opacity=effective_opacity,
            out=out, visited=visited,
        )


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
