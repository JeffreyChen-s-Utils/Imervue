"""Tests for the EXIF editor dialog: load, save, report, and the unsupported-format path."""
from __future__ import annotations

import struct
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

from Imervue.gui import exif_editor as mod
from Imervue.image.exif_fields import USER_COMMENT

_ARTIST = 0x013B


class _Recorder:
    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, args))


@pytest.fixture(autouse=True)
def _english_without_piexif(monkeypatch):
    """The default install: no piexif, English UI."""
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    monkeypatch.setitem(sys.modules, "piexif", None)


def _dialog(path):
    dlg = mod.ExifEditorDialog(SimpleNamespace(main_window=None), str(path))
    toast, sidebar = _Recorder(), _Recorder()
    dlg._gui = SimpleNamespace(main_window=SimpleNamespace(toast=toast, exif_sidebar=sidebar))  # noqa: SLF001
    return dlg, toast, sidebar


@pytest.fixture
def editor(qapp, tmp_path):
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (8, 8), "green").save(path)
    dlg, toast, sidebar = _dialog(path)
    yield dlg, path, toast, sidebar
    dlg.deleteLater()


def _exif(path):
    with Image.open(path) as img:
        exif = img.getexif()
        exif.get_ifd(0x8769)
    return exif


def test_save_writes_exif_and_reports_success(editor):
    """piexif is not a dependency: the editor used to be a "please install piexif" notice."""
    dlg, path, toast, sidebar = editor
    dlg._fields[_ARTIST].setText("Ada")  # noqa: SLF001
    dlg._save()  # noqa: SLF001
    assert _exif(path)[_ARTIST] == "Ada"
    assert toast.calls == [("success", ("EXIF saved!",))]
    assert sidebar.calls == [("update_info", (str(path),))]
    assert dlg.result() == mod.QDialog.DialogCode.Accepted


def test_save_keeps_the_pixels(editor):
    dlg, path, _toast, _sidebar = editor
    before = path.read_bytes()
    dlg._fields[_ARTIST].setText("Ada")  # noqa: SLF001
    dlg._save()  # noqa: SLF001
    after = path.read_bytes()
    assert after[after.index(b"\xff\xda"):] == before[before.index(b"\xff\xda"):]


@pytest.mark.parametrize("text", ["plain", "中文 comment", "héllo"])
def test_saved_fields_reopen_as_typed(qapp, editor, text):
    dlg, path, _toast, _sidebar = editor
    dlg._fields[USER_COMMENT].setText(text)  # noqa: SLF001
    dlg._fields[_ARTIST].setText(text)  # noqa: SLF001
    dlg._save()  # noqa: SLF001
    reopened, _t, _s = _dialog(path)
    try:
        assert reopened._fields[USER_COMMENT].text() == text  # noqa: SLF001
        assert reopened._fields[_ARTIST].text() == text  # noqa: SLF001
    finally:
        reopened.deleteLater()


def test_ascii_comment_is_stored_with_the_ascii_prefix(editor):
    dlg, path, _toast, _sidebar = editor
    dlg._fields[USER_COMMENT].setText("plain")  # noqa: SLF001
    dlg._save()  # noqa: SLF001
    assert _exif(path).get_ifd(0x8769)[USER_COMMENT] == b"ASCII\x00\x00\x00plain"


def test_existing_values_and_gps_count_are_shown(qapp, tmp_path):
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif.get_ifd(0x8825)[1] = "N"
    exif[0x8825] = 0
    path = tmp_path / "cam.jpg"
    Image.new("RGB", (8, 8)).save(path, exif=exif)
    dlg, _t, _s = _dialog(path)
    try:
        assert dlg._fields[0x010F].text() == "Canon"  # noqa: SLF001
        labels = [dlg.layout().itemAt(i).widget() for i in range(dlg.layout().count())]
        assert any(isinstance(w, mod.QLabel) and w.text() == "GPS: 1 tag(s) present" for w in labels)
    finally:
        dlg.deleteLater()


@pytest.mark.parametrize("exc", [struct.error("'H' format requires 0 <= number <= 65535"),
                                 KeyError(65000), ValueError("wrong type"), OSError("locked")])
def test_failed_write_is_reported_and_logged(editor, monkeypatch, caplog, exc):
    dlg, _path, toast, sidebar = editor

    def fail(*_a):
        raise exc

    monkeypatch.setattr(mod, "save_fields", fail)
    with caplog.at_level("DEBUG", logger="Imervue"):
        dlg._save()  # noqa: SLF001
    assert toast.calls == [("error", (f"EXIF save failed: {exc}",))]
    assert sidebar.calls == []
    assert dlg.result() != mod.QDialog.DialogCode.Accepted
    (record,) = [r for r in caplog.records if r.exc_info]
    assert record.exc_info[0] is type(exc)


@pytest.mark.parametrize("name", ["a.png", "a.webp", "a.tif"])
def test_other_formats_explain_instead_of_editing(qapp, tmp_path, name):
    path = tmp_path / name
    Image.new("RGB", (8, 8)).save(path)
    dlg, _t, _s = _dialog(path)
    try:
        assert dlg._fields == {}  # noqa: SLF001
        texts = [dlg.layout().itemAt(i).widget().text() for i in range(dlg.layout().count())]
        assert texts[0].startswith("EXIF can be edited in JPEG files")
        assert texts[1] == "Close"
    finally:
        dlg.deleteLater()


def test_unreadable_jpeg_opens_empty(qapp, tmp_path, caplog):
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"not a jpeg")
    with caplog.at_level("WARNING", logger="Imervue"):
        dlg, _t, _s = _dialog(path)
    try:
        assert all(edit.text() == "" for edit in dlg._fields.values())  # noqa: SLF001
        assert any("Could not read EXIF" in r.getMessage() for r in caplog.records)
    finally:
        dlg.deleteLater()
