"""Smoke tests for the Film Negative dialog (pure effect tested in test_film_negative)."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.film_negative_dialog import FilmNegativeDialog, open_film_negative


def _dialog():
    return FilmNegativeDialog(SimpleNamespace(), "sample.png")


class TestFilmNegativeDialog:
    def test_title_and_slider_defaults(self, qapp):
        dlg = _dialog()
        assert dlg.windowTitle() == "Film Negative"
        assert (dlg._gamma.minimum(), dlg._gamma.maximum()) == (10, 600)
        assert dlg._gamma.value() == 100


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_film_negative(viewer)  # NOSONAR
