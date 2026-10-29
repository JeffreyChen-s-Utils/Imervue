"""Sample-and-reconstruct sweeps for the native Cubism conversion.

Drives each parameter of a loaded ``.moc3`` to its min and max, turns
the deformed vertex positions into per-drawable ``vertex_morphs`` and
the ``IsVisible`` flips into ``opacity_keys`` curves, then restores the
rest pose. Split out of :mod:`puppet.cubism_native_convert`, which
re-exports every name.
"""
from __future__ import annotations

from Imervue.puppet.cubism_native_bridge import (
    CubismModel,
    DrawableInfo,
    ParameterInfo,
)
from Imervue.puppet.cubism_native_mesh import _CanvasTransform
from Imervue.puppet.document import Drawable, PuppetDocument


def _build_morph_entry(
    rest: list[float],
    deformed_min: list[float],
    deformed_max: list[float],
    morph_epsilon: float,
    transform: _CanvasTransform,
    parameter_id: str,
) -> dict | None:
    """Subtract rest from the two deformed vertex arrays and return a
    serialisable morph entry — unless both deltas are below the
    threshold (then the morph is noise, drop it)."""
    if len(rest) != len(deformed_min) or len(rest) != len(deformed_max):
        return None
    morph_min = _vertex_deltas(rest, deformed_min, transform)
    morph_max = _vertex_deltas(rest, deformed_max, transform)
    if _max_abs(morph_min) < morph_epsilon and _max_abs(morph_max) < morph_epsilon:
        return None
    return {
        "parameter": parameter_id,
        "delta_at_min": morph_min,
        "delta_at_max": morph_max,
    }


def _attach_morphs(
    document: PuppetDocument,
    model: CubismModel,
    parameters: list[ParameterInfo],
    drawables_rest: list[DrawableInfo],
    *,
    morph_epsilon: float,
    transform: _CanvasTransform,
) -> None:
    """Sweep each parameter to its min + max and record the deformed
    vertex positions; subtract rest to get per-vertex deltas (in
    pixel space, via the canvas transform) and attach the
    non-negligible ones as morphs on each drawable."""
    default_values = [p.default for p in parameters]
    rest_positions: list[list[float]] = [list(d.positions) for d in drawables_rest]
    for param_index, parameter in enumerate(parameters):
        if parameter.minimum == parameter.maximum:
            continue
        delta_min = _sample_at(model, default_values, param_index, parameter.minimum)
        delta_max = _sample_at(model, default_values, param_index, parameter.maximum)
        for d_index, rest in enumerate(rest_positions):
            entry = _build_morph_entry(
                rest, delta_min[d_index], delta_max[d_index],
                morph_epsilon, transform, parameter.id,
            )
            if entry is None:
                continue
            drawable = document.drawables[d_index]
            if drawable.vertex_morphs is None:
                drawable.vertex_morphs = []
            drawable.vertex_morphs.append(entry)
    # Restore defaults so subsequent canvas info / drawable reads from
    # this same model still reflect the rest pose.
    model.set_parameter_values(default_values)
    model.update()


def _sample_at(
    model: CubismModel,
    base_values: list[float],
    param_index: int,
    value: float,
) -> list[list[float]]:
    """Set parameter ``param_index`` to ``value`` (keeping everything
    else at default), update the model, and return each drawable's
    flat XY vertex array."""
    values = list(base_values)
    values[param_index] = float(value)
    model.set_parameter_values(values)
    model.update()
    return model.vertex_positions()


def _sample_visibility_at(
    model: CubismModel,
    base_values: list[float],
    param_index: int,
    value: float,
) -> list[bool]:
    """Set one parameter to ``value`` and read the per-drawable
    ``IsVisible`` bit. Used by :func:`_attach_visibility_keys` to
    capture parameter-driven part-tree exclusion that vertex
    sampling alone can't see."""
    values = list(base_values)
    values[param_index] = float(value)
    model.set_parameter_values(values)
    model.update()
    return model.visibility_flags()


def _emit_opacity_curve(
    drawable: Drawable,
    parameter: ParameterInfo,
    vd: bool, vmin: bool, vmax: bool,
) -> None:
    """Append a three-stop ``opacity_keys`` entry to ``drawable`` and
    force it visible + opaque so the curve has authority over the
    renderer. Caller is responsible for deciding when this transition
    is worth recording — this helper trusts that decision."""
    stops = [
        {"value": parameter.minimum, "alpha": 1.0 if vmin else 0.0},
        {"value": parameter.default, "alpha": 1.0 if vd else 0.0},
        {"value": parameter.maximum, "alpha": 1.0 if vmax else 0.0},
    ]
    if drawable.opacity_keys is None:
        drawable.opacity_keys = []
    drawable.opacity_keys.append({
        "parameter": parameter.id,
        "stops": stops,
    })
    # The curve must be the gate, not the authored base. A drawable
    # hidden at rest gets opacity=0.0 from the converter;
    # resolve_drawable_opacity multiplies that by the curve, so
    # 0 * 1 = 0 and the curve does nothing. Force visible + opaque so
    # the curve has the only say.
    drawable.visible = True
    drawable.opacity = 1.0


def _attach_visibility_keys(
    document: PuppetDocument,
    model: CubismModel,
    parameters: list[ParameterInfo],
    drawables_rest: list[DrawableInfo],
) -> None:
    """Sweep each parameter and detect per-drawable visibility flips.

    Cubism rigs toggle alternate-pose meshes (hand gestures, camera
    objects, expression overlays) via dynamic ``IsVisible`` flags
    that the deformation pipeline never touches — so the
    sample-and-reconstruct vertex sweep alone reduces those meshes
    to invisible-and-stationary. Catch the transition by reading
    :meth:`CubismModel.visibility_flags` at each parameter's min,
    default, and max; when a drawable's visibility differs across
    those points, emit a three-stop ``opacity_keys`` curve so the
    runtime fades the mesh in/out as the parameter moves.
    """
    default_values = [p.default for p in parameters]
    default_vis = [d.is_visible for d in drawables_rest]
    for param_index, parameter in enumerate(parameters):
        if parameter.minimum == parameter.maximum:
            continue
        vis_min = _sample_visibility_at(
            model, default_values, param_index, parameter.minimum,
        )
        vis_max = _sample_visibility_at(
            model, default_values, param_index, parameter.maximum,
        )
        for d_index, drawable in enumerate(document.drawables):
            vd, vmin, vmax = default_vis[d_index], vis_min[d_index], vis_max[d_index]
            if vd == vmin == vmax:
                continue
            _emit_opacity_curve(drawable, parameter, vd, vmin, vmax)
    # Restore the rest pose before any downstream caller reads the
    # model — _attach_morphs already does this for its own sweep, but
    # we may be the last sweep so be defensive.
    model.set_parameter_values(default_values)
    model.update()


def _vertex_deltas(
    rest_flat: list[float],
    deformed_flat: list[float],
    transform: _CanvasTransform,
) -> list[tuple[float, float]]:
    """Convert two flat XY arrays (in Cubism normalized units) into a
    list of pixel-space ``(dx, dy)`` deltas."""
    out: list[tuple[float, float]] = []
    for i in range(0, len(rest_flat), 2):
        out.append(transform.delta(
            deformed_flat[i] - rest_flat[i],
            deformed_flat[i + 1] - rest_flat[i + 1],
        ))
    return out


def _max_abs(deltas: list[tuple[float, float]]) -> float:
    best = 0.0
    for dx, dy in deltas:
        absdx = abs(dx)
        absdy = abs(dy)
        best = max(best, absdx)
        best = max(best, absdy)
    return best
