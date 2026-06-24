"""Smoke tests for the Tone Equalizer dialog (effect tested in test_tone_equalizer)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.tone_equalizer_dialog import ToneEqualizerDialog, open_tone_equalizer


def _dialog():
    return ToneEqualizerDialog(SimpleNamespace(), "sample.png")


class TestToneEqualizerDialog:
    def test_title_and_zone_count(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Tone Equalizer"
        assert len(dlg._zones) == 5
        assert all(slider.value() == 0 for slider in dlg._zones)
        assert dlg._smoothing.value() == 12

    def test_zone_slider_range(self, qapp):
        dlg = _dialog()
        assert (dlg._zones[0].minimum(), dlg._zones[0].maximum()) == (-400, 400)


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_tone_equalizer(viewer)  # NOSONAR
