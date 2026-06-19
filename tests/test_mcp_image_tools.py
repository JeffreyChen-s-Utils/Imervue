"""Tests for the image-analysis MCP tool handlers."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.mcp_server.tools import image_statistics, quality_metrics


def _save(path, value=128, h=24, w=24):
    Image.fromarray(np.full((h, w, 3), value, dtype=np.uint8), "RGB").save(str(path))
    return str(path)


def _save_noisy(path, h=24, w=24):
    rng = np.random.default_rng(0)
    Image.fromarray(rng.integers(0, 256, (h, w, 3), dtype=np.uint8), "RGB").save(str(path))
    return str(path)


def test_image_statistics_shape(tmp_path):
    result = image_statistics(_save(tmp_path / "a.png", value=100))
    assert result["path"].endswith("a.png")
    stats = result["statistics"]
    assert set(stats) == {"r", "g", "b", "luma"}
    assert stats["r"]["mean"] == 100.0  # NOSONAR - flat channel
    assert set(stats["r"]) == {"mean", "min", "max", "std", "median"}


def test_quality_metrics_keys(tmp_path):
    result = quality_metrics(_save_noisy(tmp_path / "n.png"))
    metrics = result["metrics"]
    assert set(metrics) == {
        "colorfulness", "entropy", "rms_contrast", "edge_density", "noise_sigma"}
    assert result["path"].endswith("n.png")


def test_missing_file_raises():
    with pytest.raises(ValueError):
        image_statistics("/no/such/file.png")
    with pytest.raises(ValueError):
        quality_metrics("/no/such/file.png")


def test_registered_in_default_tools():
    from Imervue.mcp_server.tools import _TOOL_DEFINITIONS
    names = {entry["name"] for entry in _TOOL_DEFINITIONS}
    assert {"image_statistics", "quality_metrics"} <= names
