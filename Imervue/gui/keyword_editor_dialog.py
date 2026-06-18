"""Keyword / IPTC metadata editor — edit title, creator, description, keywords.

A lightweight panel over :mod:`Imervue.image.xmp_sidecar`: it loads the image's
XMP sidecar, lets the user edit the descriptive fields, and writes them back.
Rating and colour label are preserved untouched (they have their own UI).

The keyword text parsing is pure and unit-tested; the dialog is the Qt shell.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.image import xmp_sidecar
from Imervue.image.xmp_sidecar import XmpData
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.keyword_editor")


def parse_keywords(text: str) -> list[str]:
    """Split a comma-separated keyword string into a clean, de-duplicated list."""
    out: list[str] = []
    for part in text.split(","):
        keyword = part.strip()
        if keyword and keyword not in out:
            out.append(keyword)
    return out


def keywords_to_text(keywords: list[str]) -> str:
    """Join keywords back into the comma-separated form the editor shows."""
    return ", ".join(keywords)


class KeywordEditorDialog(QDialog):
    """Edit the XMP descriptive metadata (title / creator / description / keywords)."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._existing = xmp_sidecar.load(path)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("keyword_editor_title", "Edit Keywords"))
        self.setMinimumWidth(440)

        self._title_edit = QLineEdit(self._existing.title)
        self._creator_edit = QLineEdit(self._existing.creator)
        self._keywords_edit = QLineEdit(keywords_to_text(self._existing.keywords))
        self._desc_edit = QPlainTextEdit(self._existing.description)
        self._desc_edit.setFixedHeight(80)
        self._build_layout(lang)

    def _build_layout(self, lang: dict) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get("keyword_editor_title_label", "Title:")))
        layout.addWidget(self._title_edit)
        layout.addWidget(QLabel(lang.get("keyword_editor_creator", "Creator:")))
        layout.addWidget(self._creator_edit)
        layout.addWidget(QLabel(
            lang.get("keyword_editor_keywords", "Keywords (comma-separated):")))
        layout.addWidget(self._keywords_edit)
        layout.addWidget(QLabel(lang.get("keyword_editor_description", "Description:")))
        layout.addWidget(self._desc_edit)
        layout.addLayout(self._build_buttons(lang))

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(lang.get("export_save", "Save"))
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        return row

    def _save(self) -> None:
        data = XmpData(
            rating=self._existing.rating,
            title=self._title_edit.text().strip(),
            description=self._desc_edit.toPlainText().strip(),
            keywords=parse_keywords(self._keywords_edit.text()),
            color_label=self._existing.color_label,
            creator=self._creator_edit.text().strip(),
        )
        try:
            xmp_sidecar.save(self._path, data)
        except OSError as exc:
            logger.warning("Keyword save failed for %s: %s", self._path, exc)
            return
        self._notify_saved()
        self.accept()

    def _notify_saved(self) -> None:  # pragma: no cover - Qt UI
        from pathlib import Path
        main_window = getattr(self._viewer, "main_window", None)
        toast = getattr(main_window, "toast", None)
        if toast is not None:
            toast.success(language_wrapper.language_word_dict.get(
                "keyword_editor_saved", "Saved metadata to {path}").format(
                    path=Path(self._path).name))


def open_keyword_editor(main_gui: GPUImageView) -> None:
    """Open the keyword editor for the currently viewed image."""
    images = getattr(getattr(main_gui, "model", None), "images", None) or []
    idx = getattr(main_gui, "current_index", -1)
    if 0 <= idx < len(images):
        KeywordEditorDialog(main_gui, images[idx]).exec()
