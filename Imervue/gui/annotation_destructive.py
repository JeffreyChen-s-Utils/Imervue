"""Mosaic and blur annotations of the annotation canvas.

These effects are destructive, so drawing one opens a strength dialog with a
live preview placed away from the annotation, and committing bakes the
effect into the base image as an undoable command. ``AnnotationCanvas``
mixes these methods in.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageFilter
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.gui.annotation_models import KIND_BLUR, KIND_MOSAIC, Annotation, bake
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.qimage_convert import pil_to_qimage

if TYPE_CHECKING:
    from Imervue.gui.annotation_canvas import AnnotationCanvas


class _BakeDestructiveCommand(QUndoCommand):
    """Destructively bake a mosaic/blur region into the canvas base image.

    We snapshot the full PIL image on both sides so undo/redo can swap
    them. Mosaic/blur annotations aren't kept as Annotation objects after
    this command runs — they're burned into the pixels, just like a save
    would do. The save-to-disk step still happens separately via the
    Save button, so the user can still bail out by closing without saving.
    """

    def __init__(
        self,
        canvas: AnnotationCanvas,
        old_img: Image.Image,
        new_img: Image.Image,
        text: str = "Apply mosaic/blur",
    ):
        super().__init__(text)
        self._canvas = canvas
        self._old = old_img
        self._new = new_img

    def redo(self):
        self._canvas._set_base_image(self._new)

    def undo(self):
        self._canvas._set_base_image(self._old)


class AnnotationDestructiveMixin:
    """Mosaic and blur strength prompt and commit of the annotation canvas."""

    def _prompt_destructive_strength(self, ann: Annotation) -> bool:
        """Ask the user for mosaic block size / blur radius with a live
        preview of the effect painted on the canvas.
        """
        cfg = self._destructive_prompt_config(ann)
        if cfg is None:
            return True
        title, label_text, minv, maxv = cfg
        initial = (self._last_block_size if ann.kind == KIND_MOSAIC
                   else self._last_blur_radius)
        self._drawing = ann  # keep dashed-outline preview visible during dialog
        dlg, slider, spin = self._build_strength_dialog(title, label_text, minv, maxv, initial)
        self._wire_strength_signals(slider, spin, ann, initial)
        dlg.adjustSize()
        self._position_dialog_away_from_ann(dlg, ann)
        try:
            result = dlg.exec()
        finally:
            self._drawing = None
            self._preview_qimg = None
            self._preview_rect_image = None
            self.update()
        if result != QDialog.DialogCode.Accepted:
            return False
        self._commit_destructive(ann)
        return True

    @staticmethod
    def _destructive_prompt_config(
        ann: Annotation,
    ) -> tuple[str, str, int, int] | None:
        lang = language_wrapper.language_word_dict
        if ann.kind == KIND_MOSAIC:
            return (
                lang.get("annotation_mosaic_prompt_title", "Mosaic strength"),
                lang.get("annotation_mosaic_prompt_label", "Block size (pixels):"),
                2, 200,
            )
        if ann.kind == KIND_BLUR:
            return (
                lang.get("annotation_blur_prompt_title", "Blur strength"),
                lang.get("annotation_blur_prompt_label", "Gaussian radius (pixels):"),
                1, 200,
            )
        return None

    def _build_strength_dialog(
        self, title: str, label_text: str, minv: int, maxv: int, initial: int
    ) -> tuple[QDialog, QSlider, QSpinBox]:
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(label_text))
        row = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal, dlg)
        slider.setRange(minv, maxv)
        slider.setValue(initial)
        spin = QSpinBox(dlg)
        spin.setRange(minv, maxv)
        spin.setValue(initial)
        row.addWidget(slider, 1)
        row.addWidget(spin)
        layout.addLayout(row)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dlg,
        )
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addWidget(bbox)
        return dlg, slider, spin

    def _wire_strength_signals(
        self, slider: QSlider, spin: QSpinBox, ann: Annotation, initial: int,
    ) -> None:
        def apply_value(val: int) -> None:
            if ann.kind == KIND_MOSAIC:
                ann.block_size = int(val)
            else:
                ann.blur_radius = int(val)
            self._update_destructive_preview(ann)

        def on_slider(v: int) -> None:
            spin.blockSignals(True)
            spin.setValue(v)
            spin.blockSignals(False)
            apply_value(v)

        def on_spin(v: int) -> None:
            slider.blockSignals(True)
            slider.setValue(v)
            slider.blockSignals(False)
            apply_value(v)

        slider.valueChanged.connect(on_slider)
        spin.valueChanged.connect(on_spin)
        apply_value(initial)

    def _commit_destructive(self, ann: Annotation) -> None:
        if ann.kind == KIND_MOSAIC:
            self._last_block_size = ann.block_size
        else:
            self._last_blur_radius = ann.blur_radius
        old_img = self._base
        new_img = bake(self._base, [ann])
        cmd = _BakeDestructiveCommand(self, old_img, new_img, text=ann.kind)
        self._undo_stack.push(cmd)

    def _update_destructive_preview(self, ann: Annotation) -> None:
        """Bake mosaic/blur on the annotation's region and store it as a
        QImage the paintEvent draws over the base. Called live while the
        strength-dialog slider moves.
        """
        x, y, w, h = ann.normalized_rect()
        # Clamp to image bounds — users can rubber-band past the edge.
        x = max(0, x)
        y = max(0, y)
        w = max(1, min(self._base.width - x, w))
        h = max(1, min(self._base.height - y, h))
        if w <= 0 or h <= 0:
            self._preview_qimg = None
            self._preview_rect_image = None
            self.update()
            return
        region = self._base.crop((x, y, x + w, y + h))
        if ann.kind == KIND_MOSAIC:
            block = max(2, ann.block_size)
            small = region.resize(
                (max(1, w // block), max(1, h // block)),
                resample=Image.Resampling.BILINEAR,
            )
            out = small.resize((w, h), resample=Image.Resampling.NEAREST)
        elif ann.kind == KIND_BLUR:
            out = region.filter(
                ImageFilter.GaussianBlur(radius=max(1, ann.blur_radius))
            )
        else:
            return
        self._preview_qimg = pil_to_qimage(out)
        self._preview_rect_image = (x, y, w, h)
        self.update()

    def _position_dialog_away_from_ann(self, dlg: QDialog, ann: Annotation) -> None:
        """Move ``dlg`` so it doesn't overlap the annotation's screen rect.

        Tries right → left → below → above. Falls back to clamping inside
        the available screen area so the dialog is never off-screen.
        """
        x1, y1, x2, y2 = ann.bounding_box()
        tl_local = self._image_to_screen(x1, y1)
        br_local = self._image_to_screen(x2, y2)
        tl_global = self.mapToGlobal(QPoint(int(tl_local.x()), int(tl_local.y())))
        br_global = self.mapToGlobal(QPoint(int(br_local.x()), int(br_local.y())))
        ann_rect = QRect(tl_global, br_global).normalized()

        size = dlg.sizeHint()
        dw = max(size.width(), 280)
        dh = max(size.height(), 120)
        gap = 16

        screen = self.screen()
        avail = screen.availableGeometry() if screen is not None else QRect(0, 0, 4096, 4096)

        candidates = [
            # right
            QPoint(ann_rect.right() + gap, ann_rect.top()),
            # left
            QPoint(ann_rect.left() - dw - gap, ann_rect.top()),
            # below
            QPoint(ann_rect.left(), ann_rect.bottom() + gap),
            # above
            QPoint(ann_rect.left(), ann_rect.top() - dh - gap),
        ]
        chosen = None
        for p in candidates:
            r = QRect(p, QSize(dw, dh))
            if avail.contains(r):
                chosen = p
                break
        if chosen is None:
            # Last resort: clamp the first candidate into the screen.
            p = candidates[0]
            cx = max(avail.left(), min(p.x(), avail.right() - dw))
            cy = max(avail.top(), min(p.y(), avail.bottom() - dh))
            chosen = QPoint(cx, cy)
        dlg.move(chosen)
