"""Multi-region rig demo built from a real character illustration.

Source image: Amiya (Arknights) by ``mowang_xiao_lajiao`` from
Danbooru post #11344502 (rating: g, no do_not_post tag at fetch time).
The local copy lives at ``examples/puppet/assets/amiya_source.jpg``.
Credit text lives in ``examples/puppet/assets/CREDITS.md`` next to the
image.

This builder authors a richer puppet than ``build_demo_puppet.py``:

* one drawable (the whole figure) auto-meshed at cell-size 24 so each
  warp deformer has plenty of vertices to bend
* four region-bound warp deformers — head, body, left arm, right arm —
  each with its own bounds rectangle so a single parameter only
  affects its slice of the canvas
* four parameters driving the warps:

    - ``ParamHeadX``      : head turn left / right
    - ``ParamBodySway``   : body lean
    - ``ParamArmLeftUp``  : left arm raise
    - ``ParamArmRightUp`` : right arm raise

* three looping motions:

    - ``idle``    : gentle body sway + counter-bob head
    - ``wave``    : right arm waves up and down
    - ``greet``   : both arms raise slowly, head bows slightly

The output is ``examples/puppet/demo_amiya.puppet``. Re-run this script
whenever you change the rig parameters / motions; the source image is
not regenerated.
"""
from __future__ import annotations

import math
import sys
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))

from puppet.auto_mesh import puppet_from_png   # noqa: E402
from puppet.deformers import default_warp_form   # noqa: E402
from puppet.document import (    # noqa: E402
    Deformer,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    ParameterKey,
)
from puppet.document_io import save_puppet   # noqa: E402

ASSETS = Path(__file__).with_name("assets")
SOURCE_IMAGE = ASSETS / "amiya_source.jpg"
OUTPUT_PATH = Path(__file__).with_name("demo_amiya.puppet")

# Down-scale the source image so the .puppet stays embeddable in repo
# without bloating the zip too much. 600 px on the long edge keeps the
# file <300 KB while still showing per-pixel detail at default zoom.
TARGET_LONG_EDGE = 600
CELL_SIZE = 24


def _load_and_resize_source() -> tuple[bytes, int, int]:
    img = Image.open(SOURCE_IMAGE).convert("RGBA")
    long_edge = max(img.size)
    if long_edge > TARGET_LONG_EDGE:
        ratio = TARGET_LONG_EDGE / long_edge
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), img.size[0], img.size[1]


def _vertical_band(rel_top: float, rel_bottom: float, w: int, h: int) -> tuple[float, float, float, float]:
    """Return canvas bounds covering the full image width across the
    vertical band ``[rel_top, rel_bottom]`` (each in ``[0, 1]``)."""
    return (0.0, h * rel_top, float(w), h * rel_bottom)


def _half_band(
    rel_top: float, rel_bottom: float, side: str, w: int, h: int,
) -> tuple[float, float, float, float]:
    """Same as ``_vertical_band`` but only the left or right half of
    the image — used to scope arm deformers."""
    if side == "left":
        return (0.0, h * rel_top, w * 0.5, h * rel_bottom)
    return (w * 0.5, h * rel_top, float(w), h * rel_bottom)


def _add_warp_deformer(
    deformers: list[Deformer], deformer_id: str,
    bounds: tuple[float, float, float, float],
    drawable_id: str,
    rows: int = 5, cols: int = 5,
) -> None:
    deformers.append(
        Deformer(
            id=deformer_id,
            type="warp",
            parent=None,
            drawables=[drawable_id],
            form=default_warp_form(bounds, rows=rows, cols=cols),
        ),
    )


def _shifted_grid(
    base_form: dict, shift_fn,
) -> dict:
    """Return a new warp form where each lattice point is moved by
    ``shift_fn(row, col, x, y) -> (new_x, new_y)``."""
    rows = int(base_form["rows"])
    cols = int(base_form["cols"])
    new_grid: list[list[list[float]]] = []
    for r in range(rows):
        row: list[list[float]] = []
        for c in range(cols):
            x, y = base_form["grid"][r][c]
            nx, ny = shift_fn(r, c, x, y)
            row.append([float(nx), float(ny)])
        new_grid.append(row)
    out = deepcopy(base_form)
    out["grid"] = new_grid
    return out


def _head_yaw_shift(amount: float):
    def fn(r: int, c: int, x: float, y: float) -> tuple[float, float]:
        # Top row shifts the most; bottom row stays put. This bends the
        # head sideways while keeping the neck anchored.
        rows = 5   # we use 5 everywhere
        weight = 1.0 - (r / (rows - 1))
        return (x + amount * weight, y)
    return fn


def _body_sway_shift(amount: float):
    def fn(r: int, c: int, x: float, y: float) -> tuple[float, float]:
        # Middle rows shift more; top + bottom stay anchored to the
        # neck and waist.
        rows = 5
        center = (rows - 1) / 2.0
        weight = 1.0 - abs(r - center) / center
        return (x + amount * weight, y)
    return fn


def _arm_raise_shift(amount: float, side: str):
    """Lift the outer top corner of the half-band warp upward."""
    def fn(r: int, c: int, x: float, y: float) -> tuple[float, float]:
        cols = 5
        # The outer column (furthest from the body centre) moves
        # furthest; bottom row stays put.
        rows = 5
        if side == "left":
            col_weight = 1.0 - (c / (cols - 1))   # leftmost col = 1.0
        else:
            col_weight = c / (cols - 1)            # rightmost col = 1.0
        row_weight = 1.0 - (r / (rows - 1))       # top row = 1.0
        # ``amount`` < 0 raises (image y goes down) so we add amount
        # weighted by both row and column.
        return (x, y + amount * col_weight * row_weight)
    return fn


def build_amiya_puppet() -> None:
    if not SOURCE_IMAGE.exists():
        raise FileNotFoundError(
            f"missing source image: {SOURCE_IMAGE}\n"
            f"download the Danbooru asset first (see assets/CREDITS.md).",
        )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    png_bytes, w, h = _load_and_resize_source()
    doc = puppet_from_png(
        png_bytes, drawable_id="figure",
        texture_path="textures/figure.png",
        cell_size=CELL_SIZE,
    )

    # ---- deformers ---------------------------------------------------

    head_bounds = _vertical_band(0.00, 0.30, w, h)
    body_bounds = _vertical_band(0.28, 0.62, w, h)
    arm_left_bounds = _half_band(0.28, 0.62, "left", w, h)
    arm_right_bounds = _half_band(0.28, 0.62, "right", w, h)

    _add_warp_deformer(doc.deformers, "head_warp", head_bounds, "figure")
    _add_warp_deformer(doc.deformers, "body_warp", body_bounds, "figure")
    _add_warp_deformer(doc.deformers, "arm_left_warp", arm_left_bounds, "figure")
    _add_warp_deformer(doc.deformers, "arm_right_warp", arm_right_bounds, "figure")

    head_form = doc.deformer("head_warp").form
    body_form = doc.deformer("body_warp").form
    arm_l_form = doc.deformer("arm_left_warp").form
    arm_r_form = doc.deformer("arm_right_warp").form

    # ---- parameters --------------------------------------------------

    head_swing = w * 0.12
    body_swing = w * 0.05
    arm_lift = h * 0.10

    doc.parameters.append(
        Parameter(
            id="ParamHeadX", min=-1.0, max=1.0, default=0.0,
            keys=[
                ParameterKey(value=-1.0, forms={
                    "head_warp": _shifted_grid(head_form, _head_yaw_shift(-head_swing)),
                }),
                ParameterKey(value=0.0, forms={"head_warp": deepcopy(head_form)}),
                ParameterKey(value=1.0, forms={
                    "head_warp": _shifted_grid(head_form, _head_yaw_shift(+head_swing)),
                }),
            ],
        ),
    )
    doc.parameters.append(
        Parameter(
            id="ParamBodySway", min=-1.0, max=1.0, default=0.0,
            keys=[
                ParameterKey(value=-1.0, forms={
                    "body_warp": _shifted_grid(body_form, _body_sway_shift(-body_swing)),
                }),
                ParameterKey(value=0.0, forms={"body_warp": deepcopy(body_form)}),
                ParameterKey(value=1.0, forms={
                    "body_warp": _shifted_grid(body_form, _body_sway_shift(+body_swing)),
                }),
            ],
        ),
    )
    doc.parameters.append(
        Parameter(
            id="ParamArmLeftUp", min=0.0, max=1.0, default=0.0,
            keys=[
                ParameterKey(value=0.0, forms={"arm_left_warp": deepcopy(arm_l_form)}),
                ParameterKey(value=1.0, forms={
                    "arm_left_warp": _shifted_grid(arm_l_form, _arm_raise_shift(-arm_lift, "left")),
                }),
            ],
        ),
    )
    doc.parameters.append(
        Parameter(
            id="ParamArmRightUp", min=0.0, max=1.0, default=0.0,
            keys=[
                ParameterKey(value=0.0, forms={"arm_right_warp": deepcopy(arm_r_form)}),
                ParameterKey(value=1.0, forms={
                    "arm_right_warp": _shifted_grid(arm_r_form, _arm_raise_shift(-arm_lift, "right")),
                }),
            ],
        ),
    )

    # ---- motions -----------------------------------------------------

    doc.motions.append(_idle_motion())
    doc.motions.append(_wave_motion())
    doc.motions.append(_greet_motion())

    save_puppet(doc, OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH} (size={OUTPUT_PATH.stat().st_size} bytes)")


# ---------------------------------------------------------------------------
# Motion factories — each returns a Motion with linear segments
# ---------------------------------------------------------------------------


def _sine_track(param_id: str, duration: float, amplitude: float, *, phase: float = 0.0, segments: int = 32) -> MotionTrack:
    out: list[MotionSegment] = []
    for i in range(segments):
        t0 = duration * i / segments
        t1 = duration * (i + 1) / segments
        v0 = amplitude * math.sin(2.0 * math.pi * t0 / duration + phase)
        v1 = amplitude * math.sin(2.0 * math.pi * t1 / duration + phase)
        out.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return MotionTrack(param_id=param_id, segments=out)


def _half_sine_track(
    param_id: str, duration: float, amplitude: float, *, segments: int = 32,
) -> MotionTrack:
    """Half-cycle sine that goes 0 -> amplitude -> 0; useful for
    one-shot raises that should sit in a [0, 1] parameter."""
    out: list[MotionSegment] = []
    for i in range(segments):
        t0 = duration * i / segments
        t1 = duration * (i + 1) / segments
        v0 = amplitude * math.sin(math.pi * t0 / duration)
        v1 = amplitude * math.sin(math.pi * t1 / duration)
        out.append(MotionSegment(type="linear", p0=(t0, v0), p1=(t1, v1)))
    return MotionTrack(param_id=param_id, segments=out)


def _idle_motion() -> Motion:
    """Body sways gently while the head counter-bobs the other way —
    classic Vtuber idle loop."""
    return Motion(
        name="idle",
        duration=4.0,
        loop=True,
        tracks=[
            _sine_track("ParamBodySway", 4.0, 0.6),
            _sine_track("ParamHeadX", 4.0, 0.3, phase=math.pi),
        ],
    )


def _wave_motion() -> Motion:
    """Right arm waves up and down twice."""
    return Motion(
        name="wave",
        duration=2.0,
        loop=True,
        tracks=[
            # Two half-sines back to back so the arm goes up/down/up/down
            MotionTrack(param_id="ParamArmRightUp", segments=[
                MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.25, 1.0)),
                MotionSegment(type="linear", p0=(0.25, 1.0), p1=(0.5, 0.0)),
                MotionSegment(type="linear", p0=(0.5, 0.0), p1=(0.75, 1.0)),
                MotionSegment(type="linear", p0=(0.75, 1.0), p1=(1.0, 0.0)),
                MotionSegment(type="linear", p0=(1.0, 0.0), p1=(1.5, 0.0)),
                MotionSegment(type="linear", p0=(1.5, 0.0), p1=(2.0, 0.0)),
            ]),
            _sine_track("ParamHeadX", 2.0, 0.4),
        ],
    )


def _greet_motion() -> Motion:
    """Both arms slowly raise then drop."""
    return Motion(
        name="greet",
        duration=3.0,
        loop=True,
        tracks=[
            _half_sine_track("ParamArmLeftUp", 3.0, 1.0),
            _half_sine_track("ParamArmRightUp", 3.0, 1.0),
            # Head dips slightly during the bow
            MotionTrack(param_id="ParamBodySway", segments=[
                MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.5, 0.4)),
                MotionSegment(type="linear", p0=(1.5, 0.4), p1=(3.0, 0.0)),
            ]),
        ],
    )


if __name__ == "__main__":
    build_amiya_puppet()
