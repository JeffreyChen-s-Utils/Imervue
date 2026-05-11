"""Build a 6-part puppet rig from ``puppet_char.png``.

Pipeline:

1. Load ``puppet_char.png`` and chroma-key the near-white backdrop
   (the source is a generated illustration on an off-white sheet, not
   a true transparent PNG). Pixels close to the backdrop colour get
   alpha-faded to zero with a small feather so the figure's silhouette
   stays smooth.
2. Crop to the figure bbox + a comfortable rotation pad on all sides,
   resize to a target height for a manageable .puppet file size.
3. Stack a **base layer** of the full character at the bottom of the
   draw order. Six body-part slices (head / torso / two arms / two
   legs) sit on top with feathered alpha along their rectangle edges,
   each driven by its own rotation deformer.
4. Save out as ``demo_anime_girl.puppet`` next to this script.

The base layer fills behind any rotated slice so the seam never
shows through, and the slice's own feathered edges hide the cut. The
rig still rotates each part as a rigid piece, so the limb moves
cleanly without warp smearing.
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

from Imervue.puppet.auto_mesh import triangulate_alpha_grid    # noqa: E402
from Imervue.puppet.deformers import default_rotation_form    # noqa: E402
from Imervue.puppet.document import (    # noqa: E402
    Deformer,
    Drawable,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    ParameterKey,
    PuppetDocument,
)
from Imervue.puppet.document_io import save_puppet    # noqa: E402

SOURCE_IMAGE = Path(__file__).with_name("puppet_char.png")
OUTPUT_PATH = Path(__file__).with_name("demo_anime_girl.puppet")

# ---------------------------------------------------------------------------
# Background removal + canvas prep
# ---------------------------------------------------------------------------

# Source illustration ships on an off-white backdrop near (248, 247, 245).
# Pixels brighter + closer to that get alpha-zeroed.
BG_THRESHOLD = 235      # a channel >= this counts as "near-bg"
BG_FEATHER = 12         # alpha falloff width in source-pixel units

TARGET_HEIGHT = 900
PAD_RATIO = 0.6         # pad each side by this fraction of figure width


def _key_background(arr: np.ndarray) -> np.ndarray:
    """Return an RGBA copy of ``arr`` (HxWx4 uint8) with the near-white
    backdrop alpha-keyed to zero. The figure stays at full alpha; a
    narrow feather softens the silhouette edge."""
    rgb = arr[..., :3].astype(np.int32)
    min_channel = rgb.min(axis=-1)
    distance = (BG_THRESHOLD - min_channel).clip(min=0)
    alpha = np.clip(distance / BG_FEATHER, 0.0, 1.0)
    out = arr.copy()
    out[..., 3] = (alpha * arr[..., 3]).astype(np.uint8)
    return out


def _figure_bbox(rgba: np.ndarray) -> tuple[int, int, int, int]:
    alpha = rgba[..., 3]
    ys, xs = np.where(alpha > 8)
    if not len(xs):
        raise ValueError("background-keyed image has no foreground pixels")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _load_canvas() -> Image.Image:
    src = np.array(Image.open(SOURCE_IMAGE).convert("RGBA"), dtype=np.uint8)
    keyed = _key_background(src)
    x0, y0, x1, y1 = _figure_bbox(keyed)
    figure = Image.fromarray(keyed[y0:y1, x0:x1], mode="RGBA")
    aspect = figure.size[0] / figure.size[1]
    new_h = TARGET_HEIGHT
    figure_w = max(1, int(new_h * aspect))
    figure = figure.resize((figure_w, new_h), Image.Resampling.LANCZOS)
    pad = int(figure_w * PAD_RATIO)
    canvas = Image.new("RGBA", (figure_w + 2 * pad, new_h), (0, 0, 0, 0))
    canvas.paste(figure, (pad, 0))
    return canvas


# ---------------------------------------------------------------------------
# Body-part rectangles — figure-local fractions, mapped into canvas coords
# by ``_padded_frac_*``. Tuned to the puppet_char.png standing pose so each
# slice covers exactly one body region without overlapping its neighbours.
# ---------------------------------------------------------------------------

PAD_LEFT_FRAC = PAD_RATIO / (1.0 + 2 * PAD_RATIO)        # → 0.273
FIGURE_FRAC_W = 1.0 / (1.0 + 2 * PAD_RATIO)              # → 0.455

HEAD_FRAC = (0.10, 0.00, 0.85, 0.30)
TORSO_FRAC = (0.05, 0.26, 0.95, 0.62)
ARM_LEFT_FRAC = (-0.05, 0.28, 0.30, 0.55)
ARM_RIGHT_FRAC = (0.70, 0.28, 1.10, 0.55)
LEG_LEFT_FRAC = (0.20, 0.58, 0.55, 1.00)
LEG_RIGHT_FRAC = (0.45, 0.58, 0.80, 1.00)

NECK_FRAC = (0.50, 0.28)
WAIST_FRAC = (0.50, 0.60)
SHOULDER_LEFT_FRAC = (0.22, 0.30)
SHOULDER_RIGHT_FRAC = (0.78, 0.30)
HIP_LEFT_FRAC = (0.36, 0.60)
HIP_RIGHT_FRAC = (0.64, 0.60)

FEATHER_FRAC = 0.18

# Modest joint angles — large enough to read as motion, small enough that
# the un-rotated base layer underneath stays inside the slice's feather
# zone instead of peeking out as a duplicate.
HEAD_YAW_MAX = math.radians(7)
BODY_LEAN_MAX = math.radians(4)
ARM_SWING_MAX = math.radians(15)
LEG_SWING_MAX = math.radians(9)

CELL_SIZE = 24


def _padded_frac_box(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    fw = FIGURE_FRAC_W
    left = PAD_LEFT_FRAC
    return (
        max(0.0, left + box[0] * fw),
        box[1],
        min(1.0, left + box[2] * fw),
        box[3],
    )


def _padded_frac_xy(xy: tuple[float, float]) -> tuple[float, float]:
    fw = FIGURE_FRAC_W
    left = PAD_LEFT_FRAC
    return (left + xy[0] * fw, xy[1])


def _frac_to_pixels(canvas: Image.Image, box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    w, h = canvas.size
    return (
        int(box[0] * w), int(box[1] * h),
        int(box[2] * w), int(box[3] * h),
    )


def _frac_pivot(canvas: Image.Image, frac: tuple[float, float]) -> tuple[float, float]:
    return (frac[0] * canvas.size[0], frac[1] * canvas.size[1])


# ---------------------------------------------------------------------------
# Slice → drawable (base layer + 6 feathered parts)
# ---------------------------------------------------------------------------


def _png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _drawable_from_png(
    drawable_id: str, png_bytes: bytes, draw_order: int, texture_path: str,
) -> Drawable:
    rgba = np.array(Image.open(BytesIO(png_bytes)).convert("RGBA"),
                    dtype=np.uint8)
    vertices, indices, uvs = triangulate_alpha_grid(rgba, cell_size=CELL_SIZE)
    return Drawable(
        id=drawable_id, texture=texture_path,
        vertices=vertices, indices=indices, uvs=uvs,
        draw_order=draw_order,
    )


def _feather_mask(width: int, height: int, feather_px: int) -> np.ndarray:
    if feather_px <= 0:
        return np.ones((height, width), dtype=np.float32)
    ys = np.arange(height, dtype=np.float32)
    xs = np.arange(width, dtype=np.float32)
    dx = np.minimum(xs, (width - 1) - xs)
    dy = np.minimum(ys, (height - 1) - ys)
    dist = np.minimum(dx[None, :], dy[:, None])
    return np.clip(dist / float(feather_px), 0.0, 1.0).astype(np.float32)


def _full_canvas_drawable(canvas: Image.Image) -> tuple[Drawable, str, bytes]:
    png = _png_bytes(canvas)
    return (
        _drawable_from_png("base", png, draw_order=0,
                           texture_path="textures/base.png"),
        "textures/base.png",
        png,
    )


def _part_drawable(
    canvas: Image.Image, part_id: str,
    rect_frac: tuple[float, float, float, float], draw_order: int,
) -> tuple[Drawable, str, bytes]:
    rect_px = _frac_to_pixels(canvas, rect_frac)
    left, top, right, bottom = rect_px
    crop_arr = np.array(canvas.crop((left, top, right, bottom)),
                        dtype=np.uint8)
    h, w = crop_arr.shape[:2]
    feather_px = max(1, int(min(h, w) * FEATHER_FRAC))
    mask = _feather_mask(w, h, feather_px)
    crop_arr[..., 3] = (crop_arr[..., 3].astype(np.float32) * mask
                        ).clip(0, 255).astype(np.uint8)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(Image.fromarray(crop_arr, mode="RGBA"), (left, top))
    tex = f"textures/{part_id}.png"
    png = _png_bytes(layer)
    return _drawable_from_png(part_id, png, draw_order, tex), tex, png


# ---------------------------------------------------------------------------
# Rig
# ---------------------------------------------------------------------------


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
    canvas = _load_canvas()
    w, h = canvas.size
    doc = PuppetDocument(size=(w, h))

    base_d, base_tex, base_png = _full_canvas_drawable(canvas)
    doc.drawables.append(base_d)
    doc.textures[base_tex] = base_png

    parts = (
        ("leg_left", LEG_LEFT_FRAC, 1),
        ("leg_right", LEG_RIGHT_FRAC, 2),
        ("torso", TORSO_FRAC, 3),
        ("arm_left", ARM_LEFT_FRAC, 4),
        ("arm_right", ARM_RIGHT_FRAC, 5),
        ("head", HEAD_FRAC, 6),
    )
    for part_id, frac_box, draw_order in parts:
        drawable, tex, png = _part_drawable(
            canvas, part_id, _padded_frac_box(frac_box), draw_order,
        )
        doc.drawables.append(drawable)
        doc.textures[tex] = png

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
                 drawables=["torso"], form=default_rotation_form(waist)),
        Deformer(id="arm_left_rot", type="rotation", parent=None,
                 drawables=["arm_left"],
                 form=default_rotation_form(sh_l)),
        Deformer(id="arm_right_rot", type="rotation", parent=None,
                 drawables=["arm_right"],
                 form=default_rotation_form(sh_r)),
        Deformer(id="leg_left_rot", type="rotation", parent=None,
                 drawables=["leg_left"],
                 form=default_rotation_form(hip_l)),
        Deformer(id="leg_right_rot", type="rotation", parent=None,
                 drawables=["leg_right"],
                 form=default_rotation_form(hip_r)),
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
        _idle(), _wave(), _curtsy(), _cheer(), _step_right(),
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
        _sine_track("ParamBodyLean", 4.0, 0.5),
        _sine_track("ParamHeadYaw", 4.0, 0.5, phase=math.pi),
    ])


def _wave() -> Motion:
    """Right arm raises and shakes side to side."""
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
        _sine_track("ParamHeadYaw", dur, 0.4),
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
    """Both arms swing up — sign convention: arms hang down so positive
    on the left arm + negative on the right arm raise both upward."""
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
