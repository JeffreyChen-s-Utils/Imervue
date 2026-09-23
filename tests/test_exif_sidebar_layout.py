"""Characterisation tests for ``ExifSidebar``'s construction and collapse toggle.

Pins the toggle button, the scroll area and its content column (order and
styling), the info label's interaction flags and link wiring, the edit /
keywords buttons' slots, the notes editor with its debounced save timer, and
the collapse / expand widths, so splitting the constructor cannot drop,
reorder or rewire anything.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy

from Imervue.gui import exif_sidebar as mod
from Imervue.gui.exif_sidebar import ExifSidebar


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def sidebar(qapp):
    widget = ExifSidebar(None)
    yield widget
    widget.deleteLater()


def _content_items(sidebar):
    column = sidebar._content.widget().layout()  # noqa: SLF001
    return [column.itemAt(i).widget() for i in range(column.count())]


def test_outer_layout(sidebar):
    outer = sidebar.layout()
    assert outer.count() == 1 and outer.spacing() == 0
    row = outer.itemAt(0).layout()
    assert row.spacing() == 0
    assert [row.itemAt(i).widget() for i in range(row.count())] == [
        sidebar._toggle_btn, sidebar._content]  # noqa: SLF001
    assert (sidebar.minimumWidth(), sidebar.maximumWidth()) == (0, 300)


def test_toggle_button(sidebar):
    btn = sidebar._toggle_btn  # noqa: SLF001
    assert btn.text() == "❯" and btn.isCheckable() and not btn.isChecked()
    assert btn.maximumWidth() == 24 and btn.minimumWidth() == 24
    assert btn.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert "QToolButton:checked" in btn.styleSheet()


def test_scroll_area(sidebar):
    area = sidebar._content  # noqa: SLF001
    assert isinstance(area, QScrollArea) and area.widgetResizable()
    assert area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert area.isHidden()
    assert "#1e1e1e" in area.styleSheet()


def test_content_column_order(sidebar):
    items = _content_items(sidebar)
    assert items[:6] == [
        sidebar._info_label, sidebar._edit_btn, sidebar._keywords_btn,  # noqa: SLF001
        sidebar._rating_widget, sidebar._notes_label, sidebar._notes_edit]  # noqa: SLF001
    assert items[6] is None  # trailing stretch
    assert len(items) == 7


def test_info_label(sidebar):
    label = sidebar._info_label  # noqa: SLF001
    assert isinstance(label, QLabel) and label.wordWrap()
    assert label.alignment() == Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
    assert label.textInteractionFlags() == (Qt.TextInteractionFlag.TextSelectableByMouse
                                            | Qt.TextInteractionFlag.LinksAccessibleByMouse)
    assert not label.openExternalLinks()


def test_buttons_and_link_reach_their_slots(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(ExifSidebar, "_open_editor", lambda self, *_a: calls.append("edit"))
    monkeypatch.setattr(ExifSidebar, "_open_keyword_editor",
                        lambda self, *_a: calls.append("keywords"))
    monkeypatch.setattr(ExifSidebar, "_on_link_activated",
                        lambda self, link: calls.append(("link", link)))
    widget = ExifSidebar(None)
    try:
        assert isinstance(widget._edit_btn, QPushButton)  # noqa: SLF001
        assert (widget._edit_btn.text(), widget._keywords_btn.text()) == (  # noqa: SLF001
            "Edit EXIF", "Edit Keywords")
        assert widget._edit_btn.styleSheet() == "QPushButton { margin: 4px; }"  # noqa: SLF001
        widget._edit_btn.click()  # noqa: SLF001
        widget._keywords_btn.click()  # noqa: SLF001
        widget._info_label.linkActivated.emit(mod._MAP_LINK)  # noqa: SLF001
        assert calls == ["edit", "keywords", ("link", mod._MAP_LINK)]
    finally:
        widget.deleteLater()


def test_notes_editor_and_debounce(qapp, monkeypatch):
    flushed = []
    monkeypatch.setattr(ExifSidebar, "_flush_note", lambda self: flushed.append(True))
    widget = ExifSidebar(None)
    try:
        assert widget._notes_label.text() == "Notes"  # noqa: SLF001
        edit = widget._notes_edit  # noqa: SLF001
        assert isinstance(edit, QPlainTextEdit)
        assert edit.placeholderText() == "Write notes for this image…"
        assert edit.maximumHeight() == 120 == edit.minimumHeight()
        assert widget._notes_current_path is None  # noqa: SLF001
        timer = widget._notes_save_timer  # noqa: SLF001
        assert timer.isSingleShot() and timer.interval() == 500 and timer.parent() is widget
        assert not timer.isActive()
        edit.setPlainText("hello")
        assert timer.isActive()
        timer.timeout.emit()
        assert flushed == [True]
    finally:
        widget.deleteLater()


def test_toggle_expands_and_collapses(qapp, monkeypatch):
    refreshed = []
    monkeypatch.setattr(ExifSidebar, "update_info", lambda self: refreshed.append(True))
    widget = ExifSidebar(None)
    try:
        widget._toggle_btn.click()  # noqa: SLF001
        assert not widget._content.isHidden()  # noqa: SLF001
        assert widget._toggle_btn.text() == "❮"  # noqa: SLF001
        assert (widget.minimumWidth(), widget.maximumWidth()) == (260, 300)
        assert refreshed == [True]
        widget._toggle_btn.click()  # noqa: SLF001
        assert widget._content.isHidden()  # noqa: SLF001
        assert widget._toggle_btn.text() == "❯"  # noqa: SLF001
        assert (widget.minimumWidth(), widget.maximumWidth()) == (0, 24)
        assert refreshed == [True]
    finally:
        widget.deleteLater()
