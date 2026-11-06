"""Build the illustrated Imeru from original plates without repainting their pixels."""

from __future__ import annotations

import numpy as np

from illustrated_mesh import ARTWORK, SIZE, ellipse, opacity, patch, region
from illustrated_rig import arms, common_motion, face_motion
from Imervue.puppet.document import HitArea, Part, PuppetDocument
from Imervue.puppet.standard_params import standard_parameters
from rig import physics


def _features():
    out = []
    for side, eye, brow in (
        ("r", (458, 137, 505, 166), (462, 126, 500, 138)),
        ("l", (527, 132, 570, 161), (528, 121, 565, 133)),
    ):
        for kind, source, bounds in (
            ("eye", "master", eye),
            ("closed", "alternates", eye),
            ("smile", "alternates", eye),
            ("brow", "master", brow),
        ):
            d = patch(f"{kind}_{side}", source, bounds)
            face_motion(d, kind, side)
            out.append(d)
    for kind, source, bounds in (
        ("mouth_rest", "master", (501, 184, 533, 202)),
        ("mouth_open", "alternates", (502, 184, 534, 204)),
    ):
        d = patch(kind, source, bounds)
        face_motion(d, kind)
        out.append(d)
    for side, centre in (("r", (475, 175)), ("l", (553, 170))):
        for index, radius in enumerate(((13, 6), (8, 4))):
            d = ellipse(f"cheek_{side}_{index}", centre, radius)
            d.multiply_color = (1.0, 0.65, 0.7)
            opacity(d, "ParamCheek", [(0.0, 0.0), (1.0, 0.22)])
            out.append(d)
    return out


def build():
    doc = PuppetDocument(size=SIZE)
    doc.parameters = standard_parameters()
    doc.textures = {
        f"textures/{name}.png": (ARTWORK / f"{name}.png").read_bytes()
        for name in ("master", "underlay", "alternates", "arms")
    }
    doc.drawables = [region("body", "underlay", (0, 0, *SIZE), step=12, order=10)]
    for side, bounds, hand_bounds in (
        ("r", (0, 190, 450, 1040), (0, 1010, 210, 1280)),
        ("l", (590, 190, 1024, 1040), (850, 1010, 1024, 1280)),
    ):
        d = region(f"arm_{side}", "arms", bounds, step=6)
        register_arm(d, side)
        doc.drawables.append(d)
        hand = region(f"hand_{side}", "arms", hand_bounds, step=4, order=2)
        register_arm(hand, side)
        doc.drawables.append(hand)
        alt_bounds = (165, 665, 285, 820) if side == "r" else (750, 665, 875, 820)
        doc.drawables.append(region(f"hand_open_{side}", "alternates", alt_bounds, step=4, order=3))
    doc.drawables += _features()
    for name, bounds in (("hit_head", (380, 20, 650, 240)), ("hit_body", (360, 265, 665, 680))):
        d = region(name, "master", bounds, step=120, order=100)
        d.opacity = 0.0
        doc.drawables.append(d)
    for d in doc.drawables:
        common_motion(d, body=d.id == "body")
    arms(doc)
    doc.physics_rigs = physics()
    doc.parts = [Part(id="Illustration", drawables=[d.id for d in doc.drawables])]
    doc.hit_areas = [
        HitArea(id="Head", drawables=["hit_head"], motion="TapHead"),
        HitArea(id="Body", drawables=["hit_body"], motion="TapBody"),
    ]
    _pad_motion_canvas(doc)
    return doc


def _pad_motion_canvas(doc):
    """Leave room above the crown during combined head and body movement."""
    margin = 64
    doc.size = (SIZE[0], SIZE[1] + 2 * margin)
    for drawable in doc.drawables:
        drawable.vertices = [(x, y + margin) for x, y in drawable.vertices]
    for deformer in doc.deformers:
        x, y = deformer.form["anchor"]
        deformer.form["anchor"] = [x, y + margin]


def register_arm(drawable, side):
    source = np.array((320.0, 230.0) if side == "r" else (704.0, 230.0))
    source_end = np.array((94.0, 1030.0) if side == "r" else (930.0, 1030.0))
    target = np.array((402.0, 275.0) if side == "r" else (625.0, 275.0))
    target_end = np.array((253.0, 680.0) if side == "r" else (774.0, 680.0))
    a, b = source_end - source, target_end - target
    scale = np.linalg.norm(b) / np.linalg.norm(a)
    angle = np.arctan2(b[1], b[0]) - np.arctan2(a[1], a[0])
    c, s = np.cos(angle), np.sin(angle)
    matrix = np.array([[c, -s], [s, c]]) * scale
    drawable.vertices = ((np.asarray(drawable.vertices) - source) @ matrix.T + target).tolist()
