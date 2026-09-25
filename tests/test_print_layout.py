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


class TestDecodeLikeTheViewer:
    """ReportLab read the path itself: portrait phone photos printed sideways."""

    @staticmethod
    def _drawn_sizes(monkeypatch):
        from reportlab.pdfgen import canvas as pdf_canvas
        sizes = []
        real = pdf_canvas.Canvas.drawImage

        def spy(self, image, *args, **kwargs):
            sizes.append(image.getSize())
            return real(self, image, *args, **kwargs)

        monkeypatch.setattr(pdf_canvas.Canvas, "drawImage", spy)
        return sizes

    def test_tagged_photo_is_placed_upright(self, tmp_path, monkeypatch):
        from _decode_samples import tagged_portrait
        sizes = self._drawn_sizes(monkeypatch)
        layout = print_layout.PrintLayout(image_paths=[str(tagged_portrait(tmp_path / "p.jpg"))])
        print_layout.export_print_pdf(layout, tmp_path / "out.pdf")
        assert sizes == [(20, 40)]

    def test_raw_is_developed(self, tmp_path, monkeypatch):
        import numpy as np

        from Imervue.gpu_image_view.images import image_loader
        monkeypatch.setattr(image_loader, "_load_raw",
                            lambda _p, thumbnail: np.full((30, 50, 3), 90, dtype=np.uint8))
        sizes = self._drawn_sizes(monkeypatch)
        layout = print_layout.PrintLayout(image_paths=[str(tmp_path / "shot.cr2")])
        print_layout.export_print_pdf(layout, tmp_path / "out.pdf")
        assert sizes == [(50, 30)]

    def test_unreadable_image_is_skipped(self, tmp_path, monkeypatch):
        bad = tmp_path / "bad.jpg"
        bad.write_bytes(b"nope")
        sizes = self._drawn_sizes(monkeypatch)
        layout = print_layout.PrintLayout(image_paths=[str(bad), str(_make_jpeg(tmp_path / "ok.jpg"))])
        assert print_layout.export_print_pdf(layout, tmp_path / "out.pdf").exists()
        assert sizes == [(40, 30)]
