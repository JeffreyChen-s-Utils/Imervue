"""Build a six-drawable rig from a real Rossi (Arknights) illustration.

Source: Danbooru post #11311021 by ``odmised`` (rating: g, no
do_not_post tag at fetch time). Local copy at
``examples/puppet/assets/rossi_source.jpg`` — credits in
``assets/CREDITS.md``.

Same rig topology as ``demo_tpose.puppet`` (six drawables, six
rotation deformers, five motions) but the drawables come from
rectangular slices of the real character image instead of
procedural shapes. Each slice is masked into its own RGBA PNG so
when its rotation deformer fires, only that slice's pixels move —
the rest of the figure stays in place.

The slice rectangles are eyeballed from the source image's
proportions; tweak the constants near the top of this file if you
re-run against a different illustration. A companion chibi figure
on the right side of the source is cropped out before slicing.
"""
from __future__ import annotations

import math
import sys
from copy import deepcopy
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

CROP_BOX = (50, 0, 540, 1952)   # (left, top, right, bottom) — drops the chibi
TARGET_HEIGHT = 900             # downscale long edge to keep the .puppet small

# After padding, the figure occupies the central 40% of the canvas — these
# constants live in *figure-local* fractions and are mapped into padded-
# canvas fractions by ``_padded_frac`` below. Keeping figure-local fractions
# means the slice rectangles stay readable (HEAD spans the top 16 % of the
# figure, not 16 % of a much-larger padded canvas).
PAD_RATIO = 0.75    # padding on each side as a fraction of figure width
FIGURE_FRAC_WIDTH = 1.0 / (1.0 + 2 * PAD_RATIO)   # → 0.40

HEAD_FRAC = (0.00, 0.00, 1.00, 0.16)
TORSO_FRAC = (0.10, 0.16, 0.90, 0.78)
ARM_LEFT_FRAC = (0.00, 0.18, 0.40, 0.46)
ARM_RIGHT_FRAC = (0.60, 0.18, 1.00, 0.46)
LEG_LEFT_FRAC = (0.28, 0.78, 0.55, 1.00)
LEG_RIGHT_FRAC = (0.55, 0.78, 0.78, 1.00)

NECK_FRAC = (0.50, 0.16)
WAIST_FRAC = (0.50, 0.76)
SHOULDER_LEFT_FRAC = (0.30, 0.20)
SHOULDER_RIGHT_FRAC = (0.70, 0.20)
HIP_LEFT_FRAC = (0.40, 0.78)
HIP_RIGHT_FRAC = (0.60, 0.78)


def _padded_frac_box(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Map figure-local fractions to padded-canvas fractions."""
    fw = FIGURE_FRAC_WIDTH
    left = (1.0 - fw) * 0.5
    return (left + box[0] * fw, box[1], left + box[2] * fw, box[3])


def _padded_frac_xy(xy: tuple[float, float]) -> tuple[float, float]:
    fw = FIGURE_FRAC_WIDTH
    left = (1.0 - fw) * 0.5
    return (left + xy[0] * fw, xy[1])

# Rotation extremes per parameter (radians). The canvas is tall + narrow
# (~226 × 900 after cropping the chibi off), so even modest angles around
# the waist swing the head off-screen. Keeping body lean ≤ 7° and arm
# swing ≤ 25° preserves the figure inside the visible frame; the limbs
# in the source are folded across the body so swing-by-shoulder also has
# limited authentic range.
HEAD_YAW_MAX = math.radians(12)
BODY_LEAN_MAX = math.radians(6)
ARM_SWING_MAX = math.radians(22)
LEG_SWING_MAX = math.radians(12)

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
    # Pad each side with 75 % of the figure width so a body-lean
    # rotation around the waist can swing the head sideways without
    # clipping. The figure stays centred horizontally.
    pad = int(figure_w * PAD_RATIO)
    canvas = Image.new("RGBA", (figure_w + 2 * pad, new_h), (0, 0, 0, 0))
    canvas.paste(figure, (pad, 0))
    return canvas


def _slice_part(
    canvas: Image.Image, frac_box: tuple[float, float, float, float],
) -> bytes:
    """Return a same-size RGBA PNG with everything outside ``frac_box``
    made fully transparent. Keeping the slice at the canvas's full
    dimensions means the puppet's drawables all share a coordinate
    system, so rotation deformers anchored at canvas-space pivots
    line up across slices."""
    w, h = canvas.size
    x0 = int(frac_box[0] * w)
    y0 = int(frac_box[1] * h)
    x1 = int(frac_box[2] * w)
    y1 = int(frac_box[3] * h)
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    out.paste(canvas.crop((x0, y0, x1, y1)), (x0, y0))
    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _frac_pivot(canvas: Image.Image, frac: tuple[float, float]) -> tuple[float, float]:
    return (frac[0] * canvas.size[0], frac[1] * canvas.size[1])


def _drawable_from_part(
    drawable_id: str, png_bytes: bytes, draw_order: int,
    texture_path: str,
) -> Drawable:
    rgba = _decode_rgba(png_bytes)
    vertices, indices, uvs = triangulate_alpha_grid(rgba, cell_size=CELL_SIZE)
    return Drawable(
        id=drawable_id, texture=texture_path,
        vertices=vertices, indices=indices, uvs=uvs,
        draw_order=draw_order,
    )


def _decode_rgba(png_bytes: bytes) -> np.ndarray:
    with Image.open(BytesIO(png_bytes)) as img:
        return np.asarray(img.convert("RGBA"), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Rig
# ---------------------------------------------------------------------------


def _rotation_form(anchor: tuple[float, float], angle_rad: float) -> dict:
    return {"anchor": [float(anchor[0]), float(anchor[1])], "angle": float(angle_rad)}


def _three_key(pid: str, deformer_id: str, anchor: tuple[float, float], swing: float) -> Parameter:
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

    parts = (
        ("head", HEAD_FRAC, 50),
        ("torso", TORSO_FRAC, 30),
        ("arm_left", ARM_LEFT_FRAC, 20),
        ("arm_right", ARM_RIGHT_FRAC, 20),
        ("leg_left", LEG_LEFT_FRAC, 10),
        ("leg_right", LEG_RIGHT_FRAC, 10),
    )
    for part_id, frac_box, draw_order in parts:
        png_bytes = _slice_part(canvas, _padded_frac_box(frac_box))
        tex = f"textures/{part_id}.png"
        doc.textures[tex] = png_bytes
        doc.drawables.append(
            _drawable_from_part(part_id, png_bytes, draw_order, tex),
        )

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
                 # body lean takes the upper half along
                 drawables=["torso", "head", "arm_left", "arm_right"],
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

    # Motion set is chosen so every entry produces a visibly different
    # frame in this character's pose. Rossi's source pose has her arms
    # folded across her body and only one leg fully visible, so cheer /
    # step-leg-only motions barely affect the canvas — they're omitted
    # in favour of motions driven by the head + body + dominant arm.
    doc.motions.extend([
        _idle(), _head_shake(), _bow(), _wave(),
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
    """Right arm raised + waving."""
    dur = 2.0
    n = 32
    segs: list[MotionSegment] = []
    for i in range(n):
        t0 = dur * i / n
        t1 = dur * (i + 1) / n
        base = -0.85
        wob0 = 0.15 * math.sin(2.0 * math.pi * 4 * t0 / dur)
        wob1 = 0.15 * math.sin(2.0 * math.pi * 4 * t1 / dur)
        segs.append(MotionSegment(type="linear", p0=(t0, base + wob0), p1=(t1, base + wob1)))
    return Motion(name="wave", duration=dur, loop=True, tracks=[
        MotionTrack(param_id="ParamArmRightSwing", segments=segs),
        _sine_track("ParamHeadYaw", dur, 0.3),
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


def _head_shake() -> Motion:
    """Head shakes side-to-side at 1 Hz. Drives only ParamHeadYaw so
    every viewer can see the head turn cleanly without other body
    parts confusing the picture."""
    return Motion(name="head_shake", duration=2.0, loop=True, tracks=[
        _sine_track("ParamHeadYaw", 2.0, 1.0, n=64),
    ])


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = _build_doc()
    save_puppet(doc, OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH} (size={OUTPUT_PATH.stat().st_size} bytes)")


_keep_deepcopy = deepcopy


if __name__ == "__main__":
    main()
