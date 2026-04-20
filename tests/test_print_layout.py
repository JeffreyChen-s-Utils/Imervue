"""Tests for print layout PDF export."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("reportlab")

from PIL import Image

from Imervue.image import print_layout


def _make_jpeg(path: Path) -> Path:
    Image.new("RGB", (40, 30), color=(200, 100, 50)).save(path, "JPEG")
    return path


class TestPrintLayout:
    def test_page_dimensions_portrait_vs_landscape(self):
        portrait = print_layout.PrintLayout(page_size="A4", landscape=False)
        landscape = print_layout.PrintLayout(page_size="A4", landscape=True)
        pw, ph = print_layout._page_dimensions(portrait)
        lw, lh = print_layout._page_dimensions(landscape)
        assert pw < ph
        assert lw > lh

    def test_unknown_page_size_falls_back(self):
        layout = print_layout.PrintLayout(page_size="bogus")
        dims = print_layout._page_dimensions(layout)
        assert dims == print_layout.PAGE_SIZES["A4"]

    def test_export_pdf_creates_file(self, tmp_path):
        img1 = _make_jpeg(tmp_path / "a.jpg")
        img2 = _make_jpeg(tmp_path / "b.jpg")
        layout = print_layout.PrintLayout(
            page_size="A4", rows=2, cols=1,
            image_paths=[str(img1), str(img2)],
            crop_marks=True,
        )
        out_pdf = tmp_path / "sheet.pdf"
        result = print_layout.export_print_pdf(layout, out_pdf)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_empty_layout_still_writes_single_page(self, tmp_path):
        layout = print_layout.PrintLayout(rows=1, cols=1, image_paths=[])
        out_pdf = tmp_path / "empty.pdf"
        result = print_layout.export_print_pdf(layout, out_pdf)
        assert result.exists()
