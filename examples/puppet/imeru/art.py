"""The layers of Imeru, Imervue's mascot, drawn as vector shapes.

Each ``draw_*`` returns ``{layer_id: HxWx4 uint8}`` on the 1024 x 1536 canvas; ``LAYERS``
lists them bottom to top. Geometry that the rig needs (eye lids, mouth, hair roots) is
exported as module constants so ``rig.py`` deforms what was drawn.
"""

from __future__ import annotations

import numpy as np

import refine
from draw import (
    W,
    bez,
    blur,
    chain,
    clip,
    ellipse_pts,
    finish,
    line,
    minus,
    mirror,
    new_layer,
    paint,
    paint_gradient,
    poly,
    stroke,
    taper,
)

CX = W / 2

# ---- palette -------------------------------------------------------------------------
HAIR = "#CEC8F2"
HAIR_SHADE = "#A69CE0"
HAIR_DEEP = "#7C6FC8"
HAIR_LIGHT = "#F6F3FF"
HAIR_TIP = "#94DCE8"
HAIR_LINE = "#5B4DA6"
SKIN = "#FFEDE3"
SKIN_SHADE = "#F7CFC4"
SKIN_LINE = "#C08377"
BLUSH = "#FF95A6"
IRIS_TOP = "#27357F"
IRIS_BOTTOM = "#5FE3D2"
PUPIL = "#1A1C48"
LASH = "#2B2244"
BLOUSE = "#FAFAFF"
BLOUSE_SHADE = "#D6DAF2"
NAVY = "#27335E"
NAVY_LIGHT = "#3A4A80"
CORAL = "#FF7E6B"
CORAL_SHADE = "#D95C50"
GOLD = "#EBC374"
GOLD_DARK = "#B98B3E"
LENS_TOP = "#3D6FD8"
LENS_BOTTOM = "#9CE6FF"
LINE_DARK = "#3C3563"

# ---- geometry shared with the rig ---------------------------------------------------------
HEAD_CENTRE = (CX, 520.0)
NECK_PIVOT = (CX, 760.0)
EYE_OUTER_L, EYE_INNER_L = (386.0, 606.0), (490.0, 616.0)
EYE_UPPER_C_L = ((394.0, 548.0), (462.0, 544.0))
EYE_LOWER_C_L = ((478.0, 654.0), (404.0, 658.0))
IRIS_L = (444.0, 616.0, 31.0, 41.0)
MOUTH_Y = 707.0
MOUTH_HALF = 21.0
FACE_TOP_Y = 300.0


def upper_lid(side: str = "l", n: int = 40):
    pts = bez(EYE_OUTER_L, *EYE_UPPER_C_L, EYE_INNER_L, n)
    return pts if side == "l" else mirror(pts)


def lower_lid(side: str = "l", n: int = 40):
    pts = bez(EYE_INNER_L, *EYE_LOWER_C_L, EYE_OUTER_L, n)
    return pts if side == "l" else mirror(pts)


def _face_half():
    return chain(
        bez((318, 470), (314, 520), (318, 575), (330, 612)),
        bez((330, 612), (344, 660), (380, 700), (424, 724)),
        bez((424, 724), (458, 744), (488, 754), (CX, 754)),
    )


def face_outline():
    half = _face_half()
    right = mirror(half)[::-1]
    top = bez((706, 470), (700, 390), (324, 390), (318, 470))
    return chain(half, right[1:], top[1:])


# ---- back hair ------------------------------------------------------------------------------
def draw_back_hair() -> dict[str, np.ndarray]:
    layer = new_layer()
    left = chain(
        bez((CX, 282), (400, 280), (292, 360), (292, 500)),
        bez((292, 500), (290, 640), (262, 760), (250, 900)),
        bez((250, 900), (238, 1040), (236, 1180), (262, 1330)),
    )
    tips = chain(
        bez((262, 1330), (290, 1290), (300, 1300), (318, 1372)),
        bez((318, 1372), (338, 1310), (356, 1310), (378, 1396)),
        bez((378, 1396), (396, 1330), (420, 1320), (446, 1400)),
        bez((446, 1400), (470, 1330), (490, 1320), (CX, 1380)),
    )
    half = chain(left, tips)
    shape = chain(half, mirror(half)[::-1][1:])
    mask = poly(shape)
    paint_gradient(layer, mask, (CX, 420), HAIR_SHADE, (CX, 1400), HAIR_TIP)
    # the inside of the hair, behind the neck, is in shadow
    inner = chain(
        bez((392, 700), (380, 860), (372, 1050), (404, 1330)),
        bez((404, 1330), (460, 1300), (564, 1300), (620, 1330)),
        bez((620, 1330), (652, 1050), (644, 860), (632, 700)),
    )
    paint_gradient(
        layer, blur(poly(inner), 10), (CX, 700), HAIR_DEEP, (CX, 1330), "#6FB6C9", alpha=0.85
    )
    for x0, bend in ((300, -18), (340, -8), (684, 8), (724, 18), (270, -24), (754, 24)):
        strand = bez((x0, 560), (x0 + bend, 820), (x0 + bend * 2, 1060), (x0 + bend, 1300), 40)
        paint(layer, clip(stroke(strand, taper(40, 1, 3.2, 0.5, 0.4)), mask), HAIR_DEEP, 0.45)
    refine.back_hair_detail(layer, mask)
    paint(layer, minus(line(shape + [shape[0]], 3.4), poly(shape)), HAIR_LINE, 0.9)
    return {"back_hair": finish(layer)}


# ---- body -------------------------------------------------------------------------------------
def draw_collar() -> dict[str, np.ndarray]:
    layer = new_layer()
    half = chain(
        bez((462, 836), (420, 856), (330, 872), (296, 900)),
        bez((296, 900), (292, 960), (300, 1000), (330, 1030)),
        bez((330, 1030), (400, 1010), (470, 1000), (CX, 1062)),
    )
    shape = chain(half, mirror(half)[::-1][1:])
    cut = chain(
        bez((466, 842), (486, 900), (500, 960), (CX, 1000)),
        bez((CX, 1000), (524, 960), (538, 900), (558, 842)),
    )
    mask = minus(poly(shape), poly(cut))
    paint_gradient(layer, mask, (CX, 840), NAVY_LIGHT, (CX, 1060), NAVY)
    refine.collar_detail(layer, mask)
    for offset in (14, 24):
        edge = chain(
            bez(
                (302 + offset * 0.2, 904 + offset * 0.6),
                (298, 960),
                (306, 996),
                (332, 1026 - offset),
            ),
            bez(
                (332, 1026 - offset),
                (400, 1008 - offset),
                (470, 998 - offset * 0.7),
                (CX, 1060 - offset),
            ),
        )
        paint(layer, clip(line(edge, 3.0), mask), "#F4F6FF")
        paint(layer, clip(line(mirror(edge), 3.0), mask), "#F4F6FF")
    paint(layer, line(shape + [shape[0]], 2.6), "#161D3B", 0.9)
    paint(layer, line(cut, 2.4), "#161D3B", 0.9)
    return {"collar": finish(layer)}


def draw_ribbon() -> dict[str, np.ndarray]:
    layer = new_layer()
    loop_l = chain(
        bez((CX, 1016), (470, 976), (428, 986), (430, 1016)),
        bez((430, 1016), (428, 1050), (474, 1046), (CX, 1024)),
    )
    tail_l = chain(
        bez((500, 1026), (486, 1070), (470, 1110), (452, 1150)),
        [(452, 1150), (478, 1140), (494, 1158)],
        bez((494, 1158), (500, 1110), (508, 1070), (CX, 1030)),
    )
    for shape in (loop_l, mirror(loop_l), tail_l, mirror(tail_l)):
        mask = poly(shape)
        paint_gradient(layer, mask, (CX, 980), CORAL, (CX, 1160), CORAL_SHADE)
        paint(layer, line(shape + [shape[0]], 2.4), "#9E3B36", 0.9)
    refine.ribbon_detail(layer, [loop_l, mirror(loop_l)])
    knot = poly(ellipse_pts(CX, 1022, 17, 15))
    paint(layer, knot, CORAL_SHADE)
    paint(
        layer,
        line(ellipse_pts(CX, 1022, 17, 15) + [ellipse_pts(CX, 1022, 17, 15)[0]], 2.4),
        "#9E3B36",
    )
    for side in (-1, 1):
        fold = bez(
            (CX + side * 24, 1010),
            (CX + side * 40, 1004),
            (CX + side * 56, 1010),
            (CX + side * 66, 1016),
            20,
        )
        paint(layer, line(fold, 2.0), "#B84A43", 0.7)
    return {"ribbon": finish(layer)}


# ---- face -------------------------------------------------------------------------------------
def draw_face() -> dict[str, np.ndarray]:
    layer = new_layer()
    mask = poly(face_outline())
    paint(layer, mask, SKIN)
    right_cheek = chain(
        bez((706, 470), (714, 560), (700, 640), (660, 700)),
        bez((660, 700), (640, 726), (600, 748), (560, 752)),
        bez((560, 752), (620, 700), (660, 600), (660, 470)),
    )
    paint(layer, clip(blur(poly(right_cheek), 8), mask), SKIN_SHADE, 0.85)
    half = _face_half()
    jaw = chain(half[30:], mirror(half)[::-1][1:-30])
    paint(layer, line(jaw, 2.8), SKIN_LINE)
    return {"face": finish(layer)}


def draw_neck_shadow() -> dict[str, np.ndarray]:
    layer = new_layer()
    shade = chain(bez((466, 700), (480, 760), (544, 760), (558, 700)), [(558, 700), (466, 700)])
    paint(
        layer,
        blur(poly(chain(bez((470, 720), (486, 790), (538, 790), (554, 720)))), 6),
        SKIN_SHADE,
        0.95,
    )
    paint(layer, poly(shade), SKIN_SHADE, 0.6)
    return {"neck_shadow": finish(layer)}


def _bang_tips():
    """Lower edge of the bangs, left to right: (x, y) of every tip and notch."""
    return [
        (300, 520),
        (318, 610),
        (344, 540),
        (376, 596),
        (402, 530),
        (432, 584),
        (452, 526),
        (478, 596),
        (500, 540),
        (522, 604),
        (548, 534),
        (576, 588),
        (600, 526),
        (628, 590),
        (656, 540),
        (690, 604),
        (712, 524),
    ]


def _bangs_shape():
    tips = _bang_tips()
    edge = []
    for (x0, y0), (x1, y1) in zip(tips, tips[1:], strict=False):
        edge += bez(
            (x0, y0),
            (x0 + (x1 - x0) * 0.35, y0 + (y1 - y0) * 0.1),
            (x0 + (x1 - x0) * 0.75, y0 + (y1 - y0) * 0.75),
            (x1, y1),
            12,
        )
    top = chain(
        bez((712, 524), (716, 380), (640, 284), (CX, 284), 30),
        bez((CX, 284), (384, 284), (308, 380), (300, 520), 30)[1:],
    )
    return chain(edge, top[1:])


BANG_EDGE_POINTS = 12 * 16


def draw_bang_shadow() -> dict[str, np.ndarray]:
    layer = new_layer()
    shadow = [(x, y + 14) for x, y in _bangs_shape()]
    paint(layer, clip(blur(poly(shadow), 7), poly(face_outline())), "#E9B4BE", 0.75)
    return {"bang_shadow": finish(layer)}


def draw_blush() -> dict[str, np.ndarray]:
    layer = new_layer()
    for x in (428.0, W - 428.0):
        paint(layer, blur(poly(ellipse_pts(x, 668, 38, 15)), 7), BLUSH, 0.8)
        for k in range(3):
            hatch = [(x - 16 + k * 12, 674), (x - 8 + k * 12, 662)]
            paint(layer, line(hatch, 2.0), "#F06F86", 0.8)
    return {"blush": finish(layer)}


def draw_nose() -> dict[str, np.ndarray]:
    layer = new_layer()
    paint(layer, line(bez((514, 656), (512, 662), (510, 667), (506, 670), 10), 2.6), SKIN_LINE, 0.9)
    refine.nose_and_lip(layer)
    return {"nose": finish(layer)}


def mouth_inside_shape():
    return chain(
        bez(
            (CX - MOUTH_HALF, MOUTH_Y),
            (CX - 8, MOUTH_Y + 2),
            (CX + 8, MOUTH_Y + 2),
            (CX + MOUTH_HALF, MOUTH_Y),
        ),
        bez(
            (CX + MOUTH_HALF, MOUTH_Y),
            (CX + 20, MOUTH_Y + 30),
            (CX - 20, MOUTH_Y + 30),
            (CX - MOUTH_HALF, MOUTH_Y),
        ),
    )


def draw_mouth() -> dict[str, np.ndarray]:
    inside = new_layer()
    shape = mouth_inside_shape()
    mask = poly(shape)
    paint(inside, mask, "#8A3446")
    paint(inside, clip(poly(ellipse_pts(CX + 2, MOUTH_Y + 25, 15, 9)), mask), "#EE8A98")
    paint(inside, line(shape + [shape[0]], 2.2), "#6E2436")
    upper = new_layer()
    lip = bez(
        (CX - MOUTH_HALF - 3, MOUTH_Y - 1),
        (CX - 8, MOUTH_Y + 4),
        (CX + 8, MOUTH_Y + 4),
        (CX + MOUTH_HALF + 3, MOUTH_Y - 1),
        30,
    )
    paint(upper, stroke(lip, taper(30, 1.2, 3.4, 1.2)), "#9C4454")
    return {"mouth_inside": finish(inside), "mouth_line": finish(upper)}


# ---- eyes -------------------------------------------------------------------------------------
def _sclera(side: str):
    return chain(upper_lid(side), lower_lid(side)[1:])


def _mirror_x(x: float, side: str) -> float:
    return x if side == "l" else W - x


def draw_eye(side: str) -> dict[str, np.ndarray]:
    sclera = poly(_sclera(side))
    white = new_layer()
    paint(white, sclera, "#FFFFFF")
    paint(
        white,
        clip(
            blur(poly([(x, y + 26) for x, y in upper_lid(side)] + upper_lid(side)[::-1]), 5), sclera
        ),
        "#C9C6E8",
        0.9,
    )
    cx, cy, rx, ry = IRIS_L
    cx = _mirror_x(cx, side)
    iris = new_layer()
    iris_mask = poly(ellipse_pts(cx, cy, rx, ry))
    paint_gradient(iris, iris_mask, (cx, cy - ry), IRIS_TOP, (cx, cy + ry), IRIS_BOTTOM)
    ring = [
        (cx + 19 * np.cos(a), cy + 3 + 23 * np.sin(a))
        for a in np.linspace(-np.pi / 2, 1.5 * np.pi, 7)
    ]
    paint(iris, line(ring, 2.2), "#9FF0E6", 0.8)
    for (x0, y0), (x1, y1) in zip(ring, ring[1:], strict=False):
        blade = [
            (x0, y0),
            (x0 + (x1 - x0) * 0.5 + (cx - x0) * 0.35, y0 + (y1 - y0) * 0.5 + (cy + 3 - y0) * 0.35),
        ]
        paint(iris, line(blade, 1.6), "#9FF0E6", 0.55)
    refine.iris_detail(iris, iris_mask, cx, cy, rx, ry)
    paint(iris, poly(ellipse_pts(cx, cy + 2, 12, 16)), PUPIL)
    paint(
        iris,
        clip(blur(poly(ellipse_pts(cx, cy - ry * 0.55, rx * 1.1, ry * 0.55)), 3), iris_mask),
        "#101540",
        0.6,
    )
    paint(
        iris,
        line(ellipse_pts(cx, cy, rx, ry) + [ellipse_pts(cx, cy, rx, ry)[0]], 2.4),
        "#1C2150",
        0.9,
    )
    shine = new_layer()
    paint(
        shine,
        poly(ellipse_pts(cx - 13 * (1 if side == "l" else -1), cy - 18, 9, 12, rot=0.35)),
        "#FFFFFF",
    )
    paint(
        shine, poly(ellipse_pts(cx + 12 * (1 if side == "l" else -1), cy + 20, 4.5, 4.5)), "#FFFFFF"
    )
    sx, sy = cx + 14 * (1 if side == "l" else -1), cy - 6
    star = [
        (sx, sy - 7),
        (sx + 2, sy - 2),
        (sx + 7, sy),
        (sx + 2, sy + 2),
        (sx, sy + 7),
        (sx - 2, sy + 2),
        (sx - 7, sy),
        (sx - 2, sy - 2),
    ]
    paint(shine, poly(star), "#FFFFFF", 0.9)
    upper = new_layer()
    lid = upper_lid(side)
    paint(upper, stroke(lid, taper(len(lid), 7.5, 7.0, 2.2, 0.25)), LASH)
    out = -1 if side == "l" else 1
    (ox, oy), (ax, ay) = lid[0], lid[5]
    wing = [(ax, ay - 3), (ox + out * 17, oy + 8), (ox + out * 4, oy + 5), (ox, oy + 3)]
    paint(upper, poly(wing), LASH)
    wing2 = [lid[9], (ox + out * 15, oy - 7), (ax, ay + 2)]
    paint(upper, poly(wing2), LASH)
    crease = new_layer()
    paint(
        crease,
        stroke(refine.lid_crease(side, lid), taper(len(lid) - 14, 0.4, 2.2, 0.4)),
        SKIN_LINE,
        0.75,
    )
    lower = new_layer()
    low = lower_lid(side)[6:-8]
    paint(lower, stroke(low, taper(len(low), 0.6, 2.6, 0.6)), "#7A5A7E", 0.85)
    smile = new_layer()
    x_in, x_out = _mirror_x(EYE_INNER_L[0], side), _mirror_x(EYE_OUTER_L[0], side)
    arc = bez(
        (x_out, 622),
        (x_out + (x_in - x_out) * 0.2, 586),
        (x_out + (x_in - x_out) * 0.8, 586),
        (x_in, 624),
        30,
    )
    paint(smile, stroke(arc, taper(30, 2.5, 7, 2.5)), LASH)
    return {
        f"eye_white_{side}": finish(white),
        f"iris_{side}": finish(iris),
        f"highlight_{side}": finish(shine),
        f"lower_lash_{side}": finish(lower),
        f"upper_lash_{side}": finish(upper),
        f"smile_eye_{side}": finish(smile),
        f"lid_crease_{side}": finish(crease),
    }


def draw_brow(side: str) -> dict[str, np.ndarray]:
    layer = new_layer()
    pts = bez((400, 534), (414, 520), (448, 514), (474, 522), 30)
    if side == "r":
        pts = mirror(pts)
    paint(layer, stroke(pts, taper(30, 2.5, 7.5, 4.0, 0.35)), "#5A4B9E", 0.92)
    return {f"brow_{side}": finish(layer)}


# ---- front hair -----------------------------------------------------------------------------
def draw_bangs() -> dict[str, np.ndarray]:
    layer = new_layer()
    shape = _bangs_shape()
    mask = poly(shape)
    paint_gradient(layer, mask, (CX, 290), "#DCD7F7", (CX, 610), HAIR_SHADE)
    tips = _bang_tips()
    for (_x0, y0), (x1, y1), _after in zip(tips, tips[1:], tips[2:], strict=False):
        if y1 < y0:
            continue
        crease = bez(
            (CX + (x1 - CX) * 0.3, 296),
            (CX + (x1 - CX) * 0.62, 380),
            (x1, y1 - 90),
            (x1, y1 - 6),
            30,
        )
        paint(layer, clip(stroke(crease, taper(30, 0.3, 4.0, 0.5, 0.75)), mask), HAIR_DEEP, 0.5)
        for dx in (-9, 9):
            hint = bez(
                (CX + (x1 + dx - CX) * 0.34, 310),
                (CX + (x1 + dx - CX) * 0.64, 390),
                (x1 + dx * 1.6, y1 - 120),
                (x1 + dx * 2.2, y1 - 60),
                24,
            )
            paint(layer, clip(stroke(hint, taper(24, 0.3, 2.2, 0.3, 0.6)), mask), HAIR_SHADE, 0.45)
    ring = chain(bez((326, 440), (396, 396), (628, 396), (698, 440)))
    ring_band = stroke(ring, taper(len(ring), 3, 12, 3))
    zig = [(x, y + (8 if i % 2 else -2)) for i, (x, y) in enumerate(ring)]
    paint(
        layer, clip(minus(ring_band, poly(zig + [(698, 500), (326, 500)])), mask), HAIR_LIGHT, 0.8
    )
    paint(
        layer,
        clip(
            blur(
                poly(
                    bez((330, 300), (400, 290), (620, 290), (694, 330)) + [(694, 360), (330, 360)]
                ),
                18,
            ),
            mask,
        ),
        HAIR_LIGHT,
        0.35,
    )
    refine.bangs_detail(layer, mask)
    paint(layer, line(shape[:BANG_EDGE_POINTS], 3.0), HAIR_LINE)
    return {"bangs": finish(layer)}


def _side_lock_shape():
    outer = bez((300, 470), (282, 640), (300, 820), (292, 1010), 50)
    inner = bez((292, 1010), (330, 860), (346, 700), (352, 486), 50)
    return chain(outer, inner[1:], bez((352, 486), (340, 460), (316, 452), (300, 470), 12)[1:])


def draw_side_locks() -> dict[str, np.ndarray]:
    out = {}
    for side in ("l", "r"):
        layer = new_layer()
        shape = _side_lock_shape()
        if side == "r":
            shape = mirror(shape)
        mask = poly(shape)
        x_mid = 320 if side == "l" else W - 320
        paint_gradient(layer, mask, (x_mid, 480), HAIR, (x_mid, 1010), HAIR_TIP)
        crease = bez((326, 520), (320, 700), (318, 860), (302, 980), 40)
        if side == "r":
            crease = mirror(crease)
        paint(layer, clip(stroke(crease, taper(40, 0.5, 4, 0.5)), mask), HAIR_DEEP, 0.5)
        refine.side_lock_detail(layer, mask, side)
        paint(layer, minus(line(shape + [shape[0]], 3.0), mask), HAIR_LINE)
        paint(layer, clip(line(shape, 2.4), mask), HAIR_LINE, 0.7)
        out[f"side_lock_{side}"] = finish(layer)
    return out


def draw_ahoge() -> dict[str, np.ndarray]:
    layer = new_layer()
    spine = chain(
        bez((504, 300), (494, 262), (520, 226), (556, 230)),
        bez((556, 230), (576, 234), (574, 258), (556, 262)),
    )
    shape = stroke(spine, taper(len(spine), 16, 10, 1.5, 0.2))
    paint_gradient(layer, shape, (504, 300), "#DCD7F7", (560, 234), HAIR_TIP)
    outline = chain(spine)
    paint(layer, minus(stroke(outline, taper(len(outline), 20, 14, 3.5, 0.2)), shape), HAIR_LINE)
    return {"ahoge": finish(layer)}


def draw_hairpin() -> dict[str, np.ndarray]:
    layer = new_layer()
    cx, cy = 372.0, 440.0
    paint(layer, poly(ellipse_pts(cx, cy, 25, 25)), GOLD_DARK)
    paint(layer, poly(ellipse_pts(cx, cy, 21, 21)), GOLD)
    lens = poly(ellipse_pts(cx, cy, 15, 15))
    paint_gradient(layer, lens, (cx, cy - 15), LENS_TOP, (cx, cy + 15), LENS_BOTTOM)
    for k in range(6):
        a0 = k * np.pi / 3
        blade = [
            (cx + 15 * np.cos(a0), cy + 15 * np.sin(a0)),
            (cx + 15 * np.cos(a0 + np.pi / 3), cy + 15 * np.sin(a0 + np.pi / 3)),
            (cx + 6 * np.cos(a0 + np.pi / 2), cy + 6 * np.sin(a0 + np.pi / 2)),
        ]
        paint(layer, clip(line(blade, 1.4), lens), "#1E3C8C", 0.7)
    paint(layer, poly(ellipse_pts(cx - 6, cy - 7, 4, 3, rot=-0.6)), "#FFFFFF", 0.95)
    paint(
        layer, line(ellipse_pts(cx, cy, 25, 25) + [ellipse_pts(cx, cy, 25, 25)[0]], 2.2), "#7A5A22"
    )
    for dx, dy in ((30, -6), (26, 16)):
        paint(layer, poly(ellipse_pts(cx + dx, cy + dy, 5, 5)), GOLD)
    return {"hairpin": finish(layer)}


def all_layers() -> dict[str, np.ndarray]:
    """Every layer, bottom to top."""
    from body_arms import draw_arm, draw_body

    layers: dict[str, np.ndarray] = {}
    for part in (
        draw_back_hair(),
        draw_body(),
        draw_arm("l"),
        draw_arm("r"),
        draw_collar(),
        draw_ribbon(),
        draw_neck_shadow(),
        draw_face(),
        draw_bang_shadow(),
        draw_blush(),
        draw_nose(),
        draw_mouth(),
    ):
        layers.update(part)
    for side in ("l", "r"):
        eye = draw_eye(side)
        layers.update(
            {k: v for k, v in eye.items() if k.startswith(("eye_white", "iris", "highlight"))}
        )
    for side in ("l", "r"):
        eye = draw_eye(side)
        layers.update(
            {
                k: v
                for k, v in eye.items()
                if k.startswith(("lower_lash", "upper_lash", "smile_eye", "lid_crease"))
            }
        )
    for part in (
        draw_side_locks(),
        draw_bangs(),
        draw_ahoge(),
        draw_brow("l"),
        draw_brow("r"),
        draw_hairpin(),
    ):
        layers.update(part)
    return layers


LAYER_ORDER = [
    "back_hair",
    "body",
    "upper_arm_l",
    "upper_arm_r",
    "forearm_l",
    "forearm_r",
    "hand_l",
    "hand_r",
    "hand_open_l",
    "hand_open_r",
    "collar",
    "ribbon",
    "neck_shadow",
    "face",
    "bang_shadow",
    "blush",
    "nose",
    "mouth_inside",
    "mouth_line",
    "eye_white_l",
    "iris_l",
    "highlight_l",
    "eye_white_r",
    "iris_r",
    "highlight_r",
    "lid_crease_l",
    "lower_lash_l",
    "upper_lash_l",
    "smile_eye_l",
    "lid_crease_r",
    "lower_lash_r",
    "upper_lash_r",
    "smile_eye_r",
    "side_lock_l",
    "side_lock_r",
    "bangs",
    "ahoge",
    "brow_l",
    "brow_r",
    "hairpin",
]
