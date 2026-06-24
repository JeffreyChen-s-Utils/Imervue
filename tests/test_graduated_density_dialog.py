"""Smoke tests for the Graduated Density dialog (effect tested in test_graduated_density)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.graduated_density_dialog import (
    GraduatedDensityDialog,
    open_graduated_density,
)


def _dialog():
    return GraduatedDensityDialog(SimpleNamespace(), "sample.png")


class TestGraduatedDensityDialog:
    def test_title_and_slider_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Graduated Density"
        assert dlg._angle.value() == 0
        assert (dlg._density.minimum(), dlg._density.maximum()) == (-800, 800)
        assert dlg._density.value() == 100
        assert dlg._hardness.value() == 50
        assert (dlg._offset.minimum(), dlg._offset.maximum()) == (-100, 100)
        assert dlg._offset.value() == 0


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_graduated_density(viewer)  # NOSONAR
