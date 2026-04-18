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
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
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
        with Image.open(path) as im:
            im = im.convert("RGBA")
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

    def __init__(self, main_gui: "GPUImageView"):
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
        assert self._overlay_arrs is not None
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
        assert self._diff_arrs is not None
        gain = self._diff_slider.value() / 100.0
        a, b = self._diff_arrs
        diff = compute_difference(a, b, gain)
        self._diff_label.set_qimage(_ndarray_to_qimage(diff))


def open_compare_dialog(main_gui: "GPUImageView") -> None:
    dlg = CompareDialog(main_gui)
    dlg.exec()
