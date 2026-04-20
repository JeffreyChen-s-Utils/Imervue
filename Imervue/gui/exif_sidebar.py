"""
EXIF 資訊側邊欄
Collapsible sidebar showing EXIF metadata for the current image.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QToolButton,
    QPushButton, QSizePolicy, QPlainTextEdit,
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

        # 星等評分 — 5 顆可點擊的星，點同一顆會清除
        self._rating_widget = _RatingStars(self._on_rating_clicked)

        # 備註區 — 儲存到 library SQLite index
        self._notes_label = QLabel(
            language_wrapper.language_word_dict.get("notes_title", "Notes")
        )
        self._notes_label.setStyleSheet(
            "QLabel { color: #ddd; padding: 8px 8px 2px 8px;"
            " font-weight: bold; background: #1e1e1e; }"
        )
        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setPlaceholderText(
            language_wrapper.language_word_dict.get(
                "notes_placeholder", "Write notes for this image…"
            )
        )
        self._notes_edit.setFixedHeight(120)
        self._notes_edit.setStyleSheet(
            "QPlainTextEdit { background: #262626; color: #ddd; border: none;"
            " padding: 6px; font-size: 12px; }"
        )
        self._notes_current_path: str | None = None
        self._notes_save_timer = QTimer(self)
        self._notes_save_timer.setSingleShot(True)
        self._notes_save_timer.setInterval(500)
        self._notes_save_timer.timeout.connect(self._flush_note)
        self._notes_edit.textChanged.connect(self._notes_save_timer.start)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._info_label)
        content_layout.addWidget(self._edit_btn)
        content_layout.addWidget(self._rating_widget)
        content_layout.addWidget(self._notes_label)
        content_layout.addWidget(self._notes_edit)
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

        if path is None:
            path = self._current_viewer_path()

        if not path:
            self._info_label.setText("")
            self._load_note_for(None)
            self._rating_widget.bind_path(None)
            return

        self._load_note_for(path)
        self._rating_widget.bind_path(path)
        lang = language_wrapper.language_word_dict
        p = Path(path)
        lines: list[str] = [
            f"<b>{lang.get('exif_filename', 'File')}:</b> {p.name}",
            *self._file_stat_lines(p, lang),
            "<hr>",
            *self._exif_lines(p, lang),
        ]
        self._info_label.setText("<br>".join(lines))

    def _current_viewer_path(self) -> str | None:
        viewer = self._main_window.viewer
        images = viewer.model.images
        if images and 0 <= viewer.current_index < len(images):
            return images[viewer.current_index]
        return None

    @staticmethod
    def _file_stat_lines(p: Path, lang) -> list[str]:
        lines: list[str] = []
        try:
            stat = p.stat()
        except OSError:
            return lines
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        lines.append(f"<b>{lang.get('exif_filesize', 'Size')}:</b> {size_mb} MB")
        ctime, mtime = get_file_times(p)
        if ctime:
            lines.append(f"<b>{lang.get('exif_created', 'Created')}:</b> {ctime}")
        if mtime:
            lines.append(f"<b>{lang.get('exif_modified', 'Modified')}:</b> {mtime}")
        return lines

    @staticmethod
    def _exif_lines(p: Path, lang) -> list[str]:
        exif = get_exif_data(p)
        if not exif:
            return [f"<i>{lang.get('exif_no_data', 'No EXIF data')}</i>"]
        fields = [
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
        lines = [
            f"<b>{label}:</b> {exif[key]}"
            for key, label in fields
            if exif.get(key) not in (None, "N/A")
        ]
        w = exif.get("ExifImageWidth") or exif.get("ImageWidth")
        h = exif.get("ExifImageHeight") or exif.get("ImageLength")
        if w and h:
            lines.append(f"<b>{lang.get('exif_resolution', 'Resolution')}:</b> {w} x {h}")
        return lines

    def _load_note_for(self, path: str | None) -> None:
        """Swap the notes text area to the given path, flushing any pending save first."""
        if self._notes_save_timer.isActive():
            self._notes_save_timer.stop()
            self._flush_note()
        self._notes_current_path = path
        if not path:
            self._notes_edit.blockSignals(True)
            self._notes_edit.setPlainText("")
            self._notes_edit.blockSignals(False)
            return
        try:
            from Imervue.library import image_index
            existing = image_index.get_note(path)
        except Exception:  # noqa: BLE001
            existing = ""
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(existing)
        self._notes_edit.blockSignals(False)

    def _flush_note(self) -> None:
        """Debounced write-back of the notes field to the library index."""
        path = self._notes_current_path
        if not path:
            return
        try:
            from Imervue.library import image_index
            image_index.set_note(path, self._notes_edit.toPlainText())
        except Exception:  # noqa: BLE001, S110  # nosec B110 - notes optional; swallow DB errors
            pass

    def _on_rating_clicked(self, path: str, rating: int) -> None:
        """Persist a rating from the star strip and refresh viewer badges."""
        from Imervue.user_settings.user_setting_dict import (
            user_setting_dict, schedule_save,
        )
        ratings = user_setting_dict.get("image_ratings") or {}
        current = int(ratings.get(path, 0) or 0)
        if current == rating:
            ratings.pop(path, None)
        else:
            ratings[path] = rating
        user_setting_dict["image_ratings"] = ratings
        schedule_save()
        self._rating_widget.set_value(int(ratings.get(path, 0) or 0))
        viewer = getattr(self._main_window, "viewer", None)
        if viewer is not None:
            viewer.update()


_STAR_FILLED = "\u2605"
_STAR_EMPTY = "\u2606"
_RATING_MAX = 5


class _RatingStars(QWidget):
    """Row of five clickable star glyphs bound to the current image path."""

    def __init__(self, on_rate):
        super().__init__()
        self._on_rate = on_rate
        self._path: str | None = None
        self._value = 0

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(2)
        self._labels: list[QLabel] = []
        for i in range(_RATING_MAX):
            lbl = _StarLabel(i + 1, self._clicked)
            self._labels.append(lbl)
            row.addWidget(lbl)
        row.addStretch()
        self._render()

    def bind_path(self, path: str | None) -> None:
        self._path = path
        if path is None:
            self._value = 0
        else:
            from Imervue.user_settings.user_setting_dict import user_setting_dict
            ratings = user_setting_dict.get("image_ratings") or {}
            try:
                self._value = int(ratings.get(path, 0) or 0)
            except (TypeError, ValueError):
                self._value = 0
        self._render()

    def set_value(self, value: int) -> None:
        self._value = max(0, min(int(value), _RATING_MAX))
        self._render()

    def _clicked(self, rating: int) -> None:
        if not self._path:
            return
        self._on_rate(self._path, rating)

    def _render(self) -> None:
        for idx, lbl in enumerate(self._labels):
            filled = (idx + 1) <= self._value
            lbl.setText(_STAR_FILLED if filled else _STAR_EMPTY)
            colour = "#ffd450" if filled else "#555"
            lbl.setStyleSheet(
                f"QLabel {{ color: {colour}; font-size: 18px; padding: 0 1px; }}"
            )
            lbl.setEnabled(self._path is not None)


class _StarLabel(QLabel):
    """Clickable star glyph that emits its 1-based rating on left click."""

    def __init__(self, rating: int, on_click):
        super().__init__()
        self._rating = rating
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(20)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._on_click(self._rating)
            event.accept()
            return
        super().mousePressEvent(event)
