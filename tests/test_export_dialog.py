"""Tests for the export dialog's size-estimate worker: what it reports back."""
from __future__ import annotations

import pytest
from PIL import Image

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
