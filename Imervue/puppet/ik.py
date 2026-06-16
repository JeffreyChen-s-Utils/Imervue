"""Analytic two-bone inverse kinematics for puppet rigs.

Forward LBS (:mod:`Imervue.puppet.deformers`) rotates each bone by a given
angle; this solves the opposite problem — given a two-segment chain and a target
point, return the two absolute bone angles that put the chain tip on the target
(or as close as the chain can reach). Pure 2-D math, Qt/GL-free, so the editor's
drag-to-pose handle and the unit tests share one implementation.
"""
from __future__ import annotations

import math

_EPSILON = 1e-9


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def solve_two_bone_ik(
    root: tuple[float, float],
    length1: float,
    length2: float,
    target: tuple[float, float],
    *,
    flip: bool = False,
) -> tuple[float, float]:
    """Return ``(angle1, angle2)`` in radians for a two-bone chain reaching *target*.

    ``angle1`` / ``angle2`` are the *absolute* orientations of the first and
    second segment (measured from +x, y-down screen space), suitable for the
    rotation deformer. A target outside the chain's reach is clamped to the
    nearest reachable distance, so the solver never returns NaN. ``flip`` picks
    the opposite elbow solution (both are valid).
    """
    rx, ry = root
    dx, dy = target[0] - rx, target[1] - ry
    distance = math.hypot(dx, dy)
    reach_min = abs(length1 - length2)
    reach_max = length1 + length2
    clamped = _clamp(distance, reach_min, reach_max)
    base = math.atan2(dy, dx) if distance > _EPSILON else 0.0

    if length1 <= _EPSILON or clamped <= _EPSILON:
        offset = 0.0
    else:
        cos_offset = (clamped * clamped + length1 * length1 - length2 * length2) / (
            2.0 * length1 * clamped)
        offset = math.acos(_clamp(cos_offset, -1.0, 1.0))

    angle1 = base + offset if flip else base - offset
    joint_x = rx + length1 * math.cos(angle1)
    joint_y = ry + length1 * math.sin(angle1)
    # Point the second segment from the elbow toward the (original) target; for
    # an out-of-reach target this lands the tip at the clamped extreme.
    angle2 = math.atan2(target[1] - joint_y, target[0] - joint_x)
    return angle1, angle2


def forward_two_bone(
    root: tuple[float, float],
    length1: float,
    length2: float,
    angle1: float,
    angle2: float,
) -> tuple[float, float]:
    """Tip position of a two-bone chain at the given absolute angles.

    The inverse of :func:`solve_two_bone_ik` for reachable targets; exposed so
    callers (and tests) can verify a pose without re-deriving the kinematics.
    """
    joint_x = root[0] + length1 * math.cos(angle1)
    joint_y = root[1] + length1 * math.sin(angle1)
    return joint_x + length2 * math.cos(angle2), joint_y + length2 * math.sin(angle2)


def two_bone_ik_angles(
    bone1_id: str,
    bone2_id: str,
    root: tuple[float, float],
    length1: float,
    length2: float,
    target: tuple[float, float],
    *,
    flip: bool = False,
) -> dict[str, float]:
    """Solve the chain and return ``{bone_id: angle}`` ready for the deformer."""
    angle1, angle2 = solve_two_bone_ik(root, length1, length2, target, flip=flip)
    return {bone1_id: angle1, bone2_id: angle2}
