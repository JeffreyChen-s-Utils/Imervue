"""Reusable list-of-strings widget for the pet-script editor.

:class:`_StringListEditor` backs the greetings tab, each time-of-day
band and the value panes of the section editors; :func:`_tr` is the
editor's shared translation lookup.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper


def _tr(key: str, default: str) -> str:
    return language_wrapper.language_word_dict.get(key, default)


class _StringListEditor(QWidget):
    """Editable list of strings — Add / Edit / Remove + a list
    widget showing entries. Used for greetings + each time-of-day
    band; reused inside :class:`_DictOfListsEditor` for the value
    pane."""

    def __init__(
        self, parent: QWidget | None = None, *, initial: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._list = self._build_list_widget()
        layout.addWidget(self._list)
        layout.addLayout(self._build_button_row())
        if initial:
            self.set_lines(initial)

    def _build_list_widget(self) -> QListWidget:
        widget = QListWidget(self)
        widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        widget.itemDoubleClicked.connect(self._on_edit)
        return widget

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        for label_key, default_label, handler in (
            ("desktop_pet_editor_add", "Add", self._on_add),
            ("desktop_pet_editor_edit", "Edit", self._on_edit_selected),
            ("desktop_pet_editor_remove", "Remove", self._on_remove),
        ):
            button = QPushButton(_tr(label_key, default_label))
            button.clicked.connect(handler)
            row.addWidget(button)
        row.addStretch(1)
        return row

    def set_lines(self, lines: list[str]) -> None:
        self._list.clear()
        for line in lines:
            self._list.addItem(QListWidgetItem(str(line)))

    def lines(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _on_add(self) -> None:   # pragma: no cover - Qt UI
        text, ok = QInputDialog.getText(
            self,
            _tr("desktop_pet_editor_add", "Add"),
            _tr("desktop_pet_editor_line_prompt", "Line:"),
        )
        if ok and text:
            self._list.addItem(QListWidgetItem(text))

    def _on_edit(self, item: QListWidgetItem) -> None:   # pragma: no cover - Qt UI
        text, ok = QInputDialog.getText(
            self,
            _tr("desktop_pet_editor_edit", "Edit"),
            _tr("desktop_pet_editor_line_prompt", "Line:"),
            QLineEdit.EchoMode.Normal,
            item.text(),
        )
        if ok and text:
            item.setText(text)

    def _on_edit_selected(self) -> None:   # pragma: no cover - Qt UI
        item = self._list.currentItem()
        if item is not None:
            self._on_edit(item)

    def _on_remove(self) -> None:   # pragma: no cover - Qt UI
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
