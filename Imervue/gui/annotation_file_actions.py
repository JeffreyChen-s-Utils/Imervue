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
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.qimage_convert import pil_to_qimage

logger = logging.getLogger("Imervue.annotation")

_LOAD_PROJECT_FALLBACK = "Load Project..."


def _project_filter(extensions: tuple[str, ...]) -> str:
    return translated_filter(
        "file_filter_annotation_project", "Imervue annotation project", extensions,
    )


class AnnotationFileActionsMixin:
    """File and clipboard actions mixed into ``AnnotationEditorWidget``."""

    def _baked_image(self) -> Image.Image:
        return bake(self._canvas.get_base_pil(), self._canvas.get_annotations())

    def _save(self) -> None:
        if not self._source_path:
            self._save_as()
            return
        self._write(self._source_path)

    def _save_as(self) -> None:
        lang = language_wrapper.language_word_dict
        start_dir = str(Path(self._source_path).parent) if self._source_path else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("annotation_save_as", "Save As..."),
            start_dir,
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;TIFF (*.tiff)",
        )
        if path:
            self._write(path)

    def _write(self, path: str) -> None:
        """Atomically save the baked image to ``path``.

        Writes to a sibling .tmp file then ``os.replace`` to avoid leaving
        a half-written file if the process is interrupted mid-save. This
        also matters because the source path may be open in the main
        viewer — replacing the file in one atomic step is friendlier than
        truncating the original.
        """
        img = self._baked_image()
        ext = Path(path).suffix.lower()
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        # Pass ``format=`` explicitly because the .tmp extension would
        # otherwise stop PIL from inferring the encoder.
        fmt_by_ext = {
            ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
            ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
            ".webp": "WEBP",
        }
        fmt = fmt_by_ext.get(ext, "PNG")
        try:
            if ext in (".jpg", ".jpeg"):
                img.convert("RGB").save(tmp, format="JPEG", quality=95)
            else:
                img.save(tmp, format=fmt)
            os.replace(tmp, target)
            self._notify_success(
                language_wrapper.language_word_dict.get("annotation_saved", "Saved")
            )
            if self._on_saved is not None and str(target) == self._source_path:
                try:
                    self._on_saved(str(target))
                except Exception:
                    logger.exception("on_saved callback raised")
        except Exception as exc:
            logger.exception("annotation save failed: %s", path)
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            QMessageBox.critical(self, "Error", str(exc))

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
