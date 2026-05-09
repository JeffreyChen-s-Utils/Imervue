"""Tests for the GPU brush rasterisation factory + helpers.

The GL-touching code paths (``GPUDabSession.__init__`` / ``stamp`` /
``read_back`` / ``dispose``) require a live GL context which the CI
runner doesn't have, so they are excluded with
``# pragma: no cover - GL needs display server``. Coverage in this
file is for the pure helpers: the support gate, the orthographic
matrix, and the factory's CPU-fallback wiring.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.brush_engine import BrushStroke, BrushStrokeOptions
from Imervue.paint.gpu_brush import (
    _gpu_supported,
    _ortho,
    gpu_available,
    make_brush_stroke,
)


# ---------------------------------------------------------------------------
# _ortho
# ---------------------------------------------------------------------------


def test_ortho_returns_4x4_float32():
    m = _ortho(0.0, 100.0, 50.0, 0.0)
    assert m.shape == (4, 4)
    assert m.dtype == np.float32


def test_ortho_y_down_when_bottom_greater_than_top():
    """Workspace convention is Y-down (``glOrtho(0, w, h, 0, ...)``).

    With ``bottom = h`` and ``top = 0`` the y scale should be negative
    so increasing canvas-space Y maps to increasing screen-space Y.
    """
    m = _ortho(0.0, 100.0, 50.0, 0.0)
    assert m[1, 1] < 0.0


def test_ortho_y_up_when_top_greater_than_bottom():
    m = _ortho(0.0, 100.0, 0.0, 50.0)
    assert m[1, 1] > 0.0


def test_ortho_homogeneous_w_is_one():
    m = _ortho(-1.0, 1.0, -1.0, 1.0)
    assert m[3, 3] == pytest.approx(1.0)


def test_ortho_origin_pixel_centre_maps_correctly():
    """Pixel (0, 0) at the top-left of a Y-down ortho should land at
    NDC (-1, +1) — the top-left of the screen."""
    m = _ortho(0.0, 200.0, 100.0, 0.0)
    pt = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32) @ m
    assert pt[0] == pytest.approx(-1.0)
    assert pt[1] == pytest.approx(1.0)


def test_ortho_far_corner_maps_to_bottom_right_ndc():
    m = _ortho(0.0, 200.0, 100.0, 0.0)
    pt = np.array([200.0, 100.0, 0.0, 1.0], dtype=np.float32) @ m
    assert pt[0] == pytest.approx(1.0)
    assert pt[1] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# _gpu_supported — compatibility gate
# ---------------------------------------------------------------------------


def _opts(**overrides):
    """Return a default GPU-friendly options bundle, then overlay overrides."""
    base = {
        "color": (10, 20, 30),
        "size": 8,
        "opacity": 1.0,
        "hardness": 0.5,
        "blend_mode": "normal",
        "selection": None,
        "kind": "pen",
        "pixel_art": False,
    }
    base.update(overrides)
    return BrushStrokeOptions(**base)


def test_gpu_supported_default_pen_stroke_is_supported():
    assert _gpu_supported(_opts()) is True


def test_gpu_supported_marker_stroke_is_supported():
    assert _gpu_supported(_opts(kind="marker")) is True


def test_gpu_supported_watercolor_stroke_is_supported():
    assert _gpu_supported(_opts(kind="watercolor")) is True


@pytest.mark.parametrize("mode", [
    "multiply", "screen", "overlay", "darken", "lighten",
    "color_dodge", "color_burn", "soft_light", "hard_light",
    "linear_burn", "linear_dodge",
])
def test_gpu_supported_rejects_non_normal_blend_modes(mode):
    """Only ``normal`` is wired through the shader; everything else
    must route to the CPU :class:`BrushStroke` so blend correctness
    matches the existing reference."""
    assert _gpu_supported(_opts(blend_mode=mode)) is False


def test_gpu_supported_rejects_selection_mask():
    sel = np.ones((16, 16), dtype=bool)
    assert _gpu_supported(_opts(selection=sel)) is False


def test_gpu_supported_rejects_pixel_art_mode():
    assert _gpu_supported(_opts(pixel_art=True)) is False


@pytest.mark.parametrize("kind", ["pencil", "airbrush"])
def test_gpu_supported_rejects_per_dab_kernel_kinds(kind):
    """``pencil`` / ``airbrush`` re-stylise the kernel every dab —
    re-uploading a kernel texture per dab erases the GPU win, so
    the gate keeps them on the CPU path."""
    assert _gpu_supported(_opts(kind=kind)) is False


# ---------------------------------------------------------------------------
# gpu_available — context probe
# ---------------------------------------------------------------------------


def test_gpu_available_returns_a_bool():
    """The probe never raises and always reports a boolean. The
    actual value depends on whether a prior test left a GL context
    bound — :func:`make_brush_stroke` doesn't rely on the value
    being False here, so we don't assert one direction."""
    out = gpu_available()
    assert isinstance(out, bool)


# ---------------------------------------------------------------------------
# make_brush_stroke — factory
# ---------------------------------------------------------------------------


def test_factory_returns_cpu_stroke_when_gpu_unavailable(monkeypatch):
    """With ``gpu_available`` mocked False, the factory must return
    the canonical CPU :class:`BrushStroke` regardless of what other
    tests left bound to the GL thread."""
    from Imervue.paint import gpu_brush
    monkeypatch.setattr(gpu_brush, "gpu_available", lambda: False)
    stroke = make_brush_stroke(_opts())
    assert type(stroke) is BrushStroke


def test_factory_returns_cpu_stroke_for_unsupported_options(monkeypatch):
    """Even when GL is current, an unsupported option set must
    still drop to the CPU class so behaviour stays consistent."""
    from Imervue.paint import gpu_brush
    monkeypatch.setattr(gpu_brush, "gpu_available", lambda: True)
    stroke = make_brush_stroke(_opts(blend_mode="multiply"))
    assert type(stroke) is BrushStroke


def test_factory_returns_gpu_stroke_when_both_supported(monkeypatch):
    """With ``gpu_available`` mocked True and a GPU-friendly options
    bundle, the factory yields the GPU adapter type — verified via
    ``isinstance`` of the BrushStroke subclass returned by
    ``GPUBrushStroke.__new__``."""
    from Imervue.paint import gpu_brush

    class _StubSession:
        """No-op stand-in for the GL-backed session — the factory
        only checks the attribute surface, not the side effects."""

        def __init__(self, layer):
            self.layer = layer

        def stamp(self, *args, **kwargs):
            """Pretend to stamp a dab — nothing to do without GL."""

        def read_back(self, into):
            """Pretend to read back — the test verifies the call,
            not the resulting pixels."""

        def dispose(self):
            """Pretend to free GL objects — none were allocated."""

    monkeypatch.setattr(gpu_brush, "gpu_available", lambda: True)
    monkeypatch.setattr(gpu_brush, "GPUDabSession", _StubSession)
    stroke = make_brush_stroke(_opts())
    # GPU stroke is a runtime-built BrushStroke subclass; the surest
    # check is that paint dispatches through the override.
    assert isinstance(stroke, BrushStroke)
    assert type(stroke) is not BrushStroke


def test_gpu_stroke_uses_session_when_supplied(monkeypatch):
    """End-to-end: with a stub GL session, a complete begin/extend/end
    cycle must drive ``stamp`` calls and a ``read_back`` after every
    pointer phase so ``paintGL`` sees a fresh layer mid-stroke."""
    from Imervue.paint import gpu_brush

    calls = {"stamps": 0, "read_back": 0, "dispose": 0}

    class _StubSession:
        def __init__(self, layer):
            self.layer = layer

        def stamp(self, *args, **kwargs):
            calls["stamps"] += 1

        def read_back(self, into):
            calls["read_back"] += 1

        def dispose(self):
            calls["dispose"] += 1

    monkeypatch.setattr(gpu_brush, "gpu_available", lambda: True)
    monkeypatch.setattr(gpu_brush, "GPUDabSession", _StubSession)
    canvas = np.zeros((32, 32, 4), dtype=np.uint8)
    stroke = make_brush_stroke(_opts(size=4, opacity=1.0))
    stroke.begin(canvas, 4.0, 4.0)
    stroke.extend(canvas, 16.0, 4.0)
    stroke.end(canvas, 28.0, 4.0)
    assert calls["stamps"] >= 2
    # One read_back per pointer phase, plus an extra one for the
    # extend that ``BrushStroke.end`` calls internally to drain
    # the stabiliser / tail buffer. Exact count is an
    # implementation detail; the contract is "at least one per
    # phase" so the canvas widget always sees fresh pixels.
    assert calls["read_back"] >= 3
    assert calls["dispose"] == 1


def test_factory_respects_prefer_gpu_false(monkeypatch):
    """``prefer_gpu=False`` must drop to the CPU stroke even when GL
    is current and the options are GPU-compatible. The brush
    dispatcher uses this to keep symmetry strokes off the GPU."""
    from Imervue.paint import gpu_brush
    monkeypatch.setattr(gpu_brush, "gpu_available", lambda: True)
    stroke = make_brush_stroke(_opts(), prefer_gpu=False)
    assert type(stroke) is BrushStroke


def test_gpu_stroke_falls_back_to_cpu_when_session_init_fails(monkeypatch):
    """A session-init failure (e.g., FBO incomplete on a constrained
    driver) must leave the canvas correctly painted via the CPU path."""
    from Imervue.paint import gpu_brush

    class _FailingSession:
        def __init__(self, layer):
            raise RuntimeError("FBO unavailable")

    monkeypatch.setattr(gpu_brush, "gpu_available", lambda: True)
    monkeypatch.setattr(gpu_brush, "GPUDabSession", _FailingSession)
    canvas = np.zeros((32, 32, 4), dtype=np.uint8)
    stroke = make_brush_stroke(_opts(color=(255, 0, 0), size=8, opacity=1.0))
    stroke.begin(canvas, 16.0, 16.0)
    stroke.end(canvas, 16.0, 16.0)
    # CPU fallback dabbed red into the centre — alpha must be > 0.
    assert int(canvas[16, 16, 3]) > 0
    assert int(canvas[16, 16, 0]) > 0


# ---------------------------------------------------------------------------
# CPU fastpath equivalence — the optimised normal-mode path must
# stay within 1 LSB of the float reference for a representative
# sweep of foregrounds and alphas.
# ---------------------------------------------------------------------------


def _float_normal_reference(
    bg: np.ndarray, alpha: np.ndarray, color: tuple[int, int, int],
) -> np.ndarray:
    """Float-domain "normal" alpha-over result — the historical truth."""
    bg_f = bg.astype(np.float32) / 255.0
    fg_f = np.array(color, dtype=np.float32) / 255.0
    a = alpha[..., None]
    out = bg_f[..., :3] * (1.0 - a) + fg_f * a
    bg_a = bg_f[..., 3]
    new_a = bg_a + (1.0 - bg_a) * alpha
    rgba = np.empty(bg.shape, dtype=np.uint8)
    rgba[..., :3] = np.clip(out * 255.0, 0.0, 255.0).astype(np.uint8)
    rgba[..., 3] = np.clip(new_a * 255.0, 0.0, 255.0).astype(np.uint8)
    return rgba


@pytest.mark.parametrize("color", [
    (255, 0, 0),
    (0, 128, 200),
    (200, 200, 50),
    (10, 10, 10),
])
def test_normal_fastpath_within_one_lsb_of_float(color):
    """Sweep the integer fixed-point fast path against the float
    reference for a kernel of varying alpha."""
    from Imervue.paint.brush_engine import _composite_normal_u8
    rng = np.random.default_rng(seed=0xC0DE)
    bg = rng.integers(0, 256, size=(8, 8, 4), dtype=np.uint8)
    alpha = rng.random(size=(8, 8), dtype=np.float32)
    expected = _float_normal_reference(bg, alpha, color)
    actual = bg.copy()
    _composite_normal_u8(actual[..., :], alpha, color)
    diff = np.abs(actual.astype(np.int16) - expected.astype(np.int16))
    assert diff.max() <= 1


def test_normal_fastpath_zero_alpha_is_noop():
    from Imervue.paint.brush_engine import _composite_normal_u8
    bg = np.full((4, 4, 4), 123, dtype=np.uint8)
    alpha = np.zeros((4, 4), dtype=np.float32)
    before = bg.copy()
    _composite_normal_u8(bg, alpha, (255, 0, 0))
    np.testing.assert_array_equal(bg, before)


def test_normal_fastpath_full_alpha_paints_color():
    from Imervue.paint.brush_engine import _composite_normal_u8
    bg = np.zeros((4, 4, 4), dtype=np.uint8)
    bg[..., 3] = 0
    alpha = np.ones((4, 4), dtype=np.float32)
    _composite_normal_u8(bg, alpha, (200, 100, 50))
    assert int(bg[0, 0, 0]) == 200
    assert int(bg[0, 0, 1]) == 100
    assert int(bg[0, 0, 2]) == 50
    assert int(bg[0, 0, 3]) == 255
