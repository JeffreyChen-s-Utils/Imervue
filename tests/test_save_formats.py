"""Tests for the shared output-format helpers (incl. HEIC / AVIF / JXL)."""
from __future__ import annotations

import io
from itertools import product

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


@pytest.mark.parametrize("availability", list(product((False, True), repeat=3)))
def test_optional_format_combinations_keep_order_and_probe_once(monkeypatch, availability):
    probes = ("ensure_heif_opener", "avif_available", "ensure_jxl_opener")
    names = ("HEIC", "AVIF", "JXL")
    calls = []
    for name, probe, supported in zip(names, probes, availability, strict=True):
        def available(name=name, supported=supported):
            calls.append(name)
            return supported
        monkeypatch.setattr(save_formats, probe, available)
    expected = ["PNG", "JPEG", "WebP", "BMP", "TIFF"]
    expected.extend(name for name, supported in zip(names, availability, strict=True) if supported)
    assert available_formats() == expected
    assert calls == list(names)


@pytest.mark.parametrize("format_name", ["PNG", "HEIC", "AVIF", "JXL"])
def test_save_probes_only_requested_backend(monkeypatch, format_name):
    probes = {"HEIC": "ensure_heif_opener", "AVIF": "avif_available", "JXL": "ensure_jxl_opener"}
    calls, saved = [], []
    for name, probe in probes.items():
        def available(name=name):
            calls.append(name)
            return True
        monkeypatch.setattr(save_formats, probe, available)
    monkeypatch.setattr(Image.Image, "save", lambda self, fp, **kwargs: saved.append((fp, kwargs)))
    output = io.BytesIO()
    save_image(Image.new("RGB", (2, 2)), output, format_name)
    assert calls == ([] if format_name == "PNG" else [format_name])
    assert saved == [(output, {"format": "HEIF" if format_name == "HEIC" else format_name})]


@pytest.mark.parametrize(("format_name", "probe", "message"), [
    ("HEIC", "ensure_heif_opener", "HEIC output requires the pillow-heif package."),
    ("AVIF", "avif_available", "AVIF output requires a Pillow built with libavif."),
    ("JXL", "ensure_jxl_opener", "JXL output requires the pillow-jxl-plugin package."),
])
def test_missing_backend_preserves_existing_output(monkeypatch, tmp_path, format_name, probe, message):
    monkeypatch.setattr(save_formats, probe, lambda: False)
    output = tmp_path / "existing.image"
    output.write_bytes(b"original")
    with pytest.raises(ValueError) as error:
        save_image(Image.new("RGB", (2, 2)), output, format_name)
    assert str(error.value) == message
    assert output.read_bytes() == b"original"


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


def test_available_formats_excludes_heic_without_backend(monkeypatch):
    monkeypatch.setattr(save_formats, "ensure_heif_opener", lambda: False)
    monkeypatch.setattr(save_formats, "avif_available", lambda: True)
    formats = available_formats()
    assert "HEIC" not in formats
    assert "AVIF" in formats      # Pillow's own: pillow-heif 1.x has no AVIF


def test_available_formats_excludes_avif_from_a_pillow_without_libavif(monkeypatch):
    monkeypatch.setattr(save_formats, "ensure_heif_opener", lambda: True)
    monkeypatch.setattr(save_formats, "avif_available", lambda: False)
    formats = available_formats()
    assert "AVIF" not in formats
    assert "HEIC" in formats


def test_available_formats_order(monkeypatch):
    monkeypatch.setattr(save_formats, "ensure_heif_opener", lambda: True)
    monkeypatch.setattr(save_formats, "avif_available", lambda: True)
    monkeypatch.setattr(save_formats, "ensure_jxl_opener", lambda: True)
    assert available_formats() == ["PNG", "JPEG", "WebP", "BMP", "TIFF", "HEIC", "AVIF", "JXL"]


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
    with pytest.raises(ValueError, match="pillow-heif"):
        save_image(Image.new("RGB", (8, 8)), str(tmp_path / "x.heic"), "HEIC")
    assert not (tmp_path / "x.heic").exists()


def test_save_image_avif_without_pillow_heif(monkeypatch, tmp_path):
    """AVIF used to demand pillow-heif, which has not written AVIF since 1.0."""
    monkeypatch.setattr(save_formats, "ensure_heif_opener", lambda: False)
    out = tmp_path / "x.avif"
    save_image(Image.new("RGBA", (16, 16), (40, 80, 120, 200)), str(out), "AVIF", quality=80)
    with Image.open(out) as reopened:
        reopened.load()
        assert (reopened.format, reopened.size, reopened.mode) == ("AVIF", (16, 16), "RGBA")


def test_save_image_avif_from_a_pillow_without_libavif_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(save_formats, "avif_available", lambda: False)
    with pytest.raises(ValueError, match="libavif"):
        save_image(Image.new("RGB", (8, 8)), str(tmp_path / "x.avif"), "AVIF")
    assert not (tmp_path / "x.avif").exists()


def test_save_image_heic_roundtrip(tmp_path):
    pytest.importorskip("pillow_heif")
    out = tmp_path / "x.heic"
    save_image(Image.new("RGB", (16, 16), (40, 80, 120)), str(out), "HEIC", quality=80)
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
