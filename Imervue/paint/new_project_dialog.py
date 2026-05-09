"""Modal picker for File ▸ "New Comic Project…".

Captures the template, page count, project name, and author into a
small frozen dataclass so the file-menu bridge can drive
``project_from_template`` without binding the dialog's widgets.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.page_templates import (
    DEFAULT_TEMPLATE_NAME,
    available_template_names,
)

PAGE_COUNT_MIN = 1
PAGE_COUNT_MAX = 200
DEFAULT_PAGE_COUNT = 4


@dataclass(frozen=True)
class NewProjectChoice:
    """User's selections from :class:`NewProjectDialog`."""

    template_name: str
    page_count: int
    project_name: str
    author: str


class NewProjectDialog(QDialog):
    """Pick a template + page count + project metadata."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_new_project_title", "New Comic Project"),
        )
        self.setMinimumWidth(360)

        self._template = QComboBox()
        for name in available_template_names():
            self._template.addItem(
                lang.get(f"paint_template_{name}", name), userData=name,
            )
        # Default to the canonical entry so the dialog opens on a
        # safe selection even when translations are missing.
        idx = self._template.findData(DEFAULT_TEMPLATE_NAME)
        if idx >= 0:
            self._template.setCurrentIndex(idx)

        self._page_count = QSpinBox()
        self._page_count.setRange(PAGE_COUNT_MIN, PAGE_COUNT_MAX)
        self._page_count.setValue(DEFAULT_PAGE_COUNT)

        self._project_name = QLineEdit(
            lang.get("paint_new_project_default", "Untitled Project"),
        )
        self._author = QLineEdit()

        form = QFormLayout()
        form.addRow(
            lang.get("paint_new_project_template", "Template:"), self._template,
        )
        form.addRow(
            lang.get("paint_new_project_pages", "Pages:"), self._page_count,
        )
        form.addRow(
            lang.get("paint_new_project_name", "Project name:"),
            self._project_name,
        )
        form.addRow(
            lang.get("paint_new_project_author", "Author:"), self._author,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> NewProjectChoice:
        return NewProjectChoice(
            template_name=str(self._template.currentData() or DEFAULT_TEMPLATE_NAME),
            page_count=int(self._page_count.value()),
            project_name=self._project_name.text().strip() or "Untitled Project",
            author=self._author.text().strip(),
        )
