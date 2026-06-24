"""Smoke tests for the Velvia dialog (pure effect tested in test_velvia)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.velvia_dialog import VelviaDialog, open_velvia


def _dialog():
    return VelviaDialog(SimpleNamespace(), "sample.png")


class TestVelviaDialog:
    def test_title_and_slider_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Velvia"
        assert (dlg._strength.minimum(), dlg._strength.maximum()) == (0, 400)
        assert dlg._strength.value() == 100
        assert (dlg._protection.minimum(), dlg._protection.maximum()) == (0, 100)
        assert dlg._protection.value() == 50


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_velvia(viewer)  # NOSONAR
