"""System-tray entry for the desktop-pet overlay.

A small wrapper around :class:`QSystemTrayIcon` that lets the user
toggle the pet window from the taskbar / menu-bar tray. Created by
the main window during startup and handed the workspace so its
actions can flip the workspace's check-state. Single-instance per
application — there's only one pet, so there's only one tray icon.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

if TYPE_CHECKING:
    from Imervue.desktop_pet.pet_workspace import PetWorkspace

logger = logging.getLogger("Imervue.desktop_pet.tray_icon")


class PetTrayIcon(QObject):
    """Owns the QSystemTrayIcon + its menu; routes activations
    back to the workspace.

    Subclassing :class:`QObject` rather than :class:`QSystemTrayIcon`
    so tests can construct the tray helper without spinning up a
    real platform tray (which segfaults on Linux CI without an
    X server)."""

    def __init__(self, workspace: PetWorkspace, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._tray = self._build_tray()

    @staticmethod
    def is_available() -> bool:
        """Wraps the static availability check so callers can skip
        construction on platforms without a tray (some Wayland
        sessions, headless CI). Treats a missing tray as a
        non-error — the workspace still works without it."""
        return bool(QSystemTrayIcon.isSystemTrayAvailable())

    # ---- internals ---------------------------------------------

    def _build_tray(self) -> QSystemTrayIcon:
        icon = self._fallback_icon()
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("Imervue Desktop Pet")
        menu = QMenu()

        self._show_action = QAction("Show pet", menu, checkable=True)
        self._show_action.toggled.connect(self._on_show_toggled)
        menu.addAction(self._show_action)

        self._click_through_action = QAction(
            "Click-through", menu, checkable=True,
        )
        self._click_through_action.toggled.connect(self._on_click_through_toggled)
        menu.addAction(self._click_through_action)

        menu.addSeparator()
        open_action = QAction("Open puppet…", menu)
        open_action.triggered.connect(self._on_open_puppet)
        menu.addAction(open_action)

        menu.addSeparator()
        quit_pet_action = QAction("Hide pet", menu)
        quit_pet_action.triggered.connect(self._on_hide_pet)
        menu.addAction(quit_pet_action)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        return tray

    def _fallback_icon(self) -> QIcon:
        """Use the application's style ``SP_ComputerIcon`` when
        the project doesn't ship a dedicated tray icon. Keeps the
        tray visible without bundling a new asset."""
        app = QApplication.instance()
        if app is None:
            return QIcon()
        style = app.style()
        if style is None:
            return QIcon()
        return style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    # ---- workspace bridging ------------------------------------

    def sync_visibility(self, visible: bool) -> None:
        """Workspace calls this when the pet window's visibility
        changes externally (e.g. user toggled the in-tab checkbox)
        so the tray's checkable ``Show pet`` stays in sync."""
        self._show_action.blockSignals(True)
        try:
            self._show_action.setChecked(bool(visible))
        finally:
            self._show_action.blockSignals(False)

    def sync_click_through(self, enabled: bool) -> None:
        self._click_through_action.blockSignals(True)
        try:
            self._click_through_action.setChecked(bool(enabled))
        finally:
            self._click_through_action.blockSignals(False)

    # ---- slots -------------------------------------------------

    def _on_show_toggled(self, checked: bool) -> None:
        window = self._workspace._ensure_pet_window()   # noqa: SLF001
        if checked:
            window.show()
        else:
            window.hide()

    def _on_click_through_toggled(self, checked: bool) -> None:
        window = self._workspace._ensure_pet_window()   # noqa: SLF001
        window.set_click_through(bool(checked))

    def _on_open_puppet(self) -> None:   # pragma: no cover - Qt UI
        self._workspace._on_open_puppet()   # noqa: SLF001

    def _on_hide_pet(self) -> None:
        if self._workspace.pet_window() is not None:
            self._workspace.pet_window().hide()

    def _on_tray_activated(   # pragma: no cover - Qt UI
        self, reason: QSystemTrayIcon.ActivationReason,
    ) -> None:
        # Left click toggles visibility. Right click is handled by
        # ``setContextMenu`` automatically.
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_action.toggle()
