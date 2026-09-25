"""Tests for print layout PDF export."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PIL import Image

from Imervue.image import print_layout

needs_reportlab = pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None, reason="reportlab is an optional dependency")


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

    @needs_reportlab
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

    @needs_reportlab
    def test_empty_layout_still_writes_single_page(self, tmp_path):
        layout = print_layout.PrintLayout(rows=1, cols=1, image_paths=[])
        out_pdf = tmp_path / "empty.pdf"
        result = print_layout.export_print_pdf(layout, out_pdf)
        assert result.exists()


class TestRoomForThePictures:
    """The dialog refuses margins and gutters that squeeze the cells to nothing."""

    @staticmethod
    def _one_column(margin_pt: float) -> print_layout.PrintLayout:
        return print_layout.PrintLayout(page_size="Letter", rows=1, cols=1, margin_pt=margin_pt,
                                        gutter_pt=0.0)

    def test_default_layout_fits(self):
        assert print_layout.leaves_room(print_layout.PrintLayout())

    def test_a_cell_one_point_wide_still_fits(self):
        # Letter is 612 pt wide: a 305.5 pt margin each side leaves exactly 1 pt.
        assert print_layout.leaves_room(self._one_column(305.5))

    def test_a_cell_under_a_point_does_not(self):
        assert not print_layout.leaves_room(self._one_column(305.6))

    def test_gutters_count_against_the_width(self):
        layout = print_layout.PrintLayout(page_size="A4", cols=10, margin_pt=0.0,
                                          gutter_pt=30 * print_layout.PT_PER_MM)
        assert not print_layout.leaves_room(layout)

    def test_landscape_swaps_which_side_runs_out(self):
        # Four 150 pt gutters (600 pt) overflow A4's 595 pt width; turned, 842 pt holds them.
        layout = print_layout.PrintLayout(page_size="A4", cols=5, margin_pt=0.0,
                                          gutter_pt=150.0)
        assert not print_layout.leaves_room(layout)
        layout.landscape = True
        assert print_layout.leaves_room(layout)

    def test_the_writer_keeps_a_one_point_floor(self):
        layout = self._one_column(400.0)
        _x, _y, cell_w, cell_h = print_layout._cell_geometry(layout, 612.0, 792.0)
        assert (cell_w, cell_h) == (1.0, 1.0)


@needs_reportlab
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
