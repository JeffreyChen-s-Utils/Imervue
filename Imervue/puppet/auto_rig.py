"""Auto-rig pass: derive a working Cubism-style rig from layer naming
conventions on a freshly-imported :class:`PuppetDocument`.

The PSD → puppet importer gives the user drawables but no behaviour —
they still have to author deformers and keyforms before anything
moves. This module closes that gap by scanning drawable ids for the
naming patterns Cubism artists already use, then bolting on:

* **Eye blink** — when a layer pair ``*_l_open`` / ``*_l_close`` (and
  the right-side equivalent) exists, add ``opacity_keys`` driven by
  ``ParamEyeLOpen`` / ``ParamEyeROpen`` so the standard blink driver
  cross-fades the two layers automatically.

* **Mouth viseme** — when mouth variants exist (``mouth_open`` /
  ``mouth_close`` and optional ``mouth_a / _i / _u / _e / _o``), add
  ``opacity_keys`` driven by ``ParamMouthOpenY`` and ``ParamMouthForm``
  so lip-sync produces visible mouth shapes.

* **Head tilt** — when any drawable matches a "head" pattern, add a
  rotation deformer around the head's centre keyed on
  ``ParamAngleZ`` (Live2D's head-roll axis).

* **Hair swing** — when "hair" or "bang" layers exist, add a warp
  deformer keyed on ``ParamHairFront`` (its lower rows shift sideways,
  the top row stays put) + a physics rig from ``ParamAngleX`` to
  ``ParamHairFront`` so they swing as the head moves.

All rule predicates are pure-Python (:mod:`Imervue.puppet.auto_rig_detect`,
re-exported here) so tests can exercise the detection without going
through a PSD; the shared document edits live in
:mod:`Imervue.puppet.auto_rig_mutators`.
"""
from __future__ import annotations

import math

from Imervue.puppet.auto_rig_detect import (
    detect_eye,
    detect_hair,
    detect_head,
    detect_mouth_variant,
)
from Imervue.puppet.auto_rig_mutators import (
    _drawable_group_bounds,
    _drawable_group_centre,
    _ensure_opacity_keys,
    _ensure_parameter,
    _set_param_keys,
    _unique_deformer_id,
    _unique_physics_id,
)
from Imervue.puppet.deformers import (
    default_rotation_form,
    default_warp_form,
)
from Imervue.puppet.document import (
    Deformer,
    PhysicsParticle,
    PhysicsRig,
    PuppetDocument,
)
from Imervue.puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Z,
    PARAM_EYE_L_OPEN,
    PARAM_EYE_R_OPEN,
    PARAM_HAIR_FRONT,
    PARAM_MOUTH_FORM,
    PARAM_MOUTH_OPEN_Y,
)

__all__ = [
    "auto_rig",
    "detect_eye",
    "detect_hair",
    "detect_head",
    "detect_mouth_variant",
]

_HEAD_TILT_RAD: float = math.radians(15.0)
"""Maximum head-roll angle the auto-rigger keys at ``ParamAngleZ=±1``."""

_HAIR_SWAY_FRACTION: float = 0.08
"""How far the hair warp's bottom row shifts at ``ParamHairFront=±1``,
as a fraction of the hair's width; rows above it shift proportionally
less and the top row not at all."""

_HAIR_PHYSICS_PARTICLES: int = 4
"""Default chain length for an auto-rigged hair swing. Long enough to
read as motion, short enough that the Verlet integrator stays
trivially stable at 60 FPS."""


def auto_rig(document: PuppetDocument) -> dict[str, int]:
    """Run every detection pass against ``document`` in-place. Returns
    a ``{rule: count}`` dict so callers (and tests) can introspect what
    fired."""
    counts: dict[str, int] = {
        "eyes": _rig_eyes(document),
        "mouth": _rig_mouth(document),
        "head_tilt": _rig_head_tilt(document),
        "hair_swing": _rig_hair_swing(document),
    }
    return counts


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------


def _rig_eyes(document: PuppetDocument) -> int:
    """Pair up ``*_open`` / ``*_close`` eye layers and key their
    opacity off ``ParamEyeLOpen`` / ``ParamEyeROpen``. Returns the
    number of layers patched."""
    patched = 0
    for drawable in document.drawables:
        hit = detect_eye(drawable.id)
        if hit is None:
            continue
        side, state = hit
        param = PARAM_EYE_L_OPEN if side == "l" else PARAM_EYE_R_OPEN
        if state == "open":
            stops = [
                {"value": 0.0, "alpha": 0.0},
                {"value": 1.0, "alpha": 1.0},
            ]
        else:
            stops = [
                {"value": 0.0, "alpha": 1.0},
                {"value": 1.0, "alpha": 0.0},
            ]
        _ensure_opacity_keys(drawable, param, stops)
        patched += 1
    return patched


def _rig_mouth(document: PuppetDocument) -> int:
    """Key mouth variants against ``ParamMouthOpenY`` (open/close) and
    ``ParamMouthForm`` (vowel shape) for cross-faded viseme lip-sync."""
    patched = 0
    for drawable in document.drawables:
        variant = detect_mouth_variant(drawable.id)
        if variant is None:
            continue
        _ensure_opacity_keys(drawable, PARAM_MOUTH_OPEN_Y, _mouth_open_curve(variant))
        form_curve = _mouth_form_curve(variant)
        if form_curve is not None:
            _ensure_opacity_keys(drawable, PARAM_MOUTH_FORM, form_curve)
        patched += 1
    return patched


def _mouth_open_curve(variant: str) -> list[dict]:
    """``ParamMouthOpenY=0`` is mouth shut, ``=1`` is fully open."""
    if variant == "close":
        return [
            {"value": 0.0, "alpha": 1.0},
            {"value": 1.0, "alpha": 0.0},
        ]
    return [
        {"value": 0.0, "alpha": 0.0},
        {"value": 1.0, "alpha": 1.0},
    ]


def _mouth_form_curve(variant: str) -> list[dict] | None:
    """``ParamMouthForm`` runs ``[-1, 1]``; ``-1`` is round (oh / oo),
    ``+1`` is wide (ee / ay). Vowel mouths get a triangular curve
    peaking at the matching form value so a single AIUEO blend
    yields the right shape."""
    peak_by_vowel = {
        "a": 0.5,
        "i": 1.0,
        "u": -1.0,
        "e": 0.3,
        "o": -0.5,
    }
    peak = peak_by_vowel.get(variant)
    if peak is None:
        return None
    return [
        {"value": -1.0, "alpha": 0.0 if peak >= 0 else 1.0 - abs(peak + 1.0)},
        {"value": peak, "alpha": 1.0},
        {"value": 1.0, "alpha": 1.0 - abs(peak - 1.0) if peak >= 0 else 0.0},
    ]


def _rig_head_tilt(document: PuppetDocument) -> int:
    """Add a single rotation deformer keyed on ``ParamAngleZ`` covering
    every detected head/face drawable. Skips when there's nothing
    head-like (no point in keying empty deformers)."""
    head_ids = [d.id for d in document.drawables if detect_head(d.id)]
    if not head_ids:
        return 0
    deformer_id = _unique_deformer_id(document, "head_tilt")
    anchor = _drawable_group_centre(document, head_ids)
    rotation = Deformer(
        id=deformer_id,
        type="rotation",
        parent=None,
        drawables=list(head_ids),
        form=default_rotation_form(anchor),
    )
    document.deformers.append(rotation)
    _ensure_parameter(document, PARAM_ANGLE_Z)
    _set_param_keys(
        document, PARAM_ANGLE_Z,
        {
            -1.0: {deformer_id: {"angle": -_HEAD_TILT_RAD}},
            0.0: {deformer_id: {"angle": 0.0}},
            1.0: {deformer_id: {"angle": _HEAD_TILT_RAD}},
        },
    )
    return len(head_ids)


def _rig_hair_swing(document: PuppetDocument) -> int:
    """Bundle hair / bang / fringe drawables under a single warp
    deformer and bolt a 4-particle physics chain onto it so head
    motion makes the hair swing."""
    hair_ids = [d.id for d in document.drawables if detect_hair(d.id)]
    if not hair_ids:
        return 0
    bounds = _drawable_group_bounds(document, hair_ids)
    if bounds is None:
        return 0
    deformer_id = _unique_deformer_id(document, "hair_swing")
    warp = Deformer(
        id=deformer_id,
        type="warp",
        parent=None,
        drawables=list(hair_ids),
        form=default_warp_form(bounds, rows=4, cols=4),
    )
    document.deformers.append(warp)
    _ensure_parameter(document, PARAM_ANGLE_X)
    _ensure_parameter(document, PARAM_HAIR_FRONT)
    sway = (bounds[2] - bounds[0]) * _HAIR_SWAY_FRACTION
    _set_param_keys(
        document, PARAM_HAIR_FRONT,
        {
            value: {deformer_id: {"grid": _swayed_grid(warp.form, value * sway)}}
            for value in (-1.0, 0.0, 1.0)
        },
    )
    rig_id = _unique_physics_id(document, "hair_chain")
    document.physics_rigs.append(
        PhysicsRig(
            id=rig_id,
            input_param=PARAM_ANGLE_X,
            output_param=PARAM_HAIR_FRONT,
            chain=[PhysicsParticle() for _ in range(_HAIR_PHYSICS_PARTICLES)],
        ),
    )
    return len(hair_ids)


def _swayed_grid(form: dict, shift: float) -> list[list[list[float]]]:
    """A copy of a warp's grid with each row moved ``shift`` × its depth sideways.

    Depth runs from 0 at the top row (where hair is attached) to 1 at the
    bottom row, so the tips swing furthest.
    """
    last_row = max(1, int(form["rows"]) - 1)
    return [
        [[float(x) + shift * r / last_row, float(y)] for x, y in row]
        for r, row in enumerate(form["grid"])
    ]
