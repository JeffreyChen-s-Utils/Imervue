"""Tests for per-channel image statistics and histogram CSV export."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.statistics import histogram_csv, image_statistics


def _rgba(h=10, w=10):
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[..., 0] = 100  # constant red
    rgb[..., 1] = np.tile((np.arange(w) * 20 % 200).astype(np.uint8), (h, 1))
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_statistics_keys_and_constant_channel():
    stats = image_statistics(_rgba())
    assert set(stats) == {"r", "g", "b", "luma"}
    assert stats["r"]["mean"] == 100.0  # NOSONAR - exact on a constant channel
    assert stats["r"]["std"] == 0.0     # NOSONAR - exact on a constant channel
    assert stats["b"]["max"] == 0.0     # NOSONAR - blue channel is all zero


def test_statistics_metrics_present():
    stats = image_statistics(_rgba())
    assert set(stats["g"]) == {"mean", "min", "max", "std", "median"}


def test_histogram_csv_header_and_rows():
    csv_text = histogram_csv(_rgba())
    lines = csv_text.strip().splitlines()
    assert lines[0] == "value,r,g,b,luma"
    assert len(lines) == 257  # header + 256 levels


def test_histogram_csv_red_count():
    # All 100 red pixels land in bin 100.
    csv_text = histogram_csv(_rgba(10, 10))
    row_100 = csv_text.splitlines()[1 + 100].split(",")
    assert int(row_100[1]) == 100  # 10x10 pixels in the red histogram bin 100


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        image_statistics(np.zeros((8, 8), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.image_statistics_dialog import ImageStatisticsDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_rgba()).save(str(path))
    dialog = ImageStatisticsDialog(object(), str(path))
    try:
        assert dialog._table.rowCount() == 4
    finally:
        dialog.deleteLater()
