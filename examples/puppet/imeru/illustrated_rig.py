"""Continuous illustration deformation and two-joint sleeve skinning."""

from __future__ import annotations

import math

import numpy as np

from illustrated_mesh import SIZE, morph, opacity
from Imervue.puppet.document import Deformer, Parameter, ParameterKey

ARMS = {
    "r": ((402.0, 275.0), (325.0, 500.0), (255.0, 653.0), 1.0),
    "l": ((625.0, 275.0), (702.0, 514.0), (774.0, 657.0), -1.0),
}

RIBBON_CONTOUR = (
    (785, 370), (799, 420), (812, 440), (826, 460), (838, 480), (849, 500),
    (858, 520), (865, 540), (870, 560), (872, 580), (875, 603), (907, 624),
    (943, 644), (965, 664), (999, 685), (999, 655), (992, 635), (987, 615),
    (979, 595), (970, 575), (958, 555), (944, 535), (929, 515), (911, 495),
    (893, 475), (875, 455), (858, 435), (839, 415), (825, 390), (817, 365),
)


def _ribbon_vertices(drawable):
    """Include boundary grid vertices so the opaque ribbon edge stays rigid."""
    x, y = (np.asarray(drawable.uvs) * SIZE).T
    inside = np.zeros(len(x), dtype=bool)
    boundary = np.zeros(len(x), dtype=bool)
    for start, end in zip(RIBBON_CONTOUR, (*RIBBON_CONTOUR[1:], RIBBON_CONTOUR[0]), strict=True):
        x0, y0 = start
        x1, y1 = end
        dx, dy = x1 - x0, y1 - y0
        along = np.clip(((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy), 0, 1)
        boundary |= (x - x0 - along * dx) ** 2 + (y - y0 - along * dy) ** 2 <= 10 ** 2
        if y0 != y1:
            inside ^= ((y0 > y) != (y1 > y)) & (x < x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    return inside | boundary


def ramp(x, low, high):
    t = np.clip((x - low) / (high - low), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _field(drawable, parameter, dx, dy):
    delta = np.column_stack((dx, dy))
    morph(drawable, parameter, -delta, delta)


def common_motion(drawable, *, body=False):
    v = np.asarray(drawable.vertices)
    x, y = v.T
    head = 1 - ramp(y, 210, 290)
    front = np.exp(-(((x - 516) / 110) ** 2))
    _field(drawable, "ParamAngleX", 8 * head * (0.45 + 0.55 * front), np.zeros(len(v)))
    _field(drawable, "ParamAngleY", np.zeros(len(v)), 5 * head * front)
    delta = np.column_stack((-(y - 230) * 0.07 * head, (x - 512) * 0.07 * head))
    morph(drawable, "ParamAngleZ", -delta, delta)
    upper = 1 - ramp(y, 470, 720)
    _field(drawable, "ParamBodyAngleX", 12 * upper, np.zeros(len(v)))
    _field(drawable, "ParamBodyAngleY", np.zeros(len(v)), 4 * upper)
    _field(drawable, "ParamBodyAngleZ", -(y - 1450) * 0.008, (x - 512) * 0.008)
    chest = np.exp(-(((y - 370) / 150) ** 2)) * (1 - ramp(y, 550, 680))
    _field(drawable, "ParamBreath", (x - 512) * 0.009 * chest, -2.5 * chest)
    if body:
        hair = (1 - ramp(y, 410, 470)) * ramp(np.abs(x - 512), 65, 115)
        _field(drawable, "ParamHairBack", hair * 4, hair * 0.7)
        _field(drawable, "ParamHairSide", hair * 3, hair * 0.4)
        fringe = (1 - ramp(y, 140, 170)) * ramp(y, 20, 100)
        _field(drawable, "ParamHairFront", fringe * 1.3, np.zeros(len(v)))


def arms(doc):
    for side, (shoulder, elbow, wrist, sign) in ARMS.items():
        ids = [f"arm_{side}", f"hand_{side}", f"hand_open_{side}"]
        direction = np.asarray(wrist) - elbow
        direction /= np.linalg.norm(direction)
        for name in ids:
            d = doc.drawable(name)
            along = (np.asarray(d.vertices) - elbow) @ direction
            weight = ramp(along, -24, 30) if name.startswith("arm_") else np.ones(len(along))
            if name == "arm_l":
                weight[_ribbon_vertices(d)] = 0.0
            d.bone_weights = {
                f"fixed_{side}": (1 - weight).tolist(),
                f"bend_{side}": weight.tolist(),
            }
        for bone in ("fixed", "bend"):
            doc.deformers.append(
                Deformer(
                    id=f"{bone}_{side}",
                    type="bone_rotation",
                    parent=None,
                    drawables=ids,
                    form={"bone_id": f"{bone}_{side}", "anchor": list(elbow), "angle": 0.0},
                )
            )
        doc.deformers.append(
            Deformer(
                id=f"shoulder_{side}",
                type="rotation",
                parent=None,
                drawables=ids,
                form={"anchor": list(shoulder), "angle": 0.0},
            )
        )
        for suffix, node, angle in (("A", "shoulder", 35.0), ("B", "bend", 145.0)):
            doc.parameters.append(
                Parameter(
                    id=f"ParamArm{side.upper()}{suffix}",
                    min=0.0,
                    max=1.0,
                    default=0.0,
                    keys=[
                        ParameterKey(value=0.0, forms={f"{node}_{side}": {"angle": 0.0}}),
                        ParameterKey(
                            value=1.0,
                            forms={f"{node}_{side}": {"angle": sign * math.radians(angle)}},
                        ),
                    ],
                )
            )
        opacity(
            doc.drawable(f"hand_{side}"),
            f"ParamArm{side.upper()}B",
            [(0.0, 1.0), (0.25, 1.0), (0.5, 0.0), (1.0, 0.0)],
        )
        opacity(
            doc.drawable(f"hand_open_{side}"),
            f"ParamArm{side.upper()}B",
            [(0.0, 0.0), (0.25, 0.0), (0.5, 1.0), (1.0, 1.0)],
        )


def face_motion(drawable, kind, side=None):
    v = np.asarray(drawable.vertices)
    x, y = v.T
    zero = np.zeros(len(v))
    if kind in ("eye", "closed", "smile"):
        openness = f"ParamEye{side.upper()}Open"
        smile = f"ParamEye{side.upper()}Smile"
        if kind == "eye":
            opacity(drawable, openness, [(0.0, 0.0), (0.15, 0.0), (0.4, 1.0), (1.0, 1.0)])
            opacity(drawable, smile, [(0.0, 1.0), (1.0, 0.0)])
            centre = 156 if side == "r" else 152
            morph(
                drawable, openness, np.column_stack((zero, (centre - y) * 0.85)), np.zeros_like(v)
            )
            u = (x - x.min()) / max(1, np.ptp(x))
            vv = (y - y.min()) / max(1, np.ptp(y))
            gaze = np.sin(np.pi * u) ** 2 * np.sin(np.pi * vv) ** 2
            _field(drawable, "ParamEyeBallX", 2.5 * gaze, zero)
            _field(drawable, "ParamEyeBallY", zero, 1.8 * gaze)
        elif kind == "closed":
            opacity(drawable, openness, [(0.0, 1.0), (0.15, 1.0), (0.4, 0.0), (1.0, 0.0)])
            opacity(drawable, smile, [(0.0, 1.0), (1.0, 0.0)])
        else:
            opacity(drawable, smile, [(0.0, 0.0), (1.0, 1.0)])
    elif kind == "brow":
        prefix = f"ParamBrow{side.upper()}"
        _field(drawable, prefix + "Y", zero, np.ones(len(v)) * -3)
        _field(drawable, prefix + "X", np.ones(len(v)) * 2, zero)
        _field(drawable, prefix + "Angle", zero, (x - x.mean()) * 0.1)
        _field(
            drawable,
            prefix + "Form",
            zero,
            -1.5 * np.sin(np.pi * (x - x.min()) / max(1, np.ptp(x))),
        )
    elif kind.startswith("mouth"):
        _field(drawable, "ParamMouthForm", zero, -2 * ((x - 516) / 15) ** 2)
        if kind == "mouth_open":
            opacity(drawable, "ParamMouthOpenY", [(0.0, 0.0), (0.1, 1.0), (1.0, 1.0)])
            morph(
                drawable,
                "ParamMouthOpenY",
                np.zeros_like(v),
                np.column_stack((zero, (y - 190) * 0.55)),
            )
        else:
            opacity(drawable, "ParamMouthOpenY", [(0.0, 1.0), (0.1, 0.0), (1.0, 0.0)])
