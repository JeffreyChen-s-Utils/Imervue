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

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPixmap, QKeyEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def array_to_qimage(arr: np.ndarray) -> QImage:
    """Copy an RGB or RGBA uint8 ndarray into a fresh QImage.

    ``.copy()`` detaches the QImage from the numpy buffer so it stays valid
    after the source array is freed (the viewer recycles its deep-zoom arrays
    on navigation). Raises ``ValueError`` for unsupported channel counts.
    """
    if arr.ndim != 3 or arr.shape[2] not in (3, 4):
        raise ValueError(f"expected HxWx3 or HxWx4 array, got shape {arr.shape}")
    contiguous = np.ascontiguousarray(arr)
    height, width = contiguous.shape[:2]
    fmt = (
        QImage.Format.Format_RGBA8888 if contiguous.shape[2] == 4
        else QImage.Format.Format_RGB888
    )
    qimg = QImage(contiguous.data, width, height, contiguous.strides[0], fmt)
    return qimg.copy()


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

    def set_array(self, arr: np.ndarray | None) -> None:
        """Display an in-memory RGB(A) array — the viewer's edited result."""
        if arr is None:
            self.set_image(None)
            return
        self.setStyleSheet("background-color: #000;")
        self._pixmap = QPixmap.fromImage(array_to_qimage(arr))
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

    def __init__(self, main_window: ImervueMainWindow):
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

    def set_array(self, arr) -> None:
        self._panel.set_array(arr)

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

    def __init__(self, main_window: ImervueMainWindow):
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
        self._window = win
        # Seed with the currently-shown edited image, if any.
        self._mirror_current()

        # Hook into deep-zoom display so the mirror shows the same edited
        # result the main viewer shows (not the raw file on disk).
        self._prev_on_displayed = mw.viewer.on_deep_zoom_displayed
        mw.viewer.on_deep_zoom_displayed = self._on_deep_zoom_array
        if hasattr(mw, "toast"):
            lang = language_wrapper.language_word_dict
            mw.toast.info(
                lang.get("multi_monitor_opened",
                         "Secondary display opened — Ctrl+Shift+M to close")
            )

    def _mirror_current(self) -> None:
        """Show whatever the viewer currently has loaded (or 'No image')."""
        if self._window is None:
            return
        deep_zoom = getattr(self._main_window.viewer, "deep_zoom", None)
        if deep_zoom is not None:
            self._window.set_array(deep_zoom.levels[0])
        else:
            self._window.set_image(None)

    def _on_closed(self) -> None:
        # Restore the original deep-zoom-display hook
        mw = self._main_window
        with contextlib.suppress(AttributeError):
            mw.viewer.on_deep_zoom_displayed = self._prev_on_displayed
        self._window = None

    def _on_deep_zoom_array(self, arr) -> None:
        # Forward to any previously-registered hook first, then mirror.
        with contextlib.suppress(Exception):
            if self._prev_on_displayed is not None:
                self._prev_on_displayed(arr)
        if self._window is not None:
            self._window.set_array(arr)
