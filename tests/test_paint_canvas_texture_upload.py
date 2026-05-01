"""Tests for the partial texture-upload path in :class:`PaintCanvas`.

The bug guarded against: a sub-region upload would crash the GL
driver with an access-violation because ``GL_UNPACK_ROW_LENGTH`` was
set to the full canvas width while the byte buffer handed to
``glTexSubImage2D`` was already packed (only ``damage.h * damage.w *
4`` bytes long). OpenGL would then read ``w * damage.h * 4`` bytes
off the end of the buffer.

These tests exercise the byte-budget arithmetic without spinning up
a real GL context — they monkeypatch the GL calls to record what was
asked of the driver, and assert the byte count matches the rect.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import canvas as canvas_module
from Imervue.paint.canvas import PaintCanvas
from Imervue.paint.damage import DamageRect


@pytest.fixture
def canvas(qapp):
    c = PaintCanvas()
    c.new_blank_document(width=64, height=48)
    return c


@pytest.fixture
def composite():
    """Distinctive RGB pattern so a wrong-rect upload would be obvious."""
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(48, 64, 4), dtype=np.uint8)


def _patch_gl(monkeypatch, recorded):
    """Replace the canvas-module GL calls with no-op recorders."""
    monkeypatch.setattr(canvas_module, "glBindTexture", lambda *_a: None)
    monkeypatch.setattr(canvas_module, "glGenTextures", lambda _n: 1)
    monkeypatch.setattr(canvas_module, "glDeleteTextures", lambda *_a: None)
    monkeypatch.setattr(canvas_module, "glTexParameteri", lambda *_a: None)
    monkeypatch.setattr(canvas_module, "glTexParameterf", lambda *_a: None)

    def _full_upload(*args):
        recorded.setdefault("full", []).append(args)

    def _sub_upload(*args):
        recorded.setdefault("sub", []).append(args)

    monkeypatch.setattr(canvas_module, "glTexImage2D", _full_upload)
    monkeypatch.setattr(canvas_module, "glTexSubImage2D", _sub_upload)


def test_first_upload_uses_full_glteximage2d(canvas, composite, monkeypatch):
    recorded: dict = {}
    _patch_gl(monkeypatch, recorded)
    canvas._texture = None  # noqa: SLF001 — force first-upload path
    canvas._pending_damage = DamageRect(x=0, y=0, w=64, h=48)  # noqa: SLF001
    canvas._upload_texture(composite)  # noqa: SLF001
    try:
        assert "full" in recorded and "sub" not in recorded
    finally:
        canvas.deleteLater()


def test_full_damage_uses_full_glteximage2d(canvas, composite, monkeypatch):
    recorded: dict = {}
    _patch_gl(monkeypatch, recorded)
    canvas._texture = 1  # noqa: SLF001 — pretend texture already exists
    canvas._pending_damage = DamageRect(x=0, y=0, w=64, h=48)  # noqa: SLF001
    canvas._upload_texture(composite)  # noqa: SLF001
    try:
        # Full-canvas damage takes the cheap glTexImage2D path.
        assert "full" in recorded and "sub" not in recorded
    finally:
        canvas.deleteLater()


def test_sub_region_upload_byte_count_matches_rect(
    canvas, composite, monkeypatch,
):
    """Regression: the bytes handed to ``glTexSubImage2D`` must be
    exactly ``damage.h * damage.w * 4`` long. Off-by-rowlength would
    pass too many bytes and the GL driver would crash."""
    recorded: dict = {}
    _patch_gl(monkeypatch, recorded)
    canvas._texture = 1  # noqa: SLF001 — pretend texture already exists
    canvas._pending_damage = DamageRect(x=10, y=8, w=20, h=12)  # noqa: SLF001
    canvas._upload_texture(composite)  # noqa: SLF001
    try:
        assert "sub" in recorded
        args = recorded["sub"][0]
        # Signature: (target, level, x, y, w, h, format, type, pixels)
        x, y, w, h = args[2], args[3], args[4], args[5]
        pixels = args[8]
        assert (x, y, w, h) == (10, 8, 20, 12)
        assert isinstance(pixels, bytes)
        assert len(pixels) == 12 * 20 * 4
    finally:
        canvas.deleteLater()


def test_sub_region_upload_pixels_match_source(
    canvas, composite, monkeypatch,
):
    """The bytes uploaded must equal the contiguous source slice —
    if the slice were taken with the wrong stride, this would fail."""
    recorded: dict = {}
    _patch_gl(monkeypatch, recorded)
    canvas._texture = 1  # noqa: SLF001
    canvas._pending_damage = DamageRect(x=5, y=3, w=8, h=4)  # noqa: SLF001
    canvas._upload_texture(composite)  # noqa: SLF001
    try:
        pixels = recorded["sub"][0][8]
        expected = np.ascontiguousarray(composite[3:7, 5:13, :]).tobytes()
        assert pixels == expected
    finally:
        canvas.deleteLater()


def test_sub_region_upload_clipped_to_image_bounds(
    canvas, composite, monkeypatch,
):
    """Damage rects past the image edge get clipped first; the
    upload then sees only the in-bounds portion."""
    recorded: dict = {}
    _patch_gl(monkeypatch, recorded)
    canvas._texture = 1  # noqa: SLF001
    # 100×100 damage starting at (60, 40) overflows a 64×48 image.
    canvas._pending_damage = DamageRect(x=60, y=40, w=100, h=100)  # noqa: SLF001
    canvas._upload_texture(composite)  # noqa: SLF001
    try:
        if "sub" in recorded:
            args = recorded["sub"][0]
            x, y, w, h = args[2], args[3], args[4], args[5]
            assert x + w <= 64
            assert y + h <= 48
            assert len(args[8]) == w * h * 4
        else:
            # Clipped result might cover the whole image → full upload.
            assert "full" in recorded
    finally:
        canvas.deleteLater()
