"""``GPUImageView.paintGL`` gives up quietly on a torn-down GL context only.

A queued paint can arrive after the context is gone; ``glClear`` then raises
``GLError`` and the frame is abandoned with native painting closed. Any other
error propagates. Driven unbound with a fake painter, so no GL widget is built.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from OpenGL.error import GLError

from Imervue.gpu_image_view import gpu_image_view as mod
from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class _Painter:
    log: list[str] = []

    def __init__(self, _widget):
        pass

    def beginNativePainting(self):  # noqa: N802 - mirrors Qt's camelCase API
        self.log.append("begin")

    def endNativePainting(self):  # noqa: N802 - mirrors Qt's camelCase API
        self.log.append("end")


class _LiveContext:
    @staticmethod
    def currentContext():  # noqa: N802 - mirrors Qt's camelCase API
        return object()


@pytest.fixture
def painter(monkeypatch):
    _Painter.log = []
    monkeypatch.setattr(mod, "QPainter", _Painter)
    monkeypatch.setattr("PySide6.QtGui.QOpenGLContext", _LiveContext)
    return _Painter


def _raise(exc):
    def _fail(*_args):
        raise exc
    return _fail


def test_torn_down_context_abandons_the_frame(painter, monkeypatch):
    monkeypatch.setattr(mod, "glClear", _raise(GLError(1282, None)))
    GPUImageView.paintGL(SimpleNamespace())
    assert painter.log == ["begin", "end"]


def test_unexpected_clear_error_propagates(painter, monkeypatch):
    monkeypatch.setattr(mod, "glClear", _raise(TypeError("bad mask")))
    with pytest.raises(TypeError):
        GPUImageView.paintGL(SimpleNamespace())
