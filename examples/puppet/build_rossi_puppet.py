"""Build a layered rig from a real Rossi (Arknights) illustration.

Source: Danbooru post #11043219 by ``tntl_nemui`` (rating: g, no
do_not_post tag at fetch time). Local copy at
``examples/puppet/assets/rossi_source.jpg`` — credits in
``assets/CREDITS.md``.

Pipeline notes — three iterations got us here:

1. **First pass — hard-sliced drawables.** Cut the figure into six
   rectangular crops (head / torso / arms / legs), one rotation
   deformer per part. Looked clean per part but every rectangle edge
   was visible as a hard line in the output.
2. **Second pass — single drawable + pinned-boundary warp.** One
   whole-figure drawable with six warp deformers whose lattice
   perimeter stayed pinned and interior rotated. Removed the seams
   but distorted the figure: vertices near the bounds couldn't
   follow the rotation, so the body part smeared instead of
   rotating cleanly.
3. **This pass — base layer + alpha-feathered slices.** Six
   rectangular slices with feathered alpha at the rectangle edges,
   stacked on top of the **un-deformed full original** at draw_order
   0. The base fills any gap or ghost at α=1, so the feather zone
   composites part-on-base where both carry the same source color
   → no washout, no seam. Each part still rotates as a rigid slice
   so the arm / leg moves cleanly. Modest rotation angles keep the
   un-rotated base from showing through the trailing edge as an
   obvious duplicate.
"""
from __future__ import annotations

import math
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

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

ASSETS = Path(__file__).with_name("assets")
SOURCE_IMAGE = ASSETS / "rossi_source.jpg"
OUTPUT_PATH = Path(__file__).with_name("demo_rossi.puppet")

# ---------------------------------------------------------------------------
# Source-image geometry. The original sample is 850 x 1952; the chibi side
# companion sits in the right half so we crop to the main-figure column
# first. Numbers below are in *cropped* image-space pixels and were tuned
# against the published illustration — the slice rectangles cover Rossi's
# actual head / torso / arms / legs without too much spill into adjacent
# parts.
# ---------------------------------------------------------------------------

CROP_BOX = (50, 0, 620, 1807)   # crops the rightmost margin / floating text
TARGET_HEIGHT = 900             # downscale long edge to keep the .puppet small

# After padding, the figure occupies the central 40% of the canvas — these
# constants live in *figure-local* fractions and are mapped into padded-
# canvas fractions by ``_padded_frac`` below. Keeping figure-local fractions
# means the slice rectangles stay readable (HEAD spans the top 16 % of the
# figure, not 16 % of a much-larger padded canvas).
PAD_RATIO = 0.75    # padding on each side as a fraction of figure width
FIGURE_FRAC_WIDTH = 1.0 / (1.0 + 2 * PAD_RATIO)   # → 0.40

# Body-part rectangles tuned to the standing-with-left-arm-raised pose
# in Danbooru #11043219. They overlap modestly so adjacent slices share
# a feather band — that overlap is what hides the slice line. Numbers
# are figure-local fractions and get mapped into the padded canvas via
# ``_padded_frac_*`` below.
HEAD_FRAC = (0.18, 0.00, 0.78, 0.26)
TORSO_FRAC = (0.18, 0.20, 0.84, 0.70)
ARM_LEFT_FRAC = (0.00, 0.04, 0.32, 0.36)
ARM_RIGHT_FRAC = (0.78, 0.22, 1.00, 0.56)
LEG_LEFT_FRAC = (0.28, 0.62, 0.55, 1.00)
LEG_RIGHT_FRAC = (0.55, 0.62, 0.80, 1.00)

NECK_FRAC = (0.50, 0.22)
WAIST_FRAC = (0.50, 0.62)
SHOULDER_LEFT_FRAC = (0.32, 0.20)
SHOULDER_RIGHT_FRAC = (0.78, 0.28)
HIP_LEFT_FRAC = (0.43, 0.66)
HIP_RIGHT_FRAC = (0.66, 0.66)

# Width of the alpha-feather band on the slice edge, as a fraction of
# the slice's shorter side. Wider feather hides the slice line further
# but lets more of the un-rotated base bleed through during rotation
# (visible as ghosting at the trailing edge); 0.18 sits in the sweet
# spot for this illustration.
FEATHER_FRAC = 0.18

# Rotation extremes per parameter (radians). Each part rotates as a
# rigid slice so the angles drive how cleanly the limbs move. They're
# kept modest because the un-rotated base layer underneath shows the
# original arm/leg position; a too-large swing reveals it as a
# duplicate ghost behind the rotated part. The numbers below were
# tuned by previewing every motion at p25/p50/p75 — large enough to
# read as motion, small enough that the trailing base stays hidden
# inside the feather band.
HEAD_YAW_MAX = math.radians(7)
BODY_LEAN_MAX = math.radians(3)
ARM_SWING_MAX = math.radians(14)
LEG_SWING_MAX = math.radians(9)

CELL_SIZE = 24


# ---------------------------------------------------------------------------
# Image prep
# ---------------------------------------------------------------------------


def _load_and_crop() -> Image.Image:
    """Load Rossi, crop the chibi off, downscale to TARGET_HEIGHT, and
    pad the sides with transparency so rotated limbs don't slide out
    of the canvas. Body-part bounds are still expressed as fractions
    of the *padded* canvas, so the layout below is consistent with the
    final geometry."""
    if not SOURCE_IMAGE.exists():
        raise FileNotFoundError(
            f"missing {SOURCE_IMAGE}; download from Danbooru first "
            "(see assets/CREDITS.md)",
        )
    img = Image.open(SOURCE_IMAGE).convert("RGBA")
    cropped = img.crop(CROP_BOX)
    aspect = cropped.size[0] / cropped.size[1]
    new_h = TARGET_HEIGHT
    figure_w = max(1, int(new_h * aspect))
    figure = cropped.resize((figure_w, new_h), Image.Resampling.LANCZOS)
    pad = int(figure_w * PAD_RATIO)
    canvas = Image.new("RGBA", (figure_w + 2 * pad, new_h), (0, 0, 0, 0))
    canvas.paste(figure, (pad, 0))
    return canvas


def _frac_pivot(canvas: Image.Image, frac: tuple[float, float]) -> tuple[float, float]:
    return (frac[0] * canvas.size[0], frac[1] * canvas.size[1])


def _padded_frac_box(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    fw = FIGURE_FRAC_WIDTH
    left = (1.0 - fw) * 0.5
    return (left + box[0] * fw, box[1], left + box[2] * fw, box[3])


def _padded_frac_xy(xy: tuple[float, float]) -> tuple[float, float]:
    fw = FIGURE_FRAC_WIDTH
    left = (1.0 - fw) * 0.5
    return (left + xy[0] * fw, xy[1])


# ---------------------------------------------------------------------------
# Slice → drawable
# ---------------------------------------------------------------------------


def _png_bytes(canvas: Image.Image) -> bytes:
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _full_canvas_drawable(canvas: Image.Image) -> tuple[Drawable, str, bytes]:
    """Build the un-deformed base drawable from the full canvas. Sits
    underneath every part; provides the safety net that lets the part
    slices have feathered-alpha edges without the feather zone going
    transparent."""
    png = _png_bytes(canvas)
    rgba = np.array(canvas, dtype=np.uint8)
    vertices, indices, uvs = triangulate_alpha_grid(rgba, cell_size=CELL_SIZE)
    drawable = Drawable(
        id="base", texture="textures/base.png",
        vertices=vertices, indices=indices, uvs=uvs,
        draw_order=0,
    )
    return drawable, "textures/base.png", png


def _feather_mask(width: int, height: int, feather_px: int) -> np.ndarray:
    """Build an HxW float32 mask in [0, 1] that's 1 inside the rect's
    core and fades smoothly to 0 over a ``feather_px`` band along
    every edge. Used to soften slice borders so they composite onto
    the base without a visible cut."""
    if feather_px <= 0:
        return np.ones((height, width), dtype=np.float32)
    ys = np.arange(height, dtype=np.float32)
    xs = np.arange(width, dtype=np.float32)
    dx = np.minimum(xs, (width - 1) - xs)
    dy = np.minimum(ys, (height - 1) - ys)
    dist = np.minimum(dx[None, :], dy[:, None])
    mask = np.clip(dist / float(feather_px), 0.0, 1.0)
    return mask.astype(np.float32)


def _slice_part(
    canvas: Image.Image,
    rect_px: tuple[int, int, int, int],
) -> tuple[Image.Image, tuple[int, int]]:
    """Crop ``rect_px`` (left, top, right, bottom) out of ``canvas``,
    multiply alpha by a soft-edge mask, and return the slice plus
    its top-left offset on the canvas. The offset lets the caller
    rebuild a canvas-sized texture for the drawable's UVs."""
    left, top, right, bottom = rect_px
    crop = canvas.crop((left, top, right, bottom))
    crop_arr = np.array(crop, dtype=np.uint8)
    h, w = crop_arr.shape[:2]
    feather_px = max(1, int(min(h, w) * FEATHER_FRAC))
    mask = _feather_mask(w, h, feather_px)
    alpha = crop_arr[..., 3].astype(np.float32) / 255.0
    crop_arr[..., 3] = np.clip(alpha * mask, 0.0, 1.0).__mul__(255.0).astype(np.uint8)
    return Image.fromarray(crop_arr, mode="RGBA"), (left, top)


def _part_drawable(
    canvas: Image.Image,
    part_id: str,
    rect_frac: tuple[float, float, float, float],
    draw_order: int,
) -> tuple[Drawable, str, bytes]:
    """Build a part drawable: the slice texture pasted back onto a
    full-canvas-sized transparent layer so its UVs match the canvas
    coords its mesh uses. The mesh is auto-meshed against the slice's
    own alpha so triangles only cover painted pixels (saves rasterise
    work + stops the feather zone from getting inflated)."""
    cw, ch = canvas.size
    rect_px = (
        int(rect_frac[0] * cw), int(rect_frac[1] * ch),
        int(rect_frac[2] * cw), int(rect_frac[3] * ch),
    )
    slice_img, (left, top) = _slice_part(canvas, rect_px)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(slice_img, (left, top))
    rgba = np.array(layer, dtype=np.uint8)
    vertices, indices, uvs = triangulate_alpha_grid(rgba, cell_size=CELL_SIZE)
    tex_path = f"textures/{part_id}.png"
    drawable = Drawable(
        id=part_id, texture=tex_path,
        vertices=vertices, indices=indices, uvs=uvs,
        draw_order=draw_order,
    )
    return drawable, tex_path, _png_bytes(layer)


# ---------------------------------------------------------------------------
# Rig
# ---------------------------------------------------------------------------


def _rotation_form(anchor: tuple[float, float], angle_rad: float) -> dict:
    return {"anchor": [float(anchor[0]), float(anchor[1])], "angle": float(angle_rad)}


def _three_key(
    pid: str, deformer_id: str,
    anchor: tuple[float, float], swing: float,
) -> Parameter:
    return Parameter(
        id=pid, min=-1.0, max=1.0, default=0.0,
        keys=[
            ParameterKey(value=-1.0, forms={deformer_id: _rotation_form(anchor, -swing)}),
            ParameterKey(value=0.0, forms={deformer_id: _rotation_form(anchor, 0.0)}),
            ParameterKey(value=1.0, forms={deformer_id: _rotation_form(anchor, swing)}),
        ],
    )


def _build_doc() -> PuppetDocument:
    canvas = _load_and_crop()
    w, h = canvas.size
    doc = PuppetDocument(size=(w, h))

    base_d, base_tex, base_png = _full_canvas_drawable(canvas)
    doc.drawables.append(base_d)
    doc.textures[base_tex] = base_png

    # Order matters: arms over torso, torso over legs, head on top.
    parts = (
        ("leg_left", LEG_LEFT_FRAC, 1),
        ("leg_right", LEG_RIGHT_FRAC, 2),
        ("torso", TORSO_FRAC, 3),
        ("arm_left", ARM_LEFT_FRAC, 4),
        ("arm_right", ARM_RIGHT_FRAC, 5),
        ("head", HEAD_FRAC, 6),
    )
    for part_id, frac_box, draw_order in parts:
        drawable, tex_path, png = _part_drawable(
            canvas, part_id, _padded_frac_box(frac_box), draw_order,
        )
        doc.drawables.append(drawable)
        doc.textures[tex_path] = png

    neck = _frac_pivot(canvas, _padded_frac_xy(NECK_FRAC))
    waist = _frac_pivot(canvas, _padded_frac_xy(WAIST_FRAC))
    sh_l = _frac_pivot(canvas, _padded_frac_xy(SHOULDER_LEFT_FRAC))
    sh_r = _frac_pivot(canvas, _padded_frac_xy(SHOULDER_RIGHT_FRAC))
    hip_l = _frac_pivot(canvas, _padded_frac_xy(HIP_LEFT_FRAC))
    hip_r = _frac_pivot(canvas, _padded_frac_xy(HIP_RIGHT_FRAC))

    doc.deformers.extend([
        Deformer(id="head_rot", type="rotation", parent=None,
                 drawables=["head"], form=default_rotation_form(neck)),
        Deformer(id="body_rot", type="rotation", parent=None,
                 # Body lean only rotates the torso slice; head and arms
                 # have their own deformers, and pulling them along with
                 # the torso would move them far enough from the base
                 # that the un-rotated base would peek out behind them.
                 drawables=["torso"],
                 form=default_rotation_form(waist)),
        Deformer(id="arm_left_rot", type="rotation", parent=None,
                 drawables=["arm_left"], form=default_rotation_form(sh_l)),
        Deformer(id="arm_right_rot", type="rotation", parent=None,
                 drawables=["arm_right"], form=default_rotation_form(sh_r)),
        Deformer(id="leg_left_rot", type="rotation", parent=None,
                 drawables=["leg_left"], form=default_rotation_form(hip_l)),
        Deformer(id="leg_right_rot", type="rotation", parent=None,
                 drawables=["leg_right"], form=default_rotation_form(hip_r)),
    ])

    doc.parameters.extend([
        _three_key("ParamHeadYaw", "head_rot", neck, HEAD_YAW_MAX),
        _three_key("ParamBodyLean", "body_rot", waist, BODY_LEAN_MAX),
        _three_key("ParamArmLeftSwing", "arm_left_rot", sh_l, ARM_SWING_MAX),
        _three_key("ParamArmRightSwing", "arm_right_rot", sh_r, ARM_SWING_MAX),
        _three_key("ParamLegLeftSwing", "leg_left_rot", hip_l, LEG_SWING_MAX),
        _three_key("ParamLegRightSwing", "leg_right_rot", hip_r, LEG_SWING_MAX),
    ])

    doc.motions.extend([
        _idle(), _wave(), _cheer(), _bow(), _step_right(),
    ])
    return doc


# ---------------------------------------------------------------------------
# Motions
# ---------------------------------------------------------------------------


def _sine_track(
    pid: str, dur: float, amp: float,
    *, phase: float = 0.0, n: int = 32,
) -> MotionTrack:
    out: list[MotionSegment] = []
    for i in range(n):
        t0 = dur * i / n
        t1 = dur * (i + 1) / n
        v0 = amp * math.sin(2.0 * math.pi * t0 / dur + phase)
        v1 = amp * math.sin(2.0 * math.pi * t1 / dur + phase)
        out.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return MotionTrack(param_id=pid, segments=out)


def _idle() -> Motion:
    return Motion(name="idle", duration=4.0, loop=True, tracks=[
        _sine_track("ParamBodyLean", 4.0, 0.6),
        _sine_track("ParamHeadYaw", 4.0, 0.4, phase=math.pi),
    ])


def _wave() -> Motion:
    """Left arm is already up in the source pose; oscillate it back
    and forth a few times so it looks like an actual wave."""
    dur = 2.0
    n = 48
    segs: list[MotionSegment] = []
    for i in range(n):
        t0 = dur * i / n
        t1 = dur * (i + 1) / n
        v0 = 0.6 * math.sin(2.0 * math.pi * 3 * t0 / dur)
        v1 = 0.6 * math.sin(2.0 * math.pi * 3 * t1 / dur)
        segs.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return Motion(name="wave", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamArmLeftSwing", segments=segs),
        _sine_track("ParamHeadYaw", dur, 0.3),
    ])


def _cheer() -> Motion:
    """Bring the right arm up to match the left arm — both-arms-up
    cheer pose. Mirrored signs so the right arm rotates the right
    direction (negative angle) to swing upward."""
    dur = 2.4
    return Motion(name="cheer", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamArmRightSwing", segments=[
            MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.8, -1.0)),
            MotionSegment(type="linear", p0=(0.8, -1.0), p1=(1.6, -1.0)),
            MotionSegment(type="linear", p0=(1.6, -1.0), p1=(2.4, 0.0)),
        ]),
        _sine_track("ParamArmLeftSwing", dur, 0.3),
        _sine_track("ParamHeadYaw", dur, 0.4, phase=math.pi),
    ])


def _step_right() -> Motion:
    """Lift the right leg out to the side then put it back down. Pure
    leg motion; no body counter-lean — adding ParamBodyLean here
    rotates the upper half too aggressively for the tall canvas."""
    dur = 1.6
    return Motion(name="step_right", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamLegRightSwing", segments=[
            MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.5, 1.0)),
            MotionSegment(type="linear", p0=(0.5, 1.0), p1=(1.0, 1.0)),
            MotionSegment(type="linear", p0=(1.0, 1.0), p1=(1.6, 0.0)),
        ]),
    ])


def _bow() -> Motion:
    dur = 2.4
    return Motion(name="bow", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamBodyLean", segments=[
            MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.6, 1.0)),
            MotionSegment(type="linear", p0=(0.6, 1.0), p1=(1.4, 1.0)),
            MotionSegment(type="linear", p0=(1.4, 1.0), p1=(2.0, 0.0)),
            MotionSegment(type="linear", p0=(2.0, 0.0), p1=(2.4, 0.0)),
        ]),
    ])


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = _build_doc()
    save_puppet(doc, OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH} (size={OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
