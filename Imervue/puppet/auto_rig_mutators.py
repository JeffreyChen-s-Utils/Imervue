"""Document mutators for the auto-rigger.

In-place edits the rule passes in :mod:`Imervue.puppet.auto_rig` share:
opacity curves, parameter creation and keying, unique ids, and drawable
group bounds.
"""
from __future__ import annotations

from Imervue.puppet.document import (
    Drawable,
    Parameter,
    ParameterKey,
    PuppetDocument,
)


def _ensure_opacity_keys(
    drawable: Drawable, parameter: str, stops: list[dict],
) -> None:
    if drawable.opacity_keys is None:
        drawable.opacity_keys = []
    # Replace an existing curve for the same parameter rather than
    # stacking duplicates — re-running the auto-rigger on the same
    # document should be idempotent.
    drawable.opacity_keys = [
        entry for entry in drawable.opacity_keys
        if entry.get("parameter") != parameter
    ]
    drawable.opacity_keys.append({
        "parameter": parameter,
        "stops": [dict(s) for s in stops],
    })


def _ensure_parameter(document: PuppetDocument, param_id: str) -> None:
    if document.parameter(param_id) is not None:
        return
    # Fall back to the Cubism-standard range for these well-known ids.
    document.parameters.append(
        Parameter(id=param_id, min=-1.0, max=1.0, default=0.0),
    )


def _set_param_keys(
    document: PuppetDocument,
    param_id: str,
    values_to_forms: dict[float, dict[str, dict]],
) -> None:
    parameter = document.parameter(param_id)
    if parameter is None:
        return
    for value, forms in values_to_forms.items():
        replaced = False
        for key in parameter.keys:
            if abs(key.value - value) < 1e-6:
                key.forms.update({k: dict(v) for k, v in forms.items()})
                replaced = True
                break
        if not replaced:
            parameter.keys.append(
                ParameterKey(
                    value=float(value),
                    forms={k: dict(v) for k, v in forms.items()},
                ),
            )
    parameter.keys.sort(key=lambda k: k.value)


def _unique_id(existing: set[str], prefix: str) -> str:
    """``prefix`` itself when free, else the first free ``prefix_N`` (N ≥ 2)."""
    if prefix not in existing:
        return prefix
    i = 2
    while f"{prefix}_{i}" in existing:
        i += 1
    return f"{prefix}_{i}"


def _unique_deformer_id(document: PuppetDocument, prefix: str) -> str:
    return _unique_id({d.id for d in document.deformers}, prefix)


def _unique_physics_id(document: PuppetDocument, prefix: str) -> str:
    return _unique_id({r.id for r in document.physics_rigs}, prefix)


def _drawable_group_centre(
    document: PuppetDocument, ids: list[str],
) -> tuple[float, float]:
    bounds = _drawable_group_bounds(document, ids)
    if bounds is None:
        return (document.size[0] / 2.0, document.size[1] / 2.0)
    x0, y0, x1, y1 = bounds
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _drawable_group_bounds(
    document: PuppetDocument, ids: list[str],
) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for drawable_id in ids:
        drawable = document.drawable(drawable_id)
        if drawable is None or not drawable.vertices:
            continue
        for x, y in drawable.vertices:
            xs.append(float(x))
            ys.append(float(y))
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))
