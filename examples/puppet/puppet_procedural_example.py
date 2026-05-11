"""Procedurally-built puppet example.

Each body part is drawn directly onto its own transparent canvas with
PIL primitives — there is no source illustration, no chroma-key, no
segmentation, no inpaint. Every drawable starts life with a clean
anti-aliased silhouette, so animations can never expose the white
edges, ghost overlaps, or "cut" artefacts that come from slicing a
single hand-drawn image into parts.

Pipeline:

1. Pick a canvas size and figure-frac anchors for the head, shoulders,
   hips and feet.
2. Render each body part (head, torso, two arms, two legs) onto its
   own RGBA layer at the figure's rest position, using supersampled
   PIL drawing for anti-aliasing.
3. Wrap each layer in a Drawable via :func:`triangulate_alpha_grid`,
   wire one rotation deformer per joint, and bind the same motion set
   the previous demo used.
4. Save out as ``puppet_procedural.puppet`` next to this script.

The rig demonstrates the engine end-to-end — rotation deformers,
parameter keys, motion tracks, opacity-driven cross-fades — without
the hand-drawn-source complications. Use it as the reference example
when documenting the format or onboarding new contributors.
"""
from __future__ import annotations

import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
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

OUTPUT_PATH = Path(__file__).with_name("puppet_procedural.puppet")

# ---------------------------------------------------------------------------
# Canvas + figure proportions
# ---------------------------------------------------------------------------

CANVAS_W = 520
CANVAS_H = 760
SUPERSAMPLE = 4  # render at NxN then downscale with LANCZOS for AA
CELL_SIZE = 18

# Figure landmarks in canvas pixels. Keep these in one block so the
# joints and the drawn parts stay in lockstep when you adjust the
# figure — every drawable derives its position from these numbers.
HEAD_CENTRE = (CANVAS_W // 2, 180)
HEAD_RADIUS = 95

NECK_XY = (CANVAS_W // 2, 270)
SHOULDER_LEFT = (CANVAS_W // 2 - 70, 305)
SHOULDER_RIGHT = (CANVAS_W // 2 + 70, 305)
HIP_LEFT = (CANVAS_W // 2 - 35, 525)
HIP_RIGHT = (CANVAS_W // 2 + 35, 525)
FOOT_LEFT = (CANVAS_W // 2 - 55, 720)
FOOT_RIGHT = (CANVAS_W // 2 + 55, 720)

# Arms hang down from the shoulder in rest pose so the idle motion
# can swing them subtly without first un-tposing them. End-point sits
# beside the hip so a small rotation reads as a natural sway.
ARM_LEFT_TIP = (CANVAS_W // 2 - 95, 530)
ARM_RIGHT_TIP = (CANVAS_W // 2 + 95, 530)

LIMB_THICKNESS = 38
LEG_THICKNESS = 46

# Palette tuned to read clearly against any background. No black —
# pure-black silhouettes look harsh in 2D animation and read more like
# a logo than a character.
SKIN_RGB = (244, 207, 178)
HAIR_RGB = (84, 64, 96)
JACKET_RGB = (76, 92, 132)
SHORTS_RGB = (228, 230, 236)
SHOE_RGB = (60, 56, 72)
EYE_RGB = (52, 40, 68)
MOUTH_RGB = (180, 88, 112)
# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Part:
    """One drawable's worth of pre-rendered art + rig metadata."""

    id: str
    image: Image.Image
    draw_order: int


def _blank_canvas() -> Image.Image:
    """An empty transparent canvas at the final output resolution."""
    return Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))


def _supersampled_draw(
    paint: Callable[[ImageDraw.ImageDraw], None],
) -> Image.Image:
    """Render ``paint`` onto an oversized canvas then downscale with
    LANCZOS. Anti-alising via supersampling avoids relying on Pillow's
    per-primitive AA flags, which differ between releases."""
    big = Image.new(
        "RGBA",
        (CANVAS_W * SUPERSAMPLE, CANVAS_H * SUPERSAMPLE),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(big)
    paint(draw)
    return big.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)


def _scaled_point(xy: tuple[float, float]) -> tuple[float, float]:
    return (xy[0] * SUPERSAMPLE, xy[1] * SUPERSAMPLE)


def _scaled_radius(r: float) -> float:
    return r * SUPERSAMPLE


def _draw_capsule(
    draw: ImageDraw.ImageDraw,
    p0: tuple[float, float],
    p1: tuple[float, float],
    thickness: float,
    fill: tuple[int, int, int],
) -> None:
    """A stadium-shaped limb: two circles + a quadrilateral spine.
    Used for arms and legs so the joint and the tip both have rounded
    caps that compose with any rotation without showing a flat edge."""
    sp0 = _scaled_point(p0)
    sp1 = _scaled_point(p1)
    r = _scaled_radius(thickness * 0.5)
    dx, dy = sp1[0] - sp0[0], sp1[1] - sp0[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        draw.ellipse((sp0[0] - r, sp0[1] - r, sp0[0] + r, sp0[1] + r), fill=fill)
        return
    nx, ny = -dy / length, dx / length
    spine = [
        (sp0[0] + nx * r, sp0[1] + ny * r),
        (sp1[0] + nx * r, sp1[1] + ny * r),
        (sp1[0] - nx * r, sp1[1] - ny * r),
        (sp0[0] - nx * r, sp0[1] - ny * r),
    ]
    draw.polygon(spine, fill=fill)
    draw.ellipse((sp0[0] - r, sp0[1] - r, sp0[0] + r, sp0[1] + r), fill=fill)
    draw.ellipse((sp1[0] - r, sp1[1] - r, sp1[0] + r, sp1[1] + r), fill=fill)


# ---------------------------------------------------------------------------
# Per-part drawing
# ---------------------------------------------------------------------------


def _draw_head() -> Image.Image:
    """Skin oval + dark hair cap + simple face. The head pivots around
    the neck anchor when ``ParamHeadYaw`` moves."""
    def paint(draw: ImageDraw.ImageDraw) -> None:
        cx, cy = _scaled_point(HEAD_CENTRE)
        r = _scaled_radius(HEAD_RADIUS)
        # Skin oval — slightly taller than wide for a chibi proportion.
        draw.ellipse(
            (cx - r * 0.85, cy - r, cx + r * 0.85, cy + r * 1.1),
            fill=SKIN_RGB,
        )
        # Hair cap: a low-arc ellipse sitting on the top half of the head.
        # The bottom edge stays above the eyeline so the face reads cleanly.
        draw.ellipse(
            (cx - r * 0.95, cy - r * 1.15, cx + r * 0.95, cy - r * 0.10),
            fill=HAIR_RGB,
        )
        # Eyes — two stacked ellipses for a wide-eyed anime look,
        # positioned in the lower half of the face below the hair.
        eye_dx = r * 0.32
        eye_y = cy + r * 0.30
        eye_w = r * 0.13
        eye_h = r * 0.20
        for cx_eye in (cx - eye_dx, cx + eye_dx):
            draw.ellipse(
                (cx_eye - eye_w, eye_y - eye_h, cx_eye + eye_w, eye_y + eye_h),
                fill=EYE_RGB,
            )
            # Highlight pip
            draw.ellipse(
                (cx_eye - eye_w * 0.3, eye_y - eye_h * 0.5,
                 cx_eye + eye_w * 0.3, eye_y - eye_h * 0.1),
                fill=(255, 255, 255, 255),
            )
        # Mouth — small soft curve.
        mw = r * 0.20
        mh = r * 0.06
        draw.ellipse(
            (cx - mw, cy + r * 0.75 - mh,
             cx + mw, cy + r * 0.75 + mh),
            fill=MOUTH_RGB,
        )
    return _supersampled_draw(paint)


def _draw_torso() -> Image.Image:
    """Jacket rectangle on top, shorts band below. The torso doesn't
    rotate on its own; ``body_rot`` (parent deformer) leans it with
    the rest of the rig."""
    def paint(draw: ImageDraw.ImageDraw) -> None:
        sh_l = _scaled_point(SHOULDER_LEFT)
        sh_r = _scaled_point(SHOULDER_RIGHT)
        hip_l = _scaled_point(HIP_LEFT)
        hip_r = _scaled_point(HIP_RIGHT)
        shorts_top = (sh_l[1] + hip_l[1]) / 2 + _scaled_radius(60)
        torso_pad = _scaled_radius(34)
        # Jacket trapezoid: shoulders wider than waist for a hint of taper.
        draw.polygon([
            (sh_l[0] - torso_pad, sh_l[1] - _scaled_radius(8)),
            (sh_r[0] + torso_pad, sh_r[1] - _scaled_radius(8)),
            (hip_r[0] + torso_pad * 0.6, shorts_top),
            (hip_l[0] - torso_pad * 0.6, shorts_top),
        ], fill=JACKET_RGB)
        # Shorts band — white rectangle from shorts_top to the hip line.
        shorts_bot = (hip_l[1] + hip_r[1]) / 2 + _scaled_radius(32)
        draw.polygon([
            (hip_l[0] - torso_pad * 0.6, shorts_top),
            (hip_r[0] + torso_pad * 0.6, shorts_top),
            (hip_r[0] + torso_pad * 0.5, shorts_bot),
            (hip_l[0] - torso_pad * 0.5, shorts_bot),
        ], fill=SHORTS_RGB)
        # Neck stub — small skin rectangle so the head's join with the
        # torso has skin tone showing instead of a hard jacket edge.
        neck = _scaled_point(NECK_XY)
        nw = _scaled_radius(18)
        nh = _scaled_radius(28)
        draw.polygon([
            (neck[0] - nw, neck[1] - nh),
            (neck[0] + nw, neck[1] - nh),
            (neck[0] + nw, neck[1] + nh),
            (neck[0] - nw, neck[1] + nh),
        ], fill=SKIN_RGB)
    return _supersampled_draw(paint)


def _draw_arm(
    shoulder: tuple[float, float], tip: tuple[float, float],
) -> Image.Image:
    """A skin capsule for the limb plus a slightly wider skin disc at
    the wrist for the hand silhouette. Rendered in rest pose; the
    rotation deformer rotates the whole layer around the shoulder."""
    def paint(draw: ImageDraw.ImageDraw) -> None:
        _draw_capsule(draw, shoulder, tip, LIMB_THICKNESS, SKIN_RGB)
        # Hand: a larger oval at the tip so the wrist reads as having
        # an articulated hand even without finger geometry.
        cx, cy = _scaled_point(tip)
        hr = _scaled_radius(LIMB_THICKNESS * 0.62)
        draw.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), fill=SKIN_RGB)
    return _supersampled_draw(paint)


def _draw_leg(
    hip: tuple[float, float], foot: tuple[float, float],
) -> Image.Image:
    """Skin capsule for the thigh + calf, dark oval for the shoe."""
    def paint(draw: ImageDraw.ImageDraw) -> None:
        _draw_capsule(draw, hip, foot, LEG_THICKNESS, SKIN_RGB)
        cx, cy = _scaled_point(foot)
        sw = _scaled_radius(LEG_THICKNESS * 0.85)
        sh = _scaled_radius(LEG_THICKNESS * 0.55)
        draw.ellipse((cx - sw, cy - sh, cx + sw, cy + sh), fill=SHOE_RGB)
    return _supersampled_draw(paint)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def _png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _part_drawable(part: _Part) -> tuple[Drawable, str, bytes]:
    """Wrap a rendered part in a Drawable using the standard grid mesh."""
    arr = np.array(part.image, dtype=np.uint8)
    vertices, indices, uvs = triangulate_alpha_grid(arr, cell_size=CELL_SIZE)
    tex = f"textures/{part.id}.png"
    return (
        Drawable(
            id=part.id, texture=tex,
            vertices=vertices, indices=indices, uvs=uvs,
            draw_order=part.draw_order,
        ),
        tex, _png_bytes(part.image),
    )


# Local rotation amplitudes. Smaller than the previous demo since
# rest-pose arms already hang down — a 95° swing would put them
# horizontal, not the other way around.
HEAD_YAW_MAX = math.radians(12)
BODY_LEAN_MAX = math.radians(6)
ARM_SWING_MAX = math.radians(80)
LEG_SWING_MAX = math.radians(14)


def _rotation_form(anchor: tuple[float, float], angle_rad: float) -> dict:
    return {"anchor": [float(anchor[0]), float(anchor[1])],
            "angle": float(angle_rad)}


def _three_key(
    pid: str, deformer_id: str,
    anchor: tuple[float, float], swing: float,
) -> Parameter:
    return Parameter(
        id=pid, min=-1.0, max=1.0, default=0.0,
        keys=[
            ParameterKey(value=-1.0, forms={
                deformer_id: _rotation_form(anchor, -swing),
            }),
            ParameterKey(value=0.0, forms={
                deformer_id: _rotation_form(anchor, 0.0),
            }),
            ParameterKey(value=1.0, forms={
                deformer_id: _rotation_form(anchor, swing),
            }),
        ],
    )


def _build_doc() -> PuppetDocument:
    doc = PuppetDocument(size=(CANVAS_W, CANVAS_H))
    parts = [
        _Part("torso", _draw_torso(), draw_order=1),
        _Part("leg_left", _draw_leg(HIP_LEFT, FOOT_LEFT), draw_order=2),
        _Part("leg_right", _draw_leg(HIP_RIGHT, FOOT_RIGHT), draw_order=3),
        _Part("arm_left", _draw_arm(SHOULDER_LEFT, ARM_LEFT_TIP), draw_order=4),
        _Part("arm_right", _draw_arm(SHOULDER_RIGHT, ARM_RIGHT_TIP), draw_order=5),
        _Part("head", _draw_head(), draw_order=6),
    ]
    for part in parts:
        drawable, tex, png = _part_drawable(part)
        doc.drawables.append(drawable)
        doc.textures[tex] = png

    body_anchor = (CANVAS_W / 2, (HEAD_CENTRE[1] + FOOT_LEFT[1]) / 2)
    all_drawable_ids = [d.id for d in doc.drawables]
    doc.deformers.extend([
        Deformer(id="body_rot", type="rotation", parent=None,
                 drawables=all_drawable_ids,
                 form=default_rotation_form(body_anchor)),
        Deformer(id="head_rot", type="rotation", parent=None,
                 drawables=["head"], form=default_rotation_form(NECK_XY)),
        Deformer(id="arm_left_rot", type="rotation", parent=None,
                 drawables=["arm_left"],
                 form=default_rotation_form(SHOULDER_LEFT)),
        Deformer(id="arm_right_rot", type="rotation", parent=None,
                 drawables=["arm_right"],
                 form=default_rotation_form(SHOULDER_RIGHT)),
        Deformer(id="leg_left_rot", type="rotation", parent=None,
                 drawables=["leg_left"],
                 form=default_rotation_form(HIP_LEFT)),
        Deformer(id="leg_right_rot", type="rotation", parent=None,
                 drawables=["leg_right"],
                 form=default_rotation_form(HIP_RIGHT)),
    ])

    doc.parameters.extend([
        _three_key("ParamHeadYaw", "head_rot", NECK_XY, HEAD_YAW_MAX),
        _three_key("ParamBodyLean", "body_rot", body_anchor, BODY_LEAN_MAX),
        _three_key("ParamArmLeftSwing", "arm_left_rot", SHOULDER_LEFT, ARM_SWING_MAX),
        _three_key("ParamArmRightSwing", "arm_right_rot", SHOULDER_RIGHT, ARM_SWING_MAX),
        _three_key("ParamLegLeftSwing", "leg_left_rot", HIP_LEFT, LEG_SWING_MAX),
        _three_key("ParamLegRightSwing", "leg_right_rot", HIP_RIGHT, LEG_SWING_MAX),
    ])

    doc.motions.extend([
        _idle(), _wave(), _curtsy(), _cheer(), _step_right(),
    ])
    return doc


# ---------------------------------------------------------------------------
# Motions
# ---------------------------------------------------------------------------


def _sine_track(
    pid: str, dur: float, amp: float,
    *, phase: float = 0.0, n: int = 32, bias: float = 0.0,
) -> MotionTrack:
    out: list[MotionSegment] = []
    for i in range(n):
        t0 = dur * i / n
        t1 = dur * (i + 1) / n
        v0 = bias + amp * math.sin(2.0 * math.pi * t0 / dur + phase)
        v1 = bias + amp * math.sin(2.0 * math.pi * t1 / dur + phase)
        out.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return MotionTrack(param_id=pid, segments=out)


def _idle() -> Motion:
    """Subtle body sway with arms swinging gently at their sides."""
    return Motion(name="idle", duration=4.0, loop=True, tracks=[
        _sine_track("ParamBodyLean", 4.0, 0.5),
        _sine_track("ParamHeadYaw", 4.0, 0.35, phase=math.pi),
        _sine_track("ParamArmLeftSwing", 4.0, 0.18),
        _sine_track("ParamArmRightSwing", 4.0, 0.18, phase=math.pi),
    ])


def _wave() -> Motion:
    """Right arm raises and waves side to side."""
    dur = 2.0
    n = 32
    segs: list[MotionSegment] = []
    for i in range(n):
        t0 = dur * i / n
        t1 = dur * (i + 1) / n
        base = -0.95
        wobble0 = 0.18 * math.sin(2.0 * math.pi * 4 * t0 / dur)
        wobble1 = 0.18 * math.sin(2.0 * math.pi * 4 * t1 / dur)
        segs.append(MotionSegment(type="linear", p0=(t0, base + wobble0),
                                  p1=(t1, base + wobble1)))
    return Motion(name="wave", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamArmRightSwing", segments=segs),
        _sine_track("ParamHeadYaw", dur, 0.45),
    ])


def _curtsy() -> Motion:
    """Body bows forward + head dips."""
    dur = 2.4
    return Motion(name="curtsy", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamBodyLean", segments=[
            MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.6, 1.0)),
            MotionSegment(type="linear", p0=(0.6, 1.0), p1=(1.4, 1.0)),
            MotionSegment(type="linear", p0=(1.4, 1.0), p1=(2.0, 0.0)),
            MotionSegment(type="linear", p0=(2.0, 0.0), p1=(2.4, 0.0)),
        ]),
        MotionTrack(param_id="ParamHeadYaw", segments=[
            MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.6, 0.5)),
            MotionSegment(type="linear", p0=(0.6, 0.5), p1=(1.4, 0.5)),
            MotionSegment(type="linear", p0=(1.4, 0.5), p1=(2.0, 0.0)),
            MotionSegment(type="linear", p0=(2.0, 0.0), p1=(2.4, 0.0)),
        ]),
    ])


def _cheer() -> Motion:
    """Both arms swing up — positive on the left arm + negative on
    the right both raise upward under the build's sign convention."""
    dur = 2.0
    n = 32
    arm_left: list[MotionSegment] = []
    arm_right: list[MotionSegment] = []
    for i in range(n):
        t0 = dur * i / n
        t1 = dur * (i + 1) / n
        s0 = math.sin(2.0 * math.pi * t0 / dur)
        s1 = math.sin(2.0 * math.pi * t1 / dur)
        arm_left.append(MotionSegment(type="linear", p0=(t0, -s0), p1=(t1, -s1)))
        arm_right.append(MotionSegment(type="linear", p0=(t0, +s0), p1=(t1, +s1)))
    return Motion(name="cheer", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamArmLeftSwing", segments=arm_left),
        MotionTrack(param_id="ParamArmRightSwing", segments=arm_right),
        _sine_track("ParamHeadYaw", dur, 0.4, phase=math.pi),
    ])


def _step_right() -> Motion:
    """Right leg lifts out to the side."""
    dur = 1.6
    return Motion(name="step_right", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamLegRightSwing", segments=[
            MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.5, -1.0)),
            MotionSegment(type="linear", p0=(0.5, -1.0), p1=(1.0, -1.0)),
            MotionSegment(type="linear", p0=(1.0, -1.0), p1=(1.6, 0.0)),
        ]),
    ])


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = _build_doc()
    save_puppet(doc, OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH} (size={OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
