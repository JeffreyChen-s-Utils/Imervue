"""Multi-view windows — open a second window onto the same document.

The classic "fit-to-window overview alongside zoomed-in detail" UI.
Each view is a thin :class:`SecondaryView` window holding its own
QLabel of the composite; updates ride the workspace's existing
:meth:`PaintWorkspace._refresh_navigator_preview` coalesce timer
so per-stroke cost doesn't grow with the number of open views.

Pure-Qt / no extra dependencies. The window is intentionally
lightweight (no toolbars / no docks) so it stays out of the way of
the main editing window.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

VIEW_MIN_SCALE = 0.05
VIEW_MAX_SCALE = 16.0
VIEW_DEFAULT_SCALE = 1.0
VIEW_ZOOM_STEP = 1.25


class SecondaryView(QMainWindow):
    """Independent window showing the parent workspace's composite.

    The window exposes :meth:`set_composite` so the workspace can
    push fresh frames; the view scales the composite to its current
    zoom level and shows it in a centred QLabel.
    """

    closed = Signal()

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(parent)
        self.setWindowTitle(
            lang.get("paint_secondary_view", "Second View"),
        )
        self.setMinimumSize(320, 240)

        self._scale = VIEW_DEFAULT_SCALE
        self._composite_pixmap: QPixmap | None = None

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)

        controls = QHBoxLayout()
        self._zoom_in_btn = QPushButton(
            lang.get("paint_secondary_view_zoom_in", "+"),
        )
        self._zoom_in_btn.clicked.connect(self.zoom_in)
        controls.addWidget(self._zoom_in_btn)
        self._zoom_out_btn = QPushButton(
            lang.get("paint_secondary_view_zoom_out", "−"),
        )
        self._zoom_out_btn.clicked.connect(self.zoom_out)
        controls.addWidget(self._zoom_out_btn)
        self._reset_btn = QPushButton(
            lang.get("paint_secondary_view_reset_zoom", "100%"),
        )
        self._reset_btn.clicked.connect(self.reset_zoom)
        controls.addWidget(self._reset_btn)
        self._zoom_label = QLabel("100%")
        controls.addWidget(self._zoom_label)
        controls.addStretch(1)
        layout.addLayout(controls)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background-color: #2a2a2a;")
        self._scroll.setWidget(self._image_label)
        layout.addWidget(self._scroll, stretch=1)

        self.setCentralWidget(body)

    # ---- public API -----------------------------------------------------

    def set_composite(self, pixmap: QPixmap | None) -> None:
        self._composite_pixmap = pixmap
        self._refresh_pixmap()

    def scale_factor(self) -> float:
        return self._scale

    def set_scale(self, scale: float) -> None:
        new_scale = max(VIEW_MIN_SCALE, min(VIEW_MAX_SCALE, float(scale)))
        if new_scale == self._scale:
            return
        self._scale = new_scale
        self._refresh_pixmap()
        self._zoom_label.setText(f"{int(round(new_scale * 100))}%")

    def zoom_in(self) -> None:
        self.set_scale(self._scale * VIEW_ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_scale(self._scale / VIEW_ZOOM_STEP)

    def reset_zoom(self) -> None:
        self.set_scale(VIEW_DEFAULT_SCALE)

    # ---- internals ------------------------------------------------------

    def _refresh_pixmap(self) -> None:
        if self._composite_pixmap is None or self._composite_pixmap.isNull():
            self._image_label.clear()
            self._image_label.resize(0, 0)
            return
        w = max(1, int(round(self._composite_pixmap.width() * self._scale)))
        h = max(1, int(round(self._composite_pixmap.height() * self._scale)))
        scaled = self._composite_pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)
        self._image_label.resize(w, h)

    def closeEvent(self, event):  # noqa: N802 - Qt override
        self.closed.emit()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Workspace plumbing helpers — pure Python, callable from tests
# ---------------------------------------------------------------------------


def composite_to_pixmap(composite) -> QPixmap | None:
    """Convert an HxWx4 uint8 numpy buffer into a QPixmap.

    Returns ``None`` for missing / mis-shaped inputs so callers can
    treat the composite as "nothing to push" without inspecting type
    information.
    """
    import numpy as np
    if (
        composite is None
        or not isinstance(composite, np.ndarray)
        or composite.ndim != 3
        or composite.shape[2] != 4
        or composite.dtype != np.uint8
    ):
        return None
    contiguous = np.ascontiguousarray(composite)
    h, w = contiguous.shape[:2]
    qimg = QImage(
        contiguous.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888,
    )
    return QPixmap.fromImage(qimg.copy())
