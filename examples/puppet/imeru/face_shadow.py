"""Imeru's face shading: an SDF face shadow map and a screen-space hair shadow.

3D anime games do not light a face with its normals — the nose, lips and cheeks would
break the shadow into noise. An artist paints the shadow shape for a handful of light
angles instead (the cheekbone holds the light longest, the nose throws a small shadow,
a lit triangle stays under the far eye), and the shapes are merged into one *threshold
map* by signed-distance interpolation: every pixel stores the light angle at which it
falls into shadow, so any angle in between gets a smooth, hand-shaped shadow.

Here the key shapes are drawn from the face outline (:func:`key_mask`), merged by
:func:`threshold_map`, and cut into rings (:func:`shade_layers`) that the rig fades in
as the head turns away from the light (``ParamAngleX``): the light stays put, so a turn
changes the angle between it and the face.

The hair shadow on the forehead is the other half of the trick: the hair's own outline,
pushed a few pixels along the light (:func:`hair_shadow`), so the bangs cast a clear
shadow shape however close to the skin they sit.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

#: The skin's shadow colour (the 3D skin uses the same).
SHADE = (247, 205, 193)
#: Light angle off the face's forward axis at rest, from ``blender/toon.LIGHT_DIRECTION``
#: (0.34 to the side for 0.86 toward the face).
REST_ANGLE = math.degrees(math.atan2(0.34, 0.86))
#: Light angles of the drawn key shadows; the map interpolates between them.
KEY_ANGLES = (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0)
#: How fast the shadow line moves in at each height: (canvas y, exponent on cos(angle)).
#: Small exponents hold the light (the cheekbone), large ones give it up (temple, jaw).
RETREAT = ((300.0, 1.5), (520.0, 1.5), (620.0, 0.75), (680.0, 0.9), (745.0, 1.9))
#: Where the hair shadow falls: canvas pixels along the light.
HAIR_SHADOW_OFFSET = (5, 14)
#: How far ``ParamAngleX`` = 1 turns the head, in degrees.
TURN_DEGREES = 30.0
#: The rig's shadow rings, as ranges of head turn in degrees: a ring fills in as the head
#: turns through its range (the light angle is ``REST_ANGLE`` plus the turn). Ring 0 lies
#: on the near side: past ``-REST_ANGLE`` she faces beyond the light, which then comes
#: from her other side.
RINGS = {
    "face_shade_0": (-30.0, -REST_ANGLE),
    "face_shade_1": (-REST_ANGLE, -REST_ANGLE / 2),
    "face_shade_2": (-REST_ANGLE / 2, 0.0),
    "face_shade_3": (0.0, 15.0),
    "face_shade_4": (15.0, 30.0),
}


def face_rows(face_alpha: np.ndarray, cx: float) -> dict[int, float]:
    """Half the face's width on every canvas row it covers (right edge minus centre)."""
    rows = {}
    for y in np.nonzero((face_alpha > 128).any(axis=1))[0]:
        xs = np.nonzero(face_alpha[y] > 128)[0]
        rows[int(y)] = max(0.0, float(xs.max()) + 0.5 - cx)
    return rows


def _retreat(y: float) -> float:
    ys, ps = zip(*RETREAT, strict=True)
    return float(np.interp(y, ys, ps))


def shadow_line(rows: dict[int, float], cx: float, angle: float) -> list[tuple[float, float]]:
    """The edge of the main shadow at *angle* degrees: one (x, y) per face row."""
    c = math.cos(math.radians(min(max(angle, 0.0), 90.0)))
    return [(cx + w * (c ** _retreat(y) if c > 0 else 0.0), float(y))
            for y, w in sorted(rows.items())]


def _nose(angle: float, cx: float) -> list[tuple[float, float]] | None:
    """The nose's shadow on the far side, growing from 30 degrees."""
    if angle <= 30.0:
        return None
    s = (angle - 30.0) / 60.0
    return [(cx + 1, 622.0), (cx + 2 + 10 * s, 640.0), (cx + 5 + 26 * s, 672.0),
            (cx + 3, 674.0), (cx - 2, 666.0)]


def _lit_triangle(angle: float, cx: float) -> list[tuple[float, float]] | None:
    """The lit patch under the far eye that survives the shadow from 50 to 85 degrees."""
    if not 50.0 < angle < 85.0:
        return None
    s = 1.0 - (angle - 50.0) / 35.0
    tri = [(cx + 58, 660.0), (cx + 122, 662.0), (cx + 74, 702.0)]
    mx, my = sum(p[0] for p in tri) / 3, sum(p[1] for p in tri) / 3
    return [(mx + (x - mx) * s, my + (y - my) * s) for x, y in tri]


def key_mask(shape: tuple[int, int], rows: dict[int, float], cx: float,
             angle: float) -> np.ndarray:
    """The drawn shadow at *angle*: everything right of the shadow line, nose shadow
    included, the lit triangle cut out. Boolean, canvas sized."""
    h, w = shape
    image = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(image)
    line = shadow_line(rows, cx, angle)
    if line:
        # Run the shape well past the face's top and bottom rows, so their closing edges
        # don't count as shadow lines when the map measures distances.
        (x_top, top), (x_bottom, bottom) = line[0], line[-1]
        draw.polygon([(w, top - 40), (x_top, top - 40), *line, (x_bottom, bottom + 40),
                      (w, bottom + 40)], fill=255)
    nose = _nose(angle, cx)
    if nose:
        draw.polygon(nose, fill=255)
    lit = _lit_triangle(angle, cx)
    if lit:
        draw.polygon(lit, fill=0)
    return np.asarray(image) > 127


def key_masks(face_alpha: np.ndarray, cx: float) -> list[np.ndarray]:
    """The key shadows of :data:`KEY_ANGLES`, each grown to contain the one before.

    A threshold map needs nested shapes (a pixel in shadow stays in shadow as the light
    swings further round), so wherever a drawn shape would give back light the previous
    one took — the tip of the lit triangle — the previous shadow stays.
    """
    rows = face_rows(face_alpha, cx)
    masks: list[np.ndarray] = []
    for angle in KEY_ANGLES:
        mask = key_mask(face_alpha.shape, rows, cx, angle)
        masks.append(mask | masks[-1] if masks else mask)
    return masks


def _distance(points: np.ndarray, targets: np.ndarray, chunk: int = 1024) -> np.ndarray:
    """Distance from each of *points* (N, 2) to the nearest of *targets* (M, 2)."""
    if len(targets) == 0:
        return np.full(len(points), np.inf)
    out = np.empty(len(points))
    for start in range(0, len(points), chunk):
        block = points[start:start + chunk, None, :] - targets[None, :, :]
        out[start:start + chunk] = np.sqrt((block ** 2).sum(-1)).min(axis=1)
    return out


def _edge(mask: np.ndarray) -> np.ndarray:
    """(x, y) of the mask's own pixels that touch a pixel outside it."""
    inner = mask.copy()
    inner[1:, :] &= mask[:-1, :]
    inner[:-1, :] &= mask[1:, :]
    inner[:, 1:] &= mask[:, :-1]
    inner[:, :-1] &= mask[:, 1:]
    ys, xs = np.nonzero(mask & ~inner)
    return np.stack([xs, ys], axis=1).astype(np.float64)


def threshold_map(face_alpha: np.ndarray, cx: float) -> np.ndarray:
    """The face shadow map: per pixel, the light angle (degrees) it falls into shadow at.

    Pixels between key shadow *k* and *k + 1* get an angle in between, by how far they
    are from each shape (signed-distance interpolation); pixels the 90-degree shadow
    never reaches get 90. Only face pixels are filled (the rest is 90).
    """
    masks = key_masks(face_alpha, cx)
    out = np.full(face_alpha.shape, 90.0)
    face = face_alpha > 0
    out[masks[0] & face] = KEY_ANGLES[0]
    for k in range(len(masks) - 1):
        ring = masks[k + 1] & ~masks[k] & face
        ys, xs = np.nonzero(ring)
        if not len(ys):
            continue
        points = np.stack([xs, ys], axis=1).astype(np.float64)
        to_inner = _distance(points, _edge(masks[k]))
        to_outer = _distance(points, _edge(~masks[k + 1]))
        t = np.where(np.isfinite(to_inner), to_inner / np.maximum(to_inner + to_outer, 1e-9), 0.0)
        out[ys, xs] = KEY_ANGLES[k] + t * (KEY_ANGLES[k + 1] - KEY_ANGLES[k])
    return out


def _band(angles: np.ndarray, low: float, high: float, soft: float = 0.6) -> np.ndarray:
    """Coverage of the pixels whose angle lies in (low, high], with a soft edge."""
    rise = np.clip((angles - low) / soft + 0.5, 0.0, 1.0)
    fall = np.clip((high - angles) / soft + 0.5, 0.0, 1.0)
    return rise * fall


def shade_layers(face_alpha: np.ndarray, cx: float) -> dict[str, np.ndarray]:
    """The face shadow rings of :data:`RINGS`, as RGBA layers clipped to the face."""
    angles = threshold_map(face_alpha, cx)
    mirrored = threshold_map(face_alpha[:, ::-1], face_alpha.shape[1] - cx)[:, ::-1]
    face = face_alpha.astype(np.float64) / 255.0
    layers = {}
    for name, (start, end) in RINGS.items():
        low, high = REST_ANGLE + start, REST_ANGLE + end
        near_side = high <= 0
        coverage = _band(mirrored, -high, -low) if near_side else _band(angles, low, high)
        layers[name] = _layer(coverage * face)
    return layers


def ring_opacity(name: str) -> list[dict[str, float]]:
    """``ParamAngleX`` opacity stops for ring *name*: it fades in across its range, and
    stays shown beyond it (on the near side, below it)."""
    start, end = (turn / TURN_DEGREES for turn in RINGS[name])
    if end <= -REST_ANGLE / TURN_DEGREES:
        return [{"value": start, "alpha": 1.0}, {"value": end, "alpha": 0.0}]
    return [{"value": start, "alpha": 0.0}, {"value": end, "alpha": 1.0}]


def hair_shadow(face_alpha: np.ndarray, hair_alpha: np.ndarray,
                offset: tuple[int, int] = HAIR_SHADOW_OFFSET) -> np.ndarray:
    """The hair's outline pushed *offset* pixels along the light, on the face."""
    dx, dy = offset
    shifted = np.zeros_like(hair_alpha)
    h, w = hair_alpha.shape
    shifted[dy:, dx:] = hair_alpha[:h - dy, :w - dx]
    coverage = (shifted.astype(np.float64) / 255.0) * (face_alpha.astype(np.float64) / 255.0)
    return _layer(coverage)


def _layer(coverage: np.ndarray) -> np.ndarray:
    out = np.zeros((*coverage.shape, 4), np.uint8)
    out[..., :3] = SHADE
    out[..., 3] = np.clip(coverage * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return out


def merge(*layers: np.ndarray) -> np.ndarray:
    """Layers of the same colour merged: the strongest coverage wins at each pixel."""
    out = layers[0].copy()
    for layer in layers[1:]:
        stronger = layer[..., 3] > out[..., 3]
        out[stronger] = layer[stronger]
    return out
