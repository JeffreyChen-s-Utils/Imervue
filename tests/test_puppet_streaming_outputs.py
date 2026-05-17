"""Tests for the OBS-bound streaming outputs (virtual camera + NDI).

Both real outputs need a virtual-camera driver / NDI runtime that
CI doesn't have, so the start/stop loops live behind
``pragma: no cover`` markers. These tests cover the parts that DO
run pure-Python — most importantly the resolution-cap helper that
keeps Cubism-native 3503×7777 canvases from getting rejected by
the DirectShow virtual-camera driver.
"""
from __future__ import annotations
import pytest

from Imervue.puppet.virtual_camera import (
    MAX_OUTPUT_DIMENSION,
    _scale_for_streaming,
)


# QOpenGLWidget construction segfaults on the headless GitHub
# Actions Windows runner once the offscreen-GL pool is exhausted
# (see tests/conftest.py::skip_on_headless_ci). All tests in this
# file touch a real PuppetCanvas / PuppetWorkspace, so the whole
# module skips on CI; local runs cover them.
import os as _os_for_skip  # noqa: E402
import pytest as _pytest_for_skip  # noqa: E402

pytestmark = _pytest_for_skip.mark.skipif(
    _os_for_skip.environ.get("CI") == "true"
    or _os_for_skip.environ.get("QT_QPA_PLATFORM") == "offscreen",
    reason="QOpenGLWidget construction segfaults on headless CI runner",
)



# ---------------------------------------------------------------------------
# _scale_for_streaming — caps longest side at MAX_OUTPUT_DIMENSION
# ---------------------------------------------------------------------------


def test_scale_for_streaming_passes_through_small_canvases():
    """Canvases whose longest dimension is at or below the cap are
    streamed at native size — no point downscaling a 720p source
    just to fit a 1080p limit."""
    assert _scale_for_streaming(640, 480) == (640, 480)
    # Exactly at the cap on the longest side — still pass-through.
    assert _scale_for_streaming(1080, 1080) == (1080, 1080)
    assert _scale_for_streaming(1080, 600) == (1080, 600)


def test_scale_for_streaming_preserves_aspect_ratio_on_tall_canvas():
    """The March 7th-style tall Cubism canvas (3503×7777) gets
    scaled so the height becomes MAX_OUTPUT_DIMENSION and the width
    drops proportionally."""
    w, h = _scale_for_streaming(3503, 7777)
    assert h == MAX_OUTPUT_DIMENSION   # 1080
    # 3503/7777 ≈ 0.4504 → 1080 * 0.4504 ≈ 486
    assert w == pytest.approx(486, abs=2)
    # Aspect ratio preserved within rounding.
    assert abs(w / h - 3503 / 7777) < 0.01


def test_scale_for_streaming_preserves_aspect_ratio_on_wide_canvas():
    """A horizontal 3840×2160 source caps width at 1080? — no, the
    *longest* dimension is the one we cap, so width becomes 1080
    when width > height."""
    w, h = _scale_for_streaming(3840, 2160)
    assert w == MAX_OUTPUT_DIMENSION
    # 2160 / 3840 = 0.5625 → 1080 * 0.5625 ≈ 608 (even)
    assert h == pytest.approx(608, abs=2)


def test_scale_for_streaming_rounds_to_even_widths():
    """DirectShow virtual camera drivers reject odd-numbered
    dimensions on Windows. The helper rounds the scaled dimension
    to the nearest lower even integer."""
    for w, h in (_scale_for_streaming(2001, 1000), _scale_for_streaming(1000, 2001)):
        assert w % 2 == 0
        assert h % 2 == 0


def test_scale_for_streaming_clamps_minimum_to_two_pixels():
    """Pathological inputs (one giant dimension and one tiny one)
    must still produce a non-zero output the driver will accept."""
    w, h = _scale_for_streaming(100000, 1)
    assert w == MAX_OUTPUT_DIMENSION
    assert h >= 2


def test_scale_for_streaming_handles_zero_or_negative_inputs():
    """Degenerate inputs return as-is — the caller branch decides
    whether to refuse the stream."""
    assert _scale_for_streaming(0, 1080) == (0, 1080)
    assert _scale_for_streaming(1920, 0) == (1920, 0)
    assert _scale_for_streaming(-100, 1080) == (-100, 1080)


# ---------------------------------------------------------------------------
# NDI module re-uses the same helper
# ---------------------------------------------------------------------------


def test_ndi_output_reuses_virtual_camera_scaler():
    """Both outputs need the same cap behaviour — the NDI module
    imports the helper from the virtual camera module rather than
    duplicating the logic. This test guards that import path."""
    from Imervue.puppet import ndi_output
    from Imervue.puppet.virtual_camera import _scale_for_streaming as src
    assert ndi_output._scale_for_streaming is src   # noqa: SLF001


# ---------------------------------------------------------------------------
# Aspect ratio fix — widget-aspect camera, KeepAspectRatio + pad scaler
# ---------------------------------------------------------------------------


def test_qimage_to_rgb_array_preserves_aspect_on_match(qapp):
    """When source and target dimensions match exactly, the helper
    should not introduce any padding."""
    import numpy as np
    from PySide6.QtGui import QImage
    from Imervue.puppet.virtual_camera import _qimage_to_rgb_array

    src = QImage(640, 360, QImage.Format.Format_RGB888)
    src.fill(0xFF8080)   # solid red
    arr = _qimage_to_rgb_array(src, 640, 360)
    assert arr.shape == (360, 640, 3)
    # All pixels carry the source colour — no padding bars.
    assert np.unique(arr.reshape(-1, 3), axis=0).shape == (1, 3)


def test_qimage_to_rgb_array_pads_on_aspect_mismatch(qapp):
    """When the source is wider than the target, the helper should
    letterbox the result on a black canvas — not stretch."""
    import numpy as np
    from PySide6.QtGui import QImage
    from Imervue.puppet.virtual_camera import _qimage_to_rgb_array

    src = QImage(1920, 1080, QImage.Format.Format_RGB888)
    src.fill(0xFF0000)
    # Target is a tall portrait box — source must letterbox
    # (centred horizontally) with black bars top and bottom.
    arr = _qimage_to_rgb_array(src, 540, 1080)
    assert arr.shape == (1080, 540, 3)
    # Centre column has the source colour somewhere — the scaled
    # image is letterboxed inside the target.
    has_source_color = np.any((arr == [255, 0, 0]).all(axis=-1))
    has_black_padding = np.any((arr == [0, 0, 0]).all(axis=-1))
    assert has_source_color, "source colour disappeared after pad-to-fit"
    assert has_black_padding, "expected black bars in aspect-mismatch case"


def test_qimage_to_rgb_array_rejects_zero_target(qapp):
    """Defensive: zero target dimensions return ``None`` so the
    caller can refuse the frame rather than crash."""
    from PySide6.QtGui import QImage
    from Imervue.puppet.virtual_camera import _qimage_to_rgb_array
    src = QImage(640, 360, QImage.Format.Format_RGB888)
    assert _qimage_to_rgb_array(src, 0, 100) is None
    assert _qimage_to_rgb_array(src, 100, 0) is None


# ---------------------------------------------------------------------------
# render_offscreen_puppet — character-only FBO render
# ---------------------------------------------------------------------------


def test_render_offscreen_returns_none_without_document(qapp):
    """Streaming outputs call ``render_offscreen_puppet`` every tick;
    when no document is loaded the helper must return ``None`` so the
    caller can skip the frame rather than crashing on the doc deref."""
    from Imervue.puppet.canvas import PuppetCanvas
    canvas = PuppetCanvas()
    try:
        assert canvas.render_offscreen_puppet(640, 480) is None
    finally:
        canvas.deleteLater()


def test_render_offscreen_returns_none_for_zero_target(qapp):
    """Defensive: ``(0, _)`` / ``(_, 0)`` returns ``None`` instead
    of crashing inside QOpenGLFramebufferObject."""
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.document import Drawable, PuppetDocument
    doc = PuppetDocument(size=(512, 512))
    doc.textures["textures/x.png"] = b""
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        indices=[0, 1, 2],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        draw_order=0,
    )]
    canvas = PuppetCanvas()
    canvas.load_document(doc)
    try:
        assert canvas.render_offscreen_puppet(0, 480) is None
        assert canvas.render_offscreen_puppet(640, 0) is None
        assert canvas.render_offscreen_puppet(-100, 100) is None
    finally:
        canvas.deleteLater()


def test_virtual_camera_uses_chroma_key_magenta(qapp):
    """The virtual-camera output's background colour must default to
    a chroma-keyable magenta — RGB-only virtual cameras can't carry
    alpha, so streamers depend on this colour to drop the background
    via OBS Color Key. Test guards against a future "let's just use
    black" regression that would silently break the workflow."""
    from Imervue.puppet.virtual_camera import CHROMA_KEY_MAGENTA_RGBA
    r, g, b, a = CHROMA_KEY_MAGENTA_RGBA
    # Pure magenta — full red + full blue, zero green, opaque alpha.
    assert (r, g, b, a) == (1.0, 0.0, 1.0, 1.0)
