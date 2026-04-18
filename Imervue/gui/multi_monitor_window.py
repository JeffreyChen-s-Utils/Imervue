"""
多螢幕檢視視窗
Multi-monitor window — second top-level window that mirrors whichever image
the main viewer is currently focused on, sized to fill a secondary screen.

The main window keeps running independently (tile grid / list / deep zoom)
while this window acts as a passive big-screen display. Toggle with
Ctrl+Shift+M or via the ``MultiMonitorController``.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QPixmap, QKeyEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class _PreviewPanel(QLabel):
    """Full-window scaled pixmap; black background; center-aligned."""

    def __init__(self):
        super().__init__()
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #000;")

    def set_image(self, path: str | None) -> None:
        if path is None or not Path(path).is_file():
            self._pixmap = None
            self.setPixmap(QPixmap())
            self.setText(
                language_wrapper.language_word_dict.get(
                    "multi_monitor_no_image", "No image"
                )
            )
            self.setStyleSheet("background-color: #000; color: #888;")
            return
        pm = QPixmap(path)
        if pm.isNull():
            self._pixmap = None
            return
        self._pixmap = pm
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


class MultiMonitorWindow(QWidget):
    """Frameless, full-screen-on-secondary mirror of the main viewer."""

    closed = Signal()

    def __init__(self, main_window: "ImervueMainWindow"):
        super().__init__()
        self._main_window = main_window
        self.setWindowTitle(
            language_wrapper.language_word_dict.get(
                "multi_monitor_window_title", "Imervue — Secondary Display"
            )
        )
        self.setWindowIcon(main_window.windowIcon())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._panel = _PreviewPanel()
        layout.addWidget(self._panel)

    # -------- Public API --------
    def set_image(self, path: str | None) -> None:
        self._panel.set_image(path)

    def place_on_secondary(self) -> bool:
        """Move the window to a non-primary screen and show maximized.

        Returns True if a secondary screen was found; False otherwise (in
        which case the caller may decide to show it on the primary screen
        anyway).
        """
        screens = QGuiApplication.screens()
        primary = QGuiApplication.primaryScreen()
        for screen in screens:
            if screen is not primary:
                geo = screen.availableGeometry()
                self.setGeometry(geo)
                self.showMaximized()
                return True
        # Fall back to primary screen
        self.showMaximized()
        return False

    # -------- Events --------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class MultiMonitorController:
    """Owns the secondary window and wires it to the main viewer's image changes."""

    def __init__(self, main_window: "ImervueMainWindow"):
        self._main_window = main_window
        self._window: MultiMonitorWindow | None = None

    def toggle(self) -> None:
        if self._window is not None and self._window.isVisible():
            self._window.close()
            return
        self._open()

    def is_open(self) -> bool:
        return self._window is not None and self._window.isVisible()

    def _open(self) -> None:
        mw = self._main_window
        win = MultiMonitorWindow(mw)
        win.closed.connect(self._on_closed)
        win.place_on_secondary()
        # Seed with the currently-shown image
        images = mw.viewer.model.images
        idx = mw.viewer.current_index
        if images and 0 <= idx < len(images):
            win.set_image(images[idx])
        self._window = win

        # Hook into filename-change so image mirroring stays in sync
        self._prev_on_filename = mw.viewer.on_filename_changed
        mw.viewer.on_filename_changed = self._wrap_filename_change
        if hasattr(mw, "toast"):
            lang = language_wrapper.language_word_dict
            mw.toast.info(
                lang.get("multi_monitor_opened",
                         "Secondary display opened — Ctrl+Shift+M to close")
            )

    def _on_closed(self) -> None:
        # Restore the original filename hook
        mw = self._main_window
        try:
            mw.viewer.on_filename_changed = self._prev_on_filename
        except AttributeError:
            pass
        self._window = None

    def _wrap_filename_change(self, name: str) -> None:
        # Forward to the main window's original handler first, then mirror
        try:
            if self._prev_on_filename is not None:
                self._prev_on_filename(name)
        except Exception:
            pass
        if self._window is None:
            return
        images = self._main_window.viewer.model.images
        idx = self._main_window.viewer.current_index
        if images and 0 <= idx < len(images):
            self._window.set_image(images[idx])
