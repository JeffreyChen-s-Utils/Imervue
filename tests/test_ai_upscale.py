"""
Tests for AI upscale dialog — model registry, tile helper, inference pipeline.

Tests that exercise actual ONNX inference are skipped if onnxruntime is not
installed. Registry and tile-math tests have no heavy dependencies.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from Imervue.gui.ai_upscale_dialog import UPSCALE_MODELS, _TILE_SIZE, _TILE_PAD


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

class TestModelRegistry:
    def test_all_models_have_required_fields(self):
        required = {"repo", "file", "scale", "desc_key", "desc_default"}
        for key, info in UPSCALE_MODELS.items():
            missing = required - set(info.keys())
            assert not missing, f"Model '{key}' missing fields: {missing}"

    def test_scale_values(self):
        for key, info in UPSCALE_MODELS.items():
            assert info["scale"] in (2, 4), (
                f"Model '{key}' has unexpected scale {info['scale']}"
            )

    def test_files_have_onnx_extension(self):
        for key, info in UPSCALE_MODELS.items():
            assert info["file"].endswith(".onnx"), (
                f"Model '{key}' file doesn't end with .onnx: {info['file']}"
            )

    def test_expected_models_present(self):
        assert "realesrgan-x4plus" in UPSCALE_MODELS
        assert "realesrgan-x4plus-anime" in UPSCALE_MODELS
        assert "realesrgan-x2plus" in UPSCALE_MODELS

    def test_repos_are_valid_huggingface_ids(self):
        for key, info in UPSCALE_MODELS.items():
            repo = info["repo"]
            # HuggingFace repo IDs have the format "owner/name"
            parts = repo.split("/")
            assert len(parts) == 2, f"Model '{key}' has invalid repo: {repo}"
            assert all(len(p) > 0 for p in parts)


# ---------------------------------------------------------------------------
# Tile math
# ---------------------------------------------------------------------------

class TestTileMath:
    def test_constants(self):
        assert _TILE_SIZE > 0
        assert _TILE_PAD >= 0
        assert _TILE_SIZE > _TILE_PAD * 2

    def test_tile_covers_small_image(self):
        """An image smaller than TILE_SIZE should need only 1 tile."""
        h, w = 100, 100
        tiles_x = max(1, (w + _TILE_SIZE - 1) // _TILE_SIZE)
        tiles_y = max(1, (h + _TILE_SIZE - 1) // _TILE_SIZE)
        assert tiles_x == 1
        assert tiles_y == 1

    def test_tile_count_large_image(self):
        """A 2048x2048 image should need multiple tiles."""
        h, w = 2048, 2048
        tiles_x = max(1, (w + _TILE_SIZE - 1) // _TILE_SIZE)
        tiles_y = max(1, (h + _TILE_SIZE - 1) // _TILE_SIZE)
        assert tiles_x == 4
        assert tiles_y == 4


# ---------------------------------------------------------------------------
# Tile inference (only if onnxruntime is available)
# ---------------------------------------------------------------------------

class TestUpscaleTile:
    @pytest.fixture
    def has_onnxruntime(self):
        pytest.importorskip("onnxruntime")

    def test_tile_function_signature(self):
        """_upscale_tile should be importable and callable."""
        from Imervue.gui.ai_upscale_dialog import _upscale_tile
        assert callable(_upscale_tile)

    def test_upscale_image_function_exists(self):
        from Imervue.gui.ai_upscale_dialog import _upscale_image
        assert callable(_upscale_image)


# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------

class TestScanFolder:
    @pytest.fixture
    def image_folder(self, tmp_path):
        """Create a folder with several image files and a non-image file."""
        from PIL import Image
        for name in ("a.png", "b.jpg", "c.bmp"):
            Image.new("RGB", (4, 4), "white").save(str(tmp_path / name))
        (tmp_path / "readme.txt").write_text("not an image")
        sub = tmp_path / "sub"
        sub.mkdir()
        Image.new("RGB", (4, 4), "red").save(str(sub / "d.png"))
        return tmp_path

    def test_scan_flat(self, image_folder):
        from Imervue.gui.ai_upscale_dialog import _scan_folder
        paths = _scan_folder(str(image_folder), recursive=False)
        names = [os.path.basename(p) for p in paths]
        assert "a.png" in names
        assert "b.jpg" in names
        assert "c.bmp" in names
        assert "readme.txt" not in names
        assert "d.png" not in names  # in subfolder

    def test_scan_recursive(self, image_folder):
        from Imervue.gui.ai_upscale_dialog import _scan_folder
        paths = _scan_folder(str(image_folder), recursive=True)
        names = [os.path.basename(p) for p in paths]
        assert "d.png" in names
        assert len(names) == 4  # a.png, b.jpg, c.bmp, d.png

    def test_scan_empty(self, tmp_path):
        from Imervue.gui.ai_upscale_dialog import _scan_folder
        assert _scan_folder(str(tmp_path)) == []

    def test_scan_nonexistent(self, tmp_path):
        from Imervue.gui.ai_upscale_dialog import _scan_folder
        assert _scan_folder(str(tmp_path / "nope")) == []


# ---------------------------------------------------------------------------
# Dialog folder mode
# ---------------------------------------------------------------------------

class TestDialogFolderMode:
    @pytest.fixture
    def image_folder(self, tmp_path):
        from PIL import Image
        for name in ("x.png", "y.jpg"):
            Image.new("RGB", (4, 4), "white").save(str(tmp_path / name))
        return tmp_path

    @pytest.fixture
    def stub_gui(self, qapp):
        from unittest.mock import MagicMock
        from PySide6.QtWidgets import QMainWindow
        gui = MagicMock()
        mw = QMainWindow()
        gui.main_window = mw
        yield gui
        mw.close()

    def test_folder_mode_shows_source_row(self, stub_gui):
        from Imervue.gui.ai_upscale_dialog import AIUpscaleDialog
        dlg = AIUpscaleDialog(stub_gui, paths=None, folder=None)
        # isHidden checks the widget's own hidden flag, not parent visibility
        assert not dlg._src_row_widget.isHidden()
        dlg.close()

    def test_preset_paths_hides_source_row(self, stub_gui, image_folder):
        from Imervue.gui.ai_upscale_dialog import AIUpscaleDialog
        dlg = AIUpscaleDialog(stub_gui, paths=[str(image_folder / "x.png")])
        assert dlg._src_row_widget.isHidden()
        dlg.close()

    def test_folder_prefill_scans(self, stub_gui, image_folder):
        from Imervue.gui.ai_upscale_dialog import AIUpscaleDialog
        dlg = AIUpscaleDialog(stub_gui, folder=str(image_folder))
        assert len(dlg._paths) == 2
        dlg.close()


# ---------------------------------------------------------------------------
# Traditional resampling methods
# ---------------------------------------------------------------------------

class TestTraditionalMethods:
    def test_registry_has_expected_methods(self):
        from Imervue.gui.ai_upscale_dialog import TRADITIONAL_METHODS
        assert "trad:lanczos" in TRADITIONAL_METHODS
        assert "trad:bicubic" in TRADITIONAL_METHODS
        assert "trad:nearest" in TRADITIONAL_METHODS

    def test_all_methods_have_desc(self):
        from Imervue.gui.ai_upscale_dialog import TRADITIONAL_METHODS
        for _key, info in TRADITIONAL_METHODS.items():
            assert "desc_key" in info
            assert "desc_default" in info

    def test_resampling_map_matches_registry(self):
        from Imervue.gui.ai_upscale_dialog import (
            TRADITIONAL_METHODS, _TRAD_RESAMPLING,
        )
        assert set(_TRAD_RESAMPLING.keys()) == set(TRADITIONAL_METHODS.keys())

    def test_lanczos_upscale(self, tmp_path):
        """Lanczos resize should produce exact expected dimensions."""
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker

        src = tmp_path / "small.png"
        Image.new("RGB", (10, 8), "blue").save(str(src))

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        worker = _UpscaleWorker(
            [str(src)], str(out_dir), "trad:lanczos", False,
            scale_override=3)
        worker.run()

        results = list(out_dir.glob("*.png"))
        assert len(results) == 1
        out_img = Image.open(str(results[0]))
        assert out_img.size == (30, 24)

    def test_nearest_upscale_preserves_pixels(self, tmp_path):
        """Nearest-neighbor on a solid-color image should be lossless."""
        from PIL import Image
        from Imervue.gui.ai_upscale_dialog import _UpscaleWorker
        src = tmp_path / "pixel.png"
        img = Image.new("RGB", (2, 2), (42, 99, 200))
        img.save(str(src))

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        worker = _UpscaleWorker(
            [str(src)], str(out_dir), "trad:nearest", False,
            scale_override=4)
        worker.run()

        results = list(out_dir.glob("*.png"))
        out_img = Image.open(str(results[0]))
        assert out_img.size == (8, 8)
        # Every pixel should be exactly the same color
        arr = np.asarray(out_img)
        assert np.all(arr == np.array([42, 99, 200], dtype=arr.dtype))
