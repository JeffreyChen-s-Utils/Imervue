"""Procedural anime-style girl puppet — six drawables, hand-painted with PIL.

Replaces the earlier real-illustration demos (Amiya / Rossi). Those
ran into a dead-end: any source pose with arms hanging beside the
torso forces rectangular limb slices to overlap with body pixels,
and warping a single drawable around joint pivots smears the figure
because the lattice perimeter has to stay pinned to hide the cut.

Doing it procedurally side-steps the trade-off completely — every
limb is on its own canvas-sized PNG with the rest fully transparent,
so each rotation deformer rotates exactly its body part with no
slice line and no smear. The aesthetic is anime: round face, oversized
eyes with highlights, twin-tail pink hair, sailor-style top + pleated
skirt, knee socks + Mary Jane shoes.

Pose: standing relaxed with arms held slightly out from the torso so
shoulder rotation has room to swing without colliding with the body.
"""
from __future__ import annotations

import math
import sys
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
# Canvas geometry — every joint pivot is documented here so the rotation
# anchors in the rig match the painted geometry exactly.
# ---------------------------------------------------------------------------

CANVAS_W: int = 700
CANVAS_H: int = 1000

HEAD_CENTER = (350, 230)
HEAD_RX = 110            # horizontal radius (anime face is rounder + wider)
HEAD_RY = 130            # slight vertical elongation toward the chin

NECK_Y = HEAD_CENTER[1] + HEAD_RY - 10        # 350
SHOULDER_Y = NECK_Y + 30                      # 380
TORSO_TOP = SHOULDER_Y - 6
TORSO_LEFT = 280
TORSO_RIGHT = 420
TORSO_BOTTOM = 600                            # waist line

SKIRT_TOP = TORSO_BOTTOM - 4
SKIRT_LEFT = 250
SKIRT_RIGHT = 450
SKIRT_BOTTOM = 720

# Arms held just outside the torso, slightly tilted outward at the bottom
# so the arm slice rectangle never overlaps any torso pixel.
ARM_TOP = SHOULDER_Y - 8
ARM_BOTTOM = 660
LEFT_ARM_LEFT = 220
LEFT_ARM_RIGHT = TORSO_LEFT - 4
RIGHT_ARM_LEFT = TORSO_RIGHT + 4
RIGHT_ARM_RIGHT = 480

LEG_TOP = SKIRT_BOTTOM - 6
LEG_BOTTOM = 940
LEFT_LEG_LEFT = 290
LEFT_LEG_RIGHT = 345
RIGHT_LEG_LEFT = 355
RIGHT_LEG_RIGHT = 410

# Joint pivots — rotation anchors.
NECK_PIVOT = (HEAD_CENTER[0], NECK_Y)
SHOULDER_LEFT_PIVOT = (LEFT_ARM_RIGHT - 4, SHOULDER_Y)
SHOULDER_RIGHT_PIVOT = (RIGHT_ARM_LEFT + 4, SHOULDER_Y)
HIP_LEFT_PIVOT = ((LEFT_LEG_LEFT + LEFT_LEG_RIGHT) // 2, LEG_TOP)
HIP_RIGHT_PIVOT = ((RIGHT_LEG_LEFT + RIGHT_LEG_RIGHT) // 2, LEG_TOP)
WAIST_PIVOT = (HEAD_CENTER[0], TORSO_BOTTOM)

# Rotation extremes per parameter (radians).
HEAD_YAW_MAX = math.radians(35)
BODY_LEAN_MAX = math.radians(20)
ARM_SWING_MAX = math.radians(75)
LEG_SWING_MAX = math.radians(28)

# Anime palette.
SKIN = (255, 226, 207, 255)
SKIN_LINE = (210, 150, 130, 255)
HAIR = (255, 175, 200, 255)            # soft pink twin-tails
HAIR_LINE = (180, 90, 120, 255)
HAIR_HIGHLIGHT = (255, 220, 230, 255)
EYE_WHITE = (255, 255, 255, 255)
EYE_IRIS = (110, 180, 220, 255)        # sky-blue iris
EYE_PUPIL = (35, 50, 80, 255)
EYE_HIGHLIGHT = (255, 255, 255, 255)
LASH = (60, 35, 50, 255)
MOUTH = (220, 100, 110, 255)
BLUSH = (255, 180, 190, 180)
UNIFORM = (250, 248, 245, 255)
UNIFORM_LINE = (90, 100, 130, 255)
COLLAR = (60, 95, 150, 255)
RIBBON = (220, 70, 90, 255)
SKIRT = (60, 95, 150, 255)
SKIRT_LINE = (35, 60, 100, 255)
SOCK = (250, 248, 245, 255)
SHOE = (60, 50, 70, 255)


# ---------------------------------------------------------------------------
# Per-part painters. Each returns a canvas-sized PNG with only its body part
# painted; everything else is transparent. The auto-mesh's alpha-trim drops
# empty cells, so transparent padding is free.
# ---------------------------------------------------------------------------


def _blank() -> Image.Image:
    return Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _draw_eye(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    # White
    draw.ellipse((cx - 18, cy - 22, cx + 18, cy + 22), fill=EYE_WHITE,
                 outline=LASH, width=3)
    # Iris (taller than wide for anime sparkle)
    draw.ellipse((cx - 14, cy - 18, cx + 14, cy + 20), fill=EYE_IRIS)
    # Pupil
    draw.ellipse((cx - 6, cy - 8, cx + 6, cy + 12), fill=EYE_PUPIL)
    # Top highlight
    draw.ellipse((cx - 10, cy - 18, cx - 2, cy - 10), fill=EYE_HIGHLIGHT)
    # Bottom small highlight
    draw.ellipse((cx + 4, cy + 10, cx + 9, cy + 15), fill=EYE_HIGHLIGHT)
    # Top lash thicker stroke
    draw.arc((cx - 18, cy - 24, cx + 18, cy + 4), start=180, end=360,
             fill=LASH, width=4)


def paint_head() -> bytes:
    """Face + bangs + twin-tail hair, all on one drawable.

    Layer order inside the drawable: side twin-tails first (so they
    sit *behind* the face), then the face oval, then bangs over the
    forehead, then features. Nothing extends below the chin so the
    head texture composites cleanly above the torso."""
    img = _blank()
    draw = ImageDraw.Draw(img)
    cx, cy = HEAD_CENTER

    # Twin-tail strands hanging beside the face — narrow vertical
    # ovals reaching down to mid-neck.
    for sign in (-1, +1):
        tx = cx + sign * (HEAD_RX - 18)
        ty_top = cy - HEAD_RY + 60
        ty_bot = cy + HEAD_RY + 60
        draw.rounded_rectangle(
            (tx - 32, ty_top, tx + 32, ty_bot),
            radius=22, fill=HAIR, outline=HAIR_LINE, width=3,
        )
        # Highlight along the front of the tail.
        draw.ellipse(
            (tx - 8, ty_top + 30, tx + 8, ty_bot - 30),
            fill=HAIR_HIGHLIGHT,
        )

    # Hair "cap" covering the top of the head (from the bangs back to
    # the crown). Stops at chin level so it never dips into the torso.
    cap_box = (cx - HEAD_RX - 10, cy - HEAD_RY - 20,
               cx + HEAD_RX + 10, cy - 10)
    draw.chord(cap_box, start=180, end=360, fill=HAIR, outline=HAIR_LINE,
               width=4)

    # Face shape (slightly elongated oval).
    draw.ellipse(
        (cx - HEAD_RX, cy - HEAD_RY, cx + HEAD_RX, cy + HEAD_RY),
        fill=SKIN, outline=SKIN_LINE, width=4,
    )

    # Bangs — fringe across the forehead, two soft tufts.
    bangs_top = cy - HEAD_RY + 8
    for offset in (-40, 40):
        draw.chord(
            (cx - 50 + offset, bangs_top, cx + 50 + offset, bangs_top + 100),
            start=190, end=350,
            fill=HAIR, outline=HAIR_LINE, width=3,
        )

    # Eyes (large, anime-style, with iris highlights).
    eye_y = cy + 20
    _draw_eye(draw, cx - 38, eye_y)
    _draw_eye(draw, cx + 38, eye_y)

    # Eyebrows — soft arches above each eye.
    for sign in (-1, +1):
        bx = cx + sign * 38
        draw.arc(
            (bx - 16, eye_y - 42, bx + 16, eye_y - 30),
            start=200, end=340, fill=HAIR_LINE, width=3,
        )

    # Blush ovals on the cheeks.
    for sign in (-1, +1):
        bx = cx + sign * 50
        by = cy + 56
        draw.ellipse((bx - 14, by - 6, bx + 14, by + 6), fill=BLUSH)

    # Tiny nose dot above the mouth.
    draw.ellipse((cx - 2, cy + 50, cx + 2, cy + 54), fill=SKIN_LINE)

    # Mouth — small smile.
    mx = cx
    my = cy + 76
    draw.chord((mx - 10, my - 4, mx + 10, my + 6), start=20, end=160,
               fill=MOUTH, outline=LASH, width=2)

    return _to_png_bytes(img)


def paint_torso() -> bytes:
    """Sailor-style top + pleated skirt + neck ribbon, on one drawable."""
    img = _blank()
    draw = ImageDraw.Draw(img)

    # Uniform top — rounded rectangle with sailor collar.
    draw.rounded_rectangle(
        (TORSO_LEFT, TORSO_TOP, TORSO_RIGHT, TORSO_BOTTOM + 4),
        radius=18, fill=UNIFORM, outline=UNIFORM_LINE, width=3,
    )

    # Sailor collar — V-shape across the chest.
    collar_pts = [
        (TORSO_LEFT - 4, TORSO_TOP + 4),
        (HEAD_CENTER[0] - 30, TORSO_TOP + 4),
        (HEAD_CENTER[0], TORSO_TOP + 60),
        (HEAD_CENTER[0] + 30, TORSO_TOP + 4),
        (TORSO_RIGHT + 4, TORSO_TOP + 4),
        (TORSO_RIGHT - 6, TORSO_TOP + 90),
        (HEAD_CENTER[0], TORSO_TOP + 130),
        (TORSO_LEFT + 6, TORSO_TOP + 90),
    ]
    draw.polygon(collar_pts, fill=COLLAR, outline=UNIFORM_LINE)

    # Neck ribbon (small bow at chest).
    rx, ry = HEAD_CENTER[0], TORSO_TOP + 60
    draw.polygon(
        [(rx - 22, ry - 4), (rx - 4, ry + 8), (rx - 22, ry + 20)],
        fill=RIBBON, outline=UNIFORM_LINE,
    )
    draw.polygon(
        [(rx + 22, ry - 4), (rx + 4, ry + 8), (rx + 22, ry + 20)],
        fill=RIBBON, outline=UNIFORM_LINE,
    )
    draw.rectangle((rx - 6, ry + 6, rx + 6, ry + 22), fill=RIBBON,
                   outline=UNIFORM_LINE)

    # Pleated skirt — main panel + four pleat lines.
    draw.polygon(
        [
            (TORSO_LEFT + 4, SKIRT_TOP),
            (TORSO_RIGHT - 4, SKIRT_TOP),
            (SKIRT_RIGHT, SKIRT_BOTTOM),
            (SKIRT_LEFT, SKIRT_BOTTOM),
        ],
        fill=SKIRT, outline=SKIRT_LINE,
    )
    pleats = 5
    for i in range(1, pleats):
        t = i / pleats
        x_top = TORSO_LEFT + 4 + (TORSO_RIGHT - TORSO_LEFT - 8) * t
        x_bot = SKIRT_LEFT + (SKIRT_RIGHT - SKIRT_LEFT) * t
        draw.line(
            [(x_top, SKIRT_TOP + 4), (x_bot, SKIRT_BOTTOM - 2)],
            fill=SKIRT_LINE, width=2,
        )

    # Belt accent at the waist.
    draw.rectangle(
        (TORSO_LEFT, TORSO_BOTTOM - 8, TORSO_RIGHT, TORSO_BOTTOM + 4),
        fill=COLLAR, outline=UNIFORM_LINE,
    )

    return _to_png_bytes(img)


def paint_arm(side: str) -> bytes:
    """Short uniform sleeve at top, skin-tone forearm + hand below."""
    img = _blank()
    draw = ImageDraw.Draw(img)

    if side == "left":
        x0, x1 = LEFT_ARM_LEFT, LEFT_ARM_RIGHT
    else:
        x0, x1 = RIGHT_ARM_LEFT, RIGHT_ARM_RIGHT
    sleeve_bottom = ARM_TOP + 60

    # Sleeve.
    draw.rounded_rectangle(
        (x0 - 4, ARM_TOP, x1 + 4, sleeve_bottom),
        radius=12, fill=UNIFORM, outline=UNIFORM_LINE, width=3,
    )
    # Cuff trim.
    draw.rectangle(
        (x0 - 4, sleeve_bottom - 8, x1 + 4, sleeve_bottom),
        fill=COLLAR, outline=UNIFORM_LINE,
    )
    # Forearm + hand (skin tone).
    draw.rounded_rectangle(
        (x0, sleeve_bottom - 2, x1, ARM_BOTTOM),
        radius=14, fill=SKIN, outline=SKIN_LINE, width=3,
    )
    # Knuckle hint at the bottom — a small ellipse for the hand.
    hx0, hx1 = x0 - 4, x1 + 4
    draw.ellipse(
        (hx0, ARM_BOTTOM - 14, hx1, ARM_BOTTOM + 18),
        fill=SKIN, outline=SKIN_LINE, width=3,
    )
    return _to_png_bytes(img)


def paint_leg(side: str) -> bytes:
    """Skin-tone thigh hidden by skirt; visible portion is sock + shoe."""
    img = _blank()
    draw = ImageDraw.Draw(img)
    if side == "left":
        x0, x1 = LEFT_LEG_LEFT, LEFT_LEG_RIGHT
    else:
        x0, x1 = RIGHT_LEG_LEFT, RIGHT_LEG_RIGHT

    # Bare leg (peeks out below skirt).
    draw.rounded_rectangle(
        (x0, LEG_TOP, x1, LEG_BOTTOM - 60),
        radius=14, fill=SKIN, outline=SKIN_LINE, width=3,
    )
    # Knee sock — covers the bottom half of the leg.
    sock_top = LEG_TOP + 140
    draw.rounded_rectangle(
        (x0 - 2, sock_top, x1 + 2, LEG_BOTTOM - 30),
        radius=10, fill=SOCK, outline=UNIFORM_LINE, width=3,
    )
    # Sock band stripe.
    draw.rectangle(
        (x0 - 2, sock_top + 4, x1 + 2, sock_top + 10),
        fill=COLLAR,
    )
    # Mary-Jane shoe.
    draw.rounded_rectangle(
        (x0 - 8, LEG_BOTTOM - 38, x1 + 12, LEG_BOTTOM + 6),
        radius=10, fill=SHOE, outline=LASH, width=3,
    )
    # Shoe strap.
    draw.line(
        (x0 - 4, LEG_BOTTOM - 22, x1 + 8, LEG_BOTTOM - 22),
        fill=LASH, width=3,
    )
    return _to_png_bytes(img)


# ---------------------------------------------------------------------------
# Drawable factory (auto-mesh from PNG alpha)
# ---------------------------------------------------------------------------


def _decode_rgba(png_bytes: bytes):
    import numpy as np
    from PIL import Image as _Image
    with _Image.open(BytesIO(png_bytes)) as img:
        return np.asarray(img.convert("RGBA"), dtype=np.uint8)


def _drawable_from_part(
    drawable_id: str, png_bytes: bytes, draw_order: int,
    texture_path: str, cell_size: int = 24,
) -> Drawable:
    rgba = _decode_rgba(png_bytes)
    vertices, indices, uvs = triangulate_alpha_grid(rgba, cell_size=cell_size)
    return Drawable(
        id=drawable_id, texture=texture_path,
        vertices=vertices, indices=indices, uvs=uvs,
        draw_order=draw_order,
    )


# ---------------------------------------------------------------------------
# Rig
# ---------------------------------------------------------------------------


def _rotation_at_angle(anchor: tuple[float, float], angle_rad: float) -> dict:
    return {"anchor": [float(anchor[0]), float(anchor[1])], "angle": float(angle_rad)}


def _three_key_param(
    pid: str, deformer_id: str, anchor: tuple[float, float], swing: float,
) -> Parameter:
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
        ("leg_left", lambda: paint_leg("left"), 5),
        ("leg_right", lambda: paint_leg("right"), 5),
        ("torso", paint_torso, 15),
        ("arm_left", lambda: paint_arm("left"), 25),
        ("arm_right", lambda: paint_arm("right"), 25),
        ("head", paint_head, 50),
    )
    for part_id, painter, draw_order in parts:
        png_bytes = painter()
        tex_path = f"textures/{part_id}.png"
        doc.textures[tex_path] = png_bytes
        doc.drawables.append(
            _drawable_from_part(part_id, png_bytes, draw_order, tex_path),
        )

    doc.deformers.extend([
        Deformer(id="head_rot", type="rotation", parent=None,
                 drawables=["head"], form=default_rotation_form(NECK_PIVOT)),
        Deformer(id="body_rot", type="rotation", parent=None,
                 drawables=["torso", "head", "arm_left", "arm_right"],
                 form=default_rotation_form(WAIST_PIVOT)),
        Deformer(id="arm_left_rot", type="rotation", parent=None,
                 drawables=["arm_left"],
                 form=default_rotation_form(SHOULDER_LEFT_PIVOT)),
        Deformer(id="arm_right_rot", type="rotation", parent=None,
                 drawables=["arm_right"],
                 form=default_rotation_form(SHOULDER_RIGHT_PIVOT)),
        Deformer(id="leg_left_rot", type="rotation", parent=None,
                 drawables=["leg_left"],
                 form=default_rotation_form(HIP_LEFT_PIVOT)),
        Deformer(id="leg_right_rot", type="rotation", parent=None,
                 drawables=["leg_right"],
                 form=default_rotation_form(HIP_RIGHT_PIVOT)),
    ])

    doc.parameters.extend([
        _three_key_param("ParamHeadYaw", "head_rot", NECK_PIVOT, HEAD_YAW_MAX),
        _three_key_param("ParamBodyLean", "body_rot", WAIST_PIVOT, BODY_LEAN_MAX),
        _three_key_param("ParamArmLeftSwing", "arm_left_rot",
                         SHOULDER_LEFT_PIVOT, ARM_SWING_MAX),
        _three_key_param("ParamArmRightSwing", "arm_right_rot",
                         SHOULDER_RIGHT_PIVOT, ARM_SWING_MAX),
        _three_key_param("ParamLegLeftSwing", "leg_left_rot",
                         HIP_LEFT_PIVOT, LEG_SWING_MAX),
        _three_key_param("ParamLegRightSwing", "leg_right_rot",
                         HIP_RIGHT_PIVOT, LEG_SWING_MAX),
    ])

    doc.motions.extend([
        _idle_motion(),
        _wave_motion(),
        _curtsy_motion(),
        _cheer_motion(),
        _step_motion(),
    ])
    return doc


# ---------------------------------------------------------------------------
# Motions
# ---------------------------------------------------------------------------


def _sine_track(
    pid: str, dur: float, amp: float,
    *, phase: float = 0.0, segments: int = 32,
) -> MotionTrack:
    out: list[MotionSegment] = []
    for i in range(segments):
        t0 = dur * i / segments
        t1 = dur * (i + 1) / segments
        v0 = amp * math.sin(2.0 * math.pi * t0 / dur + phase)
        v1 = amp * math.sin(2.0 * math.pi * t1 / dur + phase)
        out.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return MotionTrack(param_id=pid, segments=out)


def _idle_motion() -> Motion:
    return Motion(name="idle", duration=4.0, loop=True, tracks=[
        _sine_track("ParamBodyLean", 4.0, 0.4),
        _sine_track("ParamHeadYaw", 4.0, 0.5, phase=math.pi),
    ])


def _wave_motion() -> Motion:
    """Right arm raises and shakes — sign convention: arms hang down,
    so a NEGATIVE angle on the right arm rotates it upward (CCW in
    image coords)."""
    dur = 2.0
    n = 32
    segs: list[MotionSegment] = []
    for i in range(n):
        t0 = dur * i / n
        t1 = dur * (i + 1) / n
        base = -0.95
        wobble0 = 0.15 * math.sin(2.0 * math.pi * 4 * t0 / dur)
        wobble1 = 0.15 * math.sin(2.0 * math.pi * 4 * t1 / dur)
        segs.append(MotionSegment(type="linear", p0=(t0, base + wobble0),
                                  p1=(t1, base + wobble1)))
    return Motion(name="wave", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamArmRightSwing", segments=segs),
        _sine_track("ParamHeadYaw", dur, 0.3),
    ])


def _curtsy_motion() -> Motion:
    """Body leans forward + head dips. Anime greeting bow."""
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


def _cheer_motion() -> Motion:
    """Both arms swing up. Left arm: positive raises (CW). Right arm:
    negative raises (CCW). Two beats of arm-up + arm-down."""
    dur = 2.0
    n = 32
    arm_left: list[MotionSegment] = []
    arm_right: list[MotionSegment] = []
    for i in range(n):
        t0 = dur * i / n
        t1 = dur * (i + 1) / n
        s0 = math.sin(2.0 * math.pi * t0 / dur)
        s1 = math.sin(2.0 * math.pi * t1 / dur)
        arm_left.append(MotionSegment(type="linear", p0=(t0, +s0), p1=(t1, +s1)))
        arm_right.append(MotionSegment(type="linear", p0=(t0, -s0), p1=(t1, -s1)))
    return Motion(name="cheer", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamArmLeftSwing", segments=arm_left),
        MotionTrack(param_id="ParamArmRightSwing", segments=arm_right),
        _sine_track("ParamHeadYaw", dur, 0.3, phase=math.pi),
    ])


def _step_motion() -> Motion:
    """Right leg lifts out to the side, returns. Pure leg motion."""
    dur = 1.6
    return Motion(name="step_right", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamLegRightSwing", segments=[
            MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.5, -1.0)),
            MotionSegment(type="linear", p0=(0.5, -1.0), p1=(1.0, -1.0)),
            MotionSegment(type="linear", p0=(1.0, -1.0), p1=(1.6, 0.0)),
        ]),
    ])


def main() -> None:
    out = Path(__file__).with_name("demo_anime_girl.puppet")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = _build_doc()
    save_puppet(doc, out)
    print(f"wrote {out} (size={out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
