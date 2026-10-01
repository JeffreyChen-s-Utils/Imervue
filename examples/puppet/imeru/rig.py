"""Rig Imeru: meshes, vertex morphs, a body-roll deformer, parts, hit areas, physics.

Head turns are drawn as Live2D-style parallax: every head layer has a depth, points
near the middle of the face move furthest and the outline stays put, so the face
reads as round. Eyes close by collapsing the white of the eye onto the lower lid
(the iris and highlight are clipped to it) while the upper lash travels down; the
mouth opens from a collapsed rest shape; hair sways through physics-driven morphs.
"""

from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image

import art
from Imervue.puppet.auto_mesh import triangulate_alpha_grid
from Imervue.puppet.document import (
    Deformer,
    Drawable,
    HitArea,
    ParameterKey,
    Part,
    PhysicsParticle,
    PhysicsRig,
    PuppetDocument,
)
from Imervue.puppet.standard_params import standard_parameters

CX, PIVOT_X, PIVOT_Y = 512.0, 512.0, 760.0
TURN_X, TURN_Y = 44.0, 26.0  # px a feature at depth 1 moves at ParamAngleX / Y = ±1
ROLL = math.radians(9.0)  # head roll at ParamAngleZ = ±1
BODY_ROLL = 0.05  # rad, ParamBodyAngleZ = ±1

# character side of each drawn side: the eye drawn on the viewer's left is her right eye
SIDE = {"l": "R", "r": "L"}

HEAD_DEPTH = {  # parallax depth: 1 = eye plane, >1 in front of it, <0 behind the head
    "lid_crease": 0.75,
    "face": 0.35,
    "bang_shadow": 0.9,
    "blush": 0.72,
    "nose": 0.95,
    "mouth_inside": 0.85,
    "mouth_line": 0.85,
    "eye_white": 0.75,
    "iris": 0.8,
    "highlight": 0.82,
    "lower_lash": 0.75,
    "upper_lash": 0.75,
    "smile_eye": 0.75,
    "brow": 0.85,
    "bangs": 0.9,
    "hairpin": 0.9,
    "ahoge": 0.6,
}
RIGID_DEPTH = {"side_lock": 0.3, "neck_shadow": 0.15, "back_hair": -0.3}
BODY_LAYERS = ("body", "collar", "ribbon", "upper_arm", "forearm", "hand", "hand_open")
ARM_RAISE = math.radians(45.0)  # upper arm out and up at ParamArm?A = 1
ARM_BEND = math.radians(160.0)  # forearm bent up at ParamArm?B = 1
CELL = {
    "back_hair": 40,
    "body": 48,
    "collar": 32,
    "ribbon": 20,
    "face": 22,
    "bangs": 22,
    "side_lock": 20,
    "neck_shadow": 20,
    "bang_shadow": 24,
    "blush": 16,
    "ahoge": 10,
    "hairpin": 10,
    "nose": 6,
    "mouth_inside": 5,
    "mouth_line": 5,
    "eye_white": 7,
    "iris": 8,
    "highlight": 8,
    "lower_lash": 6,
    "upper_lash": 6,
    "smile_eye": 6,
    "brow": 6,
    "lid_crease": 6,
    "upper_arm": 20,
    "forearm": 20,
    "hand": 10,
    "hand_open": 8,
}


def kind(layer_id: str) -> str:
    """``iris_l`` -> ``iris``."""
    return layer_id[:-2] if layer_id[-2:] in ("_l", "_r") else layer_id


def drawable_id(layer_id: str) -> str:
    """Eye / brow layers are named by the character's side (Cubism's L / R)."""
    if layer_id[-2:] in ("_l", "_r") and kind(layer_id) not in ("side_lock",):
        return f"{kind(layer_id)}_{SIDE[layer_id[-1]].lower()}"
    return layer_id


# ---- meshes ---------------------------------------------------------------------------------
def _bbox(rgba: np.ndarray) -> tuple[int, int, int, int]:
    alpha = rgba[..., 3] > 0
    rows, cols = np.where(alpha.any(axis=1))[0], np.where(alpha.any(axis=0))[0]
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def _png(rgba: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def strip(top, bottom, box) -> tuple[list, list, list]:
    """A mesh between two edges sampled at the same x positions, left to right: exact outline."""
    x0, y0, x1, y1 = box
    top, bottom = np.asarray(top, float), np.asarray(bottom, float)
    vertices = np.concatenate([top, bottom])
    n = len(top)
    indices = []
    for i in range(n - 1):
        indices += [i, i + 1, n + i + 1, i, n + i + 1, n + i]
    uvs = [((x - x0) / (x1 - x0), (y - y0) / (y1 - y0)) for x, y in vertices]
    return [tuple(v) for v in vertices], indices, uvs


def _edge_pair(upper, lower, count: int = 28, grow: float = 1.6):
    """Upper and lower edges at the same x positions, pushed *grow* px outwards."""
    xs_all = [p[0] for p in upper] + [p[0] for p in lower]
    lo, hi = min(xs_all) - grow, max(xs_all) + grow
    xs = np.linspace(lo, hi, count)
    top = _curve_y(upper, np.clip(xs, lo + grow, hi - grow)) - grow
    bottom = _curve_y(lower, np.clip(xs, lo + grow, hi - grow)) + grow
    mid = (top + bottom) / 2
    ends = np.array([0, -1])
    top[ends], bottom[ends] = mid[ends], mid[ends]
    return np.stack([xs, top], 1), np.stack([xs, bottom], 1)


def outline_edges(layer_id: str):
    """The exact-outline edges of the eye whites and the mouth, or ``None`` for a grid mesh."""
    k = kind(layer_id)
    if k == "eye_white":
        return _edge_pair(art.upper_lid(layer_id[-1], 80), art.lower_lid(layer_id[-1], 80))
    if k == "mouth_inside":
        shape = art.mouth_inside_shape()
        half = len(shape) // 2
        return _edge_pair(shape[: half + 1], shape[half:], 20, 1.2)
    return None


def mesh(layer_id: str, rgba: np.ndarray, draw_order: int) -> tuple[Drawable, bytes]:
    x0, y0, x1, y1 = _bbox(rgba)
    crop = np.ascontiguousarray(rgba[y0:y1, x0:x1])
    edges = outline_edges(layer_id)
    if edges is not None:
        vertices, indices, uvs = strip(*edges, (x0, y0, x1, y1))
    else:
        local, indices, uvs = triangulate_alpha_grid(crop, cell_size=CELL[kind(layer_id)])
        vertices = [(x + x0, y + y0) for x, y in local]
    did = drawable_id(layer_id)
    drawable = Drawable(
        id=did,
        texture=f"textures/{did}.png",
        vertices=vertices,
        indices=indices,
        uvs=uvs,
        draw_order=draw_order,
    )
    return drawable, _png(crop)


# ---- morph helpers ----------------------------------------------------------------------------
def _v(drawable: Drawable) -> np.ndarray:
    return np.asarray(drawable.vertices, dtype=float)


def _morph(drawable: Drawable, parameter: str, at_min=None, at_max=None) -> None:
    entry: dict = {"parameter": parameter}
    if at_min is not None:
        entry["delta_at_min"] = [(round(float(dx), 3), round(float(dy), 3)) for dx, dy in at_min]
    if at_max is not None:
        entry["delta_at_max"] = [(round(float(dx), 3), round(float(dy), 3)) for dx, dy in at_max]
    drawable.vertex_morphs = (drawable.vertex_morphs or []) + [entry]


def _xy(dx, dy, n: int) -> np.ndarray:
    return np.stack(
        [
            np.broadcast_to(np.asarray(dx, float), (n,)),
            np.broadcast_to(np.asarray(dy, float), (n,)),
        ],
        1,
    )


def _bell(u: np.ndarray) -> np.ndarray:
    return np.clip(1.0 - u * u, 0.0, 1.0)


def _ramp(y: np.ndarray, start: float, end: float) -> np.ndarray:
    return np.clip((y - start) / (end - start), 0.0, 1.0)


def _back_hair_weight(y: np.ndarray) -> np.ndarray:
    """The share of the head's motion the back hair takes: all at the crown, a fifth at the tips."""
    return 1.0 - 0.8 * _ramp(y, 620.0, 1250.0)


# ---- head ------------------------------------------------------------
def head_turn(d: Drawable) -> None:
    v, n, k = _v(d), len(d.vertices), kind(d.id)
    x, y = v[:, 0], v[:, 1]
    if k in RIGID_DEPTH:
        depth = RIGID_DEPTH[k]
        w = _back_hair_weight(y) if k == "back_hair" else 1.0
        dx, dy = depth * TURN_X * w * np.ones(n), depth * TURN_Y * w * np.ones(n)
    else:
        depth = HEAD_DEPTH[k]
        dx = depth * TURN_X * _bell((x - CX) / 225.0)
        dy = depth * TURN_Y * _bell((y - 590.0) / 250.0)
    _morph(d, "ParamAngleX", _xy(-dx, 0, n), _xy(dx, 0, n))
    _morph(d, "ParamAngleY", _xy(0, dy, n), _xy(0, -dy, n))


def head_roll(d: Drawable) -> None:
    v = _v(d)
    rel = v - (PIVOT_X, PIVOT_Y)
    w = _back_hair_weight(v[:, 1]) if kind(d.id) == "back_hair" else 1.0
    if kind(d.id) == "side_lock":
        w = 1.0 - 0.35 * _ramp(v[:, 1], 600.0, 1000.0)
    out = []
    for sign in (-1, 1):
        c, s = math.cos(sign * ROLL), math.sin(sign * ROLL)
        rotated = np.stack([rel[:, 0] * c - rel[:, 1] * s, rel[:, 0] * s + rel[:, 1] * c], 1)
        out.append(
            (rotated - rel) * np.asarray(w)[..., None] if np.ndim(w) else (rotated - rel) * w
        )
    _morph(d, "ParamAngleZ", out[0], out[1])


def head_follows_body(d: Drawable) -> None:
    v, n = _v(d), len(d.vertices)
    w = _back_hair_weight(v[:, 1]) if kind(d.id) == "back_hair" else np.ones(n)
    _morph(d, "ParamBodyAngleX", _xy(-20 * w, 0, n), _xy(20 * w, 0, n))
    _morph(d, "ParamBodyAngleY", _xy(0, 9 * w, n), _xy(0, -9 * w, n))
    _morph(d, "ParamBreath", _xy(0, 4 * w, n), _xy(0, -4 * w, n))


# ---- body ------------------------------------------------------------
def body_moves(d: Drawable) -> None:
    v, n = _v(d), len(d.vertices)
    y = v[:, 1]
    lean = 1.0 - _ramp(y, 850.0, 1500.0)
    front = {"collar": 1.1, "ribbon": 1.25}.get(d.id, 1.0)
    _morph(d, "ParamBodyAngleX", _xy(-16 * lean * front, 0, n), _xy(16 * lean * front, 0, n))
    _morph(d, "ParamBodyAngleY", _xy(0, 6 * lean, n), _xy(0, -6 * lean, n))
    chest = 1.0 - _ramp(y, 900.0, 1320.0)
    _morph(d, "ParamBreath", _xy(0, 6 * chest, n), _xy(0, -6 * chest, n))


# ---- face features --------------------------------------------------------------------------
def _curve_y(points, x: np.ndarray) -> np.ndarray:
    pts = sorted(points)
    xs, ys = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    return np.interp(x, xs, ys)


def _lids(drawn_side: str):
    return art.upper_lid(drawn_side, 80), art.lower_lid(drawn_side, 80)


def eye_rig(d: Drawable, drawn_side: str) -> None:
    k, v, n = kind(d.id), _v(d), len(d.vertices)
    x = v[:, 0]
    char = SIDE[drawn_side]
    upper, lower = _lids(drawn_side)
    y_up, y_low = _curve_y(upper, x), _curve_y(lower, x)
    if k == "eye_white":
        half = n // 2
        closed = np.zeros((n, 2))
        closed[:half] = v[half:] - v[:half]
        _morph(d, f"ParamEye{char}Open", at_min=closed)
    elif k == "upper_lash":
        _morph(d, f"ParamEye{char}Open", at_min=_xy(0, np.maximum(y_low - y_up, 0.0) + 2.0, n))
    elif k == "lid_crease":
        _morph(d, f"ParamEye{char}Open", at_min=_xy(0, 0.55 * np.maximum(y_low - y_up, 0.0), n))
    elif k in ("iris", "highlight"):
        f = 1.0 if k == "iris" else 0.55
        _morph(d, "ParamEyeBallX", _xy(-12 * f, 0, n), _xy(12 * f, 0, n))
        _morph(d, "ParamEyeBallY", _xy(0, 7 * f, n), _xy(0, -7 * f, n))
    fade_out = [{"value": 0.0, "alpha": 1.0}, {"value": 0.5, "alpha": 0.0}]
    fade_in = [{"value": 0.3, "alpha": 0.0}, {"value": 0.7, "alpha": 1.0}]
    if k in ("eye_white", "iris", "highlight", "upper_lash", "lower_lash", "lid_crease"):
        d.opacity_keys = [{"parameter": f"ParamEye{char}Smile", "stops": fade_out}]
    elif k == "smile_eye":
        d.opacity_keys = [{"parameter": f"ParamEye{char}Smile", "stops": fade_in}]
    if k in ("iris", "highlight"):
        d.clip_mask = f"eye_white_{char.lower()}"


def brow_rig(d: Drawable, drawn_side: str) -> None:
    v, n = _v(d), len(d.vertices)
    char = SIDE[drawn_side]
    x = v[:, 0]
    closeness = -np.abs(x - CX)
    inner = (closeness - closeness.min()) / max(np.ptp(closeness), 1e-6)
    _morph(d, f"ParamBrow{char}Y", _xy(0, 11, n), _xy(0, -11, n))
    sad = -9.0 * inner + 2.5 * (1 - inner)
    _morph(d, f"ParamBrow{char}Angle", _xy(0, -sad, n), _xy(0, sad, n))
    toward_nose = 1.0 if drawn_side == "l" else -1.0
    _morph(d, f"ParamBrow{char}X", _xy(-6 * toward_nose, 0, n), _xy(6 * toward_nose, 0, n))
    arch = np.sin(np.pi * np.clip(inner, 0, 1))
    _morph(d, f"ParamBrow{char}Form", _xy(0, 5 * arch, n), _xy(0, -5 * arch, n))


def mouth_rig(d: Drawable) -> None:
    v, n = _v(d), len(d.vertices)
    x = v[:, 0]
    corner = np.clip(np.abs(x - CX) / art.MOUTH_HALF, 0.0, 1.0) ** 2
    widen = np.sign(x - CX) * np.clip(np.abs(x - CX) / art.MOUTH_HALF, 0, 1)
    _morph(
        d, "ParamMouthForm", _xy(-1.0 * widen, 6.0 * corner, n), _xy(3.0 * widen, -7.0 * corner, n)
    )
    if d.id == "mouth_inside":
        half = n // 2
        collapsed = v.copy()
        collapsed[half:] = v[:half]
        d.vertices = [(float(a), float(b)) for a, b in collapsed]
        _morph(d, "ParamMouthOpenY", at_max=v - collapsed)


def jaw_rig(d: Drawable) -> None:
    v, n = _v(d), len(d.vertices)
    x, y = v[:, 0], v[:, 1]
    jaw = _ramp(y, 690.0, 752.0) * _bell((x - CX) / 150.0)
    _morph(d, "ParamMouthOpenY", at_max=_xy(0, 8.0 * jaw, n))


def blush_rig(d: Drawable) -> None:
    d.opacity_keys = [
        {
            "parameter": "ParamCheek",
            "stops": [{"value": 0.0, "alpha": 0.3}, {"value": 1.0, "alpha": 1.0}],
        }
    ]


# ---- hair --------------------------------------------------------------------------------------
def hair_rig(d: Drawable) -> None:
    v, n, k = _v(d), len(d.vertices), kind(d.id)
    x, y = v[:, 0], v[:, 1]
    if k == "bangs":
        t = _ramp(y, 360.0, 604.0) ** 1.3
        _morph(d, "ParamHairFront", _xy(-12 * t, 0, n), _xy(12 * t, 0, n))
    elif k == "ahoge":
        t = _ramp(-y, -300.0, -226.0)
        _morph(d, "ParamHairFront", _xy(-26 * t, 4 * t, n), _xy(26 * t, 4 * t, n))
    elif k == "side_lock":
        t = _ramp(y, 480.0, 1010.0) ** 1.4
        _morph(d, "ParamHairSide", _xy(-36 * t, -3 * t, n), _xy(36 * t, -3 * t, n))
    elif k == "back_hair":
        t = _ramp(y, 640.0, 1400.0) ** 1.5 * (0.6 + 0.4 * _bell((x - CX) / 300.0))
        _morph(d, "ParamHairBack", _xy(-44 * t, -4 * t, n), _xy(44 * t, -4 * t, n))


def physics() -> list[PhysicsRig]:
    def chain(count: int, damping: float, spring: float) -> list[PhysicsParticle]:
        return [PhysicsParticle(mass=1.0, damping=damping, spring=spring) for _ in range(count)]

    return [
        PhysicsRig(
            id="hair_front",
            input_param="ParamAngleX",
            output_param="ParamHairFront",
            chain=chain(3, 0.78, 9.0),
        ),
        PhysicsRig(
            id="hair_side",
            input_param="ParamAngleZ",
            output_param="ParamHairSide",
            chain=chain(4, 0.84, 7.0),
        ),
        PhysicsRig(
            id="hair_back",
            input_param="ParamBodyAngleX",
            output_param="ParamHairBack",
            chain=chain(4, 0.88, 6.0),
        ),
    ]


# ---- assembly ------------------------------------------------------------------------------------
HEAD_KINDS = set(HEAD_DEPTH) | {"side_lock", "neck_shadow", "back_hair"}


def build(layers: dict[str, np.ndarray]) -> PuppetDocument:
    doc = PuppetDocument(size=(art.W, 1536))
    doc.parameters = standard_parameters()
    for order, layer_id in enumerate(art.LAYER_ORDER):
        drawable, png = mesh(layer_id, layers[layer_id], order * 10)
        doc.drawables.append(drawable)
        doc.textures[drawable.texture] = png
        rig_one(drawable, layer_id)
    doc.deformers = arm_deformers() + [
        Deformer(
            id="body_roll",
            type="rotation",
            parent=None,
            drawables=[d.id for d in doc.drawables],
            form={"anchor": [CX, 1500.0], "angle": 0.0},
        )
    ]
    doc.parameters += arm_parameters()
    roll = doc.parameter("ParamBodyAngleZ")
    roll.keys = [
        ParameterKey(value=-1.0, forms={"body_roll": {"angle": -BODY_ROLL}}),
        ParameterKey(value=0.0, forms={"body_roll": {"angle": 0.0}}),
        ParameterKey(value=1.0, forms={"body_roll": {"angle": BODY_ROLL}}),
    ]
    doc.physics_rigs = physics()
    doc.parts = parts()
    doc.hit_areas = [
        HitArea(id="Head", drawables=["bangs", "face"], motion="TapHead"),
        HitArea(id="Body", drawables=["collar", "ribbon"], motion="TapBody"),
    ]
    return doc


def rig_one(d: Drawable, layer_id: str) -> None:
    k = kind(layer_id)
    if k in BODY_LAYERS:
        body_moves(d)
        if k in ("hand", "hand_open"):
            hand_pose(d, layer_id[-1])
        return
    if k in {"mouth_inside", "mouth_line"}:
        mouth_rig(d)
    if k in (
        "eye_white",
        "iris",
        "highlight",
        "upper_lash",
        "lower_lash",
        "smile_eye",
        "lid_crease",
    ):
        eye_rig(d, layer_id[-1])
    if k == "brow":
        brow_rig(d, layer_id[-1])
    if k == "face":
        jaw_rig(d)
    if k == "blush":
        blush_rig(d)
    if k in ("bangs", "ahoge", "side_lock", "back_hair"):
        hair_rig(d)
    head_turn(d)
    head_roll(d)
    head_follows_body(d)
    if k == "bang_shadow":
        d.clip_mask = "face"


def hand_pose(d: Drawable, drawn_side: str) -> None:
    """The relaxed hand while the arm hangs, the open hand once it is raised to wave."""
    param = f"ParamArm{SIDE[drawn_side]}A"
    shown = [{"value": 0.2, "alpha": 0.0}, {"value": 0.45, "alpha": 1.0}]
    hidden = [{"value": 0.2, "alpha": 1.0}, {"value": 0.45, "alpha": 0.0}]
    d.opacity_keys = [{"parameter": param, "stops": shown if kind(d.id) == "hand_open" else hidden}]


def arm_deformers() -> list[Deformer]:
    """Forearm rotations first, then the whole arm's around the shoulder.

    A deformer's transform is not passed to its children, so the forearm and
    hand are listed in both deformers and the forearm's runs first: they bend
    at the elbow, then turn with the upper arm, which is forward kinematics.
    """
    from body_arms import ELBOW, SHOULDER

    forearms, uppers = [], []
    for drawn, char in (("l", "r"), ("r", "l")):
        mirror_x = (lambda x: x) if drawn == "l" else (lambda x: art.W - x)
        forearms.append(
            Deformer(
                id=f"forearm_{char}",
                type="rotation",
                parent=None,
                drawables=[f"forearm_{char}", f"hand_{char}", f"hand_open_{char}"],
                form={"anchor": [mirror_x(ELBOW[0]), ELBOW[1]], "angle": 0.0},
            )
        )
        uppers.append(
            Deformer(
                id=f"upper_arm_{char}",
                type="rotation",
                parent=None,
                drawables=[
                    f"upper_arm_{char}",
                    f"forearm_{char}",
                    f"hand_{char}",
                    f"hand_open_{char}",
                ],
                form={"anchor": [mirror_x(SHOULDER[0]), SHOULDER[1]], "angle": 0.0},
            )
        )
    return forearms + uppers


def arm_parameters() -> list:
    """``ParamArm{L,R}A`` raises the upper arm, ``ParamArm{L,R}B`` bends the forearm up (0..1)."""
    from Imervue.puppet.document import Parameter

    out = []
    for char, sign in (("R", 1.0), ("L", -1.0)):
        for suffix, deformer, angle in (
            ("A", f"upper_arm_{char.lower()}", ARM_RAISE),
            ("B", f"forearm_{char.lower()}", ARM_BEND),
        ):
            out.append(
                Parameter(
                    id=f"ParamArm{char}{suffix}",
                    min=0.0,
                    max=1.0,
                    default=0.0,
                    keys=[
                        ParameterKey(value=0.0, forms={deformer: {"angle": 0.0}}),
                        ParameterKey(value=1.0, forms={deformer: {"angle": sign * angle}}),
                    ],
                )
            )
    return out


def parts() -> list[Part]:
    return [
        Part(id="HairBack", drawables=["back_hair"]),
        Part(id="Body", drawables=["body", "collar", "ribbon", "neck_shadow"]),
        Part(
            id="Arms",
            drawables=[
                f"{k}_{s}"
                for s in ("l", "r")
                for k in ("upper_arm", "forearm", "hand", "hand_open")
            ],
        ),
        Part(id="Face", drawables=["face", "bang_shadow", "blush", "nose"]),
        Part(id="Mouth", drawables=["mouth_inside", "mouth_line"]),
        Part(
            id="Eyes",
            drawables=[
                f"{k}_{s}"
                for s in ("l", "r")
                for k in (
                    "eye_white",
                    "iris",
                    "highlight",
                    "lower_lash",
                    "upper_lash",
                    "smile_eye",
                    "lid_crease",
                )
            ],
        ),
        Part(id="Brows", drawables=["brow_l", "brow_r"]),
        Part(id="HairFront", drawables=["side_lock_l", "side_lock_r", "bangs", "ahoge", "hairpin"]),
    ]
