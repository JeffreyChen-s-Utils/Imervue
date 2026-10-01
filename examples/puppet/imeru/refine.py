"""Second-pass detail for Imeru's layers: hair, irises, eyelid creases, face and clothes.

Each function draws onto a layer ``art.py`` already painted (before ``finish``),
so the detail shares that layer's mesh and moves with it.
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
    line,
    mirror,
    paint,
    paint_gradient,
    poly,
    stroke,
    taper,
)

CX = W / 2


def hair_strand_lights(layer, mask, strands, color="#FFFFFF", alpha=0.45) -> None:
    """Thin light streaks along the strands, clipped to the hair."""
    for points, width in strands:
        paint(
            layer,
            clip(stroke(points, taper(len(points), 0.3, width, 0.3, 0.45)), mask),
            color,
            alpha,
        )


def back_hair_detail(layer, mask) -> None:
    rim = [(x, y) for x, y in bez((300, 470), (284, 700), (258, 900), (252, 1150), 40)]
    paint(layer, clip(stroke(rim, taper(40, 2, 9, 2, 0.4)), mask), "#E9E5FF", 0.55)
    paint(layer, clip(stroke(mirror(rim), taper(40, 2, 9, 2, 0.4)), mask), "#E9E5FF", 0.35)
    tips_shade = [(236, 1250), (W - 236, 1250), (W - 236, 1410), (236, 1410)]
    paint_gradient(
        layer, clip(poly(tips_shade), mask), (CX, 1250), "#94DCE8", (CX, 1410), "#5FA9C2", alpha=0.6
    )
    strands = []
    for x0, bend in ((286, -14), (318, -10), (706, 10), (738, 14)):
        strands.append(
            (
                bez(
                    (x0, 620), (x0 + bend, 820), (x0 + bend * 2, 1020), (x0 + bend * 2.4, 1200), 40
                ),
                3.2,
            )
        )
    hair_strand_lights(layer, mask, strands, "#F4F1FF", 0.5)


def bangs_detail(layer, mask) -> None:
    band = chain(
        bez((318, 470), (400, 430), (624, 430), (706, 470), 40),
        bez((706, 500), (624, 470), (400, 470), (318, 500), 40),
    )
    paint(layer, clip(blur(poly(band), 10), mask), "#9488D8", 0.35)
    strands = []
    for x_tip, y_tip in ((360, 520), (418, 510), (470, 520), (552, 512), (612, 508), (664, 520)):
        top = (CX + (x_tip - CX) * 0.32, 300)
        strands.append(
            (
                bez(
                    top,
                    (CX + (x_tip - CX) * 0.6, 360),
                    (x_tip, y_tip - 110),
                    (x_tip, y_tip - 40),
                    30,
                ),
                2.6,
            )
        )
    hair_strand_lights(layer, mask, strands, "#FFFFFF", 0.4)
    paint_gradient(layer, mask, (CX, 480), (124, 111, 200, 0), (CX, 600), (124, 111, 200, 150))
    gloss = blur(poly(ellipse_pts(430, 345, 60, 18, rot=-0.25)), 6)
    paint(layer, clip(gloss, mask), "#FFFFFF", 0.35)


def side_lock_detail(layer, mask, side: str) -> None:
    light = bez((314, 520), (304, 680), (306, 820), (300, 940), 36)
    shade = bez((346, 500), (338, 660), (332, 820), (312, 990), 36)
    if side == "r":
        light, shade = mirror(light), mirror(shade)
    paint(layer, clip(stroke(light, taper(36, 0.4, 3.4, 0.4, 0.4)), mask), "#FFFFFF", 0.5)
    paint(layer, clip(blur(stroke(shade, taper(36, 6, 12, 2, 0.4)), 4), mask), "#7C6FC8", 0.45)


def iris_detail(layer, iris_mask, cx: float, cy: float, rx: float, ry: float) -> None:
    glow = blur(poly(ellipse_pts(cx, cy + ry * 0.55, rx * 0.8, ry * 0.4)), 4)
    paint(layer, clip(glow, iris_mask), "#B8FFF2", 0.55)
    for angle in np.linspace(0, 2 * np.pi, 18, endpoint=False):
        inner = (cx + 14 * np.cos(angle), cy + 2 + 18 * np.sin(angle))
        outer = (cx + (rx - 3) * np.cos(angle), cy + (ry - 3) * np.sin(angle))
        paint(layer, clip(line([inner, outer], 1.1), iris_mask), "#7FE8DA", 0.35)
    ring = ellipse_pts(cx, cy + 2, 14.5, 18.5)
    paint(layer, line(ring + [ring[0]], 1.6), "#3E58B8", 0.8)


def lid_crease(side: str, upper_lid_points) -> np.ndarray:
    """Points of the double-eyelid crease: the middle of the upper lid, raised."""
    pts = upper_lid_points[8:-6]
    return [(x, y - 11 - 4 * np.sin(np.pi * i / (len(pts) - 1))) for i, (x, y) in enumerate(pts)]


def nose_and_lip(layer) -> None:
    paint(layer, poly(ellipse_pts(519, 652, 2.6, 4.2, rot=0.3)), "#FFFFFF", 0.8)


def collar_detail(layer, mask) -> None:
    glow = chain(bez((330, 878), (400, 870), (440, 860), (462, 846), 20), [(470, 900), (330, 930)])
    paint(layer, clip(blur(poly(glow), 10), mask), "#5A6AA6", 0.45)
    paint(layer, clip(blur(poly(mirror(glow)), 10), mask), "#5A6AA6", 0.3)
    under_hair = [(296, 900), (360, 900), (352, 1000), (300, 1010)]
    paint(layer, clip(blur(poly(under_hair), 12), mask), "#141B36", 0.5)
    paint(layer, clip(blur(poly(mirror(under_hair)), 12), mask), "#141B36", 0.5)


def ribbon_detail(layer, loops) -> None:
    for loop in loops:
        mask = poly(loop)
        xs = [p[0] for p in loop]
        ys = [p[1] for p in loop]
        cx, cy = (min(xs) + max(xs)) / 2, min(ys) + (max(ys) - min(ys)) * 0.35
        paint(
            layer,
            clip(blur(poly(ellipse_pts(cx, cy, (max(xs) - min(xs)) * 0.28, 5)), 2), mask),
            "#FFD2C8",
            0.7,
        )
