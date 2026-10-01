"""Imeru's head, neck and hair in 3D: one builder per puppet layer.

The head is lofted from the 2D face outline the eyes and mouth were drawn for (the outline
seen from the front is exact), so the painted features in ``art.py`` still sit on it. Hair
is built lock by lock as flattened tubes that follow the skull, shaded with the normals of
a smooth ball and column around it (``normals.py``) so the whole mass takes the light as
one shape, with strand lines and a broken highlight band painted on in the shader.
"""
from __future__ import annotations

import math
import random

from common import CX, bez, chain, mirror, resample, smoothstep
from geo import ellipsoid, sheet, tube
from normals import blend_fields, borrow, column_field, ellipsoid_field, face_light
from ornament import jewel
from toon import LIGHT_DIRECTION, Rim, add_outline, toon

# ---- palette (the 2D layers use the same colours) --------------------------------------
SKIN, SKIN_SHADE, SKIN_LINE = "#FFEFE6", "#F7CDC1", "#C9857A"
SKIN_EDGE = "#F79583"
HAIR, HAIR_SHADE, HAIR_DEEP = "#D7D1F7", "#ABA0E6", "#8476CF"
HAIR_SPEC, HAIR_LINE = "#FBFAFF", "#5B4DA6"

SKULL_Y, SKULL_R = 470.0, 194.0
CHIN_Y = 754.0
CROWN_Y = SKULL_Y - SKULL_R


def _face_half():
    return chain(bez((318, 470), (314, 520), (318, 575), (330, 612)),
                 bez((330, 612), (344, 660), (380, 700), (424, 724)),
                 bez((424, 724), (458, 744), (488, 754), (CX, 754)))


_HALF = sorted(_face_half(), key=lambda p: p[1])


def half_width(y: float) -> float:
    """Half the head's width at canvas *y*, as seen from the front."""
    if y <= SKULL_Y:
        return math.sqrt(max(0.0, SKULL_R ** 2 - (SKULL_Y - y) ** 2))
    if y >= CHIN_Y:
        return 0.0
    for (x0, y0), (x1, y1) in zip(_HALF, _HALF[1:], strict=False):
        if y0 <= y <= y1:
            t = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
            return CX - (x0 + (x1 - x0) * t)
    return 0.0


def front_depth(y: float) -> float:
    """How far the face bulges toward the viewer at canvas *y* (its flat-ish front)."""
    w = half_width(y)
    if y <= SKULL_Y:
        return w * 0.92
    return w * (0.92 - 0.22 * (y - SKULL_Y) / (CHIN_Y - SKULL_Y))


def surface(x: float, y: float) -> float:
    """Depth of the head's front surface at canvas (x, y); 0 outside the head."""
    w = half_width(y)
    if w <= 1e-6 or abs(x - CX) >= w:
        return 0.0
    return front_depth(y) * math.sqrt(1.0 - ((x - CX) / w) ** 2)


def _rings(y0: float, y1: float, step: float, grow: float = 0.0):
    path, radii = [], []
    y = y0
    while y <= y1 + 1e-6:
        w = half_width(y)
        path.append((CX, y, 0.0))
        radii.append((w + grow if w > 0 else 0.0, front_depth(y) + grow if w > 0 else 0.0,
                      w * 1.02 + grow if w > 0 else 0.0))
        y += step
    return path, radii


def build_face(collection_for):
    """The ``face`` layer: the head itself, lit all over but for the shadows cast on it.

    Its own light and shade come from the face shadow map (``face_shadow.py``), as in
    anime games, so the render only contributes the skin and the bangs' shadow.
    """
    skin = toon("skin", SKIN, SKIN_SHADE, split=0.16)
    path, radii = _rings(CROWN_Y, CHIN_Y, 3.0)
    head = tube("head", path, radii, skin, segments=56)
    face_light(head, -LIGHT_DIRECTION)
    add_outline(head, SKIN_LINE, 2.2)
    collection_for("face", head)


def build_neck(collection_for):
    """The neck, part of the ``body`` layer."""
    skin = toon("neck_skin", SKIN, SKIN_SHADE, split=0.3, edge=SKIN_EDGE, occlusion=0.6)
    path = [(CX, y, -36.0) for y in range(660, 881, 10)]
    radii = [(37.0 + max(0.0, (y - 800) * 0.25), 32.0, 30.0) for _, y, _ in path]
    neck = tube("neck", path, radii, skin, segments=32)
    add_outline(neck, SKIN_LINE, 2.2)
    collection_for("body", neck)


#: Hair tones down the canvas: (y, lit, shade, deep) — lavender crown, deeper lilac at the
#: ends of the bangs, blue over the shoulders, cyan tips.
HAIR_STOPS = [(300.0, "#DCD6F9", "#AEA3E9", "#8C7FD4"), (600.0, "#C4BAF1", "#9688DE", "#7466C6"),
              (920.0, "#B4C3F1", "#8A9BDF", "#6A7DCA"), (1320.0, "#A6E6EE", "#72BAD2", "#5490C1")]
BACK_STOPS = [(300.0, "#B4A9EA", "#8E80D8", "#6E61C2"), (700.0, "#A69AE2", "#7D70CF", "#6255B8"),
              (1000.0, "#8FA2E0", "#6E83CF", "#5368BA"), (1320.0, "#86C9DE", "#5EA3C6", "#4880B4")]


#: The smooth shapes the hair borrows its shading normals from: a ball around the head,
#: and columns around the side locks and the long back hair that it eases into.
HEAD_FIELD = ellipsoid_field((CX, SKULL_Y, -20.0), (215.0, 215.0, 200.0))
SIDE_FIELD = blend_fields(HEAD_FIELD, column_field(CX, -120.0, 240.0, 200.0), 430.0, 600.0)
BACK_FIELD = blend_fields(HEAD_FIELD, column_field(CX, -420.0, 280.0, 260.0), 420.0, 640.0)
#: Painted strand lines down every lock: (across, half width), shifted lock by lock.
STRANDS = {"lines": ((-0.46, 0.05), (0.1, 0.04), (0.52, 0.045)), "jitter": 0.3,
           "strength": 0.7}
#: The highlight band around the head, broken into one stroke per lock.
STREAK = {"y": 340.0, "bend": 78.0, "spread": 190.0, "half": 7.0, "jitter": 16.0,
          "edge": 0.72, "colour": HAIR_SPEC, "strength": 0.88}


def hair_material(name: str, *, split: float = 0.46, stops: list | None = None,
                  streak: dict | None = None, strands: bool = True):
    """Cel-shaded hair: the colour gradient, baked occlusion, painted strands and streak."""
    return toon(name, HAIR, HAIR_SHADE, deep=HAIR_DEEP, split=split, deep_split=0.14,
                stops=stops or HAIR_STOPS, rim=Rim("#FFFFFF", 0.8, 0.4), edge="#8F78F0",
                occlusion=0.85, strands=STRANDS if strands else None, streak=streak)


def lock(name: str, curve, width: float, material, *, lift: float = 14.0,
         flat: float = 0.32, root: float = 0.55, belly: float = 0.4, n: int = 44,
         follow: bool = True, line: float = 2.0, sink: float | None = None,
         field=HEAD_FIELD):
    """One lock of hair along a 2D or 3D curve; on the skull it follows the surface.

    With *sink* the root starts that far above the skull and rises to *lift* over the
    first fifth of the lock, so a surface just above *sink* hides where it grows from.
    The lock is shaded with the normals of *field* (see ``normals.py``).
    """
    pts = resample(curve, n)
    path = []
    for i, p in enumerate(pts):
        t = i / (n - 1)
        if len(p) == 3:
            x, y, d = p
        else:
            x, y = p
            d = surface(x, y) if follow else 0.0
        height = lift * (1.0 - 0.4 * t)
        if sink is not None:
            height = sink + (height - sink) * smoothstep(0.0, 0.22, t)
        path.append((x, y, d + height))
    radii = []
    for i in range(n):
        t = i / (n - 1)
        shape = (root + (1 - root) * math.sin(min(1.0, t / belly) * math.pi / 2)
                 if t < belly else math.cos((t - belly) / (1 - belly) * math.pi / 2) ** 0.9)
        across = width * shape
        radii.append((across, across * flat, across * flat))
    obj = tube(name, path, radii, material, segments=18)
    borrow(obj, field)
    if line > 0:
        add_outline(obj, HAIR_LINE, line)
    return obj


#: Where the parting meets the hairline, and the hairline arching down to both temples.
PART_X = 492.0
HAIRLINE = (bez((316, 492), (330, 400), (420, 352), (PART_X, 350), 30)
            + bez((PART_X, 350), (590, 352), (694, 400), (708, 492), 30)[1:])
#: Fringe locks: (root x on the hairline, tip (x, y), half width).
FRINGE = (
    (336, (306, 698), 20), (362, (318, 644), 25), (392, (334, 598), 29),
    (424, (364, 566), 31), (456, (402, 546), 32), (484, (440, 562), 30),
    (500, (536, 556), 30), (530, (574, 538), 32), (562, (614, 560), 31),
    (596, (654, 594), 29), (630, (690, 640), 25), (662, (716, 694), 20),
)
#: Two thin locks that cross the parting and fall between the eyes.
ACCENTS = ((488, (472, 612), 12), (506, (560, 598), 11))


def hairline_y(x: float) -> float:
    """The canvas y of the hairline at *x*."""
    points = sorted(HAIRLINE)
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / max(1e-6, x1 - x0)
    return points[0][1] if x < points[0][0] else points[-1][1]


def scalp_depth(x: float, y: float) -> float:
    """Depth of the hair over the skull: the head grown by the hair's thickness."""
    r = SKULL_R + 15
    dome = r * r - (x - CX) ** 2 - (y - SKULL_Y) ** 2
    dome = 0.92 * math.sqrt(dome) if dome > 0 and y <= SKULL_Y else 0.0
    return max(dome, surface(x, y) + 15 if surface(x, y) > 0 else 0.0)


def _scalp_outline():
    r = SKULL_R + 15
    arc = [(CX + r * math.cos(a), SKULL_Y + r * math.sin(a))
           for a in [math.pi + math.pi * k / 48 for k in range(49)]]
    return arc + list(reversed(HAIRLINE))[1:-1]


def _fringe_lock(name, root_x, tip, width, mat, lift):
    root = (root_x + (root_x - PART_X) * 0.1, hairline_y(root_x) - 38)
    dx, dy = tip[0] - root[0], tip[1] - root[1]
    hook = -0.18 * dx       # tips curl back toward the middle of the face
    curve = bez(root, (root[0] + 0.22 * dx, root[1] + 0.4 * dy),
                (root[0] + 0.95 * dx - hook, root[1] + 0.72 * dy), tip, 44)
    return lock(name, curve, width, mat, lift=lift, root=0.35, belly=0.36, sink=6.0)


def build_bangs(collection_for):
    """The ``bangs`` layer: the hair over the crown down to the hairline, and the fringe."""
    mat = hair_material("bangs_hair", streak=STREAK)
    scalp_mat = hair_material("scalp_hair", strands=False)
    scalp = sheet("scalp", _scalp_outline(), scalp_depth, scalp_mat, thickness=4.0, step=10.0)
    borrow(scalp, HEAD_FIELD)
    add_outline(scalp, HAIR_LINE, 2.2, even=False)
    collection_for("bangs", scalp)
    flow = toon("hair_flow", HAIR_SHADE, HAIR_DEEP, split=0.4, occlusion=0.85)
    for k, x in enumerate((392, 432, 470, 548, 588, 628)):
        top = (CX + (x - CX) * 0.25, CROWN_Y + 22)
        curve = bez(top, (CX + (x - CX) * 0.6, CROWN_Y + 40), (x, 300),
                    (x + (x - PART_X) * 0.1, hairline_y(x) - 4), 30)
        strand = lock(f"flow_{k}", curve, 3.2, flow, lift=17.5, root=1.0, belly=0.6, line=0.0)
        collection_for("bangs", strand)
    for i, (root_x, tip, width) in enumerate(FRINGE):
        centre = 1 - abs(root_x - PART_X) / 180
        collection_for("bangs", _fringe_lock(f"bang_{i}", root_x, tip, width, mat,
                                             lift=18 + 8 * max(0.0, centre)))
    for i, (root_x, tip, width) in enumerate(ACCENTS):
        collection_for("bangs", _fringe_lock(f"bang_accent_{i}", root_x, tip, width, mat,
                                             lift=30))


def build_side_locks(collection_for):
    """``side_lock_l`` / ``side_lock_r``: the long locks framing the face."""
    mat = hair_material("side_hair", split=0.44, streak=STREAK)
    strands = (((352, 352), (294, 470), (282, 720), (318, 990), 34.0, 60.0),
               ((362, 372), (312, 540), (304, 760), (336, 930), 24.0, 74.0),
               ((346, 372), (280, 540), (268, 760), (290, 880), 18.0, 50.0))
    for side in ("l", "r"):
        for k, (a, b, c, d, width, depth) in enumerate(strands):
            curve = [(x, y, depth * min(1.0, (y - a[1]) / 160.0)) for x, y in bez(a, b, c, d, 40)]
            if side == "r":
                curve = mirror(curve)
            obj = lock(f"side_{side}_{k}", curve, width, mat, lift=0.0, belly=0.36, root=0.15,
                       follow=False, field=SIDE_FIELD)
            collection_for(f"side_lock_{side}", obj)


def _back_locks(collection_for, mat, rng, *, count, spread, depth, width, prefix, length):
    for i in range(count):
        u = -1 + 2 * i / (count - 1)
        root = (CX + u * 110, 300 + 40 * abs(u), depth + 60)
        tip_x = CX + u * spread + rng.uniform(-14, 14)
        tip_y = length + 80 * math.cos(u * 2.0) + rng.uniform(-36, 30)
        curve = bez(root, (CX + u * (spread - 30), 520, depth + 30),
                    (CX + u * spread, 900, depth), (tip_x, tip_y, depth - 20), 40)
        lock_width = width + rng.uniform(-7, 9)
        collection_for("back_hair", lock(f"{prefix}_{i}", curve, lock_width, mat, lift=0.0,
                                         belly=0.2, root=0.8, follow=False, line=2.2,
                                         field=BACK_FIELD))


def build_back_hair(collection_for):
    """``back_hair``: the hair behind the head and down her back, outer and darker inner locks."""
    inner = toon("back_inner", HAIR_SHADE, HAIR_DEEP, deep="#6556B6", split=0.62,
                 stops=[(y, shade, deep, deep) for y, _, shade, deep in BACK_STOPS],
                 occlusion=0.85)
    outer = hair_material("back_hair", split=0.5, stops=BACK_STOPS, streak=STREAK)
    rng = random.Random(11)
    shell = ellipsoid("hair_mass", (CX, 476, -100), (206, 206, 150), inner, segments=48)
    add_outline(shell, HAIR_LINE, 2.2)
    collection_for("back_hair", shell)
    _back_locks(collection_for, inner, rng, count=12, spread=210, depth=-260, width=46,
                prefix="back_in", length=1330)
    _back_locks(collection_for, outer, rng, count=18, spread=262, depth=-190, width=46,
                prefix="back_out", length=1290)


def build_ahoge(collection_for):
    """``ahoge``: the single curled strand standing up from the crown."""
    mat = hair_material("ahoge_hair")
    curve = chain(bez((CX + 4, CROWN_Y + 12, 40), (CX + 6, CROWN_Y - 40, 40),
                      (CX + 60, CROWN_Y - 70, 40), (CX + 68, CROWN_Y - 40, 40), 30),
                  bez((CX + 68, CROWN_Y - 40, 40), (CX + 74, CROWN_Y - 14, 40),
                      (CX + 46, CROWN_Y - 10, 40), (CX + 44, CROWN_Y - 26, 40), 16))
    obj = lock("ahoge", curve, 7.0, mat, lift=0.0, belly=0.25, root=0.9, follow=False, line=1.8)
    collection_for("ahoge", obj)


def build_hairpin(collection_for):
    """``hairpin``: the star-lens jewel pinned in her bangs, with two gold beads."""
    x, y = 372.0, 440.0
    d = scalp_depth(x, y) + 30
    for obj in jewel("pin", x, y, d, beads=((x + 29, y - 8), (x + 26, y + 15))):
        collection_for("hairpin", obj)


BUILDERS = (build_face, build_neck, build_bangs, build_side_locks, build_back_hair,
            build_ahoge, build_hairpin)
