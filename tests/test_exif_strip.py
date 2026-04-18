"""
Tests for batch EXIF strip — scanning, core strip logic, worker.

Core logic tests are pure Python (no Qt needed).
Worker tests call .run() directly and require ``qapp``.
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

from Imervue.gui.exif_strip_dialog import (
    _scan_folder,
    strip_exif,
    _StripWorker,
    _pil_format,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_with_exif(path: str) -> str:
    """Create a JPEG with EXIF metadata."""
    arr = np.full((32, 32, 3), 128, dtype=np.uint8)
    img = Image.fromarray(arr)
    exif = img.getexif()
    # Standard EXIF tags: 271=Make, 272=Model, 315=Artist
    exif[271] = "TestCamera"
    exif[272] = "TestModel"
    exif[315] = "TestArtist"
    img.save(path, format="JPEG", exif=exif.tobytes())
    return path


def _has_exif(path: str) -> bool:
    """Check if image has non-empty EXIF data."""
    img = Image.open(path)
    exif = img.getexif()
    return len(exif) > 0


# ---------------------------------------------------------------------------
# Scan folder
# ---------------------------------------------------------------------------

class TestScanFolder:
    def test_finds_images(self, tmp_path):
        for name in ["a.jpg", "b.png", "c.tiff"]:
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            fmt = {"jpg": "JPEG", "png": "PNG", "tiff": "TIFF"}
            Image.fromarray(arr).save(
                str(tmp_path / name),
                format=fmt[name.rsplit(".", 1)[1]])
        paths = _scan_folder(str(tmp_path))
        assert len(paths) == 3

    def test_ignores_gif_bmp(self, tmp_path):
        """GIF and BMP don't typically have EXIF — not included."""
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(str(tmp_path / "x.gif"))
        Image.fromarray(arr).save(str(tmp_path / "y.bmp"))
        Image.fromarray(arr).save(str(tmp_path / "z.jpg"), format="JPEG")
        paths = _scan_folder(str(tmp_path))
        assert len(paths) == 1

    def test_ignores_non_image(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hi")
        assert _scan_folder(str(tmp_path)) == []

    def test_empty_folder(self, tmp_path):
        assert _scan_folder(str(tmp_path)) == []

    def test_sorted(self, tmp_path):
        for n in ["c.jpg", "a.jpg", "b.jpg"]:
            arr = np.full((10, 10, 3), 128, dtype=np.uint8)
            Image.fromarray(arr).save(str(tmp_path / n), format="JPEG")
        names = [os.path.basename(p) for p in _scan_folder(str(tmp_path))]
        assert names == ["a.jpg", "b.jpg", "c.jpg"]


# ---------------------------------------------------------------------------
# _pil_format
# ---------------------------------------------------------------------------

class TestPilFormat:
    def test_jpg(self):
        assert _pil_format("photo.jpg") == "JPEG"

    def test_jpeg(self):
        assert _pil_format("photo.jpeg") == "JPEG"

    def test_png(self):
        assert _pil_format("image.png") == "PNG"

    def test_webp(self):
        assert _pil_format("image.webp") == "WebP"

    def test_unknown(self):
        assert _pil_format("file.xyz") is None


# ---------------------------------------------------------------------------
# strip_exif (core logic)
# ---------------------------------------------------------------------------

class TestStripExif:
    def test_strips_exif_overwrite(self, tmp_path):
        path = str(tmp_path / "photo.jpg")
        _make_jpeg_with_exif(path)
        assert _has_exif(path)

        strip_exif(path, overwrite=True)
        assert not _has_exif(path)

    def test_strips_exif_to_output(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        _make_jpeg_with_exif(src)

        out_dir = str(tmp_path / "clean")
        os.makedirs(out_dir)
        out_path = strip_exif(src, overwrite=False, output_dir=out_dir)

        assert os.path.exists(out_path)
        assert not _has_exif(out_path)
        # Original still has EXIF
        assert _has_exif(src)

    def test_output_filename_has_clean_suffix(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        _make_jpeg_with_exif(src)

        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        out_path = strip_exif(src, overwrite=False, output_dir=out_dir)
        assert "photo_clean.jpg" in out_path

    def test_png_no_crash(self, tmp_path):
        path = str(tmp_path / "img.png")
        arr = np.full((10, 10, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(path, format="PNG")
        strip_exif(path, overwrite=True)
        # Should still be a valid image
        img = Image.open(path)
        assert img.size == (10, 10)

    def test_preserves_pixel_data(self, tmp_path):
        path = str(tmp_path / "photo.png")
        arr = np.full((16, 16, 3), 200, dtype=np.uint8)
        Image.fromarray(arr).save(path, format="PNG")

        strip_exif(path, overwrite=True)
        img = Image.open(path)
        result = np.array(img)
        # PNG is lossless — pixels should match
        assert result.shape[:2] == (16, 16)
        assert np.all(result[:, :, :3] == 200)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class TestStripWorker:
    def test_strips_multiple_files(self, tmp_path):
        paths = []
        for i in range(3):
            p = str(tmp_path / f"img{i}.jpg")
            _make_jpeg_with_exif(p)
            paths.append(p)

        worker = _StripWorker(paths, overwrite=True, output_dir=None)
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(3, 0)]
        for p in paths:
            assert not _has_exif(p)

    def test_output_dir_mode(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        _make_jpeg_with_exif(src)

        out = str(tmp_path / "clean")
        os.makedirs(out)

        worker = _StripWorker([src], overwrite=False, output_dir=out)
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(1, 0)]
        # Original unchanged
        assert _has_exif(src)

    def test_abort_stops_early(self, tmp_path):
        paths = []
        for i in range(5):
            p = str(tmp_path / f"img{i}.jpg")
            _make_jpeg_with_exif(p)
            paths.append(p)

        worker = _StripWorker(paths, overwrite=True, output_dir=None)
        worker.abort()
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(0, 0)]
