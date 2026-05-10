"""Build the demo ``.puppet`` shipped with the docs.

Run this script to (re)generate ``examples/puppet/demo_face.puppet`` —
a fully-rigged single-drawable puppet you can import into the Puppet
tab via ``Open Puppet…`` to verify the runtime end-to-end.

The puppet contains:

* one drawable (a procedurally-painted face PNG)
* a triangulated grid mesh
* one **rotation** deformer pinned at the canvas centre
* one **ParamAngleX** parameter (-1..1) with three keys at -1 / 0 / 1
  rotating the rotation deformer by ±0.6 rad
* one looping **idle** motion swinging ParamAngleX through a sine
  wave every 4 seconds via three linear segments

Pure Python — no Qt / GL needed to run this script. The output is a
plain ``.puppet`` zip that the Imervue Puppet tab consumes directly.
"""
from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

# Make the puppet plugin importable without installing the package.
# The puppet plugin's __init__ pulls in puppet_plugin which uses
# Imervue's language_wrapper, so we need both the project root (for
# Imervue.*) and the plugins/ folder (for puppet.*) on sys.path.
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))

from puppet.auto_mesh import puppet_from_png   # noqa: E402
from puppet.document import (    # noqa: E402
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    ParameterKey,
)
from puppet.document_io import save_puppet  # noqa: E402
from puppet.operations import (    # noqa: E402
    add_parameter,
    add_rotation_deformer,
    set_key_at_value,
    snapshot_current_forms,
)


CANVAS_SIZE: int = 512
OUTPUT_PATH: Path = Path(__file__).with_name("demo_face.puppet")


def build_face_png() -> bytes:
    """Procedurally render a friendly face on a transparent canvas."""
    img = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = CANVAS_SIZE // 2

    # Head
    head_radius = CANVAS_SIZE * 0.32
    draw.ellipse(
        (cx - head_radius, cy - head_radius, cx + head_radius, cy + head_radius),
        fill=(248, 220, 196, 255),
        outline=(60, 40, 30, 255),
        width=4,
    )

    # Hair as a half-disc on top
    hair_radius = head_radius + 6
    draw.pieslice(
        (cx - hair_radius, cy - hair_radius, cx + hair_radius, cy + hair_radius),
        start=190, end=350,
        fill=(80, 60, 50, 255),
    )

    # Eyes
    eye_offset_x = head_radius * 0.32
    eye_offset_y = head_radius * 0.05
    eye_radius = head_radius * 0.10
    for dx in (-eye_offset_x, eye_offset_x):
        x0 = cx + dx - eye_radius
        y0 = cy + eye_offset_y - eye_radius
        x1 = cx + dx + eye_radius
        y1 = cy + eye_offset_y + eye_radius
        draw.ellipse((x0, y0, x1, y1), fill=(40, 35, 30, 255))

    # Smile
    mouth_w = head_radius * 0.5
    mouth_h = head_radius * 0.25
    mouth_y = cy + head_radius * 0.35
    draw.arc(
        (cx - mouth_w, mouth_y - mouth_h, cx + mouth_w, mouth_y + mouth_h),
        start=10, end=170,
        fill=(170, 60, 50, 255),
        width=5,
    )

    # Cheeks
    cheek_radius = head_radius * 0.10
    for dx in (-head_radius * 0.45, head_radius * 0.45):
        x0 = cx + dx - cheek_radius
        y0 = cy + head_radius * 0.25 - cheek_radius
        x1 = cx + dx + cheek_radius
        y1 = cy + head_radius * 0.25 + cheek_radius
        draw.ellipse((x0, y0, x1, y1), fill=(255, 170, 170, 180))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_demo_puppet() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    png_bytes = build_face_png()

    # Phase 3 path — auto-mesh from PNG → one drawable + neutral mesh.
    doc = puppet_from_png(
        png_bytes, drawable_id="face",
        texture_path="textures/face.png",
        cell_size=48,
    )

    # Add a head-rotation deformer covering the only drawable.
    add_rotation_deformer(doc, "head_rotation")

    # Add ParamAngleX driving the rotation between -0.6 .. +0.6 rad.
    add_parameter(doc, "ParamAngleX", min_value=-1.0, max_value=1.0, default=0.0)
    for value, angle in ((-1.0, -0.6), (0.0, 0.0), (1.0, 0.6)):
        # Snapshot the current rotation form, then override the angle.
        forms = snapshot_current_forms(doc)
        forms["head_rotation"]["angle"] = float(angle)
        set_key_at_value(doc, "ParamAngleX", value, forms)

    # Add an idle motion that swings ParamAngleX with a sine wave.
    duration = 4.0
    samples = 32
    track_segments: list[MotionSegment] = []
    for i in range(samples):
        t0 = duration * i / samples
        t1 = duration * (i + 1) / samples
        v0 = math.sin(2.0 * math.pi * t0 / duration)
        v1 = math.sin(2.0 * math.pi * t1 / duration)
        track_segments.append(
            MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)),
        )
    doc.motions.append(
        Motion(
            name="idle",
            duration=duration,
            loop=True,
            tracks=[
                MotionTrack(param_id="ParamAngleX", segments=track_segments),
            ],
        ),
    )

    save_puppet(doc, OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH} (size={OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    build_demo_puppet()
