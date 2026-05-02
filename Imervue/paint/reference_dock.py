"""Reference window — pinned image dock with independent pan / zoom.

A small floating dock that shows one reference image at a time,
independent of the main canvas. The user can:

* **Open** — pick a file via a button; the image is read once and
  rendered as a QPixmap.
* **Zoom** — wheel-scroll over the panel changes the displayed scale
  (clamped to a sensible range so the image never disappears).
* **Pan** — middle-click + drag, or just left-click drag, repositions
  the image in its viewport.
* **Clear** — drops the image so the dock is empty again.

The dock is intentionally lightweight (Pillow + QPixmap) so it
doesn't touch the heavy GPUImageView code path; a future revision
can promote this to a true GL view if performance becomes an issue
for very large reference photos.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

REFERENCE_MIN_SCALE = 0.1
REFERENCE_MAX_SCALE = 8.0
REFERENCE_DEFAULT_SCALE = 1.0
WHEEL_STEP_FACTOR = 1.15   # one wheel notch = 15 % zoom step


class _ReferenceView(QLabel):
    """QLabel host for the reference image with pan + wheel-zoom.

    Splitting the view out of the dock body keeps the dock a thin
    layout shell; the view is reusable from a future detached
    floating window.
    """

    scale_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._scale = REFERENCE_DEFAULT_SCALE
        self._pan_origin: QPoint | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(64, 64)
        self.setStyleSheet("background-color: #2a2a2a;")
        self.setMouseTracking(True)

    def set_image(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        if pixmap is None:
            self.clear()
            return
        self._refresh()

    def has_image(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    def scale_factor(self) -> float:
        return self._scale

    def set_scale(self, scale: float) -> None:
        new_scale = max(
            REFERENCE_MIN_SCALE, min(REFERENCE_MAX_SCALE, float(scale)),
        )
        if new_scale == self._scale:
            return
        self._scale = new_scale
        self._refresh()
        self.scale_changed.emit(self._scale)

    def reset_view(self) -> None:
        self.set_scale(REFERENCE_DEFAULT_SCALE)

    # ---- paint -----------------------------------------------------------

    def _refresh(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            self.clear()
            return
        w = max(1, int(round(self._pixmap.width() * self._scale)))
        h = max(1, int(round(self._pixmap.height() * self._scale)))
        scaled = self._pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.resize(w, h)

    # ---- input -----------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if not self.has_image():
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = WHEEL_STEP_FACTOR if delta > 0 else (1.0 / WHEEL_STEP_FACTOR)
        self.set_scale(self._scale * factor)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.MiddleButton,
        ):
            self._pan_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._pan_origin is None:
            return
        # Walk up to the QScrollArea ancestor and shift its scrollbars
        # by the delta — produces a "drag the image around" feel.
        scroll = self.parent()
        while scroll is not None and not isinstance(scroll, QScrollArea):
            scroll = scroll.parent()
        if scroll is None:
            return
        current = event.position().toPoint()
        delta = current - self._pan_origin
        h_bar = scroll.horizontalScrollBar()
        v_bar = scroll.verticalScrollBar()
        h_bar.setValue(h_bar.value() - delta.x())
        v_bar.setValue(v_bar.value() - delta.y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._pan_origin is not None:
            self._pan_origin = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ReferenceDock(QDockWidget):
    """Dock containing a single :class:`_ReferenceView` plus controls."""

    image_loaded = Signal(str)   # absolute path or "" when cleared

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(
            lang.get("paint_dock_reference", "Reference"),
            parent,
        )
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)

        # Toolbar row — open / clear / fit-100% buttons.
        controls = QHBoxLayout()
        self._open_btn = QPushButton(lang.get(
            "paint_reference_open", "Open…",
        ))
        self._open_btn.clicked.connect(self._on_open_clicked)
        controls.addWidget(self._open_btn)
        self._clear_btn = QPushButton(lang.get(
            "paint_reference_clear", "Clear",
        ))
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        controls.addWidget(self._clear_btn)
        self._reset_btn = QPushButton(lang.get(
            "paint_reference_reset_zoom", "100%",
        ))
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        controls.addWidget(self._reset_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._view = _ReferenceView()
        self._scroll.setWidget(self._view)
        layout.addWidget(self._scroll, stretch=1)

        self.setWidget(body)

    # ---- public API -----------------------------------------------------

    def load_image_from_path(self, path: str | Path) -> bool:
        """Load and display ``path``. Returns ``True`` on success."""
        try:
            from PIL import Image
            with Image.open(str(path)) as img:
                rgba = img.convert("RGBA")
                w, h = rgba.size
                qimg = QImage(
                    rgba.tobytes(), w, h, w * 4,
                    QImage.Format.Format_RGBA8888,
                )
        except (OSError, ValueError):
            return False
        self._view.set_image(QPixmap.fromImage(qimg.copy()))
        self.image_loaded.emit(str(path))
        return True

    def clear_image(self) -> None:
        self._view.set_image(None)
        self.image_loaded.emit("")

    def has_image(self) -> bool:
        return self._view.has_image()

    def view(self) -> _ReferenceView:
        return self._view

    # ---- slot handlers --------------------------------------------------

    def _on_open_clicked(self) -> None:  # pragma: no cover - QFileDialog
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("paint_reference_open", "Open reference image"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)",
        )
        if path:
            self.load_image_from_path(path)

    def _on_clear_clicked(self) -> None:
        self.clear_image()

    def _on_reset_clicked(self) -> None:
        self._view.reset_view()
