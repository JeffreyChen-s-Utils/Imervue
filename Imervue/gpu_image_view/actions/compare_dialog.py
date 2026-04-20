"""
圖片比對對話框
Compare Images — side-by-side (2/4), overlay (alpha), and difference modes.

- Side-by-side: 2 or 4 tiles rendered in a grid, each auto-scaled.
- Overlay: two images stacked with a blend slider (0 = only A, 100 = only B).
- Difference: per-pixel abs(A - B), gain-boosted so subtle changes stand out.

All modes reuse ``_SyncLabel`` as the display surface so we can extend them
with synced zoom/pan later without touching the mode code.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QWidget,
    QSizePolicy, QTabWidget, QSlider, QMessageBox,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class _ImageLabel(QLabel):
    """QLabel that keeps a source QPixmap and re-scales on resize."""

    def __init__(self, path: str | None = None):
        super().__init__()
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)
        self.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        if path:
            self.load(path)

    def load(self, path: str) -> None:
        self._pixmap = QPixmap(path)
        self._update_scaled()

    def set_qimage(self, qimg: QImage) -> None:
        self._pixmap = QPixmap.fromImage(qimg)
        self._update_scaled()

    def _update_scaled(self) -> None:
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled()


class _SplitLabel(QWidget):
    """A/B split viewer: left half is image A, right half is image B.

    The vertical divider is draggable — click or drag anywhere on the widget
    to move it. Both images are rendered scaled-to-fit using A's aspect
    ratio so the two halves always align on the same pixel grid.
    """

    split_changed = Signal(float)

    def __init__(self):
        super().__init__()
        self._pm_a: QPixmap | None = None
        self._pm_b: QPixmap | None = None
        self._split: float = 0.5
        self._dragging = False
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self.setMinimumSize(200, 200)
        self.setAutoFillBackground(True)
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setMouseTracking(True)

    # --- Public API ---
    def set_pair(self, a_path: str, b_path: str) -> None:
        self._pm_a = QPixmap(a_path)
        self._pm_b = QPixmap(b_path)
        self.update()

    def set_split(self, fraction: float) -> None:
        new_value = max(0.0, min(1.0, float(fraction)))
        if new_value == self._split:
            return
        self._split = new_value
        self.update()
        self.split_changed.emit(new_value)

    def split(self) -> float:
        return self._split

    # --- Paint ---
    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(26, 26, 26))
        if self._pm_a is None or self._pm_b is None:
            return
        if self._pm_a.isNull() or self._pm_b.isNull():
            return

        scaled_a = self._pm_a.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled_b = self._pm_b.scaled(
            scaled_a.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x_off = (self.width() - scaled_a.width()) // 2
        y_off = (self.height() - scaled_a.height()) // 2
        split_x = int(self.width() * self._split)

        painter.setClipRect(0, 0, split_x, self.height())
        painter.drawPixmap(x_off, y_off, scaled_a)
        painter.setClipRect(split_x, 0, self.width() - split_x, self.height())
        painter.drawPixmap(x_off, y_off, scaled_b)
        painter.setClipping(False)
        _draw_split_handle(painter, split_x, self.height())

    # --- Mouse ---
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._set_from_event(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._set_from_event(event)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _set_from_event(self, event: QMouseEvent) -> None:
        self.set_split(event.position().x() / max(1, self.width()))


def _draw_split_handle(painter: QPainter, split_x: int, height: int) -> None:
    """Paint the divider line plus a pill-shaped grab handle at its midpoint."""
    painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
    painter.drawLine(split_x, 0, split_x, height)
    painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
    painter.setBrush(QColor(255, 255, 255, 220))
    cy = height / 2.0
    painter.drawEllipse(QPointF(split_x, cy), 10.0, 10.0)


# ===========================
# Image math helpers
# ===========================

def _load_rgba_array(path: str, max_edge: int = 2048) -> np.ndarray | None:
    """Load an image and return it as an RGBA uint8 ndarray, downscaled if huge.

    We cap the long edge at ``max_edge`` so overlay/difference operations stay
    fast on very large source images — the compare UI itself never shows more
    than ~1000 px on screen anyway.
    """
    try:
        with Image.open(path) as src:
            im = src.convert("RGBA")
            w, h = im.size
            long_edge = max(w, h)
            if long_edge > max_edge:
                scale = max_edge / long_edge
                im = im.resize(
                    (int(w * scale), int(h * scale)),
                    Image.Resampling.LANCZOS,
                )
            return np.asarray(im, dtype=np.uint8)
    except Exception:
        return None


def _match_sizes(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Resize ``b`` to match ``a``'s shape via PIL's high-quality Lanczos."""
    if a.shape == b.shape:
        return a, b
    target_h, target_w = a.shape[:2]
    im_b = Image.fromarray(b, mode="RGBA").resize(
        (target_w, target_h), Image.Resampling.LANCZOS,
    )
    return a, np.asarray(im_b, dtype=np.uint8)


def compute_overlay(a: np.ndarray, b: np.ndarray, alpha: float) -> np.ndarray:
    """Blend ``a`` and ``b`` by alpha (0 → a, 1 → b), ignoring alpha channels."""
    a, b = _match_sizes(a, b)
    alpha = float(max(0.0, min(1.0, alpha)))
    out = a.astype(np.float32) * (1.0 - alpha) + b.astype(np.float32) * alpha
    result = np.clip(out, 0, 255).astype(np.uint8)
    # Force opaque alpha — the overlay is a preview, not a transparent asset
    result[..., 3] = 255
    return result


def compute_difference(a: np.ndarray, b: np.ndarray, gain: float = 1.0) -> np.ndarray:
    """Per-pixel |a - b| on RGB, scaled by ``gain`` and clipped to [0, 255]."""
    a, b = _match_sizes(a, b)
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))[:, :, :3]
    scaled = np.clip(diff.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    # Build a solid-alpha RGBA image for QImage consumption
    h, w, _ = scaled.shape
    out = np.empty((h, w, 4), dtype=np.uint8)
    out[..., :3] = scaled
    out[..., 3] = 255
    return out


def _ndarray_to_qimage(arr: np.ndarray) -> QImage:
    """Copy an RGBA ndarray into a fresh QImage (safe against Python GC)."""
    h, w, _ = arr.shape
    # RGBA → QImage.Format_RGBA8888 lays out bytes the same way
    qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return qimg.copy()


# ===========================
# Dialog
# ===========================

class CompareDialog(QDialog):

    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui.main_window)
        self._main_gui = main_gui
        self._lang = language_wrapper.language_word_dict

        self.setWindowTitle(self._lang.get("compare_title", "Compare Images"))
        self.resize(1280, 820)

        root = QHBoxLayout(self)

        # ===== Left panel — picker + mode buttons =====
        left = QVBoxLayout()

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for path in main_gui.model.images:
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._list.addItem(item)
        left.addWidget(self._list)

        # Quick buttons: Side-by-side 2 / 4
        sbs_row = QHBoxLayout()
        btn_2 = QPushButton(self._lang.get("compare_2", "Side-by-side (2)"))
        btn_2.clicked.connect(lambda: self._run_side_by_side(2))
        sbs_row.addWidget(btn_2)
        btn_4 = QPushButton(self._lang.get("compare_4", "Side-by-side (4)"))
        btn_4.clicked.connect(lambda: self._run_side_by_side(4))
        sbs_row.addWidget(btn_4)
        left.addLayout(sbs_row)

        # Overlay / Difference (both need exactly 2 selections)
        btn_overlay = QPushButton(self._lang.get("compare_overlay", "Overlay (2)"))
        btn_overlay.clicked.connect(self._run_overlay)
        left.addWidget(btn_overlay)

        btn_diff = QPushButton(self._lang.get("compare_difference", "Difference (2)"))
        btn_diff.clicked.connect(self._run_difference)
        left.addWidget(btn_diff)

        btn_split = QPushButton(self._lang.get("compare_split", "A|B Split (2)"))
        btn_split.clicked.connect(self._run_split)
        left.addWidget(btn_split)

        root.addLayout(left, stretch=1)

        # ===== Right — tabbed display =====
        self._tabs = QTabWidget()
        root.addWidget(self._tabs, stretch=3)

        self._sbs_widget = QWidget()
        self._sbs_layout = QGridLayout(self._sbs_widget)
        self._sbs_layout.setSpacing(4)
        self._tabs.addTab(self._sbs_widget, self._lang.get("compare_tab_sbs", "Side-by-side"))
        self._sbs_labels: list[_ImageLabel] = []

        # Overlay tab
        self._overlay_widget = QWidget()
        overlay_layout = QVBoxLayout(self._overlay_widget)
        self._overlay_label = _ImageLabel()
        overlay_layout.addWidget(self._overlay_label, stretch=1)
        self._overlay_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlay_slider.setRange(0, 100)
        self._overlay_slider.setValue(50)
        self._overlay_slider.valueChanged.connect(self._on_overlay_slider)
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("A"))
        slider_row.addWidget(self._overlay_slider, stretch=1)
        slider_row.addWidget(QLabel("B"))
        overlay_layout.addLayout(slider_row)
        self._tabs.addTab(self._overlay_widget, self._lang.get("compare_tab_overlay", "Overlay"))
        self._overlay_arrs: tuple[np.ndarray, np.ndarray] | None = None

        # Difference tab
        self._diff_widget = QWidget()
        diff_layout = QVBoxLayout(self._diff_widget)
        self._diff_label = _ImageLabel()
        diff_layout.addWidget(self._diff_label, stretch=1)
        self._diff_slider = QSlider(Qt.Orientation.Horizontal)
        self._diff_slider.setRange(10, 2000)  # 0.10× … 20× gain
        self._diff_slider.setValue(100)
        self._diff_slider.valueChanged.connect(self._on_diff_slider)
        gain_row = QHBoxLayout()
        gain_row.addWidget(QLabel(self._lang.get("compare_gain", "Gain")))
        gain_row.addWidget(self._diff_slider, stretch=1)
        self._diff_gain_label = QLabel("1.0×")
        gain_row.addWidget(self._diff_gain_label)
        diff_layout.addLayout(gain_row)
        self._tabs.addTab(self._diff_widget, self._lang.get("compare_tab_difference", "Difference"))
        self._diff_arrs: tuple[np.ndarray, np.ndarray] | None = None

        # Split tab — Before/After divider
        self._split_widget = QWidget()
        split_layout = QVBoxLayout(self._split_widget)
        self._split_label = _SplitLabel()
        split_layout.addWidget(self._split_label, stretch=1)
        self._split_slider = QSlider(Qt.Orientation.Horizontal)
        self._split_slider.setRange(0, 100)
        self._split_slider.setValue(50)
        self._split_slider.valueChanged.connect(self._on_split_slider)
        self._split_label.split_changed.connect(self._on_split_widget_changed)
        split_slider_row = QHBoxLayout()
        split_slider_row.addWidget(QLabel("A"))
        split_slider_row.addWidget(self._split_slider, stretch=1)
        split_slider_row.addWidget(QLabel("B"))
        split_layout.addLayout(split_slider_row)
        self._tabs.addTab(
            self._split_widget,
            self._lang.get("compare_tab_split", "A|B Split"),
        )

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _selected_paths(self) -> list[str]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._list.selectedItems()
        ]

    def _warn(self, msg_key: str, fallback: str) -> None:
        QMessageBox.information(
            self,
            self._lang.get("compare_title", "Compare Images"),
            self._lang.get(msg_key, fallback),
        )

    def _load_pair(self) -> tuple[np.ndarray, np.ndarray] | None:
        paths = self._selected_paths()
        if len(paths) != 2:
            self._warn("compare_need_two", "Select exactly 2 images.")
            return None
        a = _load_rgba_array(paths[0])
        b = _load_rgba_array(paths[1])
        if a is None or b is None:
            self._warn("compare_load_failed", "Failed to load one of the images.")
            return None
        return a, b

    # -----------------------------------------------------------------
    # Mode handlers
    # -----------------------------------------------------------------
    def _run_side_by_side(self, count: int) -> None:
        paths = self._selected_paths()
        if len(paths) < count:
            self._warn(
                "compare_need_n",
                "Select at least {n} images.",
            )
            return
        paths = paths[:count]

        # Clear previous labels
        for lbl in self._sbs_labels:
            self._sbs_layout.removeWidget(lbl)
            lbl.deleteLater()
        self._sbs_labels.clear()

        rows, cols = (1, 2) if count == 2 else (2, 2)
        for i, p in enumerate(paths):
            r, c = divmod(i, cols)
            lbl = _ImageLabel(p)
            self._sbs_layout.addWidget(lbl, r, c)
            self._sbs_labels.append(lbl)

        self._tabs.setCurrentWidget(self._sbs_widget)

    def _run_overlay(self) -> None:
        pair = self._load_pair()
        if pair is None:
            return
        self._overlay_arrs = pair
        self._refresh_overlay()
        self._tabs.setCurrentWidget(self._overlay_widget)

    def _on_overlay_slider(self, _val: int) -> None:
        if self._overlay_arrs is not None:
            self._refresh_overlay()

    def _refresh_overlay(self) -> None:
        if self._overlay_arrs is None:
            return
        alpha = self._overlay_slider.value() / 100.0
        a, b = self._overlay_arrs
        blended = compute_overlay(a, b, alpha)
        self._overlay_label.set_qimage(_ndarray_to_qimage(blended))

    def _run_difference(self) -> None:
        pair = self._load_pair()
        if pair is None:
            return
        self._diff_arrs = pair
        self._refresh_difference()
        self._tabs.setCurrentWidget(self._diff_widget)

    def _on_diff_slider(self, val: int) -> None:
        gain = val / 100.0
        self._diff_gain_label.setText(f"{gain:.1f}\u00d7")
        if self._diff_arrs is not None:
            self._refresh_difference()

    def _refresh_difference(self) -> None:
        if self._diff_arrs is None:
            return
        gain = self._diff_slider.value() / 100.0
        a, b = self._diff_arrs
        diff = compute_difference(a, b, gain)
        self._diff_label.set_qimage(_ndarray_to_qimage(diff))

    def _run_split(self) -> None:
        paths = self._selected_paths()
        if len(paths) != 2:
            self._warn("compare_need_two", "Select exactly 2 images.")
            return
        self._split_label.set_pair(paths[0], paths[1])
        self._split_slider.blockSignals(True)
        self._split_slider.setValue(int(self._split_label.split() * 100))
        self._split_slider.blockSignals(False)
        self._tabs.setCurrentWidget(self._split_widget)

    def _on_split_slider(self, val: int) -> None:
        self._split_label.set_split(val / 100.0)

    def _on_split_widget_changed(self, fraction: float) -> None:
        self._split_slider.blockSignals(True)
        self._split_slider.setValue(int(round(fraction * 100)))
        self._split_slider.blockSignals(False)


def open_compare_dialog(main_gui: GPUImageView) -> None:
    dlg = CompareDialog(main_gui)
    dlg.exec()
