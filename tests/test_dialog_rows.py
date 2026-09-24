"""Tests for the row builders in ``Imervue.gui.dialog_rows``."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QSlider, QWidget

from Imervue.gui import dialog_rows
from Imervue.gui.dialog_rows import (
    action_button_row, folder_picker_row, path_browse_row, quality_slider,
)


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(dialog_rows.language_wrapper, "language_word_dict", {})


def _hosted(row):
    host = QWidget()
    host.setLayout(row)
    return host


def _widgets(row):
    return [row.itemAt(i).widget() for i in range(row.count())]


# ---------------------------------------------------------------------------
# path_browse_row / folder_picker_row
# ---------------------------------------------------------------------------


def test_path_browse_row(qapp):
    calls = []
    row, edit, browse = path_browse_row(lambda: calls.append(True))
    host = _hosted(row)
    try:
        assert _widgets(row) == [edit, browse]
        assert isinstance(edit, QLineEdit) and isinstance(browse, QPushButton)
        assert browse.text() == "Browse..."
        assert [row.stretch(i) for i in range(2)] == [1, 0]
        browse.click()
        browse.click()
        assert calls == [True, True]
    finally:
        host.deleteLater()


def test_folder_picker_row_holds_label_stretching_edit_and_browse(qapp):
    row, edit = folder_picker_row("Source:", lambda: None)
    host = _hosted(row)
    try:
        label, line_edit, browse = _widgets(row)
        assert isinstance(label, QLabel) and label.text() == "Source:"
        assert line_edit is edit and isinstance(edit, QLineEdit)
        assert isinstance(browse, QPushButton) and browse.text() == "Browse..."
        assert [row.stretch(i) for i in range(3)] == [0, 1, 0]
    finally:
        host.deleteLater()


def test_folder_picker_browse_button_calls_back(qapp):
    calls = []
    row, _edit = folder_picker_row("Out:", lambda: calls.append(True))
    host = _hosted(row)
    try:
        row.itemAt(2).widget().click()
        row.itemAt(2).widget().click()
        assert calls == [True, True]
    finally:
        host.deleteLater()


def test_browse_label_is_translated(qapp, monkeypatch):
    monkeypatch.setattr(dialog_rows.language_wrapper, "language_word_dict",
                        {"batch_convert_browse": "瀏覽..."})
    row, _edit = folder_picker_row("", lambda: None)
    host = _hosted(row)
    try:
        assert row.itemAt(2).widget().text() == "瀏覽..."
        assert row.itemAt(0).widget().text() == ""
    finally:
        host.deleteLater()


@pytest.mark.parametrize("builder", ["folder", "path"])
def test_browse_text_override(qapp, monkeypatch, builder):
    monkeypatch.setattr(dialog_rows.language_wrapper, "language_word_dict",
                        {"batch_convert_browse": "unused"})
    if builder == "folder":
        row, _edit = folder_picker_row("Src:", lambda: None, browse_text="Pick…")
    else:
        row, _edit, _browse = path_browse_row(lambda: None, browse_text="Pick…")
    host = _hosted(row)
    try:
        assert _widgets(row)[-1].text() == "Pick…"
    finally:
        host.deleteLater()


# ---------------------------------------------------------------------------
# quality_slider
# ---------------------------------------------------------------------------


def test_quality_slider_defaults(qapp):
    label, slider = quality_slider({})
    try:
        assert isinstance(label, QLabel) and isinstance(slider, QSlider)
        assert label.text() == "Quality: 85"
        assert (slider.minimum(), slider.maximum(), slider.value()) == (0, 100, 85)
    finally:
        label.deleteLater()
        slider.deleteLater()


@pytest.mark.parametrize("value", [0, 1, 99, 100])
def test_quality_slider_label_tracks_value(qapp, value):
    label, slider = quality_slider({}, value=50)
    try:
        assert label.text() == "Quality: 50"
        slider.setValue(value)
        assert label.text() == f"Quality: {value}"
    finally:
        label.deleteLater()
        slider.deleteLater()


def test_quality_slider_clamps_out_of_range(qapp):
    label, slider = quality_slider({})
    try:
        slider.setValue(150)
        assert slider.value() == 100 and label.text() == "Quality: 100"
    finally:
        label.deleteLater()
        slider.deleteLater()


def test_quality_slider_translated_prefix(qapp):
    label, slider = quality_slider({"export_quality": "品質："}, value=70)
    try:
        assert label.text() == "品質： 70"
        slider.setValue(71)
        assert label.text() == "品質： 71"
    finally:
        label.deleteLater()
        slider.deleteLater()


# ---------------------------------------------------------------------------
# action_button_row
# ---------------------------------------------------------------------------


def test_action_button_row_right_aligns_in_order(qapp):
    a, b = QPushButton("Cancel"), QPushButton("Go")
    row = action_button_row(a, b)
    host = _hosted(row)
    try:
        assert _widgets(row) == [None, a, b]
    finally:
        host.deleteLater()


def test_action_button_row_without_buttons_is_a_stretch(qapp):
    row = action_button_row()
    host = _hosted(row)
    try:
        assert _widgets(row) == [None]
    finally:
        host.deleteLater()


# ---------------------------------------------------------------------------
# save_path_into / open_path_into
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("picked", "expected"), [("/new.png", "/new.png"), ("", "/old.png")])
def test_save_path_into(qapp, monkeypatch, picked, expected):
    from PySide6.QtWidgets import QFileDialog
    calls = []
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(
        lambda *args: calls.append(args) or (picked, "")))
    edit = QLineEdit("/old.png")
    try:
        dialog_rows.save_path_into(None, edit, "Output", dialog_rows.image_save_filter())
        assert edit.text() == expected
        assert calls == [(None, "Output", "/old.png", "Images (*.png *.jpg *.tif)")]
    finally:
        edit.deleteLater()


@pytest.mark.parametrize(("picked", "expected"), [("/p.icc", "/p.icc"), ("", "/keep.icc")])
def test_open_path_into_starts_empty(qapp, monkeypatch, picked, expected):
    from PySide6.QtWidgets import QFileDialog
    calls = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(
        lambda *args: calls.append(args) or (picked, "")))
    edit = QLineEdit("/keep.icc")
    try:
        dialog_rows.open_path_into(None, edit, "ICC profile", "ICC (*.icc)")
        assert edit.text() == expected
        assert calls == [(None, "ICC profile", "", "ICC (*.icc)")]
    finally:
        edit.deleteLater()


def test_save_path_into_explicit_start(qapp, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    calls = []
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(
        lambda *args: calls.append(args) or ("", "")))
    edit = QLineEdit("/current.png")
    try:
        dialog_rows.save_path_into(None, edit, "Output", "F", start="merged.png")
        assert calls == [(None, "Output", "merged.png", "F")]
        assert edit.text() == "/current.png"
    finally:
        edit.deleteLater()


def test_open_path_into_explicit_start(qapp, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    calls = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(
        lambda *args: calls.append(args) or ("", "")))
    edit = QLineEdit("/keep.cube")
    try:
        dialog_rows.open_path_into(None, edit, "LUT", "F", start="C:/luts")
        assert calls == [(None, "LUT", "C:/luts", "F")]
        assert edit.text() == "/keep.cube"
    finally:
        edit.deleteLater()
