"""Imeru's arms in 3D: puffed sleeve, forearm with a navy cuff and frill, and two hands.

Each arm is three layers the rig turns about the shoulder and the elbow (``upper_arm_*``,
``forearm_*``, ``hand_*``) plus ``hand_open_*``, the open waving hand. Both hands hang
from the wrist; the rig swaps them when the arm is raised. Layers named ``*_l`` are on the
viewer's left; the right arm is the left one mirrored.
"""
from __future__ import annotations

import math

from body import (
    NAVY,
    NAVY_DEEP,
    NAVY_EDGE,
    NAVY_LINE,
    NAVY_SHADE,
    WHITE,
    WHITE_DEEP,
    WHITE_EDGE,
    WHITE_LINE,
    WHITE_SHADE,
)
from common import W, bez, resample
from geo import ellipsoid, tube
from head import SKIN, SKIN_EDGE, SKIN_LINE, SKIN_SHADE
from ornament import gold
from toon import Rim, add_outline, toon

ARM_DEPTH = -30.0


def _x(x: float, side: str) -> float:
    return x if side == "l" else W - x


def _path(points, side: str):
    return [(_x(x, side), y, d) for x, y, d in points]


def _sleeve():
    return toon("sleeve", WHITE, WHITE_SHADE, deep=WHITE_DEEP, split=0.52, deep_split=0.12,
                rim=Rim("#FFFFFF", 0.8, 0.4), edge=WHITE_EDGE, occlusion=0.8)


def _skin():
    return toon("hand_skin", SKIN, SKIN_SHADE, split=0.3, edge=SKIN_EDGE)


def build_upper_arm(side: str, collection_for) -> None:
    curve = bez((318, 868, ARM_DEPTH), (292, 920, ARM_DEPTH), (284, 1060, ARM_DEPTH),
                (288, 1174, ARM_DEPTH), 40)
    path = _path(curve, side)
    radii = []
    for _, y, _ in curve:
        puff = 12 * math.sin(math.pi * min(1.0, max(0.0, (y - 868) / 150)))
        across = 33 + puff - 2 * (y - 868) / 300
        radii.append((across, across * 0.85, across * 0.85))
    arm = tube(f"upper_arm_{side}", path, radii, _sleeve(), segments=32)
    add_outline(arm, WHITE_LINE, 2.3)
    collection_for(f"upper_arm_{side}", arm)
    fold = toon("sleeve_fold", WHITE_SHADE, WHITE_DEEP, split=0.4)
    for k, (y, dx) in enumerate(((1106, 0), (1132, 4))):
        crease = _path([(x, y + 6 * math.sin((x - 262) / 18), ARM_DEPTH + 30) for x in
                        range(266 + dx, 312, 3)], side)
        line = tube(f"sleeve_fold_{side}_{k}", crease, [(1.3, 1.0)] * len(crease), fold,
                    segments=8)
        collection_for(f"upper_arm_{side}", line)


def build_forearm(side: str, collection_for) -> None:
    ys = [1134.0 + 24 * (1 - math.cos(math.pi / 2 * k / 12)) for k in range(13)]
    ys += [float(y) for y in range(1164, 1393, 6)]
    curve = [(288, y, ARM_DEPTH) for y in ys]
    dome = [math.sqrt(max(0.0, min(1.0, (y - 1134) / 24))) for y in ys]
    radii = [(d * (33 - (y - 1140) * 0.012), d * 28.0) for d, y in zip(dome, ys, strict=True)]
    arm = tube(f"forearm_{side}", _path(curve, side), radii, _sleeve(), segments=32)
    add_outline(arm, WHITE_LINE, 2.3)
    collection_for(f"forearm_{side}", arm)
    navy = toon("cuff", NAVY, NAVY_SHADE, deep=NAVY_DEEP, split=0.4, rim=Rim("#6F86D8", 0.78),
                edge=NAVY_EDGE, occlusion=0.8)
    cuff_path = [(288, float(y), ARM_DEPTH) for y in range(1336, 1395, 4)]
    cuff = tube(f"cuff_{side}", _path(cuff_path, side), [(35.5, 31.0)] * len(cuff_path), navy,
                segments=32)
    add_outline(cuff, NAVY_LINE, 2.0)
    collection_for(f"forearm_{side}", cuff)
    for k, y in enumerate((1340, 1388)):
        ring = [(288 + 36.5 * math.cos(a), y, ARM_DEPTH + 32 * math.sin(a))
                for a in (math.pi * j / 30 for j in range(31))]
        trim = tube(f"cuff_trim_{side}_{k}", _path(ring, side), [(2.2, 2.2)] * len(ring), gold(),
                    segments=8)
        collection_for(f"forearm_{side}", trim)
    frill_path = [(288, float(y), ARM_DEPTH) for y in range(1390, 1409, 3)]
    frill = tube(f"frill_{side}", _path(frill_path, side),
                 [(30 + (y - 1390) * 0.5, 26 + (y - 1390) * 0.4) for _, y, _ in frill_path],
                 _sleeve(), segments=48,
                 squash=lambda k, theta: 1.0 + 0.07 * math.cos(theta * 12))
    add_outline(frill, WHITE_LINE, 1.6)
    collection_for(f"forearm_{side}", frill)


def _finger(name, base, angle_deg, length, radius, skin, side, curl=0.0):
    a = math.radians(angle_deg)
    end = (base[0] + math.sin(a) * length, base[1] + math.cos(a) * length)
    mid = (base[0] + math.sin(a) * length * 0.55 + curl, base[1] + math.cos(a) * length * 0.55)
    curve = resample(bez(base, mid, mid, end, 12), 12)
    path = _path([(x, y, ARM_DEPTH + 10) for x, y in curve], side)
    radii = [(radius * (1 - 0.25 * i / 11), radius * 0.85 * (1 - 0.25 * i / 11))
             for i in range(12)]
    radii[-2] = (radius * 0.6, radius * 0.5)
    radii[-1] = (0.0, 0.0)
    obj = tube(name, path, radii, skin, segments=14)
    add_outline(obj, SKIN_LINE, 1.6)
    return obj


def build_hand(side: str, collection_for) -> None:
    """A relaxed hand hanging at her side, seen edge-on: narrow, fingers curled, thumb in front."""
    skin = _skin()
    layer = f"hand_{side}"
    palm = ellipsoid(f"palm_{side}", (_x(289, side), 1420, ARM_DEPTH + 4), (15, 27, 22), skin,
                     segments=28)
    add_outline(palm, SKIN_LINE, 1.8)
    collection_for(layer, palm)
    inward = 1.0 if side == "l" else -1.0
    for k, (dz, dx, length) in enumerate(((14, -3, 34), (5, -1, 38), (-4, 1, 37), (-13, 3, 31))):
        top = (289 + dx, 1438)
        tip = (289 + dx + 9 * inward, 1438 + length)
        curve = bez(top, (top[0], top[1] + length * 0.5), (tip[0] - 4 * inward, tip[1] - 6),
                    tip, 14)
        path = _path([(x, y, ARM_DEPTH + dz) for x, y in curve], side)
        radii = [(5.6 - 1.6 * i / 13, 5.0 - 1.4 * i / 13) for i in range(14)]
        radii[-1] = (3.0, 2.8)
        finger = tube(f"finger_{side}_{k}", path, radii, skin, segments=14)
        add_outline(finger, SKIN_LINE, 1.5)
        collection_for(layer, finger)
    thumb = _finger(f"thumb_{side}", (296, 1412), -10 * inward, 30, 6.4, skin, side)
    collection_for(layer, thumb)


def build_open_hand(side: str, collection_for) -> None:
    """An open hand, palm to the viewer, fingers spread: shown when she waves."""
    skin = _skin()
    layer = f"hand_open_{side}"
    palm = ellipsoid(f"palm_open_{side}", (_x(289, side), 1418, ARM_DEPTH + 6), (22, 24, 11),
                     skin, segments=28)
    add_outline(palm, SKIN_LINE, 1.8)
    collection_for(layer, palm)
    for k, (dx, angle, length) in enumerate(((-16, -20, 36), (-5.5, -7, 44), (5.5, 7, 44),
                                             (16, 21, 37))):
        finger = _finger(f"open_finger_{side}_{k}", (289 + dx, 1436), angle, length, 6.0,
                         skin, side)
        collection_for(layer, finger)
    thumb = _finger(f"open_thumb_{side}", (270, 1416), -58, 32, 7.0, skin, side)
    collection_for(layer, thumb)


def _all(collection_for) -> None:
    for side in ("l", "r"):
        build_upper_arm(side, collection_for)
        build_forearm(side, collection_for)
        build_hand(side, collection_for)
        build_open_hand(side, collection_for)


BUILDERS = (_all,)
