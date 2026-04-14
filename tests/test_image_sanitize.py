"""
Tests for image sanitizer — scanning, core sanitize logic, naming, worker.
"""
from __future__ import annotations

import os
import re
from datetime import datetime

import numpy as np
import pytest
from PIL import Image

from Imervue.gui.image_sanitize_dialog import (
    _scan_folder,
    _get_image_date,
    _generate_name,
    _compute_upscale_params,
    sanitize_image,
    TARGET_RESOLUTIONS,
    _SanitizeWorker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image(path: str, fmt: str = "JPEG", size=(32, 32),
                with_exif: bool = False) -> str:
    arr = np.full((*size, 3), 128, dtype=np.uint8)
    img = Image.fromarray(arr)
    kwargs: dict = {"format": fmt}
    if with_exif and fmt == "JPEG":
        exif = img.getexif()
        exif[271] = "TestCamera"
        exif[36867] = "2025:06:15 10:30:00"
        kwargs["exif"] = exif.tobytes()
    img.save(path, **kwargs)
    return path


# ---------------------------------------------------------------------------
# Scan folder
# ---------------------------------------------------------------------------

class TestScanFolder:
    def test_finds_images(self, tmp_path):
        for name in ["a.jpg", "b.png", "c.bmp"]:
            fmt = {"jpg": "JPEG", "png": "PNG", "bmp": "BMP"}
            _make_image(str(tmp_path / name), fmt[name.rsplit(".", 1)[1]])
        paths = _scan_folder(str(tmp_path))
        assert len(paths) == 3

    def test_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        _make_image(str(tmp_path / "a.png"), "PNG")
        _make_image(str(sub / "b.png"), "PNG")
        assert len(_scan_folder(str(tmp_path), recursive=False)) == 1
        assert len(_scan_folder(str(tmp_path), recursive=True)) == 2

    def test_ignores_non_image(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hi")
        assert _scan_folder(str(tmp_path)) == []

    def test_empty_folder(self, tmp_path):
        assert _scan_folder(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# _get_image_date
# ---------------------------------------------------------------------------

class TestGetImageDate:
    def test_from_exif(self, tmp_path):
        path = str(tmp_path / "photo.jpg")
        _make_image(path, "JPEG", with_exif=True)
        dt = _get_image_date(path)
        assert dt.year == 2025
        assert dt.month == 6
        assert dt.day == 15

    def test_fallback_mtime(self, tmp_path):
        path = str(tmp_path / "photo.png")
        _make_image(path, "PNG")
        dt = _get_image_date(path)
        # Should be close to now
        assert abs((datetime.now() - dt).total_seconds()) < 60


# ---------------------------------------------------------------------------
# _generate_name
# ---------------------------------------------------------------------------

class TestGenerateName:
    def test_format(self):
        dt = datetime(2026, 4, 14, 12, 0, 0)
        name = _generate_name(dt, 8, ".png")
        assert name.startswith("20260414_")
        assert name.endswith(".png")
        # date(8) + underscore(1) + rand(8) + ext(4) = 21
        assert len(name) == 21

    def test_rand_length(self):
        dt = datetime(2026, 1, 1)
        name = _generate_name(dt, 12, ".jpg")
        # 20260101_ + 12 chars + .jpg
        rand_part = name[len("20260101_"):name.rfind(".")]
        assert len(rand_part) == 12

    def test_only_lowercase_and_digits(self):
        dt = datetime(2026, 1, 1)
        for _ in range(20):
            name = _generate_name(dt, 16, ".png")
            rand_part = name[len("20260101_"):name.rfind(".")]
            assert re.match(r"^[a-z0-9]+$", rand_part)


# ---------------------------------------------------------------------------
# sanitize_image (core logic)
# ---------------------------------------------------------------------------

class TestSanitizeImage:
    def test_removes_exif(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG", with_exif=True)

        out = sanitize_image(src, out_dir, "same")
        img = Image.open(out)
        assert len(img.getexif()) == 0

    def test_preserves_pixels_png(self, tmp_path):
        src = str(tmp_path / "img.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        arr = np.full((16, 16, 3), 200, dtype=np.uint8)
        Image.fromarray(arr).save(src, format="PNG")

        out = sanitize_image(src, out_dir, "same")
        result = np.array(Image.open(out))
        assert np.all(result[:, :, :3] == 200)

    def test_output_renamed_with_date(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG", with_exif=True)

        out = sanitize_image(src, out_dir, "same")
        basename = os.path.basename(out)
        # Should start with 20250615 (from EXIF date)
        assert basename.startswith("20250615_")

    def test_format_conversion(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG")

        out = sanitize_image(src, out_dir, ".png")
        assert out.endswith(".png")
        img = Image.open(out)
        assert img.format == "PNG"

    def test_same_format_keeps_ext(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG")

        out = sanitize_image(src, out_dir, "same")
        assert out.endswith(".jpg")

    def test_no_collision(self, tmp_path):
        src = str(tmp_path / "photo.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "PNG")

        # Generate multiple — all should be unique
        outputs = set()
        for _ in range(5):
            out = sanitize_image(src, out_dir, "same")
            outputs.add(out)
        assert len(outputs) == 5

    def test_jpeg_rgba_converted(self, tmp_path):
        """RGBA source saved as JPEG should be converted to RGB."""
        src = str(tmp_path / "rgba.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        arr = np.full((10, 10, 4), 128, dtype=np.uint8)
        Image.fromarray(arr, "RGBA").save(src, format="PNG")

        out = sanitize_image(src, out_dir, ".jpg")
        img = Image.open(out)
        assert img.mode == "RGB"

    def test_no_upscale_when_already_large(self, tmp_path):
        """Image already at target size should not be upscaled."""
        src = str(tmp_path / "big.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        # np size is (h, w) → PIL size is (w, h) = (1500, 2000)
        _make_image(src, "PNG", size=(2000, 1500))

        out = sanitize_image(src, out_dir, "same", target_long_edge=1920)
        img = Image.open(out)
        # long edge is 2000 >= 1920, no upscale → original size preserved
        assert img.size == (1500, 2000)


# ---------------------------------------------------------------------------
# _compute_upscale_params
# ---------------------------------------------------------------------------

class TestComputeUpscaleParams:
    def test_no_upscale_when_zero(self):
        model, fw, fh = _compute_upscale_params(800, 600, 0)
        assert model == ""
        assert (fw, fh) == (800, 600)

    def test_no_upscale_when_large_enough(self):
        model, fw, fh = _compute_upscale_params(1920, 1080, 1920)
        assert model == ""
        assert (fw, fh) == (1920, 1080)

    def test_selects_x2_for_small_ratio(self):
        # 1280 -> 1920 = 1.5x ratio, should pick x2
        model, fw, fh = _compute_upscale_params(1280, 720, 1920)
        assert model == "realesrgan-x2plus"
        assert fw == 1920
        assert fh == 1080

    def test_selects_x4_for_large_ratio(self):
        # 640 -> 3840 = 6x ratio, should pick x4
        model, fw, fh = _compute_upscale_params(640, 480, 3840)
        assert model == "realesrgan-x4plus"
        assert fw == 3840
        assert fh == 2880

    def test_portrait_aspect_ratio(self):
        # Portrait: height is long edge
        model, fw, fh = _compute_upscale_params(720, 1280, 1920)
        assert model == "realesrgan-x2plus"
        assert fh == 1920
        assert fw == 1080

    def test_square(self):
        model, fw, fh = _compute_upscale_params(500, 500, 1920)
        assert fw == 1920
        assert fh == 1920


# ---------------------------------------------------------------------------
# TARGET_RESOLUTIONS
# ---------------------------------------------------------------------------

class TestTargetResolutions:
    def test_first_is_no_upscale(self):
        assert TARGET_RESOLUTIONS[0][2] == 0

    def test_all_have_positive_or_zero_px(self):
        for key, label, px in TARGET_RESOLUTIONS:
            assert px >= 0

    def test_sorted_ascending(self):
        values = [px for _, _, px in TARGET_RESOLUTIONS]
        assert values == sorted(values)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class TestSanitizeWorker:
    def test_sanitizes_multiple(self, tmp_path):
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        paths = []
        for i in range(3):
            p = str(tmp_path / f"img{i}.jpg")
            _make_image(p, "JPEG", with_exif=True)
            paths.append(p)

        worker = _SanitizeWorker(paths, out_dir, "same", 8, 95, 6)
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(3, 0)]
        output_files = os.listdir(out_dir)
        assert len(output_files) == 3

    def test_abort_stops_early(self, tmp_path):
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        paths = []
        for i in range(5):
            p = str(tmp_path / f"img{i}.png")
            _make_image(p, "PNG")
            paths.append(p)

        worker = _SanitizeWorker(paths, out_dir, "same", 8, 95, 6)
        worker.abort()
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(0, 0)]
