"""Smoke tests for the Graduated Density dialog (effect tested in test_graduated_density)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.graduated_density_dialog import (
    GraduatedDensityDialog,
    open_graduated_density,
    tint_multiplier,
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



class TestTint:
    """The filter could tint the graded side; the dialog never offered it."""

    def test_the_tint_starts_off_and_its_colour_follows_the_box(self, qapp):
        dlg = _dialog()
        try:
            assert not dlg._tint_check.isChecked()  # noqa: SLF001
            assert not dlg._tint_color.isEnabled()  # noqa: SLF001
            dlg._tint_check.setChecked(True)  # noqa: SLF001
            assert dlg._tint_color.isEnabled()  # noqa: SLF001
            assert dlg._tint_color.rgb() == (204, 230, 255)  # noqa: SLF001
        finally:
            dlg.deleteLater()

    def test_no_tint_when_the_box_is_off(self):
        assert tint_multiplier(False, (204, 230, 255)) is None

    def test_the_colour_becomes_a_per_channel_multiplier(self):
        assert tint_multiplier(True, (255, 0, 51)) == (1.0, 0.0, 0.2)

    def test_the_chosen_tint_reaches_the_filter(self, qapp, monkeypatch):
        from Imervue.gui import graduated_density_dialog as mod
        seen = {}

        class _Worker:
            def __init__(self, _path, effect, _out):
                seen["effect"] = effect
                self.done = type("Sig", (), {"connect": lambda _s, _f: None})()

            def start(self):
                pass

        def fake_filter(_arr, *args):
            seen["args"] = args

        monkeypatch.setattr(mod, "EffectWorker", _Worker)
        monkeypatch.setattr(mod, "apply_graduated_density", fake_filter)
        dlg = _dialog()
        try:
            dlg._tint_check.setChecked(True)  # noqa: SLF001
            dlg._tint_color.set_rgb((255, 128, 0))  # noqa: SLF001
            dlg._commit()  # noqa: SLF001
            seen["effect"]("pixels")
            assert seen["args"][-1] == (1.0, 128 / 255, 0.0)
        finally:
            # The stand-in never ran, so there is no thread for the teardown to stop.
            dlg._worker = None  # noqa: SLF001
            dlg.deleteLater()
