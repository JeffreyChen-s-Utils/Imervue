"""The Desktop Pet's Apply expression entries toggle, checked while on.

An applied expression used to stay until the rig was reloaded. Stand-ins
for the pet and its canvas, no PetWindow (a QOpenGLWidget), so this runs on
headless CI.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QMenu

from Imervue.desktop_pet.pet_context_menu import _build_expressions_submenu
from Imervue.desktop_pet.pet_window import PetWindow


class _Canvas:
    def __init__(self, active=()):
        self.active = list(active)

    def active_expressions(self):
        return list(self.active)

    def add_expression(self, name):
        self.active.append(name)
        return True

    def remove_expression(self, name):
        self.active.remove(name)
        return True


def _tr(_key, fallback):
    return fallback


def test_an_expression_toggles_off_again():
    pet = SimpleNamespace(_canvas=_Canvas())
    PetWindow._apply_expression(pet, "smile")  # noqa: SLF001
    assert pet._canvas.active == ["smile"]  # noqa: SLF001
    PetWindow._apply_expression(pet, "smile")  # noqa: SLF001
    assert pet._canvas.active == []  # noqa: SLF001


def _pet_with(names, active):
    canvas = _Canvas(active)
    applied = []
    document = SimpleNamespace(expressions=[SimpleNamespace(name=n) for n in names])
    return SimpleNamespace(document=lambda: document, canvas=lambda: canvas,
                           apply_expression=applied.append), applied


def test_the_menu_checks_the_active_expressions(qapp):
    pet, applied = _pet_with(["smile", "angry", ""], active=["angry"])
    menu = QMenu()
    try:
        _build_expressions_submenu(pet, menu, _tr)
        entries = menu.actions()[0].menu().actions()
        assert [a.text() for a in entries] == ["smile", "angry", "(unnamed)"]
        assert [a.isCheckable() for a in entries] == [True, True, True]
        assert [a.isChecked() for a in entries] == [False, True, False]
        entries[1].trigger()
        assert applied == ["angry"]
    finally:
        menu.deleteLater()


def test_a_rig_without_expressions_disables_the_submenu(qapp):
    pet, _applied = _pet_with([], active=[])
    menu = QMenu()
    try:
        _build_expressions_submenu(pet, menu, _tr)
        assert not menu.actions()[0].menu().isEnabled()
    finally:
        menu.deleteLater()
