"""Smoke tests for the Polar Coordinates dialog (effect tested in test_polar)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.polar_dialog import PolarDialog, open_polar


def _dialog():
    return PolarDialog(SimpleNamespace(), "sample.png")


class TestPolarDialog:
    def test_title_and_toggle_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Polar Coordinates"
        assert dlg._to_polar.isChecked() is True
        assert dlg._invert.isChecked() is False


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_polar(viewer)  # NOSONAR
