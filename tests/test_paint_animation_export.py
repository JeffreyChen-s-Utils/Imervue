"""Tests for animated GIF / WebP / APNG export."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.animation import Animation, AnimationFrame
from Imervue.paint.animation_export import (
    export_apng,
    export_gif,
    export_webp,
)
from Imervue.paint.document import PaintDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_with_color(rgb, h=8, w=8):
    doc = PaintDocument()
    base = np.zeros((h, w, 4), dtype=np.uint8)
    base[..., :3] = rgb
    base[..., 3] = 255
    doc.load_image(base)
    return doc


def _three_frame_animation():
    return Animation(frames=[
        AnimationFrame(_doc_with_color((255, 0, 0)), name="A", duration_ms=80),
        AnimationFrame(_doc_with_color((0, 255, 0)), name="B", duration_ms=120),
        AnimationFrame(_doc_with_color((0, 0, 255)), name="C", duration_ms=160),
    ])


def _frame_count(path):
    img = Image.open(path)
    if not getattr(img, "is_animated", False):
        return 1
    return img.n_frames


# ---------------------------------------------------------------------------
# export_gif
# ---------------------------------------------------------------------------


def test_export_gif_creates_file(tmp_path):
    a = _three_frame_animation()
    path = tmp_path / "anim.gif"
    export_gif(a, path)
    assert path.exists()


def test_export_gif_writes_three_frames(tmp_path):
    a = _three_frame_animation()
    path = tmp_path / "anim.gif"
    export_gif(a, path)
    assert _frame_count(path) == 3


def test_export_gif_creates_parent_directory(tmp_path):
    a = _three_frame_animation()
    nested = tmp_path / "a" / "b" / "out.gif"
    export_gif(a, nested)
    assert nested.exists()


def test_export_gif_empty_animation_raises(tmp_path):
    a = Animation()
    with pytest.raises(ValueError, match="no frames"):
        export_gif(a, tmp_path / "empty.gif")


def test_export_gif_rejects_oversized_threshold(tmp_path):
    a = _three_frame_animation()
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        export_gif(a, tmp_path / "out.gif", transparency_threshold=300)


def test_export_gif_loop_zero_means_infinite(tmp_path):
    a = _three_frame_animation()
    path = tmp_path / "loop.gif"
    export_gif(a, path, loop=True)
    img = Image.open(path)
    assert img.info.get("loop") == 0


# ---------------------------------------------------------------------------
# export_webp
# ---------------------------------------------------------------------------


def test_export_webp_creates_file(tmp_path):
    a = _three_frame_animation()
    path = tmp_path / "anim.webp"
    export_webp(a, path)
    assert path.exists()


def test_export_webp_writes_three_frames(tmp_path):
    a = _three_frame_animation()
    path = tmp_path / "anim.webp"
    export_webp(a, path)
    assert _frame_count(path) == 3


def test_export_webp_lossless_preserves_pixels(tmp_path):
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((10, 200, 30)), name="X", duration_ms=80),
    ])
    path = tmp_path / "loss.webp"
    export_webp(a, path, lossless=True)
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)
    # Lossless WebP should match the source exactly.
    assert int(arr[0, 0, 0]) == 10
    assert int(arr[0, 0, 1]) == 200
    assert int(arr[0, 0, 2]) == 30


def test_export_webp_rejects_quality_above_100(tmp_path):
    a = _three_frame_animation()
    with pytest.raises(ValueError, match=r"\[0, 100\]"):
        export_webp(a, tmp_path / "out.webp", quality=200)


def test_export_webp_rejects_negative_quality(tmp_path):
    a = _three_frame_animation()
    with pytest.raises(ValueError, match=r"\[0, 100\]"):
        export_webp(a, tmp_path / "out.webp", quality=-1)


# ---------------------------------------------------------------------------
# export_apng
# ---------------------------------------------------------------------------


def test_export_apng_creates_file(tmp_path):
    a = _three_frame_animation()
    path = tmp_path / "anim.png"
    export_apng(a, path)
    assert path.exists()


def test_export_apng_preserves_pixels_losslessly(tmp_path):
    a = Animation(frames=[
        AnimationFrame(_doc_with_color((10, 200, 30)), name="X", duration_ms=80),
    ])
    path = tmp_path / "loss.png"
    export_apng(a, path)
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)
    # APNG is lossless.
    assert int(arr[0, 0, 0]) == 10
    assert int(arr[0, 0, 1]) == 200
    assert int(arr[0, 0, 2]) == 30


def test_export_apng_empty_raises(tmp_path):
    a = Animation()
    with pytest.raises(ValueError, match="no frames"):
        export_apng(a, tmp_path / "out.png")
