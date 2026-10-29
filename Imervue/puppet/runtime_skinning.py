"""Resolve authored bone forms and apply weighted skeleton deformation."""
from __future__ import annotations

from typing import Any

import numpy as np

from Imervue.puppet.deformers import apply_skeleton_lbs
from Imervue.puppet.document import Deformer, Drawable


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
