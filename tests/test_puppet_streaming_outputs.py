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
