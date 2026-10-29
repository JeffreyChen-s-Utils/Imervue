"""The Modify tab's destructive saves: apply a crop, save annotations, show toasts.

:class:`DevelopCanvasSaveMixin` writes the cropped or annotated full-resolution
image over its source on the owning
:class:`~Imervue.gui.develop_panel.DevelopPanel` (or to a chosen copy when the
format cannot be rewritten in place) and reports the result on a toast parented
to the visible canvas.
"""
from __future__ import annotations

import logging

from PIL import Image

from Imervue.image.in_place_save import can_rewrite_in_place, save_over_source
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.multi_language.language_wrapper import language_wrapper

# Shares the panel's logger so save failures keep reporting under it.
logger = logging.getLogger("Imervue.develop_panel")

_CROP_CANNOT_OVERWRITE = (
    "This file can't be overwritten in place (camera RAW, HEIC, animated or "
    "multi-page). Export the crop instead."
)


class DevelopCanvasSaveMixin:
    """Crop and annotation saves of :class:`DevelopPanel`."""

    def _warn_cannot_overwrite(self) -> None:
        toast = getattr(getattr(self._main_gui, "main_window", None), "toast", None)
        if toast is None:
            return
        toast.info(language_wrapper.language_word_dict.get(
            "modify_crop_cannot_overwrite", _CROP_CANNOT_OVERWRITE))

    @staticmethod
    def _write_over_source(path: str, img: Image.Image) -> bool:
        """Save edited *img* over *path*, keeping its metadata; False when the save failed."""
        try:
            save_over_source(path, img)
        except IMAGE_READ_ERRORS:
            logger.exception("Failed to save the edit over %s", path)
            return False
        return True

    def _apply_crop(self) -> None:
        if self._canvas is None or self._canvas_source_path is None:
            return
        if not self._ensure_full_canvas():
            return
        crop_rect = self._canvas.get_crop_rect()
        if crop_rect is None:
            return
        x, y, w, h = crop_rect
        if w < 2 or h < 2:
            return
        base = self._canvas.get_base_pil()
        cropped = base.crop((x, y, x + w, y + h))
        path = self._canvas_source_path
        if not can_rewrite_in_place(path):
            # RAW, HEIC, animated or multi-page: a save over it would destroy it.
            self._warn_cannot_overwrite()
            return
        if not self._write_over_source(path, cropped):
            return
        self._canvas.clear_crop()
        self._reload_after_overwrite(path, "Viewer reload after crop failed")

    def _toast(self, message: str, level: str = "info") -> None:
        """Show a status toast on the (visible) Modify canvas.

        The shared window toast is parented to the viewer, which is hidden
        while the Modify tab is active, so its notifications wouldn't be seen
        here. Parent our own toast to the canvas instead — a plain widget on
        the active tab — so save feedback is actually visible.
        """
        canvas = self._canvas
        if canvas is None:
            return
        from Imervue.gui.toast import ToastWidget
        if self._canvas_toast is None:
            self._canvas_toast = ToastWidget(canvas)
        self._canvas_toast.show_message(message, level)

    def _save_annotation(self) -> None:
        """Bake annotations into the image and save back to the source file."""
        if self._canvas is None or self._canvas_source_path is None:
            return
        if not self._ensure_full_canvas():
            return
        from Imervue.gui.annotation_models import bake

        path = self._canvas_source_path
        img = bake(self._canvas.get_base_pil(), self._canvas.get_annotations())
        if not can_rewrite_in_place(path):
            # RAW, HEIC, animated or multi-page: a save over it would destroy
            # it, so the annotated image goes to a new file instead.
            self._save_annotation_copy(path, img)
            return
        if not self._write_over_source(path, img):
            self._toast(
                language_wrapper.language_word_dict.get(
                    "annotation_save_failed", "Save failed"),
                "warning")
            return

        self._reload_after_overwrite(path, "Viewer reload after annotation save failed")

        # Toast AFTER the reload so it isn't torn down with the old canvas.
        self._toast(
            language_wrapper.language_word_dict.get("annotation_saved", "Saved"),
            "success")

    def _save_annotation_copy(self, source_path: str, img: Image.Image) -> None:
        """Save the annotated *img* to a file the user picks, leaving the source as it is."""
        from Imervue.gui.annotation_file_actions import ask_save_as_path, write_annotated

        target = ask_save_as_path(self, source_path)
        if not target:
            return
        lang = language_wrapper.language_word_dict
        try:
            write_annotated(img, target, source_path)
        except IMAGE_READ_ERRORS:
            logger.exception("Failed to save the annotated copy to %s", target)
            self._toast(lang.get("annotation_save_failed", "Save failed"), "warning")
            return
        self._toast(lang.get("annotation_saved", "Saved"), "success")
