"""Smoke tests for the Emboss dialog (pure effect tested in test_emboss)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.emboss_dialog import EmbossDialog, open_emboss


def _dialog():
    return EmbossDialog(SimpleNamespace(), "sample.png")


class TestEmbossDialog:
    def test_title_and_slider_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Emboss"
        assert (dlg._azimuth.minimum(), dlg._azimuth.maximum()) == (0, 360)
        assert dlg._azimuth.value() == 135
        assert dlg._elevation.value() == 45
        assert dlg._depth.value() == 10
        assert dlg._grayscale.isChecked() is True


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_emboss(viewer)  # NOSONAR
