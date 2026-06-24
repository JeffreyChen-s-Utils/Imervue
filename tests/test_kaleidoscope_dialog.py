"""Smoke tests for the Kaleidoscope dialog (effect tested in test_kaleidoscope)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.kaleidoscope_dialog import KaleidoscopeDialog, open_kaleidoscope


def _dialog():
    return KaleidoscopeDialog(SimpleNamespace(), "sample.png")


class TestKaleidoscopeDialog:
    def test_title_and_slider_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Kaleidoscope"
        assert (dlg._segments.minimum(), dlg._segments.maximum()) == (2, 24)
        assert dlg._segments.value() == 6
        assert dlg._angle.value() == 0


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_kaleidoscope(viewer)  # NOSONAR
