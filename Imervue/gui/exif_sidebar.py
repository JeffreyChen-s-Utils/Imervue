"""
EXIF 資訊側邊欄
Collapsible sidebar showing EXIF metadata for the current image.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QToolButton,
    QPushButton, QSizePolicy, QFrame,
)

from Imervue.image.info import get_exif_data, get_file_times
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class ExifSidebar(QWidget):
    """可摺疊的 EXIF 資訊面板"""

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__(main_window)
        self._main_window = main_window
        self._collapsed = True

        self.setMaximumWidth(300)
        self.setMinimumWidth(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 摺疊按鈕
        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("\u276f")  # ❯
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(False)
        self._toggle_btn.setFixedWidth(24)
        self._toggle_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._toggle_btn.setStyleSheet(
            "QToolButton { background: #222; color: #aaa; border: none; font-size: 14px; }"
            "QToolButton:checked { background: #333; }"
        )
        self._toggle_btn.clicked.connect(self._toggle)

        # 內容面板
        self._content = QScrollArea()
        self._content.setWidgetResizable(True)
        self._content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content.setStyleSheet("QScrollArea { background: #1e1e1e; border: none; }")
        self._content.setVisible(False)

        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._info_label.setStyleSheet(
            "QLabel { color: #ccc; padding: 8px; font-size: 12px; background: #1e1e1e; }"
        )
        self._info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # 編輯按鈕
        self._edit_btn = QPushButton(
            language_wrapper.language_word_dict.get("exif_edit_button", "Edit EXIF")
        )
        self._edit_btn.setStyleSheet("QPushButton { margin: 4px; }")
        self._edit_btn.clicked.connect(self._open_editor)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._info_label)
        content_layout.addWidget(self._edit_btn)
        content_layout.addStretch()
        self._content.setWidget(content_widget)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        h_layout.addWidget(self._toggle_btn)
        h_layout.addWidget(self._content)

        layout.addLayout(h_layout)

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        self._toggle_btn.setText("\u276e" if not self._collapsed else "\u276f")

        if not self._collapsed:
            self.setMinimumWidth(260)
            self.setMaximumWidth(300)
            self.update_info()
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(24)

    def _open_editor(self):
        from Imervue.gui.exif_editor import open_exif_editor
        open_exif_editor(self._main_window.viewer)

    def update_info(self, path: str | None = None):
        """更新 EXIF 面板內容"""
        if self._collapsed:
            return

        viewer = self._main_window.viewer

        if path is None:
            images = viewer.model.images
            if images and 0 <= viewer.current_index < len(images):
                path = images[viewer.current_index]

        if not path:
            self._info_label.setText("")
            return

        lang = language_wrapper.language_word_dict
        p = Path(path)
        lines = []

        # 基本資訊
        lines.append(f"<b>{lang.get('exif_filename', 'File')}:</b> {p.name}")

        try:
            stat = p.stat()
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            lines.append(f"<b>{lang.get('exif_filesize', 'Size')}:</b> {size_mb} MB")

            ctime, mtime = get_file_times(p)
            if ctime:
                lines.append(f"<b>{lang.get('exif_created', 'Created')}:</b> {ctime}")
            if mtime:
                lines.append(f"<b>{lang.get('exif_modified', 'Modified')}:</b> {mtime}")
        except OSError:
            pass

        lines.append("<hr>")

        # EXIF 資料
        exif = get_exif_data(p)
        if exif:
            _exif_fields = [
                ("DateTimeOriginal", lang.get("exif_taken", "Taken")),
                ("Make", lang.get("exif_make", "Make")),
                ("Model", lang.get("exif_model", "Model")),
                ("LensModel", lang.get("exif_lens", "Lens")),
                ("FocalLength", lang.get("exif_focal", "Focal Length")),
                ("FNumber", lang.get("exif_aperture", "Aperture")),
                ("ExposureTime", lang.get("exif_shutter", "Shutter")),
                ("ISOSpeedRatings", lang.get("exif_iso", "ISO")),
                ("ExposureBiasValue", lang.get("exif_ev", "EV")),
                ("WhiteBalance", lang.get("exif_wb", "White Balance")),
                ("Flash", lang.get("exif_flash", "Flash")),
            ]
            for key, label in _exif_fields:
                val = exif.get(key)
                if val is not None and val != "N/A":
                    lines.append(f"<b>{label}:</b> {val}")

            # 圖片尺寸
            w = exif.get("ExifImageWidth") or exif.get("ImageWidth")
            h = exif.get("ExifImageHeight") or exif.get("ImageLength")
            if w and h:
                lines.append(f"<b>{lang.get('exif_resolution', 'Resolution')}:</b> {w} x {h}")
        else:
            lines.append(f"<i>{lang.get('exif_no_data', 'No EXIF data')}</i>")

        self._info_label.setText("<br>".join(lines))
