"""Smoke tests for the Frosted Glass dialog (effect tested in test_frosted_glass)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.frosted_glass_dialog import FrostedGlassDialog, open_frosted_glass


def _dialog():
    return FrostedGlassDialog(SimpleNamespace(), "sample.png")


class TestFrostedGlassDialog:
    def test_title_and_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Frosted Glass"
        assert (dlg._radius.minimum(), dlg._radius.maximum()) == (0, 64)
        assert dlg._radius.value() == 4
        assert (dlg._seed.minimum(), dlg._seed.maximum()) == (0, 9999)


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_frosted_glass(viewer)  # NOSONAR
