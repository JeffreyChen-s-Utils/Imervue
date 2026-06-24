"""Smoke tests for the Defringe dialog (pure effect tested in test_defringe)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.defringe_dialog import DefringeDialog, open_defringe


def _dialog():
    return DefringeDialog(SimpleNamespace(), "sample.png")


class TestDefringeDialog:
    def test_title_and_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Defringe"
        assert dlg._amount.value() == 100
        assert (dlg._threshold.minimum(), dlg._threshold.maximum()) == (1, 100)
        assert dlg._threshold.value() == 10

    def test_hue_selector_options(self, qapp):
        dlg = _dialog()
        items = [dlg._hue.itemText(i) for i in range(dlg._hue.count())]
        assert items == ["purple", "green", "all"]


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_defringe(viewer)  # NOSONAR
