"""
EXIF 元資料編輯對話框
Edit a handful of EXIF text fields and save them back to the file.

The reading, encoding and writing live in :mod:`Imervue.image.exif_fields`:
a JPEG is edited through Pillow alone (only its EXIF segment is rewritten), a
WebP needs ``piexif``, and other formats get a read-only explanation.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox,
)

from Imervue.image.exif_fields import (
    EDITABLE_FIELDS, can_edit, load_exif, read_fields, save_fields,
)
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


logger = logging.getLogger("Imervue.exif_editor")

_GPS_IFD = 0x8825


class ExifEditorDialog(QDialog):
    """Edit the description / artist / copyright / camera / comment tags of one file."""

    def __init__(self, main_gui: GPUImageView, path: str):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._path = path

        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("exif_editor_title", "Edit EXIF Metadata"))
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        self._fields: dict[int, QLineEdit] = {}
        if not can_edit(path):
            self._build_unsupported_ui(layout, lang)
            return

        exif = self._load_exif(path)
        layout.addWidget(self._build_fields_group(lang, read_fields(exif)))
        self._append_gps_label(layout, exif)
        layout.addLayout(self._build_button_row(lang))

    def _build_unsupported_ui(self, layout, lang) -> None:
        layout.addWidget(QLabel(
            lang.get(
                "exif_editor_unsupported",
                "EXIF can be edited in JPEG files (WebP files need the piexif package).",
            )
        ))
        close_btn = QPushButton(lang.get("exif_editor_close", "Close"))
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

    @staticmethod
    def _load_exif(path: str) -> Image.Exif:
        try:
            return load_exif(path)
        except IMAGE_READ_ERRORS:
            logger.warning("Could not read EXIF of %s", path, exc_info=True)
            return Image.Exif()

    def _build_fields_group(self, lang, values: dict[int, str]) -> QGroupBox:
        form = QFormLayout()
        for field in EDITABLE_FIELDS:
            edit = QLineEdit(values.get(field.tag, ""))
            self._fields[field.tag] = edit
            form.addRow(lang.get(field.label_key, field.label) + ":", edit)
        grp = QGroupBox(lang.get("exif_editor_fields", "Metadata Fields"))
        grp.setLayout(form)
        return grp

    @staticmethod
    def _append_gps_label(layout, exif: Image.Exif) -> None:
        gps = exif.get_ifd(_GPS_IFD)
        if not gps:
            return
        gps_label = QLabel(f"GPS: {len(gps)} tag(s) present")
        gps_label.setStyleSheet("color: #888;")
        layout.addWidget(gps_label)

    def _build_button_row(self, lang) -> QHBoxLayout:
        btn_row = QHBoxLayout()
        save_btn = QPushButton(lang.get("exif_editor_save", "Save"))
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton(lang.get("exif_editor_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        return btn_row

    def _save(self):
        main_window = self._gui.main_window
        values = {tag: edit.text() for tag, edit in self._fields.items()}
        try:
            save_fields(self._path, values)
        # Pillow's EXIF writer and piexif fail in open-ended ways on a bad value:
        # struct.error for an out-of-range number, KeyError / TypeError for an
        # odd tag, on top of the ValueError / OSError of a malformed or locked file.
        except Exception as e:  # noqa: BLE001 - EXIF encoders raise open-ended types
            logger.warning("EXIF save failed for %s", self._path, exc_info=True)
            if hasattr(main_window, "toast"):
                lang = language_wrapper.language_word_dict
                main_window.toast.error(
                    lang.get("exif_save_failed", "EXIF save failed: {error}").format(error=e))
            return

        if hasattr(main_window, "toast"):
            main_window.toast.success(
                language_wrapper.language_word_dict.get("exif_editor_saved", "EXIF saved!")
            )
        # 更新 sidebar
        if hasattr(main_window, "exif_sidebar"):
            main_window.exif_sidebar.update_info(self._path)
        self.accept()


def open_exif_editor(main_gui: GPUImageView):
    """Open the EXIF editor on the image the viewer is showing."""
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return
    path = images[main_gui.current_index]
    dlg = ExifEditorDialog(main_gui, path)
    dlg.exec()
