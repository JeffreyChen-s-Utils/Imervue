"""Canonical-pixel resolution preserves optional and replaceable callbacks."""
import pytest
from PIL import Image
from PySide6.QtGui import QUndoStack

from Imervue.gui.annotation_canvas import AnnotationCanvas


@pytest.mark.parametrize("result", [True, False])
def test_injected_resolver_is_lazy_and_can_be_replaced(qapp, result):
    calls = []

    def resolve():
        calls.append("resolve")
        return result

    stack = QUndoStack()
    canvas = AnnotationCanvas(Image.new("RGBA", (2, 2)), stack, full_base_resolver=resolve)
    try:
        assert calls == []
        assert canvas.ensure_full_base() is result
        assert calls == ["resolve"]
        canvas.full_base_resolver = lambda: not result
        assert canvas.ensure_full_base() is not result
        canvas.full_base_resolver = None
        assert canvas.ensure_full_base() is True
    finally:
        canvas.close()
        canvas.deleteLater()


def test_default_resolver_and_callback_failure(qapp):
    stack = QUndoStack()
    canvas = AnnotationCanvas(Image.new("RGBA", (2, 2)), stack)

    def fail():
        raise ValueError("decode failed")

    try:
        assert canvas.ensure_full_base() is True
        canvas.full_base_resolver = fail
        with pytest.raises(ValueError, match="decode failed"):
            canvas.ensure_full_base()
        canvas.full_base_resolver = False
        with pytest.raises(TypeError):
            canvas.ensure_full_base()
    finally:
        canvas.close()
        canvas.deleteLater()
