"""Characterisation tests for ``ExifSidebar``'s construction and activation.

Pins the scroll area and its content column (order and stretch), the info
label's interaction flags and link wiring, the edit / keywords buttons' slots,
the notes editor with its debounced save timer, the sizes that follow the UI
scale, and that the panel only reads image data while its dock is shown.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QScrollArea

from Imervue.gui import exif_sidebar as mod
from Imervue.gui.exif_sidebar import ExifSidebar
from Imervue.user_settings.user_setting_dict import user_setting_dict


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
    assert outer.itemAt(0).widget() is sidebar._content  # noqa: SLF001
    # The dock decides the width: a floor, and no ceiling to fight a resize.
    assert sidebar.minimumWidth() == mod._MIN_WIDTH_PX  # noqa: SLF001
    assert sidebar.maximumWidth() > 10_000


def test_scroll_area(sidebar):
    area = sidebar._content  # noqa: SLF001
    assert isinstance(area, QScrollArea) and area.widgetResizable()
    assert area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert not area.isHidden()
    assert area.frameShape() == QScrollArea.Shape.NoFrame
    assert area.styleSheet() == ""      # colours come from the theme


def test_content_column_order(sidebar):
    items = _content_items(sidebar)
    assert items == [
        sidebar._info_label, sidebar._edit_btn, sidebar._keywords_btn,  # noqa: SLF001
        sidebar._rating_widget, sidebar._notes_label, sidebar._notes_edit]  # noqa: SLF001
    column = sidebar._content.widget().layout()  # noqa: SLF001
    # Only the notes take the spare height.
    assert [column.stretch(i) for i in range(column.count())] == [0, 0, 0, 0, 0, 1]


def test_info_label(sidebar):
    label = sidebar._info_label  # noqa: SLF001
    assert isinstance(label, QLabel) and label.wordWrap()
    assert label.alignment() == Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
    assert label.textInteractionFlags() == (Qt.TextInteractionFlag.TextSelectableByMouse
                                            | Qt.TextInteractionFlag.LinksAccessibleByMouse)
    assert not label.openExternalLinks()
    assert "color" not in label.styleSheet() and "font-size" not in label.styleSheet()


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
        # A floor, not a fixed height: the editor grows with the dock.
        assert edit.minimumHeight() == mod._NOTES_MIN_HEIGHT_PX  # noqa: SLF001
        assert edit.maximumHeight() > 10_000
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


# ---------------------------------------------------------------------------
# Activation: the dock's visibility switches the EXIF reads on and off
# ---------------------------------------------------------------------------

def test_the_panel_starts_idle_and_reads_nothing(qapp, monkeypatch):
    refreshed = []
    monkeypatch.setattr(ExifSidebar, "_current_viewer_path",
                        lambda self: refreshed.append(True))
    widget = ExifSidebar(None)
    try:
        widget.update_info()
        widget.update_info("some.png")
        assert refreshed == []
    finally:
        widget.deleteLater()


def test_becoming_active_refreshes_once(qapp, monkeypatch):
    refreshed = []
    monkeypatch.setattr(ExifSidebar, "update_info", lambda self: refreshed.append(True))
    widget = ExifSidebar(None)
    try:
        widget.set_active(True)
        assert refreshed == [True]
        widget.set_active(True)          # already active: the dock repeats the signal
        assert refreshed == [True]
        widget.set_active(False)
        assert refreshed == [True]
        widget.set_active(True)
        assert refreshed == [True, True]
    finally:
        widget.deleteLater()


def test_an_active_panel_with_no_image_shows_nothing(qapp, monkeypatch):
    monkeypatch.setattr(ExifSidebar, "_current_viewer_path", lambda self: None)
    widget = ExifSidebar(None)
    try:
        widget._info_label.setText("stale")  # noqa: SLF001
        widget.set_active(True)
        assert widget._info_label.text() == ""  # noqa: SLF001
    finally:
        widget.deleteLater()


def test_quick_image_switches_become_one_read(qapp, monkeypatch, pump_until):
    refreshed = []
    monkeypatch.setattr(ExifSidebar, "update_info", lambda self: refreshed.append(True))
    widget = ExifSidebar(None)
    try:
        widget._refresh_timer.setInterval(0)  # noqa: SLF001
        widget.set_active(True)
        refreshed.clear()
        for _ in range(5):
            widget.schedule_update()
        assert refreshed == []                 # nothing is read while paging
        assert pump_until(lambda: refreshed == [True])
    finally:
        widget.deleteLater()


def test_a_hidden_panel_schedules_nothing(sidebar):
    sidebar.schedule_update()
    assert not sidebar._refresh_timer.isActive()  # noqa: SLF001


def test_hiding_the_panel_drops_a_pending_refresh(qapp, monkeypatch):
    monkeypatch.setattr(ExifSidebar, "update_info", lambda self: None)
    widget = ExifSidebar(None)
    try:
        widget.set_active(True)
        widget.schedule_update()
        assert widget._refresh_timer.isActive()  # noqa: SLF001
        widget.set_active(False)
        assert not widget._refresh_timer.isActive()  # noqa: SLF001
    finally:
        widget.deleteLater()


def test_refresh_timer(sidebar):
    timer = sidebar._refresh_timer  # noqa: SLF001
    assert timer.isSingleShot() and timer.interval() == mod._REFRESH_DELAY_MS  # noqa: SLF001
    assert timer.parent() is sidebar


# ---------------------------------------------------------------------------
# UI scale
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("percent", "factor"), [(80, 0.8), (100, 1.0), (200, 2.0)])
def test_sizes_follow_the_ui_scale(qapp, percent, factor):
    user_setting_dict["ui_scale_percent"] = percent
    widget = ExifSidebar(None)
    try:
        assert widget.minimumWidth() == round(mod._MIN_WIDTH_PX * factor)  # noqa: SLF001
        assert widget._notes_edit.minimumHeight() == round(  # noqa: SLF001
            mod._NOTES_MIN_HEIGHT_PX * factor)  # noqa: SLF001
        star = widget._rating_widget._labels[0]  # noqa: SLF001
        assert f"font-size: {round(mod._STAR_FONT_PX * factor)}px" in star.styleSheet()  # noqa: SLF001
        assert star.minimumWidth() == round(mod._STAR_WIDTH_PX * factor)  # noqa: SLF001
    finally:
        widget.deleteLater()


def test_stars_take_the_theme_colour_until_filled(sidebar):
    stars = sidebar._rating_widget  # noqa: SLF001
    assert all("palette(mid)" in label.styleSheet() for label in stars._labels)  # noqa: SLF001
    stars.set_value(2)
    styles = [label.styleSheet() for label in stars._labels]  # noqa: SLF001
    assert [mod._STAR_FILLED_COLOUR in s for s in styles] == [True, True, False, False, False]  # noqa: SLF001
