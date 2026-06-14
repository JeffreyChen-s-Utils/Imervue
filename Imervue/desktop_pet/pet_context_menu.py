"""Right-click context menu builder for the desktop-pet overlay.

Pulled out of :class:`~Imervue.desktop_pet.pet_window.PetWindow` so
the window stays a coordinator rather than also being a menu factory.
The builder reads the window's live driver / toggle / rig state to
set each action's check-state, and wires every action back to the
window's public setters — so flipping a toggle from the menu is
exactly equivalent to flipping it from the workspace tab.

This is pure Qt-UI assembly with no testable branch logic of its own
(the behaviour it triggers is tested through the window setters), so
it is excluded from coverage like the original inline methods were.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.desktop_pet.pet_window import PetWindow

SIZE_PRESET_ORDER = ("small", "medium", "large")
UNNAMED_KEY = "desktop_pet_unnamed"
UNNAMED_DEFAULT = "(unnamed)"


def build_context_menu(   # pragma: no cover - Qt UI
    window: PetWindow, global_pos: QPoint,
) -> None:
    """Assemble and exec the pet's right-click menu at ``global_pos``."""
    tr = language_wrapper.language_word_dict.get
    menu = QMenu(window)
    hide_action = menu.addAction(tr("desktop_pet_menu_hide", "Hide pet"))
    hide_action.triggered.connect(window.hide)
    menu.addSeparator()
    _build_drivers_submenu(window, menu, tr)
    _build_motions_submenu(window, menu, tr)
    _build_expressions_submenu(window, menu, tr)
    menu.addSeparator()
    _build_toggle_actions(window, menu, tr)
    menu.addSeparator()
    _build_size_submenu(window, menu, tr)
    menu.exec(global_pos)


def _add_driver_action(   # pragma: no cover - Qt UI
    parent_menu: QMenu, label: str, current: bool,
    setter: Callable[[bool], object],
) -> QAction:
    action = parent_menu.addAction(label)
    action.setCheckable(True)
    action.setChecked(current)
    action.triggered.connect(lambda checked: setter(checked))
    return action


def _build_drivers_submenu(   # pragma: no cover - Qt UI
    window: PetWindow, menu: QMenu, tr: Callable[[str, str], str],
) -> None:
    """Live-input toggles. Each driver's "is it running?" state is
    sourced from its own object so the menu's check-state always
    matches the world."""
    drivers_menu = menu.addMenu(tr("desktop_pet_group_drivers", "Live drivers"))
    for key, default, current, setter in window.driver_menu_entries():
        _add_driver_action(drivers_menu, tr(key, default), current, setter)


def _build_motions_submenu(   # pragma: no cover - Qt UI
    window: PetWindow, menu: QMenu, tr: Callable[[str, str], str],
) -> None:
    """Lists every motion in the active rig. Each entry plays that
    motion directly. Disabled when no rig is loaded."""
    motions_menu = menu.addMenu(tr("desktop_pet_menu_play_motion", "Play motion"))
    document = window.document()
    if document is None or not document.motions:
        motions_menu.setEnabled(False)
        return
    unnamed = tr(UNNAMED_KEY, UNNAMED_DEFAULT)
    for motion in document.motions:
        action = motions_menu.addAction(motion.name or unnamed)
        action.triggered.connect(
            lambda _checked=False, m=motion: window.play_motion(m),
        )


def _build_expressions_submenu(   # pragma: no cover - Qt UI
    window: PetWindow, menu: QMenu, tr: Callable[[str, str], str],
) -> None:
    expressions_menu = menu.addMenu(
        tr("desktop_pet_menu_apply_expression", "Apply expression"),
    )
    document = window.document()
    if document is None or not document.expressions:
        expressions_menu.setEnabled(False)
        return
    unnamed = tr(UNNAMED_KEY, UNNAMED_DEFAULT)
    for expression in document.expressions:
        action = expressions_menu.addAction(expression.name or unnamed)
        action.triggered.connect(
            lambda _checked=False, e=expression: window.apply_expression(e.name),
        )


def _build_toggle_actions(   # pragma: no cover - Qt UI
    window: PetWindow, menu: QMenu, tr: Callable[[str, str], str],
) -> None:
    """The five top-level checkable toggles (anchor, click-through,
    on-bottom, fullscreen-hide, speech bubble). Each is wired so the
    user can flip it from the right-click menu as a faster alternative
    to digging through the tab."""
    for key, default, current, setter in window.toggle_menu_entries():
        action = menu.addAction(tr(key, default))
        action.setCheckable(True)
        action.setChecked(current)
        action.triggered.connect(setter)


def _build_size_submenu(   # pragma: no cover - Qt UI
    window: PetWindow, menu: QMenu, tr: Callable[[str, str], str],
) -> None:
    size_menu = menu.addMenu(tr("desktop_pet_menu_size", "Size"))
    size_labels = {
        "small": tr("desktop_pet_size_small", "Small"),
        "medium": tr("desktop_pet_size_medium", "Medium"),
        "large": tr("desktop_pet_size_large", "Large"),
    }
    current = window.current_size_preset()
    for preset in SIZE_PRESET_ORDER:
        action = size_menu.addAction(size_labels[preset])
        action.setCheckable(True)
        action.setChecked(preset == current)
        action.triggered.connect(
            lambda _checked=False, p=preset: window.set_size_preset(p),
        )
