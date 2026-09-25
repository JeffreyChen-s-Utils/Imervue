"""Tests for the export dialog: the size estimate, and never replacing a file unasked."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QFileDialog, QMessageBox

from Imervue.gui import export_dialog as mod


def _estimate(path, caplog, fmt="PNG"):
    reports: list[tuple[int, str]] = []
    worker = mod._SizeEstimateWorker(str(path), fmt, 90)  # noqa: SLF001
    worker.result_ready.connect(lambda size, err: reports.append((size, err)))
    with caplog.at_level("DEBUG", logger="Imervue"):
        worker.run()
    worker.deleteLater()
    return reports, [r for r in caplog.records if r.exc_info]


def test_estimates_the_encoded_size(qapp, tmp_path, caplog):
    path = tmp_path / "a.png"
    Image.new("RGB", (16, 16), "red").save(path)
    ((size, err),), tracebacks = _estimate(path, caplog)
    assert size > 0 and err == "" and tracebacks == []


@pytest.mark.parametrize("content", [None, b"not an image"])
def test_unreadable_source_is_reported_without_traceback(qapp, tmp_path, caplog, content):
    path = tmp_path / "bad.png"
    if content is not None:
        path.write_bytes(content)
    ((size, err),), tracebacks = _estimate(path, caplog)
    assert size == 0 and err
    assert tracebacks == []


def test_unexpected_error_is_reported_with_traceback(qapp, tmp_path, caplog, monkeypatch):
    def boom(_path):
        raise RuntimeError("bug")

    monkeypatch.setattr(mod, "open_export_source", boom)
    ((size, err),), tracebacks = _estimate(tmp_path / "a.png", caplog)
    assert (size, err) == (0, "bug")
    (record,) = tracebacks
    assert record.exc_info[0] is RuntimeError


def test_export_writes_the_metadata_the_chosen_policy_allows(qapp, tmp_path, monkeypatch):
    """Export dropped every EXIF tag, capture date included."""
    from Imervue.gui import export_metadata_combo
    monkeypatch.setattr(export_metadata_combo, "schedule_save", lambda: None)
    monkeypatch.setattr(mod._SizeEstimateWorker, "start", lambda self: None)  # noqa: SLF001
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif.get_ifd(0x8825)[1] = "N"
    exif[0x8825] = 0
    src = tmp_path / "src.jpg"
    Image.new("RGB", (20, 10)).save(src, exif=exif)
    dlg = mod.ExportDialog(str(src))
    try:
        dlg.format_combo.setCurrentText("PNG")
        dlg.path_edit.setText(str(tmp_path / "out.png"))
        combo = dlg.metadata_combo
        combo.setCurrentIndex(combo.findData("no_location"))
        dlg._do_export()  # noqa: SLF001
    finally:
        dlg.deleteLater()
    with Image.open(tmp_path / "out.png") as out:
        assert out.getexif()[0x010F] == "Canon"
        assert not out.getexif().get_ifd(0x8825)


@pytest.fixture
def export_dialog(qapp, monkeypatch):
    """An ExportDialog factory whose size estimate never starts; closed after the test."""
    monkeypatch.setattr(mod._SizeEstimateWorker, "start", lambda self: None)  # noqa: SLF001
    made = []

    def make(src):
        dlg = mod.ExportDialog(str(src))
        made.append(dlg)
        return dlg

    yield make
    for dlg in made:
        dlg.deleteLater()


@pytest.fixture
def replace_answers(monkeypatch):
    """Record every "replace it?" question and answer it with ``answers["reply"]``."""
    answers = {"reply": False, "asked": []}

    def question(_parent, _title, text, *_rest):
        answers["asked"].append(text)
        return QMessageBox.StandardButton.Yes if answers["reply"] else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", question)
    return answers


def _png(path, colour="red"):
    Image.new("RGB", (8, 8), colour).save(path)
    return path


def test_the_default_output_is_never_the_photo_itself(export_dialog, tmp_path):
    """A PNG exported as PNG defaulted to its own path and was replaced without a word."""
    src = _png(tmp_path / "photo.png")
    dlg = export_dialog(src)
    dlg.format_combo.setCurrentText("PNG")
    assert Path(dlg.path_edit.text()) == tmp_path / "photo_1.png"


def test_the_default_output_passes_over_a_sibling_sharing_the_name(export_dialog, tmp_path):
    """photo.jpg exported as PNG defaulted to photo.png, a different picture beside it."""
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (8, 8)).save(src)
    _png(tmp_path / "photo.png", "blue")
    dlg = export_dialog(src)
    dlg.format_combo.setCurrentText("JPEG")
    dlg.format_combo.setCurrentText("PNG")
    assert Path(dlg.path_edit.text()) == tmp_path / "photo_1.png"


def test_a_free_default_exports_without_asking(export_dialog, replace_answers, tmp_path):
    src = _png(tmp_path / "photo.png")
    dlg = export_dialog(src)
    dlg.format_combo.setCurrentText("PNG")
    dlg._do_export()  # noqa: SLF001
    assert (tmp_path / "photo_1.png").is_file()
    assert replace_answers["asked"] == []


def test_a_typed_existing_path_is_kept_unless_the_user_agrees(
        export_dialog, replace_answers, tmp_path):
    src = _png(tmp_path / "photo.png")
    other = _png(tmp_path / "other.png", "blue")
    before = other.read_bytes()
    dlg = export_dialog(src)
    dlg.format_combo.setCurrentText("PNG")
    dlg.path_edit.setText(str(other))
    dlg._do_export()  # noqa: SLF001
    assert other.read_bytes() == before
    assert len(replace_answers["asked"]) == 1 and "other.png" in replace_answers["asked"][0]
    replace_answers["reply"] = True
    dlg._do_export()  # noqa: SLF001
    assert other.read_bytes() != before


def test_exporting_over_the_photo_itself_asks_even_after_browse(
        export_dialog, replace_answers, tmp_path, monkeypatch):
    """Browse's Save dialog asks generically; the photo itself gets its own question."""
    src = _png(tmp_path / "photo.png")
    before = src.read_bytes()
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *_a, **_k: (str(src), ""))
    dlg = export_dialog(src)
    dlg.format_combo.setCurrentText("PNG")
    dlg._browse_output()  # noqa: SLF001
    dlg._do_export()  # noqa: SLF001
    assert src.read_bytes() == before
    assert len(replace_answers["asked"]) == 1


def test_an_existing_file_picked_through_browse_is_not_asked_twice(
        export_dialog, replace_answers, tmp_path, monkeypatch):
    src = _png(tmp_path / "photo.png")
    other = _png(tmp_path / "other.png", "blue")
    before = other.read_bytes()
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *_a, **_k: (str(other), ""))
    dlg = export_dialog(src)
    dlg.format_combo.setCurrentText("PNG")
    dlg._browse_output()  # noqa: SLF001
    dlg._do_export()  # noqa: SLF001
    assert replace_answers["asked"] == []
    assert other.read_bytes() != before


def test_a_browse_that_is_cancelled_confirms_nothing(
        export_dialog, replace_answers, tmp_path, monkeypatch):
    src = _png(tmp_path / "photo.png")
    other = _png(tmp_path / "other.png", "blue")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_k: ("", ""))
    dlg = export_dialog(src)
    dlg.format_combo.setCurrentText("PNG")
    dlg.path_edit.setText(str(other))
    dlg._browse_output()  # noqa: SLF001
    dlg._do_export()  # noqa: SLF001
    assert len(replace_answers["asked"]) == 1



def test_a_failed_export_says_so_and_keeps_the_dialog_open(
        export_dialog, tmp_path, monkeypatch):
    """A failed save was only logged: Save seemed to do nothing at all."""
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda _parent, title, text, *_rest: warnings.append((title, text)))

    def disk_full(*_args, **_kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(mod, "save_image", disk_full)
    src = _png(tmp_path / "photo.png")
    dlg = export_dialog(src)
    dlg._do_export()  # noqa: SLF001
    ((title, text),) = warnings
    assert title == "Export Image" and "No space left on device" in text
    assert dlg.result() != dlg.DialogCode.Accepted


def test_a_successful_export_warns_nothing(export_dialog, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
    dlg = export_dialog(_png(tmp_path / "photo.png"))
    dlg._do_export()  # noqa: SLF001
    assert warnings == []
    assert dlg.result() == dlg.DialogCode.Accepted
