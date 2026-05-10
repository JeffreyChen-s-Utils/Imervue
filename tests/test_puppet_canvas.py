"""Qt-smoke coverage for the PuppetCanvas widget.

Real GL rendering needs a display, which CI doesn't have — these tests
exercise the construction path, document binding, draw-list building,
and the pure-Python view state without forcing a paint cycle.
"""
from __future__ import annotations

from puppet.canvas import PuppetCanvas
from puppet.document import Drawable, PuppetDocument


def _doc_with_one_drawable() -> PuppetDocument:
    doc = PuppetDocument(size=(512, 512))
    doc.textures["textures/x.png"] = b"\x89PNG\r\n\x1a\n"   # not a real PNG, no upload happens
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            indices=[0, 1, 2],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            draw_order=0,
        ),
    ]
    return doc


def test_canvas_constructs_without_document(qapp):
    c = PuppetCanvas()
    try:
        assert c.document() is None
        assert c.zoom_factor() == 1.0
    finally:
        c.deleteLater()


def test_load_document_builds_draw_list(qapp):
    c = PuppetCanvas()
    try:
        doc = _doc_with_one_drawable()
        c.load_document(doc)
        assert c.document() is doc
        assert len(c._draw_list) == 1   # noqa: SLF001
        assert c._draw_list[0].drawable_id == "x"   # noqa: SLF001
    finally:
        c.deleteLater()


def test_load_none_clears_state(qapp):
    c = PuppetCanvas()
    try:
        c.load_document(_doc_with_one_drawable())
        c.load_document(None)
        assert c.document() is None
        assert c._draw_list == []   # noqa: SLF001
    finally:
        c.deleteLater()


def test_load_document_emits_signal(qapp):
    c = PuppetCanvas()
    try:
        captured = []
        c.document_loaded.connect(lambda: captured.append(True))
        c.load_document(_doc_with_one_drawable())
        assert captured == [True]
    finally:
        c.deleteLater()


def test_reset_view_unlocks_user_view(qapp):
    """After programmatic ``reset_view`` the next paint is allowed to
    re-fit the puppet — used when a new document loads or the user hits
    the toolbar's Fit button."""
    c = PuppetCanvas()
    try:
        c.load_document(_doc_with_one_drawable())
        c._user_view_locked = True   # noqa: SLF001
        c.reset_view()
        assert c._user_view_locked is False   # noqa: SLF001
    finally:
        c.deleteLater()
