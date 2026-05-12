"""Complete puppet example — wires every shipping feature into one rig.

Builds a procedurally-drawn chibi character that demonstrates the
full surface of the puppet plugin:

* **14 drawables** — head, body, two arms, two legs, left/right eye
  open + close variants, mouth open + close, and two hair strands
  for physics-driven motion.
* **Auto-meshed via** :func:`puppet.auto_mesh.triangulate_alpha_grid`
  so each part keeps its own anti-aliased silhouette without any
  source-image slicing.
* **Cubism-standard parameter catalogue** (``ParamAngleX/Y/Z``,
  ``ParamEyeLOpen``, ``ParamMouthOpenY``, ``ParamCheek``, …) seeded
  by :mod:`puppet.standard_params` so the live drivers (webcam,
  blink, lip-sync, cursor look-at, viseme) work without per-rig
  configuration.
* **Bone hierarchy** — ``root → torso → {head, arm_l, arm_r}`` plus
  ``root → {leg_l, leg_r}``. The runtime's topological sort means
  rotating ``torso`` rotates head + arms together (FK).
* **1D parameter keyforms** for head Z-tilt and arm swing.
* **2D parameter blend** keyed on ``ParamAngleX × ParamAngleY`` so
  the head's offset is bilinear across both axes.
* **Opacity keys** — left/right eye open<->close cross-fade keyed on
  ``ParamEyeLOpen`` / ``ParamEyeROpen``; mouth close<->open keyed on
  ``ParamMouthOpenY``.
* **Multiply-color tint** — the head's skin colour shifts toward
  rosy as ``ParamCheek`` rises (blush effect).
* **Two expressions** — ``smile`` and ``surprised`` (additive
  parameter overrides).
* **Three motions** — ``idle_a`` and ``idle_b`` in the ``Idle`` group
  (so the idle motion cycler picks between them), plus ``tap_head``
  in the ``TapHead`` group (so the head HitArea triggers it).
  Each motion carries fade-in / fade-out durations.
* **Physics rig** — anchored on ``ParamAngleX``, drives
  ``ParamHairFront`` so the hair lags the head's turn.
* **Two hit areas** — ``head`` (clicks fire the ``TapHead`` motion
  group) and ``body`` (clicks toggle the ``surprised`` expression).
* **Part tree** — ``face`` (head + eyes + mouth) and ``hair`` and
  ``body_group`` (torso + arms + legs) with cascading visibility.

Run::

    python examples/puppet/puppet_complete_example.py

Outputs::

    examples/puppet/puppet_complete.puppet

Drag the resulting file into the Puppet tab. Every input toggle
(Webcam tracking, Auto idle, Idle motions, Mic lip-sync, Drag-track
head) should produce visible motion immediately — that's the whole
point of the rig.
"""
from __future__ import annotations

import math
import sys
from collections.abc import Callable
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
    BlendKey,
    Deformer,
    Drawable,
    Expression,
    ExpressionParam,
    HitArea,
    Motion,
    MotionSegment,
    MotionTrack,
    ParameterBlend,
    ParameterKey,
    Part,
    PhysicsParticle,
    PhysicsRig,
    PuppetDocument,
)
from puppet.document_io import save_puppet    # noqa: E402
from puppet.standard_params import standard_parameters    # noqa: E402
from puppet.validator import severity_counts, validate    # noqa: E402

OUTPUT_PATH = Path(__file__).with_name("puppet_complete.puppet")


# ---------------------------------------------------------------------------
# Canvas + figure landmarks
# ---------------------------------------------------------------------------

CANVAS_W = 520
CANVAS_H = 760
SUPERSAMPLE = 4   # render NxN then downscale with LANCZOS for AA
CELL_SIZE = 16    # finer mesh than the basic example — better deforms

# Every drawable's pixel position derives from these landmarks so a
# single nudge here moves the whole figure consistently.
HEAD_CENTRE = (CANVAS_W // 2, 180)
HEAD_RADIUS = 95

NECK_XY = (CANVAS_W // 2, 270)
SHOULDER_LEFT = (CANVAS_W // 2 - 70, 305)
SHOULDER_RIGHT = (CANVAS_W // 2 + 70, 305)
HIP_LEFT = (CANVAS_W // 2 - 35, 525)
HIP_RIGHT = (CANVAS_W // 2 + 35, 525)
FOOT_LEFT = (CANVAS_W // 2 - 55, 720)
FOOT_RIGHT = (CANVAS_W // 2 + 55, 720)
ARM_LEFT_TIP = (CANVAS_W // 2 - 95, 530)
ARM_RIGHT_TIP = (CANVAS_W // 2 + 95, 530)

EYE_LEFT_CENTRE = (CANVAS_W // 2 - 32, 175)
EYE_RIGHT_CENTRE = (CANVAS_W // 2 + 32, 175)
EYE_RADIUS = 12
MOUTH_CENTRE = (CANVAS_W // 2, 220)

LIMB_THICKNESS = 38
LEG_THICKNESS = 46

# Palette — chibi anime style. No pure black so the rig doesn't look
# like a logo; warm skin, soft lavender hair, navy + white sailor top.
SKIN_RGB = (252, 220, 195)
SKIN_SHADOW = (228, 188, 165)
HAIR_RGB = (155, 130, 200)
HAIR_SHADOW = (122, 100, 168)
JACKET_RGB = (72, 95, 162)
COLLAR_RGB = (250, 250, 252)
COLLAR_TRIM = (60, 80, 145)
SCARF_RGB = (208, 78, 92)
SKIRT_RGB = (92, 72, 132)
SKIRT_SHADOW = (66, 50, 100)
SHOE_RGB = (60, 56, 72)
SOCK_RGB = (250, 250, 252)
EYE_WHITE = (252, 252, 252)
EYE_IRIS = (110, 175, 220)
EYE_IRIS_SHADOW = (78, 138, 188)
EYE_PUPIL = (38, 48, 72)
EYE_OUTLINE = (52, 40, 68)
MOUTH_RGB = (216, 110, 130)
BLUSH_RGB = (255, 180, 188, 130)


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def _blank() -> Image.Image:
    return Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))


def _supersampled(paint: Callable[[ImageDraw.ImageDraw], None]) -> Image.Image:
    """Render ``paint`` onto an oversized canvas then downscale with
    LANCZOS — Pillow's per-primitive AA differs between releases,
    supersampling sidesteps the lottery."""
    big = Image.new(
        "RGBA",
        (CANVAS_W * SUPERSAMPLE, CANVAS_H * SUPERSAMPLE),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(big)
    paint(draw)
    return big.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)


def _scale_point(p: tuple[int, int]) -> tuple[int, int]:
    return p[0] * SUPERSAMPLE, p[1] * SUPERSAMPLE


def _scale(value: float) -> int:
    return int(value * SUPERSAMPLE)


def _png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Body part drawing functions — one per drawable
# ---------------------------------------------------------------------------


def _draw_head() -> Image.Image:
    """Chibi-style face: skin oval slightly taller than wide, two ear
    blobs, three-clump bangs across the forehead, blush dots, and a
    soft nose hint. The eyes and mouth are separate drawables so they
    can cross-fade via opacity keys."""
    def paint(d: ImageDraw.ImageDraw) -> None:
        cx, cy = _scale_point(HEAD_CENTRE)
        r = _scale(HEAD_RADIUS)
        # Slight chin taper — head is taller than it is wide
        d.ellipse(
            (cx - r, cy - int(r * 1.08),
             cx + r, cy + int(r * 1.02)),
            fill=SKIN_RGB,
        )
        # Ears — small ovals tucked at the sides
        ear_w, ear_h = _scale(14), _scale(22)
        d.ellipse(
            (cx - r - ear_w // 2 + _scale(4), cy - ear_h // 2,
             cx - r + ear_w // 2 + _scale(4), cy + ear_h // 2),
            fill=SKIN_RGB,
        )
        d.ellipse(
            (cx + r - ear_w // 2 - _scale(4), cy - ear_h // 2,
             cx + r + ear_w // 2 - _scale(4), cy + ear_h // 2),
            fill=SKIN_RGB,
        )
        # Bangs — wide cap covering the forehead to the eyebrow line,
        # then three small clumps poking just below it as bang tips,
        # plus a small wisp between the eyes. Cap_bot stays well above
        # the eye centres so the eyes never disappear under the hair.
        cap_top = cy - int(r * 1.10)
        cap_bot = cy - int(r * 0.35)
        d.ellipse(
            (cx - int(r * 1.02), cap_top,
             cx + int(r * 1.02), cap_bot),
            fill=HAIR_RGB,
        )
        # Bang tips — small ellipses overlapping the cap's lower edge
        for cx_frac, c_r_frac in [(-0.55, 0.22), (0.05, 0.26), (0.60, 0.20)]:
            ccx = cx + int(r * cx_frac)
            cr = int(r * c_r_frac)
            tip_centre_y = cap_bot - int(cr * 0.35)
            d.ellipse(
                (ccx - int(cr * 0.85), tip_centre_y - cr,
                 ccx + int(cr * 0.85), tip_centre_y + int(cr * 0.55)),
                fill=HAIR_RGB,
            )
        # Centre wisp — small triangular bang pointing between the eyes
        wisp_top_y = cap_bot - _scale(6)
        wisp_tip_y = cap_bot + _scale(10)
        d.polygon(
            [
                (cx - _scale(8), wisp_top_y),
                (cx + _scale(8), wisp_top_y),
                (cx, wisp_tip_y),
            ],
            fill=HAIR_RGB,
        )
        # Cheek blush dots
        blush_r = _scale(14)
        blush_y = cy + int(r * 0.30)
        for sign in (-1, 1):
            blush_x = cx + sign * int(r * 0.60)
            d.ellipse(
                (blush_x - blush_r, blush_y - blush_r,
                 blush_x + blush_r, blush_y + blush_r),
                fill=BLUSH_RGB,
            )
        # Nose — single soft tick
        nose_x = cx
        nose_y = cy + int(r * 0.08)
        d.line(
            (nose_x, nose_y, nose_x, nose_y + _scale(8)),
            fill=SKIN_SHADOW, width=_scale(2),
        )
    return _supersampled(paint)


def _draw_body() -> Image.Image:
    """Sailor-style top with white V-collar over a navy jacket, red
    scarf knot, and a pleated skirt below the hip line."""
    def paint(d: ImageDraw.ImageDraw) -> None:
        neck = _scale_point(NECK_XY)
        hip_l = _scale_point(HIP_LEFT)
        hip_r = _scale_point(HIP_RIGHT)
        # Jacket trapezoid — slightly tapered at the waist
        d.polygon(
            [
                (neck[0] - _scale(48), neck[1]),
                (neck[0] + _scale(48), neck[1]),
                (hip_r[0] + _scale(22), hip_r[1]),
                (hip_l[0] - _scale(22), hip_l[1]),
            ],
            fill=JACKET_RGB,
        )
        # Sailor collar — wraps around the shoulders, drops to a V
        collar_top = neck[1] - _scale(4)
        collar_v_y = neck[1] + _scale(50)
        d.polygon(
            [
                (neck[0] - _scale(55), collar_top),
                (neck[0] - _scale(32), collar_top + _scale(8)),
                (neck[0] - _scale(28), collar_v_y - _scale(6)),
                (neck[0], collar_v_y),
                (neck[0] + _scale(28), collar_v_y - _scale(6)),
                (neck[0] + _scale(32), collar_top + _scale(8)),
                (neck[0] + _scale(55), collar_top),
                (neck[0] + _scale(48), collar_top + _scale(40)),
                (neck[0] - _scale(48), collar_top + _scale(40)),
            ],
            fill=COLLAR_RGB,
        )
        # Collar trim — two narrow lines along the V
        d.line(
            (neck[0] - _scale(48), collar_top + _scale(40),
             neck[0], collar_v_y),
            fill=COLLAR_TRIM, width=_scale(3),
        )
        d.line(
            (neck[0] + _scale(48), collar_top + _scale(40),
             neck[0], collar_v_y),
            fill=COLLAR_TRIM, width=_scale(3),
        )
        # Scarf knot at the V tip
        d.polygon(
            [
                (neck[0] - _scale(10), collar_v_y),
                (neck[0] + _scale(10), collar_v_y),
                (neck[0] + _scale(7), collar_v_y + _scale(20)),
                (neck[0] - _scale(7), collar_v_y + _scale(20)),
            ],
            fill=SCARF_RGB,
        )
        # Skirt — pleats hinted with vertical shadow lines
        skirt_top_y = hip_l[1] + _scale(2)
        skirt_bot_y = hip_l[1] + _scale(60)
        skirt_l = hip_l[0] - _scale(50)
        skirt_r = hip_r[0] + _scale(50)
        d.polygon(
            [
                (hip_l[0] - _scale(18), skirt_top_y),
                (hip_r[0] + _scale(18), skirt_top_y),
                (skirt_r, skirt_bot_y),
                (skirt_l, skirt_bot_y),
            ],
            fill=SKIRT_RGB,
        )
        # Pleat shadow lines
        n_pleats = 5
        pleat_span = skirt_r - skirt_l
        for i in range(1, n_pleats):
            t = i / n_pleats
            x_top = (hip_l[0] - _scale(18)) + int(
                t * (hip_r[0] + _scale(18) - (hip_l[0] - _scale(18))),
            )
            x_bot = skirt_l + int(t * pleat_span)
            d.line(
                (x_top, skirt_top_y + _scale(6), x_bot, skirt_bot_y),
                fill=SKIRT_SHADOW, width=_scale(2),
            )
    return _supersampled(paint)


def _draw_arm(start: tuple[int, int], tip: tuple[int, int]) -> Image.Image:
    """Tapered sleeve + skin forearm + small round hand. Two-segment
    construction so the arm has visible "elbow taper" instead of a
    uniform cylinder."""
    def paint(d: ImageDraw.ImageDraw) -> None:
        sx, sy = _scale_point(start)
        tx, ty = _scale_point(tip)
        dx, dy = tx - sx, ty - sy
        length = max(1.0, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        shoulder_w = _scale(LIMB_THICKNESS // 2 + 4)
        elbow_w = _scale(LIMB_THICKNESS // 2 - 2)
        wrist_w = _scale(LIMB_THICKNESS // 2 - 10)
        # Elbow point — 60% down the arm
        ex = sx + dx * 0.60
        ey = sy + dy * 0.60
        # Sleeve (shoulder → elbow): jacket colour
        d.polygon(
            [
                (sx + nx * shoulder_w, sy + ny * shoulder_w),
                (sx - nx * shoulder_w, sy - ny * shoulder_w),
                (ex - nx * elbow_w, ey - ny * elbow_w),
                (ex + nx * elbow_w, ey + ny * elbow_w),
            ],
            fill=JACKET_RGB,
        )
        # Sleeve cuff — white collar trim band right at the elbow
        cuff_inner = 0.55
        ix = sx + dx * cuff_inner
        iy = sy + dy * cuff_inner
        cw = _scale(LIMB_THICKNESS // 2 - 1)
        d.polygon(
            [
                (ix + nx * cw, iy + ny * cw),
                (ix - nx * cw, iy - ny * cw),
                (ex - nx * elbow_w, ey - ny * elbow_w),
                (ex + nx * elbow_w, ey + ny * elbow_w),
            ],
            fill=COLLAR_RGB,
        )
        # Forearm (elbow → wrist): skin
        d.polygon(
            [
                (ex + nx * elbow_w, ey + ny * elbow_w),
                (ex - nx * elbow_w, ey - ny * elbow_w),
                (tx - nx * wrist_w, ty - ny * wrist_w),
                (tx + nx * wrist_w, ty + ny * wrist_w),
            ],
            fill=SKIN_RGB,
        )
        # Hand (round disc, slightly larger than the wrist)
        hand_r = _scale(17)
        d.ellipse(
            (tx - hand_r, ty - hand_r + _scale(2),
             tx + hand_r, ty + hand_r + _scale(2)),
            fill=SKIN_RGB,
        )
    return _supersampled(paint)


def _draw_leg(hip: tuple[int, int], foot: tuple[int, int]) -> Image.Image:
    """Skin leg with white knee-high sock + dark shoe."""
    def paint(d: ImageDraw.ImageDraw) -> None:
        hx, hy = _scale_point(hip)
        fx, fy = _scale_point(foot)
        # Bare-skin upper leg
        upper_w = _scale(LEG_THICKNESS // 2 + 2)
        knee_y = (hy + fy) // 2
        knee_x = (hx + fx) // 2
        d.polygon(
            [
                (hx - upper_w, hy),
                (hx + upper_w, hy),
                (knee_x + upper_w - _scale(4), knee_y),
                (knee_x - upper_w + _scale(4), knee_y),
            ],
            fill=SKIN_RGB,
        )
        # White knee-high sock from the knee down to the shoe
        sock_top_w = _scale(LEG_THICKNESS // 2 - 2)
        sock_bot_w = _scale(LEG_THICKNESS // 2 - 8)
        d.polygon(
            [
                (knee_x - sock_top_w, knee_y),
                (knee_x + sock_top_w, knee_y),
                (fx + sock_bot_w, fy - _scale(8)),
                (fx - sock_bot_w, fy - _scale(8)),
            ],
            fill=SOCK_RGB,
        )
        # Sock band — narrow shadow line at the top of the sock
        d.line(
            (knee_x - sock_top_w, knee_y + _scale(4),
             knee_x + sock_top_w, knee_y + _scale(4)),
            fill=(220, 220, 226), width=_scale(2),
        )
        # Shoe — squat oval at the foot
        d.ellipse(
            (fx - _scale(28), fy - _scale(12),
             fx + _scale(28), fy + _scale(20)),
            fill=SHOE_RGB,
        )
    return _supersampled(paint)


def _draw_eye(centre: tuple[int, int], *, open_: bool) -> Image.Image:
    """Anime-style eye when open: rounded outline + sclera + iris +
    pupil + highlight + lower-lash hint. The closed variant is a
    single curved lash arc — the workspace cross-fades between the
    two via ``ParamEyeLOpen`` / ``ParamEyeROpen`` opacity keys."""
    def paint(d: ImageDraw.ImageDraw) -> None:
        cx, cy = _scale_point(centre)
        r = _scale(EYE_RADIUS)
        if open_:
            # Outer lid (slightly almond, taller than wide)
            d.ellipse(
                (cx - r, cy - int(r * 1.15),
                 cx + r, cy + int(r * 1.15)),
                fill=EYE_OUTLINE,
            )
            # Sclera — slightly smaller than the lid so the outline shows
            d.ellipse(
                (cx - int(r * 0.85), cy - int(r * 0.95),
                 cx + int(r * 0.85), cy + int(r * 0.95)),
                fill=EYE_WHITE,
            )
            # Iris — fills most of the visible eye
            d.ellipse(
                (cx - int(r * 0.75), cy - int(r * 0.65),
                 cx + int(r * 0.75), cy + int(r * 0.85)),
                fill=EYE_IRIS,
            )
            # Iris shadow at the bottom — adds depth
            d.chord(
                (cx - int(r * 0.75), cy - int(r * 0.65),
                 cx + int(r * 0.75), cy + int(r * 0.85)),
                start=200, end=340,
                fill=EYE_IRIS_SHADOW,
            )
            # Pupil
            d.ellipse(
                (cx - int(r * 0.35), cy - int(r * 0.25),
                 cx + int(r * 0.35), cy + int(r * 0.45)),
                fill=EYE_PUPIL,
            )
            # Catchlight — bright spot upper-left
            d.ellipse(
                (cx - int(r * 0.45), cy - int(r * 0.55),
                 cx - int(r * 0.05), cy - int(r * 0.10)),
                fill=EYE_WHITE,
            )
            # Secondary tiny catchlight lower-right
            d.ellipse(
                (cx + int(r * 0.15), cy + int(r * 0.20),
                 cx + int(r * 0.40), cy + int(r * 0.50)),
                fill=EYE_WHITE,
            )
        else:
            # Closed eyelash arc — sweeps in a happy "u" shape
            d.arc(
                (cx - r, cy - int(r * 0.5),
                 cx + r, cy + int(r * 0.5)),
                start=200, end=340,
                fill=EYE_OUTLINE, width=_scale(4),
            )
            # Tiny lash flick at each end
            for sign in (-1, 1):
                lash_x = cx + sign * r
                d.line(
                    (lash_x, cy - _scale(2),
                     lash_x + sign * _scale(5), cy - _scale(6)),
                    fill=EYE_OUTLINE, width=_scale(2),
                )
    return _supersampled(paint)


def _draw_mouth(open_: bool) -> Image.Image:
    """Closed mouth = small upward arc (smile). Open mouth = small
    oval with a tongue-pink lower-lip highlight."""
    def paint(d: ImageDraw.ImageDraw) -> None:
        cx, cy = _scale_point(MOUTH_CENTRE)
        if open_:
            r = _scale(10)
            # Mouth interior
            d.ellipse(
                (cx - r, cy - int(r * 0.8),
                 cx + r, cy + int(r * 1.4)),
                fill=MOUTH_RGB,
            )
            # Lower-lip highlight curve
            d.arc(
                (cx - int(r * 0.7), cy - int(r * 0.0),
                 cx + int(r * 0.7), cy + int(r * 1.1)),
                start=15, end=165,
                fill=(245, 165, 180), width=_scale(2),
            )
        else:
            r = _scale(14)
            # Smile arc — corners turn up
            d.arc(
                (cx - r, cy - int(r * 0.4),
                 cx + r, cy + int(r * 0.6)),
                start=20, end=160,
                fill=MOUTH_RGB, width=_scale(3),
            )
    return _supersampled(paint)


def _draw_hair_strand(side: int) -> Image.Image:
    """Side-hair strand. ``side`` is ``-1`` for left or ``+1`` for
    right. Each strand starts wide at the temple, tapers as it falls
    past the shoulder, with a soft inner-shadow stripe so the volume
    reads even at small angles."""
    def paint(d: ImageDraw.ImageDraw) -> None:
        cx, cy = _scale_point(HEAD_CENTRE)
        r = _scale(HEAD_RADIUS)
        anchor_x = cx + side * int(r * 0.88)
        anchor_y = cy - int(r * 0.15)
        mid_x = anchor_x + side * _scale(14)
        mid_y = anchor_y + _scale(100)
        tip_x = anchor_x + side * _scale(28)
        tip_y = anchor_y + _scale(220)
        # Main strand silhouette
        d.polygon(
            [
                (anchor_x - _scale(14), anchor_y - _scale(8)),
                (anchor_x + _scale(14), anchor_y - _scale(2)),
                (mid_x + _scale(11), mid_y),
                (tip_x + _scale(4), tip_y),
                (tip_x - _scale(4), tip_y),
                (mid_x - _scale(11), mid_y),
            ],
            fill=HAIR_RGB,
        )
        # Inner shadow stripe — darker hair colour, ~60% of the strand
        d.polygon(
            [
                (anchor_x - _scale(6), anchor_y),
                (anchor_x + _scale(2), anchor_y),
                (mid_x - _scale(2), mid_y - _scale(20)),
                (mid_x - _scale(8), mid_y - _scale(15)),
            ],
            fill=HAIR_SHADOW,
        )
    return _supersampled(paint)


# ---------------------------------------------------------------------------
# Drawable construction
# ---------------------------------------------------------------------------


def _drawable_from_pil(
    image: Image.Image, *, id_: str, draw_order: int,
) -> tuple[Drawable, bytes]:
    """Auto-mesh ``image`` and wrap the result in a :class:`Drawable`.
    Returns ``(drawable, png_bytes)`` — the bytes go straight into
    ``doc.textures``."""
    rgba = np.asarray(image, dtype=np.uint8)
    vertices, indices, uvs = triangulate_alpha_grid(rgba, cell_size=CELL_SIZE)
    texture_path = f"textures/{id_}.png"
    return (
        Drawable(
            id=id_, texture=texture_path,
            vertices=vertices, indices=indices, uvs=uvs,
            draw_order=draw_order,
        ),
        _png_bytes(image),
    )


def _build_all_drawables() -> tuple[list[Drawable], dict[str, bytes]]:
    """Render every body part to PIL, auto-mesh each one, and return
    the drawable + texture map. Draw order goes back-to-front: hair
    behind body, body behind face features."""
    specs: list[tuple[str, Image.Image, int]] = [
        # Hair strands sit behind everything else so the body
        # silhouette covers the anchor join.
        ("hair_back_l", _draw_hair_strand(-1), 0),
        ("hair_back_r", _draw_hair_strand(+1), 0),
        # Limbs below the torso
        ("leg_l", _draw_leg(HIP_LEFT, FOOT_LEFT), 5),
        ("leg_r", _draw_leg(HIP_RIGHT, FOOT_RIGHT), 5),
        ("body", _draw_body(), 10),
        ("arm_l", _draw_arm(SHOULDER_LEFT, ARM_LEFT_TIP), 15),
        ("arm_r", _draw_arm(SHOULDER_RIGHT, ARM_RIGHT_TIP), 15),
        ("head", _draw_head(), 20),
        ("eye_l_close", _draw_eye(EYE_LEFT_CENTRE, open_=False), 30),
        ("eye_l_open", _draw_eye(EYE_LEFT_CENTRE, open_=True), 31),
        ("eye_r_close", _draw_eye(EYE_RIGHT_CENTRE, open_=False), 30),
        ("eye_r_open", _draw_eye(EYE_RIGHT_CENTRE, open_=True), 31),
        ("mouth_close", _draw_mouth(open_=False), 32),
        ("mouth_open", _draw_mouth(open_=True), 32),
    ]
    drawables: list[Drawable] = []
    textures: dict[str, bytes] = {}
    for id_, image, draw_order in specs:
        drawable, png_bytes = _drawable_from_pil(image, id_=id_, draw_order=draw_order)
        drawables.append(drawable)
        textures[drawable.texture] = png_bytes
    return drawables, textures


# ---------------------------------------------------------------------------
# Rigging — deformers, parameters, opacity keys, motions, expressions
# ---------------------------------------------------------------------------


def _build_deformers() -> list[Deformer]:
    """Three rotation deformers wired in a parent chain. The runtime's
    topological sort applies ``root`` → ``torso`` → ``head`` in order
    so a torso lean carries the head + arms with it."""
    return [
        Deformer(
            id="root", type="rotation", parent=None,
            drawables=["body", "arm_l", "arm_r", "head",
                       "eye_l_open", "eye_l_close", "eye_r_open",
                       "eye_r_close", "mouth_open", "mouth_close",
                       "hair_back_l", "hair_back_r",
                       "leg_l", "leg_r"],
            form=default_rotation_form(HEAD_CENTRE),
        ),
        Deformer(
            id="torso", type="rotation", parent="root",
            drawables=["body", "arm_l", "arm_r", "head",
                       "eye_l_open", "eye_l_close", "eye_r_open",
                       "eye_r_close", "mouth_open", "mouth_close"],
            form=default_rotation_form(NECK_XY),
        ),
        Deformer(
            id="head_rot", type="rotation", parent="torso",
            drawables=["head", "eye_l_open", "eye_l_close",
                       "eye_r_open", "eye_r_close",
                       "mouth_open", "mouth_close"],
            form=default_rotation_form(HEAD_CENTRE),
        ),
    ]


def _wire_parameter_keys(doc: PuppetDocument) -> None:
    """1D keyforms — ``ParamAngleZ`` tilts the head, ``ParamBodyAngleZ``
    leans the torso. Each parameter writes to a different deformer so
    they compose cleanly."""
    deg = math.radians(15.0)
    _add_keys(doc, "ParamAngleZ", {
        -1.0: {"head_rot": {"angle": -deg}},
        0.0: {"head_rot": {"angle": 0.0}},
        1.0: {"head_rot": {"angle": deg}},
    })
    body_deg = math.radians(6.0)
    _add_keys(doc, "ParamBodyAngleZ", {
        -1.0: {"torso": {"angle": -body_deg}},
        0.0: {"torso": {"angle": 0.0}},
        1.0: {"torso": {"angle": body_deg}},
    })


def _add_keys(
    doc: PuppetDocument,
    param_id: str,
    keys: dict[float, dict[str, dict]],
) -> None:
    param = doc.parameter(param_id)
    if param is None:
        return
    param.keys = [
        ParameterKey(value=float(v), forms={k: dict(form) for k, form in entry.items()})
        for v, entry in sorted(keys.items())
    ]


def _build_parameter_blend() -> ParameterBlend:
    """Bilinear blend on ``ParamAngleX`` × ``ParamAngleY``. Amplitude
    set high enough (~17°) that webcam / cursor-track drift is
    clearly visible — the bilinear interpolation between four corners
    is the headline 2D-keyform feature."""
    return ParameterBlend(
        id="head_xy_blend",
        parameters=["ParamAngleX", "ParamAngleY"],
        keys=[
            BlendKey(coords=[-1.0, -1.0], forms={"head_rot": {"angle": -0.30}}),
            BlendKey(coords=[1.0, -1.0], forms={"head_rot": {"angle": 0.30}}),
            BlendKey(coords=[-1.0, 1.0], forms={"head_rot": {"angle": -0.20}}),
            BlendKey(coords=[1.0, 1.0], forms={"head_rot": {"angle": 0.20}}),
        ],
    )


def _wire_opacity_keys(doc: PuppetDocument) -> None:
    """Eye blink cross-fade + mouth open/close cross-fade. The
    standard input drivers (``InputEngine`` blink, ``audio_to_viseme``
    lip-sync) push the matching parameter values, so this is the only
    glue needed."""
    for side in ("l", "r"):
        open_id = f"eye_{side}_open"
        close_id = f"eye_{side}_close"
        param = f"ParamEye{side.upper()}Open"
        _opacity_curve(doc, open_id, param, [(0.0, 0.0), (1.0, 1.0)])
        _opacity_curve(doc, close_id, param, [(0.0, 1.0), (1.0, 0.0)])
    _opacity_curve(doc, "mouth_open", "ParamMouthOpenY",
                   [(0.0, 0.0), (1.0, 1.0)])
    _opacity_curve(doc, "mouth_close", "ParamMouthOpenY",
                   [(0.0, 1.0), (1.0, 0.0)])


def _opacity_curve(
    doc: PuppetDocument,
    drawable_id: str,
    parameter: str,
    stops: list[tuple[float, float]],
) -> None:
    drawable = doc.drawable(drawable_id)
    if drawable is None:
        return
    if drawable.opacity_keys is None:
        drawable.opacity_keys = []
    drawable.opacity_keys.append({
        "parameter": parameter,
        "stops": [{"value": v, "alpha": a} for v, a in stops],
    })


def _wire_cheek_tint(doc: PuppetDocument) -> None:
    """``ParamCheek`` shifts the head's multiply colour toward rosy.
    A cleaner production rig would add a separate cheek-overlay
    drawable; tinting the head shows the colour-key feature
    end-to-end in one place."""
    head = doc.drawable("head")
    if head is None:
        return
    head.multiply_color_keys = [{
        "parameter": "ParamCheek",
        "stops": [
            {"value": 0.0, "color": (1.0, 1.0, 1.0)},
            {"value": 1.0, "color": (1.0, 0.78, 0.82)},
        ],
    }]


def _build_expressions() -> list[Expression]:
    return [
        Expression(
            name="smile",
            params=[
                ExpressionParam(id="ParamMouthForm", value=0.8, mode="overwrite"),
                ExpressionParam(id="ParamMouthOpenY", value=0.3, mode="additive"),
                ExpressionParam(id="ParamCheek", value=0.5, mode="overwrite"),
            ],
        ),
        Expression(
            name="surprised",
            params=[
                ExpressionParam(id="ParamMouthOpenY", value=0.8, mode="overwrite"),
                ExpressionParam(id="ParamEyeLOpen", value=1.0, mode="overwrite"),
                ExpressionParam(id="ParamEyeROpen", value=1.0, mode="overwrite"),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Motions
# ---------------------------------------------------------------------------


def _linear_motion(
    name: str,
    duration: float,
    *,
    group: str,
    tracks: list[tuple[str, list[tuple[float, float]]]],
    loop: bool = False,
    fade_in: float = 0.5,
    fade_out: float = 0.5,
) -> Motion:
    """Build a motion from ``(param_id, [(t, v), …])`` pairs. Each
    consecutive pair becomes one linear segment — the simplest curve
    type the runtime understands."""
    motion = Motion(
        name=name, duration=duration, loop=loop, group=group,
        fade_in_duration=fade_in, fade_out_duration=fade_out,
    )
    for param_id, samples in tracks:
        segments: list[MotionSegment] = []
        for i in range(len(samples) - 1):
            segments.append(MotionSegment(
                type="linear", p0=samples[i], p1=samples[i + 1],
            ))
        motion.tracks.append(MotionTrack(param_id=param_id, segments=segments))
    return motion


def _build_motions() -> list[Motion]:
    """Two Idle motions for the cycler to pick between, plus one
    TapHead response for the head hit area.

    Amplitudes deliberately large — a "demo" rig has to move
    visibly. A production rig would dial these down to ~0.2 for a
    more naturalistic idle."""
    return [
        _linear_motion(
            "idle_breath", 4.0, group="Idle", loop=True,
            tracks=[
                # Head tilts L → R → L → 0 over the cycle. ±0.6 maps
                # through the ParamAngleZ keyforms to about ±9° — small
                # but unmistakable.
                ("ParamAngleZ", [
                    (0.0, 0.0), (1.0, 0.6), (2.0, 0.0),
                    (3.0, -0.6), (4.0, 0.0),
                ]),
                # Body lean alternates with the head so the figure
                # never freezes.
                ("ParamBodyAngleZ", [
                    (0.0, 0.0), (1.0, 0.3), (2.0, 0.0),
                    (3.0, -0.3), (4.0, 0.0),
                ]),
                ("ParamBreath", [(0.0, 0.0), (2.0, 1.0), (4.0, 0.0)]),
            ],
        ),
        _linear_motion(
            "idle_look", 5.0, group="Idle", loop=True,
            tracks=[
                # Through the 2D blend (±0.30 rad on the angle), this
                # sweeps the head about 17° to each side.
                ("ParamAngleX", [
                    (0.0, 0.0), (1.5, 0.8), (3.5, -0.8), (5.0, 0.0),
                ]),
                ("ParamAngleY", [(0.0, 0.0), (2.5, 0.4), (5.0, 0.0)]),
                ("ParamMouthOpenY", [(0.0, 0.0), (3.0, 0.4), (5.0, 0.0)]),
            ],
        ),
        _linear_motion(
            "tap_head", 1.0, group="TapHead",
            fade_in=0.2, fade_out=0.3,
            tracks=[
                ("ParamAngleZ", [(0.0, 0.0), (0.3, 0.9), (0.7, -0.6), (1.0, 0.0)]),
                ("ParamMouthOpenY", [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)]),
                ("ParamCheek", [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)]),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Physics, hit areas, parts
# ---------------------------------------------------------------------------


def _build_physics() -> list[PhysicsRig]:
    """One four-particle Verlet chain — ``ParamAngleX`` drives the
    anchor, the chain's tip displacement writes ``ParamHairFront``,
    which an authored rig would key onto hair-strand warps. Even
    without that, the parameter writes still surface in the dock."""
    return [
        PhysicsRig(
            id="hair_chain",
            input_param="ParamAngleX",
            output_param="ParamHairFront",
            chain=[PhysicsParticle() for _ in range(4)],
        ),
    ]


def _build_hit_areas() -> list[HitArea]:
    """Two clickable regions. The workspace's HitArea handler routes
    ``area.motion`` either to a single motion or — when the value
    matches a motion *group* — to a random pick from that group."""
    return [
        HitArea(
            id="head", drawables=["head", "eye_l_open", "eye_r_open"],
            motion="TapHead",   # name of the group → random pick
        ),
        HitArea(
            id="body", drawables=["body"],
            expression="surprised",
        ),
    ]


def _build_parts() -> list[Part]:
    """Three-Part hierarchy. Toggling the ``hair`` Part's visibility
    hides both strands at once — useful for testing the cascade."""
    return [
        Part(id="face", drawables=[
            "head", "eye_l_open", "eye_l_close", "eye_r_open",
            "eye_r_close", "mouth_open", "mouth_close",
        ]),
        Part(id="hair", drawables=["hair_back_l", "hair_back_r"]),
        Part(id="body_group", drawables=[
            "body", "arm_l", "arm_r", "leg_l", "leg_r",
        ]),
    ]


# ---------------------------------------------------------------------------
# Assemble + save
# ---------------------------------------------------------------------------


def build() -> PuppetDocument:
    print(f"rendering 14 drawables at {CANVAS_W}×{CANVAS_H} (supersample ×{SUPERSAMPLE})")
    drawables, textures = _build_all_drawables()

    doc = PuppetDocument(size=(CANVAS_W, CANVAS_H))
    doc.drawables = drawables
    doc.textures = textures
    doc.parameters = standard_parameters()
    doc.deformers = _build_deformers()
    doc.parameter_blends = [_build_parameter_blend()]
    doc.expressions = _build_expressions()
    doc.motions = _build_motions()
    doc.physics_rigs = _build_physics()
    doc.hit_areas = _build_hit_areas()
    doc.parts = _build_parts()
    doc.display_names = {
        "ParamAngleX": "Head Yaw",
        "ParamAngleY": "Head Pitch",
        "ParamAngleZ": "Head Roll",
        "ParamMouthOpenY": "Mouth Open",
        "ParamCheek": "Blush",
        "ParamHairFront": "Hair Sway",
    }

    _wire_parameter_keys(doc)
    _wire_opacity_keys(doc)
    _wire_cheek_tint(doc)
    return doc


def main() -> int:
    doc = build()
    issues = validate(doc)
    counts = severity_counts(issues)
    if counts.get("error", 0):
        print(f"FAILED — {counts['error']} validator errors:")
        for issue in issues:
            if issue.severity == "error":
                print(f"  {issue.code}  {issue.location}  {issue.message}")
        return 1
    if counts.get("warning", 0):
        print(f"validator: {counts['warning']} warnings (proceeding):")
        for issue in issues:
            if issue.severity == "warning":
                print(f"  {issue.code}  {issue.location}  {issue.message}")
    print(
        f"saving to {OUTPUT_PATH.name} — "
        f"{len(doc.drawables)} drawables, "
        f"{len(doc.deformers)} deformers, "
        f"{len(doc.parameters)} parameters, "
        f"{len(doc.motions)} motions, "
        f"{len(doc.expressions)} expressions, "
        f"{len(doc.hit_areas)} hit areas, "
        f"{len(doc.parts)} parts, "
        f"{len(doc.parameter_blends)} blends, "
        f"{len(doc.physics_rigs)} physics rigs"
    )
    save_puppet(doc, OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH}")
    print()
    print("Drag the .puppet file into the Puppet tab. Try:")
    print("  • Auto idle + Idle motions toggles  → breath + alternating idle clips")
    print("  • Auto-blink toggle                  → eye-open/close cross-fade")
    print("  • Drag-track head toggle             → cursor look-at via ParamAngleX/Y")
    print("  • Click the head                     → triggers a tap_head response")
    print("  • Click the body                     → toggles the surprised expression")
    return 0


if __name__ == "__main__":
    sys.exit(main())
