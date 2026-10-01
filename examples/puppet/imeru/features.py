"""Imeru's painted face features: eyes, brows, blush, nose and mouth.

They are 2D, like a 3D game character's face textures.

The 3D render gives the head its shape; the features sit on it as flat layers the rig can
blink, turn and open. The eye geometry (``upper_lid`` / ``lower_lid``, the iris position)
comes from ``art.py`` so the rig closes the lids it was built for.
"""
from __future__ import annotations

import numpy as np

from art import (
    CX,
    EYE_INNER_L,
    EYE_OUTER_L,
    IRIS_L,
    MOUTH_HALF,
    MOUTH_Y,
    W,
    lower_lid,
    mouth_inside_shape,
    upper_lid,
)
from draw import (
    bez,
    blur,
    chain,
    clip,
    ellipse_pts,
    finish,
    line,
    mirror,
    new_layer,
    paint,
    paint_gradient,
    poly,
    stroke,
    taper,
)

LASH = "#211936"
LASH_WARM = "#4A2E52"
SKIN_LINE = "#C9857A"
IRIS_DEEP, IRIS_TOP, IRIS_MID, IRIS_LOW = "#141F57", "#1F3C86", "#2C93B4", "#86F3E2"
IRIS_RIM = "#121A4A"
PUPIL = "#0E1236"
GLOW = "#D2FFF7"


def _mx(x: float, side: str) -> float:
    return x if side == "l" else W - x


def _sclera(side: str):
    return chain(upper_lid(side), lower_lid(side)[1:])


def _eye_white(side: str):
    sclera = poly(_sclera(side))
    layer = new_layer()
    paint(layer, sclera, "#FFFFFF")
    under_lid = poly([(x, y + 30) for x, y in upper_lid(side)] + upper_lid(side)[::-1])
    paint(layer, clip(blur(under_lid, 7), sclera), "#BDB8E6", 0.85)
    inner = _mx(EYE_INNER_L[0], side)
    paint(layer, clip(blur(poly(ellipse_pts(inner, 618, 12, 16)), 6), sclera), "#F7C9CF", 0.6)
    return layer


def _iris(side: str):
    cx, cy, rx, ry = IRIS_L
    cx = _mx(cx, side)
    mask = poly(ellipse_pts(cx, cy, rx, ry))
    layer = new_layer()
    paint_gradient(layer, mask, (cx, cy - ry), IRIS_TOP, (cx, cy + ry * 0.2), IRIS_MID)
    paint_gradient(layer, clip(poly([(cx - rx, cy), (cx + rx, cy), (cx + rx, cy + ry),
                                     (cx - rx, cy + ry)]), mask),
                   (cx, cy), IRIS_MID, (cx, cy + ry), IRIS_LOW)
    for angle in np.linspace(0, 2 * np.pi, 28, endpoint=False):
        inner = (cx + 13 * np.cos(angle), cy + 2 + 17 * np.sin(angle))
        outer = (cx + (rx - 4) * np.cos(angle), cy + (ry - 4) * np.sin(angle))
        tone = "#A6FFF0" if np.sin(angle) > -0.2 else "#5FA6D6"
        paint(layer, clip(line([inner, outer], 1.0), mask), tone, 0.35)
    glow = chain(bez((cx - rx * 0.78, cy + ry * 0.32), (cx - rx * 0.4, cy + ry * 0.62),
                     (cx + rx * 0.4, cy + ry * 0.62), (cx + rx * 0.78, cy + ry * 0.32), 24),
                 bez((cx + rx * 0.78, cy + ry * 0.32), (cx + rx * 0.5, cy + ry * 0.98),
                     (cx - rx * 0.5, cy + ry * 0.98), (cx - rx * 0.78, cy + ry * 0.32), 24))
    paint(layer, clip(blur(poly(glow), 3), mask), GLOW, 0.75)
    top_shadow = poly(ellipse_pts(cx, cy - ry * 0.75, rx * 1.2, ry * 0.62))
    paint(layer, clip(blur(top_shadow, 5), mask), IRIS_DEEP, 0.75)
    ring = ellipse_pts(cx, cy + 2, 17.5, 22)
    paint(layer, clip(line(ring + [ring[0]], 2.0), mask), "#4FD0D8", 0.7)
    paint(layer, poly(ellipse_pts(cx, cy + 2, 11.5, 15.5)), PUPIL)
    paint(layer, clip(blur(poly(ellipse_pts(cx, cy + 9, 7, 6)), 3),
                      poly(ellipse_pts(cx, cy + 2, 11.5, 15.5))), "#3B3F8F", 0.7)
    rim = ellipse_pts(cx, cy, rx, ry)
    paint(layer, line(rim + [rim[0]], 3.0), IRIS_RIM, 0.95)
    return layer


def _highlights(side: str):
    cx, cy, rx, ry = IRIS_L
    cx = _mx(cx, side)
    s = 1 if side == "l" else -1
    layer = new_layer()
    paint(layer, poly(ellipse_pts(cx - 12 * s, cy - 17, 10, 13.5, rot=0.35 * s)), "#FFFFFF")
    paint(layer, poly(ellipse_pts(cx + 13 * s, cy + 19, 4.6, 4.6)), "#FFFFFF")
    paint(layer, poly(ellipse_pts(cx + 4 * s, cy + 27, 2.2, 2.2)), "#FFFFFF", 0.8)
    arc = bez((cx - rx * 0.55, cy + ry * 0.62), (cx - rx * 0.2, cy + ry * 0.8),
              (cx + rx * 0.2, cy + ry * 0.8), (cx + rx * 0.5, cy + ry * 0.6), 20)
    paint(layer, stroke(arc, taper(20, 0.3, 1.8, 0.3)), "#FFFFFF", 0.65)
    sx, sy = cx + 15 * s, cy - 7
    star = [(sx, sy - 8), (sx + 2.2, sy - 2.2), (sx + 8, sy), (sx + 2.2, sy + 2.2),
            (sx, sy + 8), (sx - 2.2, sy + 2.2), (sx - 8, sy), (sx - 2.2, sy - 2.2)]
    paint(layer, poly(star), "#FFFFFF", 0.95)
    return layer


def _upper_lash(side: str):
    lid = upper_lid(side)
    layer = new_layer()
    paint(layer, stroke(lid, taper(len(lid), 8.5, 7.8, 2.0, 0.22)), LASH)
    paint(layer, stroke(lid[8:-4], taper(len(lid) - 12, 0.4, 1.6, 0.4)), LASH_WARM, 0.7)
    out = -1 if side == "l" else 1
    (ox, oy), (ax, ay) = lid[0], lid[5]
    paint(layer, poly([(ax, ay - 3), (ox + out * 19, oy + 9), (ox + out * 5, oy + 6),
                       (ox, oy + 3)]), LASH)
    for k, (dy, length) in enumerate(((-2, 15), (-6, 13), (-9, 10))):
        base = lid[2 + k * 4]
        tip = (base[0] + out * length, base[1] - 7 - dy * 0.3 - k * 2)
        spike = bez(base, (base[0] + out * length * 0.4, base[1] - 2),
                    (tip[0] - out * 3, tip[1] + 2), tip, 12)
        paint(layer, stroke(spike, taper(12, 3.2, 2.4, 0.3, 0.2)), LASH)
    return layer


def _lower_lash(side: str):
    low = lower_lid(side)[5:-6]
    layer = new_layer()
    paint(layer, stroke(low, taper(len(low), 0.5, 2.2, 1.2, 0.7)), "#6E4F7C", 0.8)
    out = -1 if side == "l" else 1
    (ox, oy) = lower_lid(side)[-4]
    paint(layer, stroke(bez((ox, oy), (ox + out * 4, oy + 3), (ox + out * 7, oy + 5),
                            (ox + out * 9, oy + 9), 10), taper(10, 1.6, 1.2, 0.3)),
          "#6E4F7C", 0.8)
    return layer


def _lid_crease(side: str):
    lid = upper_lid(side)
    pts = lid[8:-6]
    crease = [(x, y - 12 - 4 * np.sin(np.pi * i / (len(pts) - 1))) for i, (x, y) in
              enumerate(pts)]
    layer = new_layer()
    lid_shadow = poly(crease + lid[8:-6][::-1])
    paint(layer, blur(lid_shadow, 3), "#E9A9A6", 0.35)
    paint(layer, stroke(crease, taper(len(crease), 0.3, 1.9, 0.3)), SKIN_LINE, 0.75)
    return layer


def _smile_eye(side: str):
    x_in, x_out = _mx(EYE_INNER_L[0], side), _mx(EYE_OUTER_L[0], side)
    arc = bez((x_out, 622), (x_out + (x_in - x_out) * 0.2, 586),
              (x_out + (x_in - x_out) * 0.8, 586), (x_in, 624), 30)
    layer = new_layer()
    paint(layer, stroke(arc, taper(30, 2.5, 7.5, 2.5)), LASH)
    return layer


def draw_eye(side: str) -> dict[str, np.ndarray]:
    """Every layer of one eye: white, iris, highlights, lashes, lid crease, happy-closed arc."""
    return {
        f"eye_white_{side}": finish(_eye_white(side)),
        f"iris_{side}": finish(_iris(side)),
        f"highlight_{side}": finish(_highlights(side)),
        f"lower_lash_{side}": finish(_lower_lash(side)),
        f"upper_lash_{side}": finish(_upper_lash(side)),
        f"smile_eye_{side}": finish(_smile_eye(side)),
        f"lid_crease_{side}": finish(_lid_crease(side)),
    }


def draw_brow(side: str) -> dict[str, np.ndarray]:
    """A fine brow, darker at its inner end."""
    pts = bez((398, 534), (414, 521), (448, 515), (476, 522), 30)
    if side == "r":
        pts = mirror(pts)
    layer = new_layer()
    paint(layer, stroke(pts, taper(30, 2.0, 5.6, 3.6, 0.3)), "#6A58B4", 0.9)
    return {f"brow_{side}": finish(layer)}


def draw_blush() -> dict[str, np.ndarray]:
    """Soft rosy cheeks."""
    layer = new_layer()
    for x in (430.0, W - 430.0):
        paint(layer, blur(poly(ellipse_pts(x, 668, 40, 16)), 9), "#FF8FA3", 0.62)
        paint(layer, blur(poly(ellipse_pts(x, 667, 18, 7)), 5), "#FF7A92", 0.35)
    return {"blush": finish(layer)}


def draw_nose() -> dict[str, np.ndarray]:
    """A small shaded nose tip and its highlight."""
    layer = new_layer()
    paint(layer, line(bez((514, 656), (512, 662), (510, 667), (506, 670), 10), 2.2),
          SKIN_LINE, 0.8)
    paint(layer, poly(ellipse_pts(519, 652, 2.4, 4.0, rot=0.3)), "#FFFFFF", 0.8)
    return {"nose": finish(layer)}


def draw_mouth() -> dict[str, np.ndarray]:
    """The open mouth (tongue, upper teeth line) under a fine upper lip."""
    inside = new_layer()
    shape = mouth_inside_shape()
    mask = poly(shape)
    paint(inside, mask, "#7A2B40")
    paint(inside, clip(poly(ellipse_pts(CX + 2, MOUTH_Y + 25, 15, 9)), mask), "#F2899A")
    paint(inside, clip(poly([(CX - MOUTH_HALF, MOUTH_Y - 4), (CX + MOUTH_HALF, MOUTH_Y - 4),
                             (CX + MOUTH_HALF, MOUTH_Y + 4), (CX - MOUTH_HALF, MOUTH_Y + 4)]),
                       mask), "#FFFFFF", 0.9)
    paint(inside, line(shape + [shape[0]], 2.0), "#5E1E30")
    upper = new_layer()
    lip = bez((CX - MOUTH_HALF - 3, MOUTH_Y - 1), (CX - 8, MOUTH_Y + 4),
              (CX + 8, MOUTH_Y + 4), (CX + MOUTH_HALF + 3, MOUTH_Y - 1), 30)
    paint(upper, stroke(lip, taper(30, 1.0, 3.0, 1.0)), "#9C4454")
    return {"mouth_inside": finish(inside), "mouth_line": finish(upper)}


def all_features() -> dict[str, np.ndarray]:
    """Every painted face layer."""
    layers: dict[str, np.ndarray] = {}
    for side in ("l", "r"):
        layers.update(draw_eye(side))
        layers.update(draw_brow(side))
    layers.update(draw_blush())
    layers.update(draw_nose())
    layers.update(draw_mouth())
    return layers
