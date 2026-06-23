"""Smoke tests for the Glow dialog (pure effect tested in test_glow)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.glow_dialog import GlowDialog, open_glow


def _dialog():
    # Stub viewer (not a QWidget) -> dialog uses parent=None, clean teardown.
    return GlowDialog(SimpleNamespace(), "sample.png")


class TestGlowDialog:
    def test_title_and_slider_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Diffuse Glow"
        assert (dlg._amount.minimum(), dlg._amount.maximum()) == (0, 100)
        assert dlg._amount.value() == 50
        assert (dlg._radius.minimum(), dlg._radius.maximum()) == (1, 100)
        assert dlg._radius.value() == 15
        assert dlg._threshold.value() == 0

    def test_value_labels_track_sliders(self, qapp):
        dlg = _dialog()
        dlg._amount.setValue(80)
        dlg._radius.setValue(25)
        dlg._threshold.setValue(60)
        assert dlg._amount_label.text() == "80"
        assert dlg._radius_label.text() == "25"
        assert dlg._threshold_label.text() == "60"


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_glow(viewer)  # NOSONAR
