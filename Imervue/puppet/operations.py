"""Pure-Python edit operations on a :class:`PuppetDocument`.

Each function mutates the document in-place and returns ``True`` on
success. Qt-free so tests can run them without a ``qapp``; the
workspace's toolbar actions wrap these with file-dialog UI.

Phase 5 covers the smallest set of operations needed for the user to
build a rig from scratch:

* :func:`add_rotation_deformer` / :func:`add_warp_deformer`
* :func:`add_parameter`
* :func:`set_key_at_value` / :func:`remove_key`

Future phases extend this module with motion / expression / physics
operations rather than scattering edit logic across UI code.
"""
from __future__ import annotations

from typing import Any

from Imervue.puppet.deformers import (
    default_rotation_form,
    default_warp_form,
)
from Imervue.puppet.document import (
    Deformer,
    Parameter,
    ParameterKey,
    PuppetDocument,
)


# ---------------------------------------------------------------------------
# Deformers
# ---------------------------------------------------------------------------


def add_rotation_deformer(
    document: PuppetDocument,
    deformer_id: str,
    drawables: list[str] | None = None,
    *,
    anchor: tuple[float, float] | None = None,
    parent: str | None = None,
) -> bool:
    """Append a new rotation deformer to ``document``.

    ``drawables`` defaults to *every* drawable currently in the
    document — most users want a rotation to control the whole puppet
    when they create their first deformer. ``anchor`` defaults to the
    centre of the canvas.
    """
    if document.deformer(deformer_id) is not None:
        return False
    if anchor is None:
        anchor = (document.size[0] / 2, document.size[1] / 2)
    if drawables is None:
        drawables = [d.id for d in document.drawables]
    document.deformers.append(
        Deformer(
            id=deformer_id,
            type="rotation",
            parent=parent,
            drawables=list(drawables),
            form=default_rotation_form(anchor),
        ),
    )
    return True


def add_warp_deformer(
    document: PuppetDocument,
    deformer_id: str,
    drawables: list[str] | None = None,
    *,
    bounds: tuple[float, float, float, float] | None = None,
    rows: int = 5,
    cols: int = 5,
    parent: str | None = None,
) -> bool:
    """Append a new warp deformer. ``bounds`` defaults to the whole
    canvas; ``drawables`` defaults to every drawable in the document."""
    if document.deformer(deformer_id) is not None:
        return False
    if bounds is None:
        bounds = (0.0, 0.0, float(document.size[0]), float(document.size[1]))
    if drawables is None:
        drawables = [d.id for d in document.drawables]
    document.deformers.append(
        Deformer(
            id=deformer_id,
            type="warp",
            parent=parent,
            drawables=list(drawables),
            form=default_warp_form(bounds, rows=rows, cols=cols),
        ),
    )
    return True


def remove_deformer(document: PuppetDocument, deformer_id: str) -> bool:
    """Drop the deformer and any parameter keys that referenced it."""
    target = document.deformer(deformer_id)
    if target is None:
        return False
    document.deformers.remove(target)
    for param in document.parameters:
        for key in param.keys:
            key.forms.pop(deformer_id, None)
    return True


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


def add_parameter(
    document: PuppetDocument,
    param_id: str,
    *,
    min_value: float = -1.0,
    max_value: float = 1.0,
    default: float = 0.0,
) -> bool:
    """Append a new parameter to ``document``. ``min_value`` /
    ``max_value`` / ``default`` set the slider range; default values
    cover the most common Cubism-style ``ParamAngleX`` -1..1 case."""
    if document.parameter(param_id) is not None:
        return False
    if min_value > max_value:
        raise ValueError(
            f"min_value ({min_value}) must be <= max_value ({max_value})",
        )
    if not (min_value <= default <= max_value):
        raise ValueError(
            f"default ({default}) must lie within [{min_value}, {max_value}]",
        )
    document.parameters.append(
        Parameter(
            id=param_id,
            min=float(min_value),
            max=float(max_value),
            default=float(default),
            keys=[],
        ),
    )
    return True


def remove_parameter(document: PuppetDocument, param_id: str) -> bool:
    target = document.parameter(param_id)
    if target is None:
        return False
    document.parameters.remove(target)
    return True


# ---------------------------------------------------------------------------
# Parameter keys
# ---------------------------------------------------------------------------


def set_key_at_value(
    document: PuppetDocument,
    param_id: str,
    value: float,
    forms: dict[str, dict[str, Any]],
) -> bool:
    """Add or replace a key on ``param_id`` at ``value``.

    ``forms`` is a ``{deformer_id: form_snapshot}`` map — typically
    captured by the editor at the moment the user pressed "Set key"
    (so the snapshot includes whatever overrides the runtime is
    currently rendering).

    Tolerance for "is this an existing key": values within 1e-6 are
    considered the same key, so dragging the slider then tapping Set
    Key twice updates rather than appending a duplicate.
    """
    parameter = document.parameter(param_id)
    if parameter is None:
        return False
    if not (parameter.min <= value <= parameter.max):
        raise ValueError(
            f"value ({value}) outside parameter range "
            f"[{parameter.min}, {parameter.max}]",
        )
    captured = {k: dict(v) for k, v in forms.items()}
    for existing in parameter.keys:
        if abs(existing.value - value) < 1e-6:
            existing.forms = captured
            return True
    parameter.keys.append(ParameterKey(value=float(value), forms=captured))
    parameter.keys.sort(key=lambda k: k.value)
    return True


def remove_key(
    document: PuppetDocument,
    param_id: str,
    value: float,
) -> bool:
    parameter = document.parameter(param_id)
    if parameter is None:
        return False
    target = None
    for k in parameter.keys:
        if abs(k.value - value) < 1e-6:
            target = k
            break
    if target is None:
        return False
    parameter.keys.remove(target)
    return True


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def snapshot_current_forms(document: PuppetDocument) -> dict[str, dict[str, Any]]:
    """Return a ``{deformer_id: form_copy}`` map of every deformer's
    current authored form. The editor calls this at the moment the
    user presses "Set key" so the captured snapshot includes whatever
    deformer-edits the user made before keying."""
    return {d.id: dict(d.form) for d in document.deformers}
