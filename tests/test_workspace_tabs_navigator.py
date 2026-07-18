"""TabManagerMixin._rebind_canvas_signals must move the navigator -> canvas
wiring to the newly-active tab.

The navigator zoom/fit signals were connected once to the first tab's canvas and
never moved, so after switching paint tabs the navigator drove the wrong (still
background) canvas. Driven on the mixin method with fake QObject canvases — no
PaintCanvas (QOpenGLWidget) — so this runs on headless CI.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal

from Imervue.paint.workspace_tabs import TabManagerMixin


class _FakeCanvas(QObject):
    hover_changed = Signal()
    image_loaded = Signal()
    zoom_changed = Signal(float)
    document_changed = Signal()

    def __init__(self):
        super().__init__()
        self.zoom_args: list[float] = []
        self.resets = 0

    def set_zoom(self, value):
        self.zoom_args.append(value)

    def reset_view(self):
        self.resets += 1


class _FakeNavigator(QObject):
    zoom_changed = Signal(float)
    fit_requested = Signal()

    def set_zoom(self, value):
        pass


def _fake_workspace(navigator):
    return SimpleNamespace(
        _navigator_dock=navigator,
        _on_hover_changed=lambda *a: None,
        _on_image_loaded=lambda *a: None,
        _on_zoom_changed_refresh_cursor=lambda *a: None,
        _on_document_changed=lambda *a: None,
    )


def _wire_initial(navigator, canvas, workspace):
    """Reproduce what paint_workspace._wire_canvas_signals does for the first
    canvas: both directions of the navigator/canvas links."""
    navigator.zoom_changed.connect(canvas.set_zoom)
    navigator.fit_requested.connect(canvas.reset_view)
    canvas.hover_changed.connect(workspace._on_hover_changed)
    canvas.image_loaded.connect(workspace._on_image_loaded)
    canvas.zoom_changed.connect(navigator.set_zoom)
    canvas.zoom_changed.connect(workspace._on_zoom_changed_refresh_cursor)
    canvas.document_changed.connect(workspace._on_document_changed)


def test_rebind_moves_navigator_to_new_canvas(qapp):
    nav = _FakeNavigator()
    old = _FakeCanvas()
    new = _FakeCanvas()
    ws = _fake_workspace(nav)
    _wire_initial(nav, old, ws)

    TabManagerMixin._rebind_canvas_signals(ws, old, new)

    nav.zoom_changed.emit(2.5)
    nav.fit_requested.emit()

    assert new.zoom_args == [2.5]   # navigator now drives the new tab
    assert new.resets == 1
    assert old.zoom_args == []      # and no longer the old tab
    assert old.resets == 0


def test_rebind_from_none_only_connects_new(qapp):
    """First bind (old_canvas is None) just wires the new canvas without a
    disconnect attempt."""
    nav = _FakeNavigator()
    new = _FakeCanvas()
    ws = _fake_workspace(nav)

    TabManagerMixin._rebind_canvas_signals(ws, None, new)

    nav.zoom_changed.emit(3.0)
    nav.fit_requested.emit()
    assert new.zoom_args == [3.0]
    assert new.resets == 1
