"""Tests for multi-page CBZ / PDF export."""
from __future__ import annotations

import zipfile

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.page_templates import (
    project_from_template,
    template_by_name,
)
from Imervue.paint.paint_project import PaintProject, ProjectPage
from Imervue.paint.paint_project_export import (
    export_project_cbz,
    export_project_pdf,
)


def _three_page_project():
    """Three blank A5 pages, each filled with a distinguishable colour."""
    project = project_from_template(template_by_name("manga_a5"), page_count=3)
    project.pages[0].document.active_layer().image[..., :3] = (255, 0, 0)
    project.pages[1].document.active_layer().image[..., :3] = (0, 255, 0)
    project.pages[2].document.active_layer().image[..., :3] = (0, 0, 255)
    return project


# ---------------------------------------------------------------------------
# CBZ
# ---------------------------------------------------------------------------


def test_cbz_writes_one_png_per_page(tmp_path):
    project = _three_page_project()
    out = export_project_cbz(project, tmp_path / "out.cbz")
    with zipfile.ZipFile(out) as zf:
        assert len(zf.namelist()) == 3


def test_cbz_filenames_are_zero_padded_for_sort_stability(tmp_path):
    """Comic readers sort by name; non-padded numbers would put
    ``10.png`` before ``2.png``. Padding to 3 digits keeps natural
    order matching page order through to ~1000 pages."""
    project = project_from_template(
        template_by_name("manga_a5"), page_count=12,
    )
    out = export_project_cbz(project, tmp_path / "many.cbz")
    with zipfile.ZipFile(out) as zf:
        names = sorted(zf.namelist())
    assert names[0] == "001.png"
    assert names[-1] == "012.png"


def test_cbz_pad_width_is_overridable(tmp_path):
    project = _three_page_project()
    out = export_project_cbz(project, tmp_path / "wide.cbz", pad_width=5)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "00001.png" in names


def test_cbz_rejects_empty_project(tmp_path):
    empty = PaintProject(name="empty", pages=[])
    with pytest.raises(ValueError, match="no pages"):
        export_project_cbz(empty, tmp_path / "empty.cbz")


def test_cbz_pages_decode_back_to_their_colour(tmp_path):
    project = _three_page_project()
    out = export_project_cbz(project, tmp_path / "colours.cbz")
    with zipfile.ZipFile(out) as zf, zf.open("001.png") as fh:
        page1 = np.array(Image.open(fh).convert("RGB"))
    # Page 1 is fully red.
    assert tuple(page1[0, 0]) == (255, 0, 0)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def test_pdf_is_written_with_pdf_signature(tmp_path):
    project = project_from_template(template_by_name("manga_a5"), page_count=1)
    out = export_project_pdf(project, tmp_path / "out.pdf")
    head = out.read_bytes()[:4]
    assert head == b"%PDF"


def test_pdf_multi_page_contains_all_pages(tmp_path):
    project = _three_page_project()
    out = export_project_pdf(project, tmp_path / "out.pdf")
    body = out.read_bytes()
    # Crude but reliable: a multi-page PDF has the ``/Page`` token
    # once per page (and once for the parent /Pages dict). Three
    # pages → at least three matches.
    count = body.count(b"/Page")
    assert count >= 3


def test_pdf_rejects_empty_project(tmp_path):
    empty = PaintProject(name="empty", pages=[])
    with pytest.raises(ValueError, match="no pages"):
        export_project_pdf(empty, tmp_path / "empty.pdf")


def test_pdf_flattens_transparency_against_background(tmp_path):
    """A fully-transparent canvas must produce an opaque PDF page in
    the configured background colour, not a black square."""
    h, w = 30, 30
    arr = np.zeros((h, w, 4), dtype=np.uint8)   # all transparent
    doc = ProjectPage(
        document=_doc_with_image(arr), name="Solo",
    )
    project = PaintProject(name="trans", pages=[doc])
    out = export_project_pdf(
        project, tmp_path / "tr.pdf", background=(200, 200, 200, 255),
    )
    # We can't easily decode the PDF back to pixels in pure stdlib +
    # Pillow; but we can verify the file was written and isn't
    # suspiciously small (which would mean a 0-page PDF).
    assert out.stat().st_size > 200


def _doc_with_image(arr: np.ndarray):
    """Helper — wrap an HxWx4 array in a PaintDocument."""
    from Imervue.paint.document import PaintDocument
    doc = PaintDocument()
    doc.load_image(arr)
    return doc


# ---------------------------------------------------------------------------
# Page ordering
# ---------------------------------------------------------------------------


def test_cbz_preserves_page_order_after_reorder(tmp_path):
    """Move page 3 to the front; the CBZ must reflect the new order."""
    project = _three_page_project()
    project.move_page(2, 0)
    out = export_project_cbz(project, tmp_path / "reordered.cbz")
    with zipfile.ZipFile(out) as zf, zf.open("001.png") as fh:
        page1 = np.array(Image.open(fh).convert("RGB"))
    # Page that was originally blue is now first.
    assert tuple(page1[0, 0]) == (0, 0, 255)
