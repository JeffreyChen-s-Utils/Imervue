"""End-to-end render of a real rig through the canvas drawing mixin.

``canvas_render.PuppetCanvasRenderMixin`` holds the GL drawing (drawables,
stencil clipping, texture upload with premultiplied alpha, checker backdrop).
Unit tests cover its pure helper; this renders the bundled example rig so the
GL path itself runs with a document loaded. Needs a real GL context, so it is
skipped on headless CI like every other ``QOpenGLWidget`` test.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from _qt_skip import pytestmark  # noqa: E402,F401

_RIG = Path(__file__).resolve().parents[1] / "examples" / "puppet" / "vivian.puppet"


@pytest.fixture(scope="module")
def shown_canvas(qapp):
    """One shown canvas with the example rig, shared by the module (the rig is ~21 MB)."""
    from PySide6.QtTest import QTest

    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.document_io import load_puppet

    if not _RIG.is_file():
        pytest.skip("example rig not present")
    canvas = PuppetCanvas()
    canvas.resize(240, 320)
    canvas.show()
    assert QTest.qWaitForWindowExposed(canvas)
    canvas.load_document(load_puppet(_RIG))
    yield canvas
    canvas.close()
    canvas.deleteLater()


def _rgba(image) -> np.ndarray:
    image = image.convertToFormat(image.Format.Format_RGBA8888)
    buffer = image.constBits()
    return np.frombuffer(buffer, np.uint8).reshape(image.height(), image.width(), 4).copy()


def test_offscreen_render_draws_the_character(shown_canvas):
    image = shown_canvas.render_offscreen_puppet(240, 320)
    assert image is not None
    pixels = _rgba(image)
    opaque = int((pixels[..., 3] > 0).sum())
    # The character covers a good part of the frame, and the background
    # (transparent by default) is still around it.
    assert 0.05 * pixels.shape[0] * pixels.shape[1] < opaque < pixels.shape[0] * pixels.shape[1]


def test_widget_frame_has_the_checker_backdrop_and_the_character(shown_canvas, qapp):
    shown_canvas.repaint()
    qapp.processEvents()
    pixels = _rgba(shown_canvas.grabFramebuffer())
    assert (pixels[..., 3] == 255).all()          # backdrop fills the frame
    assert len(np.unique(pixels.reshape(-1, 4), axis=0)) > 50   # more than a flat fill


def test_textures_are_cached_after_a_render(shown_canvas):
    shown_canvas.render_offscreen_puppet(120, 160)
    assert shown_canvas._texture_cache  # noqa: SLF001
