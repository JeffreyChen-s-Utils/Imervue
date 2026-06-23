"""Smoke tests for the Solarize dialog (pure effect tested in test_solarize)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.solarize_dialog import SolarizeDialog, open_solarize


def _dialog():
    # A bare stub viewer (not a QWidget) makes the dialog use parent=None,
    # which keeps qapp teardown clean.
    return SolarizeDialog(SimpleNamespace(), "sample.png")


class TestSolarizeDialog:
    def test_title_and_slider_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Solarize"
        assert (dlg._threshold.minimum(), dlg._threshold.maximum()) == (0, 100)
        assert dlg._threshold.value() == 50
        assert (dlg._mix.minimum(), dlg._mix.maximum()) == (0, 100)
        assert dlg._mix.value() == 100

    def test_value_labels_track_sliders(self, qapp):
        dlg = _dialog()
        dlg._threshold.setValue(30)
        dlg._mix.setValue(70)
        assert dlg._threshold_label.text() == "30"
        assert dlg._mix_label.text() == "70"


def test_open_guard_no_images_is_noop():
    # No current image → returns without constructing a dialog or raising.
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_solarize(viewer)  # NOSONAR
