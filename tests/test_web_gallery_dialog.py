"""Tests for the Web Gallery export dialog."""
from __future__ import annotations

import pytest

from Imervue.gui import web_gallery_dialog as mod
from Imervue.gui.web_gallery_dialog import WebGalleryDialog


@pytest.fixture
def started(monkeypatch, tmp_path):
    """Pick *tmp_path* as the output folder and record the workers instead of running them."""
    workers = []
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory", lambda *_a, **_k: str(tmp_path))
    pool = type("Pool", (), {"start": lambda _self, worker: workers.append(worker)})()
    monkeypatch.setattr(mod.QThreadPool, "globalInstance", staticmethod(lambda: pool))
    return workers


@pytest.fixture
def dialog(qapp):
    dlg = WebGalleryDialog(None)
    yield dlg
    dlg.deleteLater()


def test_client_review_starts_off(dialog):
    assert not dialog._review_check.isChecked()  # noqa: SLF001
    assert dialog._review_check.text() == "Client review: a comment box under each picture"  # noqa: SLF001


def test_client_review_reaches_the_generator(dialog, started):
    """The generator had a review mode that no dialog, CLI or MCP call could switch on."""
    dialog._review_check.setChecked(True)  # noqa: SLF001
    dialog._export(["a.png"])  # noqa: SLF001
    (worker,) = started
    assert worker.opts.review_mode is True
    assert worker.images == ["a.png"]


def test_a_plain_gallery_has_no_review_boxes(dialog, started):
    dialog._export(["a.png"])  # noqa: SLF001
    (worker,) = started
    assert worker.opts.review_mode is False


def test_the_review_page_is_written(tmp_path):
    """End to end: the generated page carries the comment boxes and the export button."""
    from PIL import Image

    from Imervue.export.web_gallery import WebGalleryOptions, generate_web_gallery
    picture = tmp_path / "shot.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(picture)
    out = tmp_path / "site"
    generate_web_gallery([str(picture)], str(out), WebGalleryOptions(review_mode=True))
    page = (out / "index.html").read_text(encoding="utf-8")
    assert 'data-key="shot.png"' in page
    assert "export-comments" in page
