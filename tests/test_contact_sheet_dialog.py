"""Tests for the contact-sheet dialog's render worker: what it reports back."""
from __future__ import annotations

from PIL import Image

from Imervue.export.contact_sheet import ContactSheetOptions
from Imervue.gui.contact_sheet_dialog import _RenderWorker

_OPTS = ContactSheetOptions(rows=1, cols=1, dpi=72)


def _run(images, out):
    reports: list[tuple[str, str]] = []
    worker = _RenderWorker(images, str(out), _OPTS)
    worker.signals.done.connect(lambda path, err: reports.append((path, err)))
    worker.run()
    return reports


def _image(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGB", (8, 8), "blue").save(path)
    return str(path)


def test_success_reports_no_error(qapp, tmp_path):
    out = tmp_path / "sheet.pdf"
    assert _run([_image(tmp_path)], out) == [(str(out), "")]
    assert out.exists()


def test_unwritable_target_reports_the_error(qapp, tmp_path):
    out = tmp_path / "taken.pdf"
    out.mkdir()
    ((path, err),) = _run([_image(tmp_path)], out)
    assert path == str(out) and "taken.pdf" in err


def test_no_images_reports_the_error(qapp, tmp_path):
    ((_path, err),) = _run([], tmp_path / "sheet.pdf")
    assert "at least one image" in err
