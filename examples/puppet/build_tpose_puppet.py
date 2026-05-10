"""Multi-drawable T-pose puppet — the cleanest possible rig demo.

Why T-pose + 6 drawables instead of one image with warps:

* Standing-pose illustrations make the arms hang down at the sides;
  rectangular warp bounds can't isolate "the arm" without also
  catching torso pixels, so swings end up as muddy blobs.
* T-pose puts the limbs out along the X axis, completely separate
  from the torso. Painting each limb on its own PNG with the joint
  pivot at a known canvas position lets each rotation deformer
  rotate exactly its body part — no overlap, no bleed.

The rig:

* 6 drawables painted procedurally with PIL — head, torso,
  left arm, right arm, left leg, right leg
* 6 rotation deformers, one per limb / part, each anchored at the
  joint:
    - head_rot     pivots the head around the neck base
    - body_rot     leans the torso around the hips
    - arm_left_rot rotates the left arm around the left shoulder
    - arm_right_rot                            right shoulder
    - leg_left_rot rotates the left leg around the left hip
    - leg_right_rot                           right hip
* 6 parameters in [-1, 1] driving the angles (each ±60 ° at the
  extremes — visibly dramatic)
* 5 motions that compose the parameters in different ways:
    - idle          subtle body sway + counter head bob
    - wave          right-arm waves up and down twice
    - jumping_jacks both arms swing out, both legs spread, syncopated
    - bow           head + body lean forward
    - stretch       arms stretch outward then return

Output: ``examples/puppet/demo_tpose.puppet``. Pure Python; no Qt,
no OpenGL, no external assets.
"""
from __future__ import annotations

import math
import sys
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))

from puppet.auto_mesh import triangulate_alpha_grid    # noqa: E402
from puppet.deformers import default_rotation_form    # noqa: E402
from puppet.document import (    # noqa: E402
    Deformer,
    Drawable,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    ParameterKey,
    PuppetDocument,
)
from puppet.document_io import save_puppet    # noqa: E402

# ---------------------------------------------------------------------------
# Canvas geometry — every joint anchor is documented here so the rotation
# anchors below match the painted geometry exactly.
# ---------------------------------------------------------------------------

CANVAS_W: int = 800
CANVAS_H: int = 1000

HEAD_CENTER = (400, 150)
HEAD_RADIUS = 80
NECK_TOP_Y = HEAD_CENTER[1] + HEAD_RADIUS - 8   # 222
NECK_BOTTOM_Y = 240
SHOULDER_Y = 260
TORSO_TOP_LEFT = (350, NECK_BOTTOM_Y)
TORSO_BOTTOM_RIGHT = (450, 500)
HIP_Y = TORSO_BOTTOM_RIGHT[1]    # 500

ARM_HEIGHT = 60
LEFT_ARM_BOX = (140, SHOULDER_Y, TORSO_TOP_LEFT[0], SHOULDER_Y + ARM_HEIGHT)
RIGHT_ARM_BOX = (TORSO_BOTTOM_RIGHT[0], SHOULDER_Y, 660, SHOULDER_Y + ARM_HEIGHT)

LEG_WIDTH = 50
_LL = TORSO_TOP_LEFT[0] + 10
_LR = TORSO_BOTTOM_RIGHT[0] - 10
LEFT_LEG_BOX = (_LL, HIP_Y - 10, _LL + LEG_WIDTH, 900)
RIGHT_LEG_BOX = (_LR - LEG_WIDTH, HIP_Y - 10, _LR, 900)

# Joint pivots (rotation anchors).
NECK_PIVOT = (HEAD_CENTER[0], NECK_TOP_Y)
SHOULDER_LEFT_PIVOT = (TORSO_TOP_LEFT[0] + 4, SHOULDER_Y + ARM_HEIGHT * 0.5)
SHOULDER_RIGHT_PIVOT = (TORSO_BOTTOM_RIGHT[0] - 4, SHOULDER_Y + ARM_HEIGHT * 0.5)
HIP_LEFT_PIVOT = (LEFT_LEG_BOX[0] + LEG_WIDTH * 0.5, HIP_Y)
HIP_RIGHT_PIVOT = (RIGHT_LEG_BOX[0] + LEG_WIDTH * 0.5, HIP_Y)
WAIST_PIVOT = (HEAD_CENTER[0], HIP_Y)

# Rotation extremes per parameter (radians).
HEAD_YAW_MAX = math.radians(40)
BODY_LEAN_MAX = math.radians(25)
ARM_SWING_MAX = math.radians(80)
LEG_SWING_MAX = math.radians(35)

# Palette — flat cartoon colours; vaguely Rossi-flavoured (tan, brown, blue).
SKIN = (244, 213, 187, 255)
HAT = (215, 145, 80, 255)
SHIRT = (115, 130, 165, 255)
TROUSERS = (60, 75, 95, 255)
ACCENT = (220, 90, 60, 255)


# ---------------------------------------------------------------------------
# Per-part PNG painters. Each returns RGBA bytes the size of the canvas with
# the body part painted at its T-pose canvas position; everything else is
# fully transparent. We pad the bounding box by a few pixels so the
# auto-mesh's alpha-trim doesn't shave the silhouette.
# ---------------------------------------------------------------------------


def _blank() -> Image.Image:
    return Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def paint_head() -> bytes:
    img = _blank()
    draw = ImageDraw.Draw(img)
    cx, cy = HEAD_CENTER
    r = HEAD_RADIUS
    # Hat brim
    draw.ellipse(
        (cx - r - 16, cy - 12, cx + r + 16, cy + 14),
        fill=HAT, outline=(60, 40, 30, 255), width=4,
    )
    # Head circle
    draw.ellipse(
        (cx - r, cy - r, cx + r, cy + r),
        fill=SKIN, outline=(60, 40, 30, 255), width=4,
    )
    # Hat crown
    draw.pieslice(
        (cx - r, cy - r - 30, cx + r, cy + r - 30),
        start=190, end=350,
        fill=HAT, outline=(60, 40, 30, 255), width=4,
    )
    # Eyes
    eye_dy = -8
    eye_r = 7
    for dx in (-22, 22):
        x0, y0 = cx + dx - eye_r, cy + eye_dy - eye_r
        x1, y1 = cx + dx + eye_r, cy + eye_dy + eye_r
        draw.ellipse((x0, y0, x1, y1), fill=(40, 30, 25, 255))
    # Smile
    draw.arc(
        (cx - 26, cy + 4, cx + 26, cy + 32),
        start=10, end=170, fill=(170, 60, 50, 255), width=4,
    )
    return _to_png_bytes(img)


def paint_torso() -> bytes:
    img = _blank()
    draw = ImageDraw.Draw(img)
    x0, y0 = TORSO_TOP_LEFT
    x1, y1 = TORSO_BOTTOM_RIGHT
    # Shirt with rounded shoulders + waist
    draw.rounded_rectangle(
        (x0 - 6, y0, x1 + 6, y1 + 8),
        radius=20,
        fill=SHIRT, outline=(40, 50, 70, 255), width=4,
    )
    # Belt accent
    belt_y = y1 - 16
    draw.rectangle((x0 - 6, belt_y, x1 + 6, belt_y + 12), fill=ACCENT)
    return _to_png_bytes(img)


def paint_arm(side: str) -> bytes:
    img = _blank()
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = LEFT_ARM_BOX if side == "left" else RIGHT_ARM_BOX
    # Sleeve in shirt colour
    sleeve_x_split = (x0 + x1) // 2 if side == "right" else (x0 + x1) // 2
    if side == "left":
        draw.rounded_rectangle(
            (sleeve_x_split, y0 - 4, x1, y1 + 4),
            radius=12, fill=SHIRT, outline=(40, 50, 70, 255), width=3,
        )
        # Forearm + hand in skin tone (outer half)
        draw.rounded_rectangle(
            (x0, y0, sleeve_x_split, y1),
            radius=14, fill=SKIN, outline=(60, 40, 30, 255), width=3,
        )
        # Fingers hint
        draw.ellipse(
            (x0 - 6, y0 - 4, x0 + 18, y1 + 4),
            fill=SKIN, outline=(60, 40, 30, 255), width=3,
        )
    else:
        draw.rounded_rectangle(
            (x0, y0 - 4, sleeve_x_split, y1 + 4),
            radius=12, fill=SHIRT, outline=(40, 50, 70, 255), width=3,
        )
        draw.rounded_rectangle(
            (sleeve_x_split, y0, x1, y1),
            radius=14, fill=SKIN, outline=(60, 40, 30, 255), width=3,
        )
        draw.ellipse(
            (x1 - 18, y0 - 4, x1 + 6, y1 + 4),
            fill=SKIN, outline=(60, 40, 30, 255), width=3,
        )
    return _to_png_bytes(img)


def paint_leg(side: str) -> bytes:
    img = _blank()
    draw = ImageDraw.Draw(img)
    box = LEFT_LEG_BOX if side == "left" else RIGHT_LEG_BOX
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=14, fill=TROUSERS, outline=(20, 30, 50, 255), width=3,
    )
    # Boot
    draw.rounded_rectangle(
        (x0 - 4, y1 - 24, x1 + 8, y1 + 12),
        radius=8, fill=(40, 30, 25, 255),
    )
    return _to_png_bytes(img)


# ---------------------------------------------------------------------------
# Drawable factory — each body part becomes one drawable with its own
# auto-meshed PNG. Vertices live in canvas-space pixels so the rotation
# anchors below operate on the same coordinate system.
# ---------------------------------------------------------------------------


def _drawable_from_part(
    drawable_id: str, png_bytes: bytes, draw_order: int,
    texture_path: str, cell_size: int = 24,
) -> Drawable:
    rgba = _decode_rgba(png_bytes)
    vertices, indices, uvs = triangulate_alpha_grid(rgba, cell_size=cell_size)
    return Drawable(
        id=drawable_id,
        texture=texture_path,
        vertices=vertices,
        indices=indices,
        uvs=uvs,
        draw_order=draw_order,
    )


def _decode_rgba(png_bytes: bytes):
    import numpy as np
    from PIL import Image as _Image
    with _Image.open(BytesIO(png_bytes)) as img:
        return np.asarray(img.convert("RGBA"), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Rig
# ---------------------------------------------------------------------------


def _rotation_at_angle(anchor: tuple[float, float], angle_rad: float) -> dict:
    return {"anchor": [float(anchor[0]), float(anchor[1])], "angle": float(angle_rad)}


def _three_key_param(
    pid: str, deformer_id: str, anchor: tuple[float, float],
    swing: float,
) -> Parameter:
    """Build a -1 / 0 / +1 parameter that rotates ``deformer_id``
    by ``-swing`` / 0 / ``+swing`` radians around ``anchor``."""
    return Parameter(
        id=pid, min=-1.0, max=1.0, default=0.0,
        keys=[
            ParameterKey(value=-1.0, forms={
                deformer_id: _rotation_at_angle(anchor, -swing),
            }),
            ParameterKey(value=0.0, forms={
                deformer_id: _rotation_at_angle(anchor, 0.0),
            }),
            ParameterKey(value=1.0, forms={
                deformer_id: _rotation_at_angle(anchor, swing),
            }),
        ],
    )


def _build_doc() -> PuppetDocument:
    doc = PuppetDocument(size=(CANVAS_W, CANVAS_H))
    parts = (
        ("head", paint_head, 50),
        ("torso", paint_torso, 30),
        ("arm_left", lambda: paint_arm("left"), 20),
        ("arm_right", lambda: paint_arm("right"), 20),
        ("leg_left", lambda: paint_leg("left"), 10),
        ("leg_right", lambda: paint_leg("right"), 10),
    )
    for part_id, painter, draw_order in parts:
        png_bytes = painter()
        tex_path = f"textures/{part_id}.png"
        doc.textures[tex_path] = png_bytes
        doc.drawables.append(
            _drawable_from_part(part_id, png_bytes, draw_order, tex_path),
        )

    # Rotation deformers — one per body part.
    doc.deformers.extend([
        Deformer(
            id="head_rot", type="rotation", parent=None,
            drawables=["head"], form=default_rotation_form(NECK_PIVOT),
        ),
        Deformer(
            id="body_rot", type="rotation", parent=None,
            # Body lean drags the upper half (torso + head + arms) along
            # with it so the puppet bows / sways as a coherent unit.
            # Legs stay anchored. Arm rotations applied later compose on
            # top of the rotated torso.
            drawables=["torso", "head", "arm_left", "arm_right"],
            form=default_rotation_form(WAIST_PIVOT),
        ),
        Deformer(
            id="arm_left_rot", type="rotation", parent=None,
            drawables=["arm_left"], form=default_rotation_form(SHOULDER_LEFT_PIVOT),
        ),
        Deformer(
            id="arm_right_rot", type="rotation", parent=None,
            drawables=["arm_right"], form=default_rotation_form(SHOULDER_RIGHT_PIVOT),
        ),
        Deformer(
            id="leg_left_rot", type="rotation", parent=None,
            drawables=["leg_left"], form=default_rotation_form(HIP_LEFT_PIVOT),
        ),
        Deformer(
            id="leg_right_rot", type="rotation", parent=None,
            drawables=["leg_right"], form=default_rotation_form(HIP_RIGHT_PIVOT),
        ),
    ])

    # Parameters.
    doc.parameters.extend([
        _three_key_param("ParamHeadYaw", "head_rot", NECK_PIVOT, HEAD_YAW_MAX),
        _three_key_param("ParamBodyLean", "body_rot", WAIST_PIVOT, BODY_LEAN_MAX),
        _three_key_param("ParamArmLeftSwing", "arm_left_rot", SHOULDER_LEFT_PIVOT, ARM_SWING_MAX),
        _three_key_param(
            "ParamArmRightSwing", "arm_right_rot",
            SHOULDER_RIGHT_PIVOT, ARM_SWING_MAX,
        ),
        _three_key_param("ParamLegLeftSwing", "leg_left_rot", HIP_LEFT_PIVOT, LEG_SWING_MAX),
        _three_key_param("ParamLegRightSwing", "leg_right_rot", HIP_RIGHT_PIVOT, LEG_SWING_MAX),
    ])

    # Motions.
    doc.motions.extend([
        _idle_motion(),
        _wave_motion(),
        _jumping_jacks_motion(),
        _bow_motion(),
        _stretch_motion(),
    ])
    return doc


# ---------------------------------------------------------------------------
# Motion factories
# ---------------------------------------------------------------------------


def _sine_track(
    param_id: str, duration: float, amplitude: float,
    *, phase: float = 0.0, segments: int = 32,
) -> MotionTrack:
    out: list[MotionSegment] = []
    for i in range(segments):
        t0 = duration * i / segments
        t1 = duration * (i + 1) / segments
        v0 = amplitude * math.sin(2.0 * math.pi * t0 / duration + phase)
        v1 = amplitude * math.sin(2.0 * math.pi * t1 / duration + phase)
        out.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return MotionTrack(param_id=param_id, segments=out)


def _idle_motion() -> Motion:
    return Motion(
        name="idle", duration=4.0, loop=True,
        tracks=[
            _sine_track("ParamBodyLean", 4.0, 0.5),
            _sine_track("ParamHeadYaw", 4.0, 0.4, phase=math.pi),
        ],
    )


def _wave_motion() -> Motion:
    """Right arm raised and shaking left/right twice."""
    duration = 2.0
    segments = []
    n = 32
    for i in range(n):
        t0 = duration * i / n
        t1 = duration * (i + 1) / n
        # Right arm: held high (around -0.85) the whole motion; oscillates a bit.
        base = -0.85
        wobble = 0.15 * math.sin(2.0 * math.pi * 4 * t0 / duration)
        v0 = base + wobble
        wobble1 = 0.15 * math.sin(2.0 * math.pi * 4 * t1 / duration)
        v1 = base + wobble1
        segments.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return Motion(
        name="wave", duration=duration, loop=True,
        tracks=[
            MotionTrack(param_id="ParamArmRightSwing", segments=segments),
            _sine_track("ParamHeadYaw", duration, 0.3),
        ],
    )


def _jumping_jacks_motion() -> Motion:
    """Classic jumping jacks: arms swing up while legs spread outward.

    Sign convention (image-space, y goes down):
    * left arm starts extended left (vector points LEFT). Positive
      angle (CW on screen) brings the hand upward; negative rotates
      it down/in. So ParamArmLeftSwing = +s raises the left arm.
    * right arm starts extended right. Negative angle (CCW on screen)
      raises it. So ParamArmRightSwing = -s raises the right arm.
    * left leg hangs straight down. Positive angle swings the foot to
      the LEFT (outward). ParamLegLeftSwing = +s spreads.
    * right leg: negative angle swings the foot to the RIGHT (outward).
      ParamLegRightSwing = -s spreads.

    With these signs the limbs move symmetrically — arms go up + legs
    go out at the sine peak.
    """
    duration = 1.6
    n = 32
    arm_left: list[MotionSegment] = []
    arm_right: list[MotionSegment] = []
    leg_left: list[MotionSegment] = []
    leg_right: list[MotionSegment] = []
    for i in range(n):
        t0 = duration * i / n
        t1 = duration * (i + 1) / n
        s0 = math.sin(2.0 * math.pi * t0 / duration)
        s1 = math.sin(2.0 * math.pi * t1 / duration)
        arm_left.append(MotionSegment(type="linear", p0=(t0, +s0), p1=(t1, +s1)))
        arm_right.append(MotionSegment(type="linear", p0=(t0, -s0), p1=(t1, -s1)))
        leg_left.append(MotionSegment(type="linear", p0=(t0, +s0 * 0.7), p1=(t1, +s1 * 0.7)))
        leg_right.append(MotionSegment(type="linear", p0=(t0, -s0 * 0.7), p1=(t1, -s1 * 0.7)))
    return Motion(
        name="jumping_jacks", duration=duration, loop=True,
        tracks=[
            MotionTrack(param_id="ParamArmLeftSwing", segments=arm_left),
            MotionTrack(param_id="ParamArmRightSwing", segments=arm_right),
            MotionTrack(param_id="ParamLegLeftSwing", segments=leg_left),
            MotionTrack(param_id="ParamLegRightSwing", segments=leg_right),
        ],
    )


def _bow_motion() -> Motion:
    """Head + body lean forward then back."""
    duration = 2.4
    return Motion(
        name="bow", duration=duration, loop=True,
        tracks=[
            MotionTrack(param_id="ParamBodyLean", segments=[
                MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.6, 1.0)),
                MotionSegment(type="linear", p0=(0.6, 1.0), p1=(1.4, 1.0)),
                MotionSegment(type="linear", p0=(1.4, 1.0), p1=(2.0, 0.0)),
                MotionSegment(type="linear", p0=(2.0, 0.0), p1=(2.4, 0.0)),
            ]),
            MotionTrack(param_id="ParamHeadYaw", segments=[
                MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.6, 0.6)),
                MotionSegment(type="linear", p0=(0.6, 0.6), p1=(1.4, 0.6)),
                MotionSegment(type="linear", p0=(1.4, 0.6), p1=(2.0, 0.0)),
                MotionSegment(type="linear", p0=(2.0, 0.0), p1=(2.4, 0.0)),
            ]),
        ],
    )


def _stretch_motion() -> Motion:
    """Both arms reach upward (Y-pose). Same sign convention as
    jumping_jacks — left arm uses positive parameter values, right
    arm uses negative, so they raise symmetrically."""
    duration = 3.0
    return Motion(
        name="stretch", duration=duration, loop=True,
        tracks=[
            MotionTrack(param_id="ParamArmLeftSwing", segments=[
                MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0)),
                MotionSegment(type="linear", p0=(1.0, 1.0), p1=(2.0, 1.0)),
                MotionSegment(type="linear", p0=(2.0, 1.0), p1=(3.0, 0.0)),
            ]),
            MotionTrack(param_id="ParamArmRightSwing", segments=[
                MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, -1.0)),
                MotionSegment(type="linear", p0=(1.0, -1.0), p1=(2.0, -1.0)),
                MotionSegment(type="linear", p0=(2.0, -1.0), p1=(3.0, 0.0)),
            ]),
        ],
    )


def main() -> None:
    out = Path(__file__).with_name("demo_tpose.puppet")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = _build_doc()
    save_puppet(doc, out)
    print(f"wrote {out} (size={out.stat().st_size} bytes)")


# Keep deepcopy import live for any future motion factory that mutates a
# shared form template before keying it.
_keep_deepcopy = deepcopy


if __name__ == "__main__":
    main()
