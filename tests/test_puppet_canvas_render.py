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


def _square(drawable_id, box, color, **extra):
    """A one-quad drawable over *box* ``(x0, y0, x1, y1)`` with a solid-colour texture."""
    import io

    from PIL import Image

    from Imervue.puppet.document import Drawable
    x0, y0, x1, y1 = box
    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), color).save(buf, format="PNG")
    drawable = Drawable(id=drawable_id, texture=f"textures/{drawable_id}.png",
                        vertices=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)], indices=[0, 1, 2, 0, 2, 3],
                        uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], **extra)
    return drawable, buf.getvalue()


def _red_columns(pixels: np.ndarray) -> np.ndarray:
    red = (pixels[..., 0] > 200) & (pixels[..., 1] < 60) & (pixels[..., 2] < 60)
    columns = np.where(red)[1]
    assert columns.size, "the clipped drawable was not drawn at all"
    return columns


def test_clip_masks_clip_on_screen_and_off_screen(qapp):
    """A clipped drawable shows only inside its (invisible) mask, in the widget and off-screen.

    Off-screen, the framebuffer lacked a stencil buffer, so nothing was clipped;
    on NVIDIA's 616 driver a ``glClear`` of the stencil dropped every later draw of
    the frame, so clipped drawables vanished on screen too.
    """
    from PySide6.QtTest import QTest

    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.document import PuppetDocument

    doc = PuppetDocument(size=(100, 100))
    mask, mask_png = _square("mask", (40, 0, 60, 100), (0, 0, 255, 255), draw_order=0, visible=False)
    red, red_png = _square("red", (0, 0, 100, 100), (255, 0, 0, 255), draw_order=1, clip_mask="mask")
    doc.drawables = [mask, red]
    doc.textures = {mask.texture: mask_png, red.texture: red_png}
    canvas = PuppetCanvas()
    try:
        canvas.resize(100, 100)
        canvas.show()
        assert QTest.qWaitForWindowExposed(canvas)
        canvas.load_document(doc)
        offscreen = _rgba(canvas.render_offscreen_puppet(100, 100))
        canvas.repaint()
        qapp.processEvents()
        on_screen = _rgba(canvas.grabFramebuffer())
        assert _red_columns(offscreen).min() >= 38 and _red_columns(offscreen).max() <= 61
        # The widget fits the document with its own zoom and pan, so only the band's width is known:
        # the mask's fifth of the document, not all of it.
        columns = _red_columns(on_screen)
        assert columns.max() - columns.min() + 1 <= 0.3 * on_screen.shape[1]
    finally:
        canvas.close()
        canvas.deleteLater()
