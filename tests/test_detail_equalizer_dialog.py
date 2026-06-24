"""Smoke tests for the Detail Equalizer dialog (effect tested in test_detail_equalizer)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.detail_equalizer_dialog import (
    DetailEqualizerDialog,
    open_detail_equalizer,
)


def _dialog():
    return DetailEqualizerDialog(SimpleNamespace(), "sample.png")


class TestDetailEqualizerDialog:
    def test_title_and_band_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Detail Equalizer"
        assert len(dlg._bands) == 4
        # Every band defaults to neutral (1.00 -> raw 100).
        assert all(slider.value() == 100 for slider in dlg._bands)

    def test_band_slider_range(self, qapp):
        dlg = _dialog()
        assert (dlg._bands[0].minimum(), dlg._bands[0].maximum()) == (0, 400)


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_detail_equalizer(viewer)  # NOSONAR
