"""Tests for the Desktop Pet's hide-on-fullscreen watch.

The mixin runs on a small QObject stand-in whose show / hide call the same
hooks as ``PetWindow.showEvent`` / ``hideEvent`` - no PetWindow (a
QOpenGLWidget) - so this file runs on headless CI.
"""
from __future__ import annotations

from PySide6.QtCore import QObject

from Imervue.desktop_pet.pet_window_flags import PetWindowFlagsMixin


class _Pet(PetWindowFlagsMixin, QObject):
    """What the fullscreen watch reads, with show / hide wired like the real window."""

    def __init__(self, hide_on_fullscreen=True):
        QObject.__init__(self)
        self._hide_on_fullscreen = hide_on_fullscreen
        self._fullscreen_detector = None
        self._hidden_by_fullscreen = False
        self.visible = False
        self.saved = {}

    def _persist(self, **values):
        self.saved.update(values)

    def isVisible(self):  # noqa: N802 - Qt name
        return self.visible

    def show(self):
        self.visible = True
        self._watch_fullscreen_on_show()

    def hide(self):
        self.visible = False
        self._watch_fullscreen_on_hide()


def _watching(pet):
    detector = pet._fullscreen_detector  # noqa: SLF001
    return detector is not None and detector._timer.isActive()  # noqa: SLF001


def test_the_first_show_watches_when_the_setting_is_on(qapp):
    """The setting defaults to on, but the detector was only built by the checkbox."""
    pet = _Pet()
    pet.show()
    assert _watching(pet)


def test_the_first_show_does_not_watch_when_the_setting_is_off(qapp):
    pet = _Pet(hide_on_fullscreen=False)
    pet.show()
    assert pet._fullscreen_detector is None  # noqa: SLF001


def test_the_pet_comes_back_when_fullscreen_ends(qapp):
    """Hiding stopped the poll, so the end of fullscreen was never seen."""
    pet = _Pet()
    pet.show()
    pet._on_fullscreen_state_changed(True)  # noqa: SLF001
    assert not pet.visible
    assert _watching(pet)
    pet._on_fullscreen_state_changed(False)  # noqa: SLF001
    assert pet.visible
    assert _watching(pet)


def test_hiding_the_pet_yourself_stops_watching(qapp):
    pet = _Pet()
    pet.show()
    pet.hide()
    assert not _watching(pet)


def test_showing_the_pet_during_fullscreen_overrides_the_auto_hide(qapp):
    """Shown by hand while fullscreen, then hidden by hand: it must stay hidden."""
    pet = _Pet()
    pet.show()
    pet._on_fullscreen_state_changed(True)  # noqa: SLF001
    pet.show()
    pet.hide()
    assert not _watching(pet)
    pet._on_fullscreen_state_changed(False)  # noqa: SLF001
    assert not pet.visible


def test_turning_the_setting_on_while_shown_starts_watching(qapp):
    pet = _Pet(hide_on_fullscreen=False)
    pet.show()
    pet.set_hide_on_fullscreen(True)
    assert _watching(pet)
    assert pet.saved == {"hide_on_fullscreen": True}
    pet.set_hide_on_fullscreen(False)
    assert not _watching(pet)
