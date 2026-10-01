"""Imeru's body and outfit in 3D: blouse, waistband and pleated skirt, sailor collar, bow.

Layers: ``body`` (torso in a white blouse with a gold-buttoned placket, navy waistband,
pleated navy skirt; the neck comes from ``head.py``), ``collar`` (a navy sailor collar
edged in white and gold) and ``ribbon`` (a coral bow held by the star-lens brooch).
"""
from __future__ import annotations

import math

from common import CX, bez, chain, mirror, smoothstep
from geo import ellipsoid, sheet, tube
from ornament import button, jewel
from toon import add_outline, toon

WHITE, WHITE_SHADE, WHITE_DEEP, WHITE_LINE = "#FBFBFF", "#D5D9F1", "#AEB5DC", "#565C8C"
NAVY, NAVY_SHADE, NAVY_DEEP, NAVY_LINE = "#34437E", "#232E5C", "#171E40", "#0E1430"
CORAL, CORAL_SHADE, CORAL_DEEP, CORAL_LINE = "#FF8A78", "#E0604F", "#B2443A", "#7C2B2A"
TRIM_WHITE = "#F2F3FF"

#: Torso half width and front bulge down the body: (y, half width, front depth).
TORSO = ((834, 48, 34), (850, 120, 50), (872, 178, 70), (900, 204, 86), (940, 200, 100),
         (1000, 190, 112), (1060, 178, 108), (1130, 162, 98), (1200, 150, 92),
         (1270, 154, 96), (1330, 166, 104), (1400, 180, 110), (1536, 200, 118))
TORSO_DEPTH = -40.0


def _interp(table, y: float, column: int) -> float:
    rows = sorted(table)
    if y <= rows[0][0]:
        return rows[0][column]
    for a, b in zip(rows, rows[1:], strict=False):
        if a[0] <= y <= b[0]:
            t = (y - a[0]) / (b[0] - a[0])
            t = t * t * (3 - 2 * t)
            return a[column] + (b[column] - a[column]) * t
    return rows[-1][column]


def torso_half(y: float) -> float:
    """Half the torso's width at canvas *y*."""
    return _interp(TORSO, y, 1)


def torso_front(x: float, y: float) -> float:
    """Depth of the torso's front surface at canvas (x, y)."""
    w = torso_half(y)
    if abs(x - CX) >= w:
        return TORSO_DEPTH
    return TORSO_DEPTH + _interp(TORSO, y, 2) * math.sqrt(1 - ((x - CX) / w) ** 2)


def _blouse():
    return toon("blouse", WHITE, WHITE_SHADE, deep=WHITE_DEEP, split=0.36, deep_split=0.1,
                rim="#FFFFFF", rim_split=0.8, rim_strength=0.4)


def _navy():
    return toon("navy", NAVY, NAVY_SHADE, deep=NAVY_DEEP, split=0.4, deep_split=0.12,
                rim="#6F86D8", rim_split=0.8, rim_strength=0.45)


def build_torso(collection_for):
    """The blouse-covered torso, its placket and buttons."""
    path, radii = [], []
    for y in range(int(TORSO[0][0]), 1541, 6):
        path.append((CX, float(y), TORSO_DEPTH))
        radii.append((torso_half(y), _interp(TORSO, y, 2), torso_half(y) * 0.62))
    torso = tube("torso", path, radii, _blouse(), segments=48)
    add_outline(torso, WHITE_LINE, 2.4)
    collection_for("body", torso)
    placket = [(CX - 9, 1040), (CX + 9, 1040), (CX + 9, 1262), (CX - 9, 1262)]
    plate = sheet("placket", placket, lambda x, y: torso_front(x, y) + 1.5, _blouse(),
                  thickness=2.0, step=6.0)
    add_outline(plate, WHITE_LINE, 1.4, even=False)
    collection_for("body", plate)
    for k, y in enumerate((1120, 1180, 1240)):
        collection_for("body", button(f"blouse_button_{k}", CX, y, torso_front(CX, y) + 4, 5.0))


def build_skirt(collection_for):
    """Navy waistband with gold trim and buttons, and the pleated skirt below it."""
    navy = _navy()
    band_path = [(CX, float(y), TORSO_DEPTH) for y in range(1262, 1337, 4)]
    band_radii = [(torso_half(y) + 5, _interp(TORSO, y, 2) + 5, 100.0) for _, y, _ in band_path]
    band = tube("waistband", band_path, band_radii, navy, segments=48)
    add_outline(band, NAVY_LINE, 2.2)
    collection_for("body", band)
    for k, y in enumerate((1266, 1333)):
        trim = [(CX + torso_half(y) * 1.03 * math.cos(a), y,
                 TORSO_DEPTH + (_interp(TORSO, y, 2) + 7) * math.sin(a))
                for a in (math.pi * j / 40 for j in range(41))]
        piping = tube(f"waist_trim_{k}", trim, [(2.6, 2.6)] * len(trim), _gold_trim(),
                      segments=10)
        collection_for("body", piping)
    for k, dx in enumerate((-30, 30)):
        y = 1300
        collection_for("body", button(f"waist_button_{k}", CX + dx, y,
                                      torso_front(CX + dx, y) + 9, 7.0))
    pleats = 18

    def pleat(k: int, theta: float) -> float:
        saw = (theta * pleats / (2 * math.pi)) % 1.0
        return 1.0 + 0.09 * (saw - 0.5)

    def skirt_radius(y: float) -> tuple[float, float]:
        return torso_half(y) + 14 + (y - 1334) * 0.32, _interp(TORSO, y, 2) + 16 + (y - 1334) * 0.1

    skirt_path = [(CX, float(y), TORSO_DEPTH) for y in range(1334, 1541, 6)]
    skirt_radii = [(*skirt_radius(y), 120.0) for _, y, _ in skirt_path]
    skirt = tube("skirt", skirt_path, skirt_radii, navy, segments=pleats * 4, squash=pleat)
    for polygon in skirt.data.polygons:
        polygon.use_smooth = False
    add_outline(skirt, NAVY_LINE, 2.2)
    collection_for("body", skirt)
    crease = toon("pleat_crease", NAVY_DEEP, NAVY_DEEP, split=0.5)
    for k in range(1, pleats // 2):
        a = math.pi * k / (pleats // 2)
        fold = []
        for y in range(1340, 1541, 10):
            across, front = skirt_radius(y)
            fold.append((CX + across * 0.975 * math.cos(a), float(y),
                         TORSO_DEPTH + front * 0.975 * math.sin(a) + 3))
        line = tube(f"pleat_{k}", fold, [(1.2, 0.8)] * len(fold), crease, segments=6)
        collection_for("body", line)
    stripe_mat = toon("skirt_stripe", TRIM_WHITE, "#C9CCE6", split=0.35)
    for k, (y, width, mat) in enumerate(((1488, 4.2, stripe_mat), (1502, 2.4, _gold_trim()))):
        across, front = skirt_radius(y)
        ring = [(CX + (across + 6) * math.cos(a), y, TORSO_DEPTH + (front + 8) * math.sin(a))
                for a in (math.pi * j / 60 for j in range(61))]
        band = tube(f"skirt_stripe_{k}", ring, [(width, width * 0.6)] * len(ring), mat,
                    segments=10)
        collection_for("body", band)


def _gold_trim():
    from ornament import gold
    return gold()


def _collar_half():
    """The left half of the sailor collar seen from the front, neck to V point."""
    outer = chain(bez((472, 836), (420, 850), (346, 864), (306, 896)),
                  bez((306, 896), (300, 920), (310, 934), (336, 952)),
                  bez((336, 952), (400, 996), (460, 1034), (CX, 1068)))
    inner = bez((CX, 1014), (488, 980), (464, 918), (476, 848), 24)
    return outer, inner


def build_collar(collection_for):
    """``collar``: the navy sailor collar with a white stripe and gold piping."""
    navy = _navy()
    outer, inner = _collar_half()
    flap = chain(outer, inner)

    def depth(x, y):
        return torso_front(x, y) + 7 + 10 * smoothstep(900, 1060, y)

    for name, outline in (("l", flap), ("r", mirror(flap)[::-1])):
        plate = sheet(f"collar_flap_{name}", outline, depth, navy, thickness=4.0, step=9.0)
        add_outline(plate, NAVY_LINE, 2.2, even=False)
        collection_for("collar", plate)
    band = [(470, 834), (554, 834), (552, 850), (472, 850)]
    back = sheet("collar_back", band, lambda x, y: TORSO_DEPTH - 20.0, navy, thickness=3.0,
                 step=6.0)
    collection_for("collar", back)
    for side_points, name in ((outer, "l"), (mirror(outer), "r")):
        inset = [(x + (CX - x) * 0.09 + 8 * (1 - smoothstep(880, 940, y)),
                  y - 14 * smoothstep(1000, 1068, y) + 10 * (1 - smoothstep(880, 920, y)))
                 for x, y in side_points[5:-6]]
        stripe = [(x, y, depth(x, y) + 3.5) for x, y in inset]
        white = toon("collar_stripe", TRIM_WHITE, "#C9CCE6", split=0.35)
        line = tube(f"collar_stripe_{name}", stripe, [(3.4, 1.6)] * len(stripe), white,
                    segments=10)
        collection_for("collar", line)
        edge = [(x, y, depth(x, y) + 2.5) for x, y in side_points]
        piping = tube(f"collar_piping_{name}", edge, [(2.4, 2.4)] * len(edge), _gold_trim(),
                      segments=10)
        collection_for("collar", piping)


def _loop(name, side: str, coral):
    """One loop of the bow: a puffy teardrop plate."""
    outline = chain(bez((CX - 6, 1050), (470, 1000), (420, 1000), (412, 1040), 20),
                    bez((412, 1040), (404, 1080), (450, 1098), (CX - 6, 1066), 20))
    if side == "r":
        outline = mirror(outline)
    cx = sum(p[0] for p in outline) / len(outline)

    def depth(x, y):
        bulge = 18 * max(0.0, 1 - ((x - cx) / 52) ** 2 - ((y - 1048) / 44) ** 2)
        return torso_front(CX, 1050) + 26 + bulge

    plate = sheet(name, outline, depth, coral, thickness=5.0, step=7.0)
    add_outline(plate, CORAL_LINE, 2.0, even=False)
    return plate


def _tail(name, side: str, coral):
    outline = [(496, 1060), (512, 1068), (474, 1186), (459, 1170), (440, 1180)]
    if side == "r":
        outline = mirror(outline)
    plate = sheet(name, outline, lambda x, y: torso_front(CX, 1060) + 20 - (y - 1066) * 0.08,
                  coral, thickness=4.0, step=6.0)
    add_outline(plate, CORAL_LINE, 1.8, even=False)
    return plate


def build_ribbon(collection_for):
    """``ribbon``: the coral bow with two tails, held by the star-lens brooch."""
    coral = toon("coral", CORAL, CORAL_SHADE, deep=CORAL_DEEP, split=0.4, deep_split=0.12,
                 rim="#FFD2C8", rim_split=0.76, rim_strength=0.5, spec="#FFE6DF",
                 spec_split=0.84, roughness=0.3)
    for side in ("l", "r"):
        collection_for("ribbon", _tail(f"bow_tail_{side}", side, coral))
        collection_for("ribbon", _loop(f"bow_loop_{side}", side, coral))
    knot = ellipsoid("bow_knot", (CX, 1058, torso_front(CX, 1058) + 40), (24, 22, 14), coral)
    add_outline(knot, CORAL_LINE, 2.0)
    collection_for("ribbon", knot)
    for obj in jewel("brooch", CX, 1058, torso_front(CX, 1058) + 56, scale=0.82):
        collection_for("ribbon", obj)


BUILDERS = (build_torso, build_skirt, build_collar, build_ribbon)
