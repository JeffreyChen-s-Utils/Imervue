"""Save, save-as, clipboard and project-file actions of the annotation editor.

``AnnotationFileActionsMixin`` bakes the annotations into the image and writes
it (atomically, via a ``.tmp`` sibling), copies it to the clipboard, and saves
or loads ``.imervue_annot.json`` projects. It relies on the editor's
``_canvas``, ``_source_path`` and ``_on_saved``.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from Imervue.gui.file_filters import translated_filter
from Imervue.gui.annotation_models import AnnotationProject, bake
from Imervue.image.in_place_save import (
    can_rewrite_in_place, in_place_format, save_over_source,
)
from Imervue.system.atomic_write import replace_atomically
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.qimage_convert import pil_to_qimage

logger = logging.getLogger("Imervue.annotation")

_LOAD_PROJECT_FALLBACK = "Load Project..."
_SAVE_AS_FILTER = "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;TIFF (*.tiff)"


def ask_save_as_path(parent, source_path: str | None) -> str:
    """Ask where to save an annotated image; ``""`` when cancelled.

    The dialog starts in *source_path*'s folder. A name whose extension
    Imervue can't write (``.cr2``, ``.heic``, none) gets ``.png`` appended so
    the bytes match the name.
    """
    start_dir = str(Path(source_path).parent) if source_path else ""
    path, _ = QFileDialog.getSaveFileName(
        parent,
        language_wrapper.language_word_dict.get("annotation_save_as", "Save As..."),
        start_dir,
        _SAVE_AS_FILTER,
    )
    if path and in_place_format(path) is None:
        path += ".png"
    return path


def write_annotated(img: Image.Image, path: str, source_path: str | None) -> None:
    """Save the baked annotated *img* to *path* in one step.

    Over its own source the file keeps its metadata (``save_over_source``);
    a new file is written plainly. Raises what Pillow raises on failure
    (``IMAGE_READ_ERRORS``), and ``ValueError`` for a source that can't be
    written back whole.
    """
    if source_path and _same_file(path, source_path):
        save_over_source(path, img)
        return
    fmt = in_place_format(path) or "PNG"
    out = img.convert("RGB") if fmt == "JPEG" and img.mode not in ("RGB", "L") else img
    kwargs = {"quality": 95} if fmt == "JPEG" else {}
    replace_atomically(path, lambda tmp: out.save(tmp, format=fmt, **kwargs))


def _same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _project_filter(extensions: tuple[str, ...]) -> str:
    return translated_filter(
        "file_filter_annotation_project", "Imervue annotation project", extensions,
    )


class AnnotationFileActionsMixin:
    """File and clipboard actions mixed into ``AnnotationEditorWidget``."""

    def _baked_image(self) -> Image.Image:
        return bake(self._canvas.get_base_pil(), self._canvas.get_annotations())

    def _save(self) -> None:
        # A file that can't be written back whole (camera RAW, HEIC, animated,
        # multi-page) goes to Save As instead of being overwritten.
        if not self._source_path or not can_rewrite_in_place(self._source_path):
            self._save_as()
            return
        self._write(self._source_path)

    def _save_as(self) -> None:
        path = ask_save_as_path(self, self._source_path)
        if path:
            self._write(path)

    def _write(self, path: str) -> None:
        """Save the baked image to *path*, replacing the file in one step.

        A crash mid-save can't leave a half-written file, which matters
        because the source may be open in the main viewer.
        """
        try:
            write_annotated(self._baked_image(), path, self._source_path)
        except IMAGE_READ_ERRORS as exc:
            logger.exception("annotation save failed: %s", path)
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._notify_success(
            language_wrapper.language_word_dict.get("annotation_saved", "Saved")
        )
        if self._on_saved is not None and _same_file(path, self._source_path or ""):
            try:
                self._on_saved(path)
            except Exception:
                logger.exception("on_saved callback raised")

    def _copy_to_clipboard(self) -> None:
        img = self._baked_image()
        qimg = pil_to_qimage(img)
        QApplication.clipboard().setImage(qimg)
        self._notify_success(
            language_wrapper.language_word_dict.get(
                "annotation_copy_success", "Copied to clipboard"
            )
        )

    def _save_project(self) -> None:
        lang = language_wrapper.language_word_dict
        start_dir = str(Path(self._source_path).parent) if self._source_path else ""
        suggested = ""
        if self._source_path:
            suggested = str(
                Path(start_dir) / (Path(self._source_path).stem + ".imervue_annot.json")
            )
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("annotation_save_project", "Save Project..."),
            suggested or start_dir,
            _project_filter(("imervue_annot.json", "json")),
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".imervue_annot.json"
        base = self._canvas.get_base_pil()
        project = AnnotationProject(
            source_path=self._source_path,
            source_size=(base.width, base.height),
            annotations=self._canvas.get_annotations(),
        )
        try:
            project.save(path)
            self._notify_success(
                lang.get("annotation_saved", "Saved")
            )
        except Exception as exc:
            logger.exception("project save failed: %s", path)
            QMessageBox.critical(self, "Error", str(exc))

    def _load_project(self) -> None:
        lang = language_wrapper.language_word_dict
        start_dir = str(Path(self._source_path).parent) if self._source_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("annotation_load_project", _LOAD_PROJECT_FALLBACK),
            start_dir,
            _project_filter(("json",)),
        )
        if not path:
            return
        try:
            project = AnnotationProject.load(path)
        except Exception as exc:
            logger.exception("project load failed: %s", path)
            QMessageBox.critical(self, "Error", str(exc))
            return

        base = self._canvas.get_base_pil()
        if project.source_size not in {(0, 0), (base.width, base.height)}:
            warning = lang.get(
                "annotation_project_size_mismatch",
                "Project was saved against a {pw}x{ph} image; current image "
                "is {cw}x{ch}. Annotation positions may be off.",
            ).format(
                pw=project.source_size[0], ph=project.source_size[1],
                cw=base.width, ch=base.height,
            )
            QMessageBox.warning(
                self,
                lang.get("annotation_load_project", _LOAD_PROJECT_FALLBACK),
                warning,
            )
        self._canvas.set_annotations(project.annotations)

    def _notify_success(self, message: str) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "toast"):
            parent.toast.success(message)
        else:
            logger.info(message)
