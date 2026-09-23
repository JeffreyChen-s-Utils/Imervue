"""Tests for the EXIF editor's save: success path and how a failed write is reported."""
from __future__ import annotations

import struct
from types import SimpleNamespace

import pytest
from PIL import Image

piexif = pytest.importorskip("piexif")

from Imervue.gui import exif_editor as mod  # noqa: E402


class _Recorder:
    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, args))


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def editor(qapp, tmp_path):
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (8, 8), "green").save(path)
    dlg = mod.ExifEditorDialog(SimpleNamespace(main_window=None), str(path))
    toast, sidebar = _Recorder(), _Recorder()
    dlg._gui = SimpleNamespace(main_window=SimpleNamespace(toast=toast, exif_sidebar=sidebar))  # noqa: SLF001
    yield dlg, path, toast, sidebar
    dlg.deleteLater()


def test_save_writes_exif_and_reports_success(editor):
    dlg, path, toast, sidebar = editor
    dlg._fields[("0th", "Artist")].setText("Ada")  # noqa: SLF001
    dlg._save()  # noqa: SLF001
    assert piexif.load(str(path))["0th"][piexif.ImageIFD.Artist] == b"Ada"
    assert toast.calls == [("success", ("EXIF saved!",))]
    assert sidebar.calls == [("update_info", (str(path),))]
    assert dlg.result() == mod.QDialog.DialogCode.Accepted


def test_user_comment_is_written(editor):
    """Saving used to raise AttributeError: ``piexif.helper`` was never imported."""
    dlg, path, _toast, _sidebar = editor
    dlg._fields[("Exif", "UserComment")].setText("héllo")  # noqa: SLF001
    dlg._save()  # noqa: SLF001
    raw = piexif.load(str(path))["Exif"][piexif.ExifIFD.UserComment]
    assert piexif.helper.UserComment.load(raw) == "héllo"


def test_ascii_comment_stays_ascii(editor):
    dlg, path, _toast, _sidebar = editor
    dlg._fields[("Exif", "UserComment")].setText("plain")  # noqa: SLF001
    dlg._save()  # noqa: SLF001
    raw = piexif.load(str(path))["Exif"][piexif.ExifIFD.UserComment]
    assert raw == b"ASCII\x00\x00\x00plain"


@pytest.mark.parametrize("text", ["plain", "中文 comment"])
def test_saved_comment_reopens_without_its_prefix(qapp, editor, text):
    dlg, path, _toast, _sidebar = editor
    dlg._fields[("Exif", "UserComment")].setText(text)  # noqa: SLF001
    dlg._save()  # noqa: SLF001
    reopened = mod.ExifEditorDialog(SimpleNamespace(main_window=None), str(path))
    try:
        assert reopened._fields[("Exif", "UserComment")].text() == text  # noqa: SLF001
    finally:
        reopened.deleteLater()


@pytest.mark.parametrize("raw, shown", [
    (b"UNICODE\x00" + "é".encode("utf-16-be"), "é"),
    (b"no prefix here", "no prefix here"),
    (b"", ""),
])
def test_decode_user_comment(raw, shown):
    assert mod._decode_user_comment(piexif, raw) == shown  # noqa: SLF001


@pytest.mark.parametrize("exc", [struct.error("'H' format requires 0 <= number <= 65535"),
                                 KeyError(65000), ValueError("wrong type"), OSError("locked")])
def test_failed_write_is_reported_and_logged(editor, monkeypatch, caplog, exc):
    dlg, _path, toast, sidebar = editor

    def fail(*_a):
        raise exc

    monkeypatch.setattr(piexif, "insert", fail)
    with caplog.at_level("DEBUG", logger="Imervue"):
        dlg._save()  # noqa: SLF001
    assert toast.calls == [("error", (f"EXIF save failed: {exc}",))]
    assert sidebar.calls == []
    assert dlg.result() != mod.QDialog.DialogCode.Accepted
    (record,) = [r for r in caplog.records if r.exc_info]
    assert record.exc_info[0] is type(exc)
