"""Tests for the shared output-format helpers (incl. optional HEIC/AVIF)."""
from __future__ import annotations

import pytest
from PIL import Image

from Imervue.image import save_formats
from Imervue.image.save_formats import (
    FORMAT_EXTENSIONS,
    available_formats,
    pil_format,
    prepare_for_format,
    save_image,
)


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------


def test_extensions_include_heif():
    assert FORMAT_EXTENSIONS["HEIC"] == ".heic"
    assert FORMAT_EXTENSIONS["AVIF"] == ".avif"


def test_extensions_include_jxl():
    assert FORMAT_EXTENSIONS["JXL"] == ".jxl"


def test_available_formats_excludes_jxl_without_backend(monkeypatch):
    monkeypatch.setattr(save_formats, "ensure_jxl_opener", lambda: False)
    assert "JXL" not in available_formats()


def test_save_image_jxl_without_backend_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(save_formats, "ensure_jxl_opener", lambda: False)
    with pytest.raises(ValueError):
        save_image(Image.new("RGB", (8, 8)), str(tmp_path / "x.jxl"), "JXL")


def test_save_image_jxl_roundtrip(tmp_path):
    pytest.importorskip("pillow_jxl")
    out = tmp_path / "x.jxl"
    save_image(Image.new("RGB", (16, 16), (40, 80, 120)), str(out), "JXL", quality=80)
    assert out.exists()
    with Image.open(out) as reopened:
        reopened.load()
        assert reopened.size == (16, 16)


def test_pil_format_maps_heic_to_heif():
    assert pil_format("HEIC") == "HEIF"
    assert pil_format("AVIF") == "AVIF"
    assert pil_format("PNG") == "PNG"


# ---------------------------------------------------------------------------
# prepare_for_format
# ---------------------------------------------------------------------------


def test_prepare_jpeg_drops_alpha():
    assert prepare_for_format(Image.new("RGBA", (4, 4)), "JPEG").mode == "RGB"


def test_prepare_png_keeps_alpha():
    assert prepare_for_format(Image.new("RGBA", (4, 4)), "PNG").mode == "RGBA"


def test_prepare_exotic_mode_to_rgba():
    assert prepare_for_format(Image.new("CMYK", (4, 4)), "PNG").mode == "RGBA"


# ---------------------------------------------------------------------------
# available_formats
# ---------------------------------------------------------------------------


def test_available_formats_base_always_present():
    formats = available_formats()
    for name in ("PNG", "JPEG", "WebP", "BMP", "TIFF"):
        assert name in formats


def test_available_formats_excludes_heif_without_backend(monkeypatch):
    monkeypatch.setattr(save_formats, "ensure_heif_opener", lambda: False)
    formats = available_formats()
    assert "HEIC" not in formats
    assert "AVIF" not in formats


# ---------------------------------------------------------------------------
# save_image
# ---------------------------------------------------------------------------


def test_save_image_png_roundtrip(tmp_path):
    out = tmp_path / "x.png"
    save_image(Image.new("RGB", (8, 8), (10, 20, 30)), str(out), "PNG")
    assert out.exists()
    with Image.open(out) as reopened:
        assert reopened.size == (8, 8)


def test_save_image_jpeg_with_quality(tmp_path):
    out = tmp_path / "x.jpg"
    save_image(Image.new("RGBA", (8, 8), (10, 20, 30, 255)), str(out), "JPEG", quality=70)
    assert out.exists()


def test_save_image_extra_dpi_applied(tmp_path):
    out = tmp_path / "x.jpg"
    save_image(Image.new("RGB", (8, 8)), str(out), "JPEG", quality=90,
               extra={"dpi": (96, 96)})
    with Image.open(out) as reopened:
        assert reopened.info.get("dpi") == (96, 96)


def test_save_image_heic_without_backend_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(save_formats, "ensure_heif_opener", lambda: False)
    with pytest.raises(ValueError):
        save_image(Image.new("RGB", (8, 8)), str(tmp_path / "x.heic"), "HEIC")


@pytest.mark.parametrize(("fmt", "ext"), [("HEIC", ".heic"), ("AVIF", ".avif")])
def test_save_image_heif_roundtrip(tmp_path, fmt, ext):
    pytest.importorskip("pillow_heif")
    out = tmp_path / f"x{ext}"
    save_image(Image.new("RGB", (16, 16), (40, 80, 120)), str(out), fmt, quality=80)
    assert out.exists()
    with Image.open(out) as reopened:
        reopened.load()
        assert reopened.size == (16, 16)


class TestSavingOverAnExistingFile:
    """Pillow opens a path with w+b: a failed save used to leave the old file truncated."""

    def test_a_failed_save_leaves_the_old_file_whole(self, tmp_path, monkeypatch):
        target = tmp_path / "photo.jpg"
        Image.new("RGB", (4, 4), (10, 20, 30)).save(target)
        before = target.read_bytes()

        def half_written(self, fp, *args, **kwargs):
            with open(fp, "wb") as fh:
                fh.write(b"\xff\xd8 partial")
            raise OSError("disk full")

        monkeypatch.setattr(Image.Image, "save", half_written)
        with pytest.raises(OSError, match="disk full"):
            save_image(Image.new("RGB", (4, 4)), str(target), "JPEG", 90)
        assert target.read_bytes() == before
        assert sorted(p.name for p in tmp_path.iterdir()) == ["photo.jpg"]

    def test_a_save_over_an_existing_file_replaces_it(self, tmp_path):
        target = tmp_path / "photo.png"
        Image.new("RGB", (4, 4), (0, 0, 0)).save(target)
        save_image(Image.new("RGB", (6, 2), (255, 0, 0)), target, "PNG")
        with Image.open(target) as saved:
            assert saved.size == (6, 2)
            assert saved.getpixel((0, 0)) == (255, 0, 0)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["photo.png"]

    def test_a_file_object_is_written_in_place(self):
        import io
        buffer = io.BytesIO()
        save_image(Image.new("RGB", (3, 3)), buffer, "PNG")
        assert buffer.getvalue().startswith(b"\x89PNG")
