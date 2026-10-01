"""Imeru's torso, skirt and two-segment arms (upper arm, forearm with cuff, hand), with cel shading.

Arms are separate layers so the rig can raise and bend them; ``SHOULDER`` and
``ELBOW`` are the pivots (the viewer's-left arm; the other is mirrored).
"""

from __future__ import annotations

import numpy as np

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
BLOUSE = "#FAFAFF"
BLOUSE_MID = "#E7E9F8"
BLOUSE_SHADE = "#CDD2EE"
BLOUSE_DEEP = "#B3B9E0"
NAVY = "#27335E"
NAVY_LIGHT = "#3A4A80"
NAVY_DEEP = "#18213F"
SKIN = "#FFEDE3"
SKIN_SHADE = "#F5C9BD"
SKIN_LINE = "#C08377"
LINE_DARK = "#3C3563"

SHOULDER = (300.0, 905.0)
ELBOW = (288.0, 1162.0)


def _side(points, side: str):
    return points if side == "l" else mirror(points)


def torso_shape():
    left = chain(
        bez((470, 820), (440, 842), (372, 858), (330, 878)),
        bez((330, 878), (322, 950), (330, 1060), (336, 1150)),
        bez((336, 1150), (342, 1260), (350, 1360), (344, 1440)),
        [(344, 1440), (330, 1536)],
    )
    return chain(left, [(330, 1536), (W - 330, 1536)], mirror(left)[::-1])


def draw_body() -> dict[str, np.ndarray]:
    layer = new_layer()
    neck = chain(
        bez((476, 690), (474, 760), (470, 800), (462, 850)),
        [(462, 850), (562, 850)],
        bez((562, 850), (554, 800), (550, 760), (548, 690)),
    )
    neck_mask = poly(neck)
    paint(layer, neck_mask, SKIN)
    paint_gradient(
        layer,
        clip(blur(poly([(476, 690), (548, 690), (552, 800), (472, 800)]), 6), neck_mask),
        (CX, 700),
        SKIN_SHADE,
        (CX, 805),
        SKIN,
        alpha=0.95,
    )
    paint(
        layer,
        clip(blur(poly([(536, 700), (560, 700), (566, 860), (540, 860)]), 4), neck_mask),
        SKIN_SHADE,
        0.7,
    )
    shape = torso_shape()
    torso = poly(shape)
    paint_gradient(layer, torso, (CX, 860), BLOUSE, (CX, 1440), BLOUSE_MID)
    for side in ("l", "r"):
        edge = _side(
            chain(
                bez((330, 878), (322, 950), (330, 1060), (336, 1150)),
                bez((336, 1150), (342, 1260), (350, 1360), (344, 1440)),
                [(400, 1440), (392, 1150), (384, 900)],
            ),
            side,
        )
        paint(layer, clip(blur(poly(edge), 12), torso), BLOUSE_SHADE, 0.85)
        hair_shadow = _side(
            bez((300, 880), (350, 900), (372, 960), (360, 1010), 30)
            + [(330, 1010), (318, 960), (300, 900)],
            side,
        )
        paint(layer, clip(blur(poly(hair_shadow), 10), torso), "#C9C3EC", 0.6)
    for x0, bend in ((430, -8), (468, 4), (556, -4), (594, 8)):
        crease = bez((x0, 1080), (x0 + bend, 1180), (x0 + bend * 2, 1300), (x0 + bend, 1430), 30)
        paint(layer, clip(stroke(crease, taper(30, 0.3, 3.6, 0.6, 0.6)), torso), BLOUSE_SHADE, 0.75)
    tuck = chain(
        bez((344, 1408), (430, 1424), (594, 1424), (680, 1408)), [(680, 1440), (344, 1440)]
    )
    paint(layer, clip(blur(poly(tuck), 6), torso), BLOUSE_SHADE, 0.8)
    for x in (380, 420, 470, 512, 556, 604, 648):
        fold = [(x - 6, 1410), (x, 1438)]
        paint(layer, clip(line(fold, 2.0), torso), BLOUSE_DEEP, 0.55)
    _skirt(layer)
    paint(layer, line(shape[:-2], 2.8), LINE_DARK, 0.8)
    paint(layer, line(neck[:40], 2.6), SKIN_LINE)
    paint(layer, line(neck[-40:], 2.6), SKIN_LINE)
    return {"body": finish(layer)}


def _skirt(layer) -> None:
    top = bez((340, 1440), (430, 1430), (594, 1430), (684, 1440), 40)
    skirt = chain(top, [(706, 1536), (318, 1536)])
    mask = poly(skirt)
    paint(layer, mask, NAVY)
    xs = np.linspace(340, 684, 9)
    for i, (x0, x1) in enumerate(zip(xs, xs[1:], strict=False)):
        spread = 0.12
        pleat = [
            (x0, 1446),
            (x1, 1446),
            (x1 + (x1 - CX) * spread, 1536),
            (x0 + (x0 - CX) * spread, 1536),
        ]
        paint_gradient(
            layer,
            clip(poly(pleat), mask),
            (x0, 1446),
            NAVY_LIGHT if i % 2 else NAVY,
            (x1, 1536),
            NAVY if i % 2 else NAVY_DEEP,
        )
        paint(
            layer,
            clip(line([(x0, 1450), (x0 + (x0 - CX) * spread, 1536)], 1.8), mask),
            NAVY_DEEP,
            0.9,
        )
    band = chain(top, bez((684, 1456), (594, 1446), (430, 1446), (340, 1456), 40))
    paint(layer, poly(band), NAVY_DEEP, 0.85)
    paint(layer, line(top, 2.4), "#10162D", 0.9)


def _upper_arm_shape():
    return chain(
        bez((330, 875), (290, 880), (266, 930), (262, 1000)),
        bez((262, 1000), (258, 1060), (254, 1120), (256, 1170)),
        bez((256, 1170), (262, 1196), (312, 1198), (318, 1176)),
        bez((318, 1176), (324, 1100), (332, 1000), (334, 940)),
        bez((334, 940), (336, 905), (334, 885), (330, 875)),
    )


def _forearm_shape():
    return chain(
        bez((258, 1150), (254, 1230), (248, 1320), (250, 1388)),
        [(250, 1388), (322, 1394)],
        bez((322, 1394), (324, 1320), (322, 1230), (318, 1150)),
        bez((318, 1150), (312, 1124), (264, 1124), (258, 1150)),
    )


def _hand_shape():
    return chain(
        bez((266, 1384), (258, 1410), (260, 1440), (270, 1462)),
        bez((270, 1462), (280, 1480), (302, 1482), (310, 1462)),
        bez((310, 1462), (318, 1446), (330, 1440), (328, 1426)),
        bez((328, 1426), (326, 1414), (318, 1414), (316, 1404)),
        [(316, 1404), (314, 1386), (266, 1384)],
    )


def _sleeve_shading(layer, mask, outer_x: float, inner_x: float, y0: float, y1: float) -> None:
    paint_gradient(layer, mask, (outer_x, y0), BLOUSE_SHADE, (inner_x, y0), BLOUSE)
    rim = [(inner_x - 10, y0), (inner_x + 6, y0), (inner_x + 6, y1), (inner_x - 10, y1)]
    paint(layer, clip(blur(poly(rim), 8), mask), BLOUSE_SHADE, 0.6)


def draw_arm(side: str) -> dict[str, np.ndarray]:
    outer, inner = (250.0, 334.0) if side == "l" else (W - 250.0, W - 334.0)
    upper = new_layer()
    shape = _side(_upper_arm_shape(), side)
    mask = poly(shape)
    paint(upper, mask, BLOUSE)
    _sleeve_shading(upper, mask, outer, inner, 900, 1190)
    for k, y in enumerate((1110, 1140)):
        fold = _side(bez((268, y), (284, y + 10), (300, y + 8), (314, y - 4 + k * 6), 16), side)
        paint(upper, clip(stroke(fold, taper(16, 0.4, 3.2, 0.4)), mask), BLOUSE_DEEP, 0.6)
    paint(upper, line(shape + [shape[0]], 2.6), LINE_DARK, 0.8)
    fore = new_layer()
    shape = _side(_forearm_shape(), side)
    mask = poly(shape)
    paint(fore, mask, BLOUSE)
    _sleeve_shading(fore, mask, outer, inner, 1130, 1394)
    cuff = _side([(249, 1346), (323, 1352), (322, 1394), (250, 1388)], side)
    cuff_mask = clip(poly(cuff), mask)
    paint(fore, cuff_mask, "#F2F3FC")
    for y in (1360, 1372):
        stripe = _side([(250, y), (323, y + 5)], side)
        paint(fore, clip(line(stripe, 3.0), mask), NAVY, 0.95)
    button = _side(ellipse_pts(310, 1384, 4, 4), side)
    paint(fore, poly(button), "#E9C374")
    paint(fore, line(shape + [shape[0]], 2.6), LINE_DARK, 0.8)
    hand = new_layer()
    shape = _side(_hand_shape(), side)
    mask = poly(shape)
    paint(hand, mask, SKIN)
    shade = _side([(258, 1384), (276, 1384), (282, 1480), (258, 1470)], side)
    paint(hand, clip(blur(poly(shade), 6), mask), SKIN_SHADE, 0.85)
    for x in (282, 294):
        finger = _side([(x, 1440), (x + 2, 1468)], side)
        paint(hand, clip(line(finger, 1.6), mask), SKIN_LINE, 0.7)
    paint(hand, line(shape + [shape[0]], 2.4), SKIN_LINE)
    return {
        f"upper_arm_{side}": finish(upper),
        f"forearm_{side}": finish(fore),
        f"hand_{side}": finish(hand),
        f"hand_open_{side}": draw_open_hand(side),
    }


def draw_open_hand(side: str) -> np.ndarray:
    """An open hand, palm to the viewer, hanging from the wrist: shown once the arm is raised."""
    layer = new_layer()
    palm = _side(
        chain(
            bez((264, 1388), (258, 1404), (260, 1424), (266, 1436)),
            [(266, 1436), (312, 1440)],
            bez((312, 1440), (318, 1420), (318, 1402), (316, 1388)),
        ),
        side,
    )
    fingers = []
    for x0, x1, length in ((268, 263, 30), (279, 278, 36), (291, 293, 36), (302, 307, 31)):
        fingers.append(_side([(x0, 1430), (x1, 1430 + length)], side))
    thumb = _side(bez((312, 1404), (324, 1408), (332, 1418), (336, 1432), 12), side)
    shape = poly(palm)
    for finger in fingers:
        shape = line(finger, 10.5, shape)
    shape = stroke(thumb, taper(12, 11, 10, 8), shape)
    paint(layer, shape, SKIN)
    shade = _side([(258, 1388), (274, 1388), (276, 1440), (258, 1436)], side)
    paint(layer, clip(blur(poly(shade), 5), shape), SKIN_SHADE, 0.8)
    paint(layer, minus(line_mask_dilate(shape), shape), SKIN_LINE)
    for finger in fingers[1:]:
        x = finger[0][0] - (5 if side == "l" else -5)
        paint(layer, clip(line([(x, 1432), (x, 1446)], 1.4), shape), SKIN_LINE, 0.6)
    return finish(layer)


def line_mask_dilate(mask):
    """*mask* grown by about 1.3 px, for an outline drawn just outside a shape."""
    from PIL import ImageFilter

    return mask.filter(ImageFilter.MaxFilter(9))
