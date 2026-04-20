"""
Face detection dialog.

Runs OpenCV's Haar frontal-face cascade on the current image, shows the
detected regions over a scaled preview, and lets the user rename each
face. Names persist into ``Recipe.extra['face_tags']`` so they survive
across sessions without a dedicated sidecar format.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.face_detection import (
    FaceTag,
    detect_faces,
    face_tags_from_dict_list,
    face_tags_to_dict_list,
)
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.face_detection_dialog")

_PREVIEW_MAX = 720


class _FacePreview(QWidget):
    def __init__(self, pixmap: QPixmap, image_size: tuple[int, int], parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._image_size = image_size
        self._tags: list[FaceTag] = []
        self._selected: int | None = None
        self.setFixedSize(pixmap.size())

    def set_tags(self, tags: list[FaceTag]) -> None:
        self._tags = list(tags)
        self.update()

    def set_selected(self, idx: int | None) -> None:
        self._selected = idx
        self.update()

    def _scale(self) -> tuple[float, float]:
        iw, ih = self._image_size
        return self.width() / max(1, iw), self.height() / max(1, ih)

    def paintEvent(self, event):  # noqa: N802 - Qt override
        _ = event
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        sx, sy = self._scale()
        for i, t in enumerate(self._tags):
            color = QColor(255, 200, 40) if i == self._selected else QColor(50, 220, 120)
            pen = QPen(color, 2)
            painter.setPen(pen)
            rect = QRectF(t.x * sx, t.y * sy, t.w * sx, t.h * sy)
            painter.drawRect(rect)
            if t.name:
                painter.drawText(rect.bottomLeft(), t.name)


class FaceDetectionDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("face_title", "Face Detection"))

        self._recipe = recipe_store.get_for_path(path) or Recipe()

        pixmap, img_size, arr = self._build_preview(path)
        self._preview = _FacePreview(pixmap, img_size)

        # Start with any tags already stored in the recipe.
        existing = self._recipe.extra.get("face_tags") or []
        self._tags: list[FaceTag] = face_tags_from_dict_list(
            existing if isinstance(existing, list) else [],
        )

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemChanged.connect(self._on_item_renamed)

        self._detect_btn = QPushButton(lang.get("face_detect", "Detect Faces"))
        self._detect_btn.clicked.connect(lambda: self._detect(arr))
        self._clear_btn = QPushButton(lang.get("face_clear", "Clear"))
        self._clear_btn.clicked.connect(self._clear_tags)
        self._remove_btn = QPushButton(lang.get("face_remove", "Remove selected"))
        self._remove_btn.clicked.connect(self._remove_selected)

        self._status = QLabel()

        side = QVBoxLayout()
        side.addWidget(self._detect_btn)
        side.addWidget(self._clear_btn)
        side.addWidget(self._remove_btn)
        side.addWidget(QLabel(lang.get("face_list", "Detected faces (double-click to rename):")))
        side.addWidget(self._list, 1)
        side.addWidget(self._status)

        body = QHBoxLayout()
        body.addWidget(self._preview, 1, Qt.AlignmentFlag.AlignCenter)
        body.addLayout(side, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            lang.get("face_save", "Save"))
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "face_hint",
            "Runs OpenCV's Haar cascade. Names are saved with the recipe.",
        )))
        layout.addLayout(body, 1)
        layout.addWidget(buttons)

        self._refresh()

    @staticmethod
    def _build_preview(path: str):
        img = Image.open(path).convert("RGB")
        w, h = img.size
        scale = min(1.0, _PREVIEW_MAX / max(w, h))
        pw, ph = max(1, int(w * scale)), max(1, int(h * scale))
        preview = img.resize((pw, ph), Image.Resampling.LANCZOS)
        parr = np.asarray(preview)
        qimg = QImage(
            parr.data, pw, ph, parr.strides[0], QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(qimg.copy())
        full_arr = np.asarray(img)
        return pixmap, (w, h), full_arr

    def _refresh(self) -> None:
        self._preview.set_tags(self._tags)
        self._list.blockSignals(True)
        self._list.clear()
        for t in self._tags:
            item = QListWidgetItem(t.name or "")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _detect(self, rgb_arr: np.ndarray) -> None:
        lang = language_wrapper.language_word_dict
        try:
            detections = detect_faces(rgb_arr)
        except (ValueError, RuntimeError, ImportError) as exc:
            self._status.setText(str(exc))
            logger.warning("Face detection failed: %s", exc)
            return
        # Merge: keep any existing named tags, add new detections.
        existing_boxes = {(t.x, t.y, t.w, t.h) for t in self._tags}
        for d in detections:
            if (d.x, d.y, d.w, d.h) not in existing_boxes:
                self._tags.append(d)
        self._status.setText(
            lang.get("face_found", "{n} face(s) total.").format(n=len(self._tags)),
        )
        self._refresh()

    def _clear_tags(self) -> None:
        self._tags = []
        self._refresh()

    def _remove_selected(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._tags):
            del self._tags[row]
            self._refresh()

    def _on_row_changed(self, row: int) -> None:
        self._preview.set_selected(row if 0 <= row < len(self._tags) else None)

    def _on_item_renamed(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if 0 <= row < len(self._tags):
            t = self._tags[row]
            self._tags[row] = FaceTag(x=t.x, y=t.y, w=t.w, h=t.h, name=item.text())
            self._preview.set_tags(self._tags)

    def _commit(self) -> None:
        old = self._recipe
        new = Recipe(**{
            f.name: getattr(old, f.name) for f in old.__dataclass_fields__.values()
        })
        new.extra = dict(old.extra)
        new.extra["face_tags"] = face_tags_to_dict_list(self._tags)
        recipe_store.set_for_path(self._path, new)
        self.accept()


def open_face_detection(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    FaceDetectionDialog(viewer, str(path)).exec()
