"""Gold and gem pieces shared by Imeru's hairpin and brooch: the star-lens motif."""
from __future__ import annotations

from functools import cache

from geo import ellipsoid, star, torus
from toon import add_outline, toon

GOLD, GOLD_SHADE, GOLD_DEEP, GOLD_LINE = "#F7DA92", "#D3A24A", "#99692A", "#7A5220"
GEM, GEM_SHADE, GEM_LINE = "#7CC4FF", "#3A6CD6", "#22357F"


@cache
def gold():
    """Polished gold: three tones, a hard highlight and a warm rim."""
    return toon("gold", GOLD, GOLD_SHADE, deep=GOLD_DEEP, split=0.4, spec="#FFFBEA",
                spec_split=0.5, roughness=0.2, rim="#FFF4CC", rim_split=0.7)


@cache
def gem():
    """A blue lens: bright rim, a sharp white glint."""
    return toon("gem", GEM, GEM_SHADE, split=0.35, spec="#FFFFFF", spec_split=0.45,
                roughness=0.15, rim="#D6F2FF", rim_split=0.6, rim_strength=0.7)


def jewel(prefix: str, x: float, y: float, depth: float, scale: float = 1.0,
          beads: tuple = ()) -> list:
    """A gold ring round a blue lens with a little star on it, plus optional gold beads."""
    s = scale
    ring = torus(f"{prefix}_ring", (x, y, depth), 21.0 * s, 4.6 * s, gold())
    add_outline(ring, GOLD_LINE, 1.6)
    lens = ellipsoid(f"{prefix}_lens", (x, y, depth - 2 * s), (19 * s, 19 * s, 7 * s), gem(),
                     segments=40)
    add_outline(lens, GEM_LINE, 1.4)
    sparkle = star(f"{prefix}_star", (x, y, depth + 6 * s), 10.0 * s, 4.2 * s, 3.0 * s, gold(),
                   turn=0.2)
    add_outline(sparkle, GOLD_LINE, 1.2)
    parts = [ring, lens, sparkle]
    for k, (bx, by) in enumerate(beads):
        bead = ellipsoid(f"{prefix}_bead_{k}", (bx, by, depth - 4 * s), (5.5 * s,) * 3, gold(),
                         segments=20)
        add_outline(bead, GOLD_LINE, 1.2)
        parts.append(bead)
    return parts


def button(name: str, x: float, y: float, depth: float, radius: float = 6.0):
    """A small domed gold button."""
    obj = ellipsoid(name, (x, y, depth), (radius, radius, radius * 0.6), gold(), segments=20)
    add_outline(obj, GOLD_LINE, 1.2)
    return obj
