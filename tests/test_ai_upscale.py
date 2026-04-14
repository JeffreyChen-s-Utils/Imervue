"""
Tests for AI upscale dialog — model registry, tile helper, inference pipeline.

Tests that exercise actual ONNX inference are skipped if onnxruntime is not
installed. Registry and tile-math tests have no heavy dependencies.
"""
from __future__ import annotations

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
