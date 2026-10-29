"""Contract tests pinning the brush engine's observable output.

Every stroke below runs on a small synthetic canvas and is compared by a
SHA-256 digest of the canvas bytes, so any change in dab placement, kernel
shape, compositing or RNG consumption shows up as a digest mismatch.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from Imervue.paint import brush_engine
from Imervue.paint.brush_engine import (
    BrushStroke,
    BrushStrokeOptions,
    DabResult,
    apply_dab,
    apply_erase_dab,
    dab_bbox,
    round_brush_kernel,
    sample_pixel,
    spacing_from_brush,
    square_brush_kernel,
    stroke_dab_positions,
)

_PATH = [(4.0, 5.0), (12.5, 9.0), (20.0, 22.0), (27.0, 26.0)]


def _digest(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()[:16]


def _canvas(fill: tuple[int, int, int, int] = (0, 0, 0, 0)) -> np.ndarray:
    canvas = np.zeros((32, 32, 4), dtype=np.uint8)
    canvas[...] = fill
    return canvas


def _run_stroke(options: BrushStrokeOptions, canvas: np.ndarray | None = None):
    canvas = _canvas() if canvas is None else canvas
    stroke = BrushStroke(options)
    damages = [stroke.begin(canvas, *_PATH[0])]
    damages.extend(stroke.extend(canvas, *p) for p in _PATH[1:-1])
    damages.append(stroke.end(canvas, *_PATH[-1]))
    return canvas, damages, stroke.stroke_damage


def _opts(**kw) -> BrushStrokeOptions:
    base = {"color": (200, 40, 90), "size": 7, "opacity": 0.8, "hardness": 0.5}
    base.update(kw)
    return BrushStrokeOptions(**base)


# ---------------------------------------------------------------------------
# Re-exported public surface
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", [
    "BLEND_MODES", "KERNEL_SIZE_MIN", "KERNEL_SIZE_MAX", "DabResult",
    "BrushStroke", "BrushStrokeOptions", "apply_dab", "apply_erase_dab",
    "dab_bbox", "round_brush_kernel", "square_brush_kernel", "sample_pixel",
    "spacing_from_brush", "stroke_dab_positions", "_composite_normal_u8",
    "_composite_in_place", "_union", "_check_canvas", "_resolve_base_kernel",
])
def test_names_stay_importable_from_brush_engine(name):
    assert hasattr(brush_engine, name)


def test_kernel_size_bounds():
    assert (brush_engine.KERNEL_SIZE_MIN, brush_engine.KERNEL_SIZE_MAX) == (1, 1024)


# ---------------------------------------------------------------------------
# Kernels, spacing, interpolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("size", "hardness", "expected"), [
    (1, 0.5, "1"),
    (0, 0.5, "1"),
    (5, 1.0, None),
    (6, 0.0, None),
    (9, 0.4, None),
    (9, 2.0, None),
])
def test_round_kernel_shape_and_range(size, hardness, expected):
    kernel = round_brush_kernel(size, hardness)
    clamped = max(1, size)
    assert kernel.shape == (clamped, clamped)
    assert kernel.dtype == np.float32
    assert float(kernel.min()) >= 0.0
    assert float(kernel.max()) <= 1.0
    if expected == "1":
        assert kernel.tolist() == [[1.0]]


def test_round_kernel_values_pinned():
    hard = round_brush_kernel(5, 1.0)
    assert hard.astype(int).tolist() == [
        [0, 0, 1, 0, 0],
        [0, 1, 1, 1, 0],
        [1, 1, 1, 1, 1],
        [0, 1, 1, 1, 0],
        [0, 0, 1, 0, 0],
    ]
    soft = round_brush_kernel(7, 0.3)
    np.testing.assert_allclose(soft[3, 3], 1.0)
    np.testing.assert_allclose(soft[3, 0], 0.0, atol=1e-6)
    np.testing.assert_allclose(soft[3, 5], 0.4643127, atol=1e-5)


def test_square_kernel_clamps():
    assert square_brush_kernel(0).shape == (1, 1)
    assert square_brush_kernel(5000).shape == (1024, 1024)
    assert float(square_brush_kernel(3).sum()) == pytest.approx(9.0)


@pytest.mark.parametrize(("size", "hardness", "expected"), [
    (10, 1.0, 1.0),
    (10, 0.0, 4.0),
    (40, 0.5, 10.0),
    (1, 0.5, 1.0),
    (0, -3.0, 1.0),
])
def test_spacing_from_brush(size, hardness, expected):
    assert spacing_from_brush(size, hardness) == pytest.approx(expected)


def test_stroke_dab_positions_exact():
    assert stroke_dab_positions((0, 0), (1, 0), 2.0) == [(1.0, 0.0)]
    assert stroke_dab_positions((0, 0), (10, 0), 3.0) == [
        (2.5, 0.0), (5.0, 0.0), (7.5, 0.0), (10.0, 0.0),
    ]
    with pytest.raises(ValueError, match="spacing must be > 0"):
        stroke_dab_positions((0, 0), (1, 1), 0)


def test_resolve_base_kernel_falls_back_on_bad_tip(tmp_path):
    missing = str(tmp_path / "nope.png")
    kernel = brush_engine._resolve_base_kernel(_opts(tip_path=missing))
    np.testing.assert_array_equal(kernel, round_brush_kernel(7, 0.5))
    pixel = brush_engine._resolve_base_kernel(_opts(pixel_art=True, tip_path=missing))
    np.testing.assert_array_equal(pixel, square_brush_kernel(7))


# ---------------------------------------------------------------------------
# Dabs
# ---------------------------------------------------------------------------


def test_dab_bbox_clipping():
    assert dab_bbox((10, 10), (3, 3), 0, 0) == (0, 0, 2, 2, 1, 1, 3, 3)
    assert dab_bbox((10, 10), (4, 4), 5, 5) == (3, 3, 7, 7, 0, 0, 4, 4)
    assert dab_bbox((10, 10), (3, 3), -5, 4) is None


def test_apply_dab_validation_errors():
    canvas = _canvas()
    kernel = round_brush_kernel(3, 1.0)
    with pytest.raises(ValueError, match="canvas must be HxWx4 uint8 RGBA"):
        apply_dab(np.zeros((4, 4, 3), np.uint8), 1, 1, kernel, (1, 2, 3))
    with pytest.raises(ValueError, match="kernel must be 2-D"):
        apply_dab(canvas, 1, 1, np.ones(3, np.float32), (1, 2, 3))
    with pytest.raises(ValueError, match="unknown blend_mode"):
        apply_dab(canvas, 1, 1, kernel, (1, 2, 3), blend_mode="nope")
    with pytest.raises(ValueError, match="selection mask shape"):
        apply_dab(canvas, 1, 1, kernel, (1, 2, 3), selection=np.ones((3, 3), bool))


def test_apply_dab_empty_results():
    canvas = _canvas()
    kernel = round_brush_kernel(3, 1.0)
    assert apply_dab(canvas, 5, 5, kernel, (9, 9, 9), opacity=0.0) == DabResult(0, 0, 0, 0)
    assert apply_dab(canvas, -40, 5, kernel, (9, 9, 9)) == DabResult(0, 0, 0, 0)
    assert not canvas.any()


@pytest.mark.parametrize("mode", ["normal", "multiply", "screen"])
def test_apply_dab_pixels_pinned(mode):
    canvas = _canvas((30, 120, 220, 128))
    canvas[0:4, 0:4, 3] = 0
    selection = np.ones((32, 32), dtype=bool)
    selection[:, 3] = False
    kernel = round_brush_kernel(7, 0.4)
    result = apply_dab(
        canvas, 2.6, 3.2, kernel, (250, 60, 10),
        opacity=0.7, blend_mode=mode, selection=selection,
    )
    assert result == DabResult(0, 0, 7, 7)
    assert _digest(canvas) == _DAB_DIGESTS[mode]


def test_apply_erase_dab_pixels_pinned():
    canvas = _canvas((90, 100, 110, 255))
    kernel = round_brush_kernel(5, 1.0)
    result = apply_erase_dab(canvas, 10, 10, kernel)
    assert result == DabResult(8, 8, 5, 5)
    assert canvas[10, 10].tolist() == [0, 0, 0, 0]
    assert canvas[8, 8].tolist() == [90, 100, 110, 255]
    partial = apply_erase_dab(canvas, 20, 20, round_brush_kernel(5, 0.0), opacity=0.5)
    assert partial == DabResult(18, 18, 5, 5)
    assert _digest(canvas) == _ERASE_DIGEST


def test_apply_erase_dab_edges():
    canvas = _canvas((1, 2, 3, 255))
    kernel = round_brush_kernel(3, 1.0)
    assert apply_erase_dab(canvas, 4, 4, kernel, opacity=-1) == DabResult(0, 0, 0, 0)
    assert apply_erase_dab(canvas, 99, 4, kernel) == DabResult(0, 0, 0, 0)
    with pytest.raises(ValueError, match="kernel must be 2-D"):
        apply_erase_dab(canvas, 1, 1, np.ones(3, np.float32))
    with pytest.raises(ValueError, match="selection mask shape"):
        apply_erase_dab(canvas, 1, 1, kernel, selection=np.ones((2, 2), bool))
    sel = np.zeros((32, 32), dtype=bool)
    assert apply_erase_dab(canvas, 4, 4, kernel, selection=sel) == DabResult(3, 3, 3, 3)
    assert (canvas[..., 3] == 255).all()


def test_sample_pixel():
    canvas = _canvas((5, 6, 7, 8))
    assert sample_pixel(canvas, 3.4, 2.6) == (5, 6, 7)
    assert sample_pixel(canvas, -1, 0) is None
    assert sample_pixel(canvas, 0, 32) is None


def test_union():
    empty = DabResult(0, 0, 0, 0)
    a = DabResult(1, 2, 3, 4)
    assert brush_engine._union(empty, a) == a
    assert brush_engine._union(a, empty) == a
    assert brush_engine._union(a, DabResult(10, 0, 2, 2)) == DabResult(1, 0, 11, 6)
    assert DabResult(0, 0, 0, 5).is_empty
    assert not a.is_empty


# ---------------------------------------------------------------------------
# Strokes — pinned digests (positions, kernels, RNG consumption)
# ---------------------------------------------------------------------------

_STROKE_CASES = {
    "pen": {},
    "marker": {"kind": "marker"},
    "pencil": {"kind": "pencil", "seed": 3},
    "airbrush": {"kind": "airbrush", "seed": 11},
    "watercolor": {"kind": "watercolor", "seed": 5},
    "pixel_art": {"pixel_art": True, "kind": "pencil", "size": 3},
    "spacing": {"spacing": 1.5, "hardness": 1.0},
    "taper": {"taper_start_dabs": 3, "taper_end_dabs": 4},
    "random": {"scatter": 0.6, "color_jitter": 0.4, "seed": 7},
    "random_pixel": {"scatter": 0.8, "seed": 9, "pixel_art": True},
    "blend": {"blend_mode": "multiply"},
}


@pytest.mark.parametrize("case", sorted(_STROKE_CASES))
def test_stroke_output_pinned(case):
    canvas = _canvas((10, 200, 60, 255))
    canvas[:, :8, 3] = 0
    canvas, damages, total = _run_stroke(_opts(**_STROKE_CASES[case]), canvas)
    assert _digest(canvas) == _STROKE_DIGESTS[case]
    assert [tuple(d.__dict__.values()) for d in damages] == _STROKE_DAMAGES[case]
    assert tuple(total.__dict__.values()) == _STROKE_TOTALS[case]


def test_stroke_with_selection_and_tilt():
    selection = np.zeros((32, 32), dtype=bool)
    selection[:, 10:] = True
    opts = _opts(follow_tilt=True, selection=selection, size=9, seed=2)
    canvas = _canvas()
    stroke = BrushStroke(opts)
    stroke.set_tilt(0.7, -0.3)
    stroke.begin(canvas, 5, 5)
    stroke.extend(canvas, 15, 12)
    stroke.set_tilt(-0.2, 0.9)
    stroke.end(canvas, 25, 20)
    assert not canvas[:, :10, 3].any()
    assert _digest(canvas) == _TILT_DIGEST


def test_same_seed_is_reproducible_and_seed_matters():
    a, _, _ = _run_stroke(_opts(kind="airbrush", seed=4, scatter=0.5, color_jitter=0.3))
    b, _, _ = _run_stroke(_opts(kind="airbrush", seed=4, scatter=0.5, color_jitter=0.3))
    c, _, _ = _run_stroke(_opts(kind="airbrush", seed=5, scatter=0.5, color_jitter=0.3))
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_stroke_state_machine_errors():
    stroke = BrushStroke(_opts())
    canvas = _canvas()
    assert not stroke.is_active
    with pytest.raises(RuntimeError, match="extend called before begin"):
        stroke.extend(canvas, 1, 1)
    with pytest.raises(RuntimeError, match="end called before begin"):
        stroke.end(canvas, 1, 1)
    stroke.begin(canvas, 1, 1)
    assert stroke.is_active
    with pytest.raises(RuntimeError, match="already active"):
        stroke.begin(canvas, 1, 1)
    stroke.end(canvas, 2, 2)
    assert not stroke.is_active
    assert stroke.dispose() is None


def test_taper_end_short_stroke_flushes_all_dabs():
    canvas = _canvas()
    stroke = BrushStroke(_opts(taper_end_dabs=10, hardness=1.0))
    first = stroke.begin(canvas, 10, 10)
    assert first.is_empty
    assert not canvas.any()
    last = stroke.end(canvas, 10, 10)
    assert last == DabResult(7, 7, 7, 7)
    assert canvas[10, 10, 3] > 0


_DAB_DIGESTS = {
    "normal": "b754d9df3f416f74",
    "multiply": "e7a9883c620ab713",
    "screen": "755903f51c04e1a2",
}
_ERASE_DIGEST = "9dfaa80099057be0"
_TILT_DIGEST = "03b82d157b3e90a2"
_STROKE_DIGESTS = {
    "airbrush": "3c78b999677b175e",
    "blend": "34a1301694d86f77",
    "marker": "f2eb25f85fbc8165",
    "pen": "f2eb25f85fbc8165",
    "pencil": "07b8d4401c97a570",
    "pixel_art": "73317213ac58591c",
    "random": "ee4712112b088840",
    "random_pixel": "746cdda2065ee53e",
    "spacing": "552119a40220b39b",
    "taper": "21c563dc90697f18",
    "watercolor": "16ee9e0bdb89b9e5",
}
_DEFAULT_DAMAGES = [(1, 2, 7, 7), (2, 3, 14, 10), (10, 7, 14, 19), (18, 20, 13, 10)]
_STROKE_DAMAGES = {
    "airbrush": _DEFAULT_DAMAGES,
    "blend": _DEFAULT_DAMAGES,
    "marker": _DEFAULT_DAMAGES,
    "pen": _DEFAULT_DAMAGES,
    "pencil": _DEFAULT_DAMAGES,
    "pixel_art": [(3, 4, 3, 3), (4, 4, 10, 7), (11, 9, 11, 15), (20, 21, 9, 7)],
    "random": [(0, 0, 5, 6), (1, 3, 14, 10), (11, 9, 15, 16), (18, 19, 14, 11)],
    "random_pixel": [(2, 1, 7, 7), (0, 0, 21, 13), (9, 7, 17, 21), (14, 21, 18, 11)],
    "spacing": _DEFAULT_DAMAGES,
    "taper": [(0, 0, 0, 0), (1, 2, 10, 8), (5, 4, 16, 16), (15, 15, 16, 15)],
    "watercolor": _DEFAULT_DAMAGES,
}
_DEFAULT_TOTAL = (1, 2, 30, 28)
_STROKE_TOTALS = {
    "airbrush": _DEFAULT_TOTAL,
    "blend": _DEFAULT_TOTAL,
    "marker": _DEFAULT_TOTAL,
    "pen": _DEFAULT_TOTAL,
    "pencil": _DEFAULT_TOTAL,
    "pixel_art": (3, 4, 26, 24),
    "random": (0, 0, 32, 30),
    "random_pixel": (0, 0, 32, 32),
    "spacing": _DEFAULT_TOTAL,
    "taper": _DEFAULT_TOTAL,
    "watercolor": _DEFAULT_TOTAL,
}
