"""Tests for image_loader: load_image_file and _scan_images."""
import os
import numpy as np
import pytest
from PIL import Image

pytest.importorskip("imageio")
pytest.importorskip("rawpy")

from Imervue.gpu_image_view.images.image_loader import load_image_file, _scan_images


class TestLoadImageFile:
    def test_load_png_returns_rgba(self, sample_png):
        result = load_image_file(sample_png)
        assert result.ndim == 3
        assert result.shape[2] == 4
        assert result.dtype == np.uint8

    def test_load_jpeg_returns_rgba(self, sample_jpeg):
        result = load_image_file(sample_jpeg)
        assert result.ndim == 3
        assert result.shape[2] == 4

    def test_load_grayscale_returns_rgba(self, sample_grayscale_png):
        result = load_image_file(sample_grayscale_png)
        assert result.ndim == 3
        assert result.shape[2] == 4

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises((FileNotFoundError, OSError)):
            load_image_file(str(tmp_path / "nonexistent.png"))


class TestScanImages:
    def test_scan_finds_supported_files(self, image_folder):
        results = _scan_images(image_folder)
        basenames = [os.path.basename(p) for p in results]
        assert "alpha.png" in basenames
        assert "beta.jpg" in basenames
        assert "gamma.png" in basenames
        assert "delta.bmp" in basenames

    def test_scan_sorted_alphabetically(self, image_folder):
        results = _scan_images(image_folder)
        basenames = [os.path.basename(p).lower() for p in results]
        assert basenames == sorted(basenames)

    def test_scan_ignores_non_image(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.csv").write_text("a,b")
        (tmp_path / "real.png").write_bytes(
            Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8)).tobytes()
        )
        # Create a real png
        img = Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8))
        img.save(str(tmp_path / "real.png"))
        results = _scan_images(str(tmp_path))
        assert len(results) == 1
        assert results[0].endswith("real.png")

    def test_scan_empty_dir(self, tmp_path):
        results = _scan_images(str(tmp_path))
        assert results == []

    def test_scan_nonexistent_dir(self):
        results = _scan_images("/nonexistent/path/xyz")
        assert results == []


class TestOpenFolder:
    def test_empty_folder_resets_to_clean_grid(self, tmp_path):
        # Navigating "back" to an image-less folder must rebuild the wall empty
        # rather than leave the previous folder's stale thumbnails behind.
        from pathlib import Path
        from types import SimpleNamespace

        from Imervue.gpu_image_view.images.image_loader import _open_folder

        empty = tmp_path / "empty"
        empty.mkdir()
        loaded = []
        view = SimpleNamespace(
            _unfiltered_images=["stale.png"],
            _stack_members={"k": 1},
            load_tile_grid_async=lambda paths: loaded.append(list(paths)),
            main_window=object(),  # no plugin_manager
        )
        # The duck-typed fake deliberately stands in for a real GPUImageView;
        # S5655's argument-type check is a false positive for test doubles.
        _open_folder(view, Path(str(empty)))  # NOSONAR
        assert loaded == [[]]
        assert view._unfiltered_images == []


def _write_sample_video(path, frame_count=5):
    iio = pytest.importorskip("imageio").v2
    pytest.importorskip("imageio_ffmpeg")
    frames = [
        np.full((16, 16, 3), 40 + idx * 30, dtype=np.uint8)
        for idx in range(frame_count)
    ]
    try:
        iio.mimwrite(str(path), frames, format="ffmpeg", fps=5)
    except (OSError, RuntimeError, ValueError) as exc:  # ffmpeg binary issues
        pytest.skip(f"ffmpeg writer unavailable: {exc}")


class TestVideoInGrid:
    def test_video_ext_supported(self):
        from Imervue.gpu_image_view.images.image_loader import _SUPPORTED_EXTS
        assert ".mp4" in _SUPPORTED_EXTS

    def test_scan_finds_video(self, tmp_path):
        _write_sample_video(tmp_path / "clip.mp4")
        results = _scan_images(str(tmp_path))
        assert any(p.endswith("clip.mp4") for p in results)

    def test_load_video_returns_rgba_poster(self, tmp_path):
        video = tmp_path / "clip.mp4"
        _write_sample_video(video)
        result = load_image_file(str(video))
        assert result.ndim == 3
        assert result.shape[2] == 4
        assert result.dtype == np.uint8


class TestHeifInGrid:
    def test_heif_exts_supported(self):
        from Imervue.gpu_image_view.images.image_loader import _SUPPORTED_EXTS
        assert ".heic" in _SUPPORTED_EXTS
        assert ".avif" in _SUPPORTED_EXTS

    def test_scan_finds_heic(self, tmp_path):
        pillow_heif = pytest.importorskip("pillow_heif")
        pillow_heif.register_heif_opener()
        img = Image.fromarray(np.full((16, 16, 3), 70, dtype=np.uint8))
        img.save(str(tmp_path / "photo.heic"))
        results = _scan_images(str(tmp_path))
        assert any(p.endswith("photo.heic") for p in results)
