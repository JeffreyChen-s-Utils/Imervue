"""Imeru's layers: the 3D render (Blender) plus the painted face features, bottom to top.

The body, outfit, arms, head and hair are modelled and cel-shaded in Blender
(``blender/``, run through ``render3d.py``); the face's own shading comes from an SDF face
shadow map and the hair's outline pushed along the light (``face_shadow.py``); the eyes,
brows, blush, nose and mouth are painted on top like a game character's face textures
(``features.py``). This module holds
the geometry both sides and the rig share — the eye lids, the iris, the mouth, the arm
joints — and ``LAYER_ORDER``, the drawing order from the bottom.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from draw import W, bez, chain, mirror

CX = W / 2

# ---- geometry shared with the rig ---------------------------------------------------------
HEAD_CENTRE = (CX, 520.0)
NECK_PIVOT = (CX, 760.0)
EYE_OUTER_L, EYE_INNER_L = (386.0, 606.0), (490.0, 616.0)
EYE_UPPER_C_L = ((394.0, 548.0), (462.0, 544.0))
EYE_LOWER_C_L = ((478.0, 654.0), (404.0, 658.0))
IRIS_L = (444.0, 616.0, 31.0, 41.0)
MOUTH_Y = 707.0
MOUTH_HALF = 21.0
#: The joints the arm deformers turn about (the arm drawn on the viewer's left).
SHOULDER = (300.0, 905.0)
ELBOW = (288.0, 1162.0)


def upper_lid(side: str = "l", n: int = 40):
    """The upper eyelid, outer corner to inner corner."""
    pts = bez(EYE_OUTER_L, *EYE_UPPER_C_L, EYE_INNER_L, n)
    return pts if side == "l" else mirror(pts)


def lower_lid(side: str = "l", n: int = 40):
    """The lower eyelid, inner corner to outer corner."""
    pts = bez(EYE_INNER_L, *EYE_LOWER_C_L, EYE_OUTER_L, n)
    return pts if side == "l" else mirror(pts)


def mouth_inside_shape():
    """The open mouth's outline: the lip line on top, the jaw curve below."""
    return chain(
        bez((CX - MOUTH_HALF, MOUTH_Y), (CX - 8, MOUTH_Y + 2), (CX + 8, MOUTH_Y + 2),
            (CX + MOUTH_HALF, MOUTH_Y)),
        bez((CX + MOUTH_HALF, MOUTH_Y), (CX + 20, MOUTH_Y + 30), (CX - 20, MOUTH_Y + 30),
            (CX - MOUTH_HALF, MOUTH_Y)),
    )


def all_layers(render_dir: Path | None = None) -> dict[str, np.ndarray]:
    """Every layer: the Blender render in *render_dir* (render3d's cache) and the features."""
    import face_shadow
    import features
    import render3d

    layers = render3d.load(render_dir or render3d.CACHE)
    face_alpha = layers["face"][..., 3]
    layers.update(face_shadow.shade_layers(face_alpha, CX))
    layers["bang_shadow"] = face_shadow.merge(
        layers["bang_shadow"], face_shadow.hair_shadow(face_alpha, layers["bangs"][..., 3]))
    layers.update(features.all_features())
    missing = [name for name in LAYER_ORDER if name not in layers]
    if missing:
        raise RuntimeError(f"layers missing from the render: {missing}")
    return {name: layers[name] for name in LAYER_ORDER}


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
    "face_shade_0",
    "face_shade_1",
    "face_shade_2",
    "face_shade_3",
    "face_shade_4",
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
