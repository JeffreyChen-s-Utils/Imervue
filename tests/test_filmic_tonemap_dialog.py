"""Smoke tests for the Filmic Tone Map dialog (effect tested in test_filmic_tonemap)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.filmic_tonemap_dialog import FilmicTonemapDialog, open_filmic_tonemap


def _dialog():
    return FilmicTonemapDialog(SimpleNamespace(), "sample.png")


class TestFilmicTonemapDialog:
    def test_title_and_slider_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Filmic Tone Map"
        assert dlg._exposure.value() == 0
        assert dlg._white.value() == 400
        assert dlg._contrast.value() == 100
        assert dlg._saturation.value() == 100

    def test_mode_options(self, qapp):
        dlg = _dialog()
        items = [dlg._mode.itemText(i) for i in range(dlg._mode.count())]
        assert items == ["reinhard", "hable"]


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_filmic_tonemap(viewer)  # NOSONAR
