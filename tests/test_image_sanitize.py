"""
Tests for image sanitizer — scanning, date extraction, naming,
core sanitize logic, upscale parameter selection, and worker thread.

Core logic tests are pure Python (no Qt / ONNX needed).
Worker tests call .run() directly (synchronous, no event loop required).
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
    _PIL_FORMAT_MAP,
    _IMAGE_EXTS,
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
        exif[272] = "TestModel"
        exif[36867] = "2025:06:15 10:30:00"  # DateTimeOriginal
        kwargs["exif"] = exif.tobytes()
    img.save(path, **kwargs)
    return path


def _make_rgba_image(path: str, fmt: str = "PNG", size=(32, 32)) -> str:
    arr = np.full((*size, 4), 180, dtype=np.uint8)
    Image.fromarray(arr, "RGBA").save(path, format=fmt)
    return path


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_image_exts_are_lowercase(self):
        for ext in _IMAGE_EXTS:
            assert ext == ext.lower()
            assert ext.startswith(".")

    def test_pil_format_map_covers_common_exts(self):
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"):
            assert ext in _PIL_FORMAT_MAP

    def test_pil_format_map_values_are_valid(self):
        valid_fmts = {"JPEG", "PNG", "TIFF", "WebP", "BMP"}
        for fmt in _PIL_FORMAT_MAP.values():
            assert fmt in valid_fmts


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

    def test_recursive_nested(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        _make_image(str(deep / "deep.png"), "PNG")
        assert len(_scan_folder(str(tmp_path), recursive=True)) == 1

    def test_ignores_non_image(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hi")
        (tmp_path / "data.json").write_text("{}")
        assert _scan_folder(str(tmp_path)) == []

    def test_empty_folder(self, tmp_path):
        assert _scan_folder(str(tmp_path)) == []

    def test_sorted_by_name(self, tmp_path):
        for n in ["c.jpg", "a.jpg", "b.jpg"]:
            _make_image(str(tmp_path / n), "JPEG")
        names = [os.path.basename(p) for p in _scan_folder(str(tmp_path))]
        assert names == ["a.jpg", "b.jpg", "c.jpg"]

    def test_case_insensitive_ext(self, tmp_path):
        p = str(tmp_path / "photo.JPG")
        _make_image(p, "JPEG")
        assert len(_scan_folder(str(tmp_path))) == 1

    def test_all_supported_formats(self, tmp_path):
        fmts = {"img.jpg": "JPEG", "img.png": "PNG", "img.bmp": "BMP",
                "img.webp": "WebP", "img.tiff": "TIFF"}
        for name, fmt in fmts.items():
            _make_image(str(tmp_path / name), fmt)
        assert len(_scan_folder(str(tmp_path))) == 5

    def test_nonexistent_folder(self):
        assert _scan_folder("/nonexistent/path/12345") == []


# ---------------------------------------------------------------------------
# _get_image_date
# ---------------------------------------------------------------------------

class TestGetImageDate:
    def test_from_exif_datetimeoriginal(self, tmp_path):
        path = str(tmp_path / "photo.jpg")
        _make_image(path, "JPEG", with_exif=True)
        dt = _get_image_date(path)
        assert dt == datetime(2025, 6, 15, 10, 30, 0)

    def test_fallback_mtime(self, tmp_path):
        path = str(tmp_path / "photo.png")
        _make_image(path, "PNG")
        dt = _get_image_date(path)
        assert abs((datetime.now() - dt).total_seconds()) < 60

    def test_returns_datetime_type(self, tmp_path):
        path = str(tmp_path / "photo.png")
        _make_image(path, "PNG")
        dt = _get_image_date(path)
        assert isinstance(dt, datetime)

    def test_corrupt_file_returns_now(self, tmp_path):
        path = str(tmp_path / "bad.jpg")
        (tmp_path / "bad.jpg").write_bytes(b"not an image")
        dt = _get_image_date(path)
        assert isinstance(dt, datetime)
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
        rand_part = name[len("20260101_"):name.rfind(".")]
        assert len(rand_part) == 12

    def test_min_rand_length(self):
        dt = datetime(2026, 1, 1)
        name = _generate_name(dt, 4, ".png")
        rand_part = name[len("20260101_"):name.rfind(".")]
        assert len(rand_part) == 4

    def test_only_lowercase_and_digits(self):
        dt = datetime(2026, 1, 1)
        for _ in range(20):
            name = _generate_name(dt, 16, ".png")
            rand_part = name[len("20260101_"):name.rfind(".")]
            assert re.match(r"^[a-z0-9]+$", rand_part)

    def test_uniqueness(self):
        dt = datetime(2026, 1, 1)
        names = {_generate_name(dt, 16, ".png") for _ in range(100)}
        assert len(names) == 100  # all should be unique

    def test_various_extensions(self):
        dt = datetime(2026, 1, 1)
        for ext in (".png", ".jpg", ".webp", ".tiff", ".bmp"):
            name = _generate_name(dt, 8, ext)
            assert name.endswith(ext)


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

    def test_removes_all_metadata_keys(self, tmp_path):
        """Verify that .info dict is empty (no ICC, no XMP, etc.)."""
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG", with_exif=True)

        out = sanitize_image(src, out_dir, "same")
        img = Image.open(out)
        # .info should not contain exif, icc_profile, or xmp
        assert "exif" not in img.info
        assert "icc_profile" not in img.info

    def test_preserves_pixels_png(self, tmp_path):
        src = str(tmp_path / "img.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        arr = np.full((16, 16, 3), 200, dtype=np.uint8)
        Image.fromarray(arr).save(src, format="PNG")

        out = sanitize_image(src, out_dir, "same")
        result = np.array(Image.open(out))
        # LSB is scrambled to defeat stealth steganography — allow ±1.
        assert np.all(np.abs(result[:, :, :3].astype(int) - 200) <= 1)

    def test_preserves_dimensions(self, tmp_path):
        src = str(tmp_path / "img.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "PNG", size=(100, 80))

        out = sanitize_image(src, out_dir, "same")
        img = Image.open(out)
        assert img.size == (80, 100)  # (w, h) from numpy (h, w)

    def test_output_renamed_with_date(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG", with_exif=True)

        out = sanitize_image(src, out_dir, "same")
        basename = os.path.basename(out)
        assert basename.startswith("20250615_")

    def test_output_name_has_random_part(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG")

        out = sanitize_image(src, out_dir, "same", rand_len=10)
        basename = os.path.basename(out)
        # yyyymmdd_ + 10 chars + .jpg
        stem = basename[:basename.rfind(".")]
        rand_part = stem.split("_", 1)[1]
        assert len(rand_part) == 10

    def test_format_conversion_jpg_to_png(self, tmp_path):
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG")

        out = sanitize_image(src, out_dir, ".png")
        assert out.endswith(".png")
        img = Image.open(out)
        assert img.format == "PNG"

    def test_format_conversion_png_to_webp(self, tmp_path):
        src = str(tmp_path / "photo.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "PNG")

        out = sanitize_image(src, out_dir, ".webp")
        assert out.endswith(".webp")

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

        outputs = set()
        for _ in range(10):
            out = sanitize_image(src, out_dir, "same")
            outputs.add(out)
        assert len(outputs) == 10

    def test_jpeg_rgba_converted(self, tmp_path):
        """RGBA source saved as JPEG should be converted to RGB."""
        src = str(tmp_path / "rgba.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_rgba_image(src)

        out = sanitize_image(src, out_dir, ".jpg")
        img = Image.open(out)
        assert img.mode == "RGB"

    def test_no_upscale_when_already_large(self, tmp_path):
        """Image already at target size should not be upscaled."""
        src = str(tmp_path / "big.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "PNG", size=(2000, 1500))

        out = sanitize_image(src, out_dir, "same", target_long_edge=1920)
        img = Image.open(out)
        assert img.size == (1500, 2000)

    def test_no_upscale_without_session(self, tmp_path):
        """target_long_edge set but no ort_session and no trad → skip upscale."""
        src = str(tmp_path / "small.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "PNG", size=(100, 80))

        out = sanitize_image(src, out_dir, "same",
                             target_long_edge=1920, ort_session=None)
        img = Image.open(out)
        assert img.size == (80, 100)  # unchanged

    def test_traditional_lanczos_upscale(self, tmp_path):
        """Traditional Lanczos upscale should resize to target long edge."""
        src = str(tmp_path / "small.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "PNG", size=(100, 80))  # numpy (h, w) → PIL (80, 100)

        out = sanitize_image(src, out_dir, "same",
                             target_long_edge=200,
                             trad_resampling=Image.Resampling.LANCZOS)
        img = Image.open(out)
        # numpy (100,80) → PIL (w=80, h=100), long edge=100→200
        assert img.size == (160, 200)

    def test_traditional_nearest_upscale(self, tmp_path):
        """Nearest-neighbor upscale preserves exact pixel colors."""
        src = str(tmp_path / "pixel.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        arr = np.full((4, 4, 3), 42, dtype=np.uint8)
        Image.fromarray(arr).save(src, format="PNG")

        out = sanitize_image(src, out_dir, "same",
                             target_long_edge=8,
                             trad_resampling=Image.Resampling.NEAREST)
        img = Image.open(out)
        assert img.size == (8, 8)
        arr = np.asarray(img)
        # LSB is scrambled to defeat stealth steganography — allow ±1.
        assert np.all(np.abs(arr[..., :3].astype(int) - 42) <= 1)

    def test_traditional_no_upscale_when_large_enough(self, tmp_path):
        """Traditional upscale should skip when image already meets target."""
        src = str(tmp_path / "big.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "PNG", size=(200, 300))

        out = sanitize_image(src, out_dir, "same",
                             target_long_edge=200,
                             trad_resampling=Image.Resampling.LANCZOS)
        img = Image.open(out)
        assert img.size == (300, 200)  # unchanged

    def test_traditional_removes_metadata(self, tmp_path):
        """Traditional upscale should still strip EXIF."""
        src = str(tmp_path / "photo.jpg")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "JPEG", size=(50, 40), with_exif=True)

        out = sanitize_image(src, out_dir, ".png",
                             target_long_edge=100,
                             trad_resampling=Image.Resampling.LANCZOS)
        img = Image.open(out)
        assert len(img.getexif()) == 0
        assert img.size[0] == 100 or img.size[1] == 100

    def test_jpeg_quality_parameter(self, tmp_path):
        """Different JPEG quality should produce different file sizes."""
        src = str(tmp_path / "photo.jpg")
        # Use random noise so JPEG compression has something to work with
        rng = np.random.RandomState(42)
        arr = rng.randint(0, 256, (200, 200, 3), dtype=np.uint8)
        Image.fromarray(arr).save(src, format="JPEG")

        out_hi = str(tmp_path / "out_hi")
        out_lo = str(tmp_path / "out_lo")
        os.makedirs(out_hi)
        os.makedirs(out_lo)

        path_hi = sanitize_image(src, out_hi, "same", jpeg_quality=95)
        path_lo = sanitize_image(src, out_lo, "same", jpeg_quality=10)
        assert os.path.getsize(path_hi) > os.path.getsize(path_lo)

    def test_output_is_valid_image(self, tmp_path):
        """Output can be reopened and has valid pixel data."""
        src = str(tmp_path / "photo.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        _make_image(src, "PNG", size=(50, 50))

        out = sanitize_image(src, out_dir, "same")
        img = Image.open(out)
        arr = np.array(img)
        assert arr.shape[0] == 50
        assert arr.shape[1] == 50


# ---------------------------------------------------------------------------
# _compute_upscale_params
# ---------------------------------------------------------------------------

class TestComputeUpscaleParams:
    def test_no_upscale_when_zero(self):
        model, fw, fh = _compute_upscale_params(800, 600, 0)
        assert model == ""
        assert (fw, fh) == (800, 600)

    def test_no_upscale_when_negative(self):
        model, fw, fh = _compute_upscale_params(800, 600, -100)
        assert model == ""

    def test_no_upscale_when_large_enough(self):
        model, fw, fh = _compute_upscale_params(1920, 1080, 1920)
        assert model == ""
        assert (fw, fh) == (1920, 1080)

    def test_no_upscale_when_larger_than_target(self):
        model, fw, fh = _compute_upscale_params(4000, 3000, 1920)
        assert model == ""

    def test_selects_x2_for_small_ratio(self):
        model, fw, fh = _compute_upscale_params(1280, 720, 1920)
        assert model == "realesrgan-x2plus"
        assert fw == 1920
        assert fh == 1080

    def test_selects_x2_at_boundary(self):
        # ratio = 2.0 exactly → x2
        model, fw, fh = _compute_upscale_params(960, 540, 1920)
        assert model == "realesrgan-x2plus"

    def test_selects_x4_for_large_ratio(self):
        model, fw, fh = _compute_upscale_params(640, 480, 3840)
        assert model == "realesrgan-x4plus"
        assert fw == 3840
        assert fh == 2880

    def test_selects_x4_when_ratio_above_2(self):
        # 800 → 1920 = 2.4x, needs x4
        model, fw, fh = _compute_upscale_params(800, 600, 1920)
        assert model == "realesrgan-x4plus"

    def test_portrait_aspect_ratio(self):
        model, fw, fh = _compute_upscale_params(720, 1280, 1920)
        assert model == "realesrgan-x2plus"
        assert fh == 1920
        assert fw == 1080

    def test_square(self):
        model, fw, fh = _compute_upscale_params(500, 500, 1920)
        assert fw == 1920
        assert fh == 1920

    def test_extreme_portrait(self):
        model, fw, fh = _compute_upscale_params(100, 1000, 1920)
        assert fh == 1920
        assert fw == 192  # 100 * 1920 / 1000

    def test_returns_valid_model_keys(self):
        from Imervue.gui.ai_upscale_dialog import UPSCALE_MODELS
        for w, h, target in [(640, 480, 1920), (1280, 720, 3840)]:
            model, _, _ = _compute_upscale_params(w, h, target)
            if model:
                assert model in UPSCALE_MODELS


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

    def test_all_entries_are_three_tuples(self):
        for entry in TARGET_RESOLUTIONS:
            assert len(entry) == 3
            key, label, px = entry
            assert isinstance(key, str)
            assert isinstance(label, str)
            assert isinstance(px, int)

    def test_common_resolutions_present(self):
        pxs = {px for _, _, px in TARGET_RESOLUTIONS}
        assert 1920 in pxs   # 1080p
        assert 3840 in pxs   # 4K
        assert 7680 in pxs   # 8K

    def test_keys_are_valid_i18n_keys(self):
        for key, _, _ in TARGET_RESOLUTIONS:
            assert key.startswith("sanitize_res_")


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

    def test_output_files_have_no_exif(self, tmp_path):
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        paths = []
        for i in range(2):
            p = str(tmp_path / f"img{i}.jpg")
            _make_image(p, "JPEG", with_exif=True)
            paths.append(p)

        worker = _SanitizeWorker(paths, out_dir, "same", 8, 95, 6)
        worker.run()

        for f in os.listdir(out_dir):
            img = Image.open(os.path.join(out_dir, f))
            assert len(img.getexif()) == 0

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

    def test_progress_signal_emitted(self, tmp_path):
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        paths = []
        for i in range(3):
            p = str(tmp_path / f"img{i}.png")
            _make_image(p, "PNG")
            paths.append(p)

        worker = _SanitizeWorker(paths, out_dir, "same", 8, 95, 6)
        progress_log = []
        worker.progress.connect(
            lambda cur, tot, name: progress_log.append((cur, tot, name)))
        worker.run()

        assert len(progress_log) == 3
        assert progress_log[-1][0] == 3  # last current == total
        assert progress_log[-1][1] == 3

    def test_format_conversion_in_worker(self, tmp_path):
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        p = str(tmp_path / "img.jpg")
        _make_image(p, "JPEG")

        worker = _SanitizeWorker([p], out_dir, ".png", 8, 95, 6)
        worker.run()

        files = os.listdir(out_dir)
        assert len(files) == 1
        assert files[0].endswith(".png")

    def test_traditional_upscale_in_worker(self, tmp_path):
        """Worker with trad:lanczos should upscale without ONNX."""
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        p = str(tmp_path / "small.png")
        _make_image(p, "PNG", size=(50, 40))

        worker = _SanitizeWorker(
            [p], out_dir, "same", 8, 95, 6,
            target_long_edge=100, model_key="trad:lanczos")
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(1, 0)]
        files = os.listdir(out_dir)
        assert len(files) == 1
        img = Image.open(os.path.join(out_dir, files[0]))
        # Long edge should be 100
        assert max(img.size) == 100

    def test_traditional_nearest_in_worker(self, tmp_path):
        """Worker with trad:nearest should upscale using nearest neighbor."""
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        p = str(tmp_path / "small.png")
        _make_image(p, "PNG", size=(10, 10))

        worker = _SanitizeWorker(
            [p], out_dir, "same", 8, 95, 6,
            target_long_edge=20, model_key="trad:nearest")
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(1, 0)]
        files = os.listdir(out_dir)
        img = Image.open(os.path.join(out_dir, files[0]))
        assert img.size == (20, 20)

    def test_handles_corrupt_file_gracefully(self, tmp_path):
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        bad = str(tmp_path / "bad.jpg")
        (tmp_path / "bad.jpg").write_bytes(b"not an image at all")
        good = str(tmp_path / "good.png")
        _make_image(good, "PNG")

        worker = _SanitizeWorker([bad, good], out_dir, "same", 8, 95, 6)
        results = []
        worker.result_ready.connect(lambda s, f: results.append((s, f)))
        worker.run()

        assert results == [(1, 1)]  # 1 success, 1 failed

    def test_recursive_mirrors_subfolders(self, tmp_path):
        """With src_root set, output preserves the source subfolder layout."""
        src = tmp_path / "src"
        (src / "a" / "b").mkdir(parents=True)
        (src / "c").mkdir(parents=True)
        p_root = str(src / "root.png")
        p_a = str(src / "a" / "inner.png")
        p_ab = str(src / "a" / "b" / "deep.png")
        p_c = str(src / "c" / "sibling.png")
        for p in (p_root, p_a, p_ab, p_c):
            _make_image(p, "PNG")

        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        worker = _SanitizeWorker(
            [p_root, p_a, p_ab, p_c],
            out_dir, "same", 8, 95, 6,
            src_root=str(src))
        worker.run()

        assert len(os.listdir(out_dir)) == 3  # root.png flat + 'a' + 'c'
        assert any(f.endswith(".png") for f in os.listdir(out_dir))
        assert len(os.listdir(os.path.join(out_dir, "a"))) == 2  # inner + b/
        assert len(os.listdir(os.path.join(out_dir, "a", "b"))) == 1
        assert len(os.listdir(os.path.join(out_dir, "c"))) == 1

    def test_no_src_root_is_flat(self, tmp_path):
        """Without src_root all outputs land flat in output_dir (backcompat)."""
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        p1 = str(src / "a.png")
        p2 = str(src / "sub" / "b.png")
        _make_image(p1, "PNG")
        _make_image(p2, "PNG")

        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        worker = _SanitizeWorker([p1, p2], out_dir, "same", 8, 95, 6)
        worker.run()

        # Both files land directly under out_dir — no subfolders created.
        entries = os.listdir(out_dir)
        assert len(entries) == 2
        assert all(os.path.isfile(os.path.join(out_dir, e)) for e in entries)

    def test_lsb_steganography_is_disrupted(self, tmp_path):
        """Fake stealth-pnginfo LSB payload must not survive sanitize."""
        src = str(tmp_path / "stego.png")
        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)

        # Build a 64×64 RGBA canvas and hide a bit pattern in channel LSBs.
        arr = np.full((64, 64, 4), 128, dtype=np.uint8)
        # Alpha channel is fully opaque
        arr[..., 3] = 255
        # Hidden message bits, encoded as alternating 0/1 pattern in all
        # four channel LSBs — a stand-in for NovelAI's stealth pnginfo.
        payload = np.zeros((64, 64, 4), dtype=np.uint8)
        flat = payload.reshape(-1)
        flat[::2] = 1  # alternating LSB pattern
        arr = (arr & np.uint8(0xFE)) | payload
        Image.fromarray(arr, "RGBA").save(src, format="PNG")

        out = sanitize_image(src, out_dir, "same")
        result = np.array(Image.open(out))

        # Visual content preserved within ±1 per channel.
        assert result.shape == arr.shape
        assert np.all(np.abs(result.astype(int) - arr.astype(int)) <= 1)

        # The deterministic payload pattern should be gone — compare the
        # recovered LSB stream against the planted one; equality would
        # mean LSBs passed through unchanged.
        recovered = result & np.uint8(0x01)
        matches = np.sum(recovered == payload)
        total = payload.size
        # Random LSB noise should match ~50% of the time; leave generous
        # slack but clearly rule out full pass-through (would be 100%).
        assert matches < total * 0.75, (
            f"LSB payload appears to have survived — {matches}/{total} "
            f"bits match ({matches / total:.1%}).")

    def test_escaping_path_falls_back_to_flat(self, tmp_path):
        """Paths outside src_root must not escape output_dir via '..'."""
        src = tmp_path / "src"
        src.mkdir()
        outside = tmp_path / "outside.png"
        _make_image(str(outside), "PNG")

        out_dir = str(tmp_path / "out")
        os.makedirs(out_dir)
        worker = _SanitizeWorker(
            [str(outside)], out_dir, "same", 8, 95, 6,
            src_root=str(src))
        worker.run()

        # File is written flat under out_dir; no '..' directory created.
        assert os.listdir(out_dir)  # one output file
        # Nothing should have been created as a sibling of out_dir.
        siblings = {p.name for p in tmp_path.iterdir()}
        assert siblings == {"src", "outside.png", "out"}
