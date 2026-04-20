"""
EXIF 元資料編輯對話框
Edit EXIF metadata fields and save back to file using piexif.
Falls back gracefully if piexif is not installed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _try_import_piexif():
    try:
        import piexif
        return piexif
    except ImportError:
        return None


class ExifEditorDialog(QDialog):

    # 可編輯的欄位 (IFD, tag_name, label_key, default_label)
    _EDITABLE = [
        ("0th", "ImageDescription", "exif_edit_description", "Description"),
        ("0th", "Artist", "exif_edit_artist", "Artist"),
        ("0th", "Copyright", "exif_edit_copyright", "Copyright"),
        ("0th", "Make", "exif_edit_make", "Make"),
        ("0th", "Model", "exif_edit_model", "Model"),
        ("Exif", "UserComment", "exif_edit_user_comment", "User Comment"),
    ]

    def __init__(self, main_gui: GPUImageView, path: str):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._path = path

        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("exif_editor_title", "Edit EXIF Metadata"))
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        self._piexif = _try_import_piexif()
        if not self._piexif:
            self._build_missing_piexif_ui(layout, lang)
            return

        self._exif_dict = self._load_exif_dict(path)
        self._fields: dict[tuple[str, str], QLineEdit] = {}
        layout.addWidget(self._build_fields_group(lang))
        self._append_gps_label(layout)
        layout.addLayout(self._build_button_row(lang))

    def _build_missing_piexif_ui(self, layout, lang) -> None:
        layout.addWidget(QLabel(
            lang.get(
                "exif_editor_no_piexif",
                "piexif package is required for EXIF editing.\n"
                "Install with: pip install piexif",
            )
        ))
        close_btn = QPushButton(lang.get("exif_editor_close", "Close"))
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

    def _load_exif_dict(self, path: str) -> dict:
        try:
            return self._piexif.load(path)
        except (ValueError, OSError):
            return {
                "0th": {}, "Exif": {}, "GPS": {},
                "1st": {}, "Interop": {}, "thumbnail": None,
            }

    def _build_fields_group(self, lang) -> QGroupBox:
        form = QFormLayout()
        for ifd_name, tag_name, label_key, default_label in self._EDITABLE:
            edit = QLineEdit()
            self._prefill_field(edit, ifd_name, tag_name)
            self._fields[(ifd_name, tag_name)] = edit
            form.addRow(lang.get(label_key, default_label) + ":", edit)
        grp = QGroupBox(lang.get("exif_editor_fields", "Metadata Fields"))
        grp.setLayout(form)
        return grp

    def _prefill_field(self, edit: QLineEdit, ifd_name: str, tag_name: str) -> None:
        ifd_key = getattr(self._piexif.ImageIFD, tag_name, None) \
            or getattr(self._piexif.ExifIFD, tag_name, None)
        if ifd_key is None:
            return
        raw = self._exif_dict.get(ifd_name, {}).get(ifd_key, b"")
        if isinstance(raw, bytes):
            edit.setText(raw.decode("utf-8", errors="replace"))
        elif isinstance(raw, str):
            edit.setText(raw)

    def _append_gps_label(self, layout) -> None:
        gps = self._exif_dict.get("GPS", {})
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
        piexif = self._piexif
        if not piexif:
            return

        for (ifd_name, tag_name), edit in self._fields.items():
            text = edit.text()
            ifd_key = getattr(piexif.ImageIFD, tag_name, None)
            if ifd_key is None:
                ifd_key = getattr(piexif.ExifIFD, tag_name, None)
            if ifd_key is None:
                continue

            ifd = self._exif_dict.setdefault(ifd_name, {})

            if tag_name == "UserComment":
                # UserComment 需要特殊編碼
                ifd[ifd_key] = piexif.helper.UserComment.dump(text)
            else:
                ifd[ifd_key] = text.encode("utf-8")

        try:
            exif_bytes = piexif.dump(self._exif_dict)
            piexif.insert(exif_bytes, self._path)

            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.success(
                    language_wrapper.language_word_dict.get("exif_editor_saved", "EXIF saved!")
                )
            # 更新 sidebar
            if hasattr(self._gui.main_window, "exif_sidebar"):
                self._gui.main_window.exif_sidebar.update_info(self._path)

            self.accept()
        except Exception as e:
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.error(f"EXIF save failed: {e}")


def open_exif_editor(main_gui: GPUImageView):
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return
    path = images[main_gui.current_index]
    dlg = ExifEditorDialog(main_gui, path)
    dlg.exec()
