"""Tests for size estimation and target-file-size encoding."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.optimize import encode_to_budget, estimate_size_kb


def _photo_rgba(h=256, w=256, seed=0):
    rng = np.random.default_rng(seed)
    rgb = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_estimate_size_positive():
    assert estimate_size_kb(_photo_rgba(), "JPEG", 85) > 0


def test_higher_quality_is_larger():
    img = _photo_rgba()
    assert estimate_size_kb(img, "JPEG", 90) > estimate_size_kb(img, "JPEG", 20)


def test_encode_to_budget_respects_budget():
    img = _photo_rgba()
    data, quality = encode_to_budget(img, max_kb=20.0, fmt="JPEG")
    assert 5 <= quality <= 95
    # Either we hit the budget, or even the lowest quality is returned.
    assert len(data) / 1024.0 <= 20.0 or quality == 5


def test_webp_budget_runs():
    data, _q = encode_to_budget(_photo_rgba(), max_kb=15.0, fmt="WEBP")
    assert isinstance(data, bytes) and len(data) > 0


def test_lossless_format_rejected():
    with pytest.raises(ValueError):
        encode_to_budget(_photo_rgba(), max_kb=50.0, fmt="PNG")


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        estimate_size_kb(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.optimize_dialog import OptimizeDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_photo_rgba(32, 32)).save(str(path))
    dialog = OptimizeDialog(object(), str(path))
    try:
        assert dialog._budget.value() == 200
        assert dialog._format.count() == 2
    finally:
        dialog.deleteLater()
