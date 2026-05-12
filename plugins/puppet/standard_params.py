"""Cubism-style standard parameter catalogue.

Live2D rigs converge on a known set of parameter ids — head angles,
eye openness, brow angle, mouth shape, breath. Seeding every fresh
puppet with these saves the user from authoring 30 sliders by hand
and lets the live drivers (webcam, drag, blink, lip-sync) find
parameters by id without per-rig configuration.

Ranges follow this project's internal convention, not Cubism's:

* angle-like params (head, body, brow, eye-ball) → ``[-1, 1]``
  so the heuristic drivers in :mod:`input_drivers` and
  :mod:`face_landmark_mapper` (which produce normalised values) can
  drop their outputs in directly.
* openness-like params (eye open / smile, mouth open, cheek, breath)
  → ``[0, 1]`` with a sensible default (eyes default open at ``1.0``).

Per-axis defaults match Cubism: eyes default open, mouth closed,
angles centered, breath at the curve's midpoint. Callers can append
project-specific parameters after this baseline without conflict.
"""
from __future__ import annotations

from puppet.document import Parameter

# Public id constants so other modules (drivers, tests) refer to one
# source instead of bare string literals.
PARAM_ANGLE_X: str = "ParamAngleX"
PARAM_ANGLE_Y: str = "ParamAngleY"
PARAM_ANGLE_Z: str = "ParamAngleZ"
PARAM_BODY_ANGLE_X: str = "ParamBodyAngleX"
PARAM_BODY_ANGLE_Y: str = "ParamBodyAngleY"
PARAM_BODY_ANGLE_Z: str = "ParamBodyAngleZ"
PARAM_EYE_L_OPEN: str = "ParamEyeLOpen"
PARAM_EYE_R_OPEN: str = "ParamEyeROpen"
PARAM_EYE_L_SMILE: str = "ParamEyeLSmile"
PARAM_EYE_R_SMILE: str = "ParamEyeRSmile"
PARAM_EYE_BALL_X: str = "ParamEyeBallX"
PARAM_EYE_BALL_Y: str = "ParamEyeBallY"
PARAM_BROW_L_Y: str = "ParamBrowLY"
PARAM_BROW_R_Y: str = "ParamBrowRY"
PARAM_BROW_L_X: str = "ParamBrowLX"
PARAM_BROW_R_X: str = "ParamBrowRX"
PARAM_BROW_L_FORM: str = "ParamBrowLForm"
PARAM_BROW_R_FORM: str = "ParamBrowRForm"
PARAM_BROW_L_ANGLE: str = "ParamBrowLAngle"
PARAM_BROW_R_ANGLE: str = "ParamBrowRAngle"
PARAM_MOUTH_OPEN_Y: str = "ParamMouthOpenY"
PARAM_MOUTH_FORM: str = "ParamMouthForm"
PARAM_CHEEK: str = "ParamCheek"
PARAM_HAIR_FRONT: str = "ParamHairFront"
PARAM_HAIR_SIDE: str = "ParamHairSide"
PARAM_HAIR_BACK: str = "ParamHairBack"
PARAM_BREATH: str = "ParamBreath"


# ``(id, min, max, default)`` rows — one source of truth that both the
# factory and tests can inspect. Keeping the spec as data (not as a
# wall of ``Parameter(...)`` constructors) keeps the module under the
# 75-line function limit.
_SPEC: tuple[tuple[str, float, float, float], ...] = (
    # Head angles
    (PARAM_ANGLE_X, -1.0, 1.0, 0.0),
    (PARAM_ANGLE_Y, -1.0, 1.0, 0.0),
    (PARAM_ANGLE_Z, -1.0, 1.0, 0.0),
    # Body angles
    (PARAM_BODY_ANGLE_X, -1.0, 1.0, 0.0),
    (PARAM_BODY_ANGLE_Y, -1.0, 1.0, 0.0),
    (PARAM_BODY_ANGLE_Z, -1.0, 1.0, 0.0),
    # Eye open / smile
    (PARAM_EYE_L_OPEN, 0.0, 1.0, 1.0),
    (PARAM_EYE_R_OPEN, 0.0, 1.0, 1.0),
    (PARAM_EYE_L_SMILE, 0.0, 1.0, 0.0),
    (PARAM_EYE_R_SMILE, 0.0, 1.0, 0.0),
    # Eye ball direction
    (PARAM_EYE_BALL_X, -1.0, 1.0, 0.0),
    (PARAM_EYE_BALL_Y, -1.0, 1.0, 0.0),
    # Brows
    (PARAM_BROW_L_Y, -1.0, 1.0, 0.0),
    (PARAM_BROW_R_Y, -1.0, 1.0, 0.0),
    (PARAM_BROW_L_X, -1.0, 1.0, 0.0),
    (PARAM_BROW_R_X, -1.0, 1.0, 0.0),
    (PARAM_BROW_L_FORM, -1.0, 1.0, 0.0),
    (PARAM_BROW_R_FORM, -1.0, 1.0, 0.0),
    (PARAM_BROW_L_ANGLE, -1.0, 1.0, 0.0),
    (PARAM_BROW_R_ANGLE, -1.0, 1.0, 0.0),
    # Mouth
    (PARAM_MOUTH_OPEN_Y, 0.0, 1.0, 0.0),
    (PARAM_MOUTH_FORM, -1.0, 1.0, 0.0),
    # Cheek
    (PARAM_CHEEK, 0.0, 1.0, 0.0),
    # Hair physics outputs
    (PARAM_HAIR_FRONT, -1.0, 1.0, 0.0),
    (PARAM_HAIR_SIDE, -1.0, 1.0, 0.0),
    (PARAM_HAIR_BACK, -1.0, 1.0, 0.0),
    # Breathing
    (PARAM_BREATH, 0.0, 1.0, 0.5),
)


def standard_parameter_ids() -> tuple[str, ...]:
    """Return the ordered tuple of standard parameter ids. Used by tests
    and by introspection tools that want to know whether a rig follows
    the convention."""
    return tuple(row[0] for row in _SPEC)


def standard_parameters() -> list[Parameter]:
    """Build a fresh list of the standard Cubism-style parameters with
    project-internal ranges. Each call returns independent
    :class:`Parameter` instances so callers can mutate them without
    leaking state across documents."""
    return [
        Parameter(id=row[0], min=row[1], max=row[2], default=row[3], keys=[])
        for row in _SPEC
    ]
