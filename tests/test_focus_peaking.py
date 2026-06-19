"""Tests for focus-peaking edge overlay."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.focus_peaking import focus_peaking


def _edge_rgba(h=16, w=16):
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:, w // 2 :] = 255  # a hard vertical edge in the middle
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def _flat_rgba(value=120, h=16, w=16):
    rgb = np.full((h, w, 3), value, dtype=np.uint8)
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alpha], axis=2)


def test_shape_and_alpha():
    out = focus_peaking(_edge_rgba())
    assert out.shape == (16, 16, 4)
    assert np.all(out[..., 3] == 255)


def test_edge_is_painted_marker_color():
    out = focus_peaking(_edge_rgba(), color=(255, 0, 0), threshold=0.2)
    marker = np.all(out[..., :3] == (255, 0, 0), axis=-1)
    # Peaks cluster along the central edge, not in the flat regions.
    assert marker[:, 6:10].sum() > 0
    assert marker[:, :3].sum() == 0


def test_flat_image_has_no_peaks():
    out = focus_peaking(_flat_rgba(), color=(255, 0, 0))
    assert not np.any(np.all(out[..., :3] == (255, 0, 0), axis=-1))


def test_threshold_clamped():
    # Out-of-range thresholds must not raise.
    assert focus_peaking(_edge_rgba(), threshold=5.0).shape == (16, 16, 4)


def test_bad_shape_raises():
    with pytest.raises(ValueError):
        focus_peaking(np.zeros((4, 4), dtype=np.uint8))


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from Imervue.gui.image_inspector_dialog import ImageInspectorDialog

    path = tmp_path / "scene.png"
    PILImage.fromarray(_edge_rgba(40, 40)).save(str(path))
    dialog = ImageInspectorDialog(object(), str(path))
    try:
        assert dialog._tabs.count() == 6  # waveform, parade, false-color, peaking, ELA, clone
    finally:
        dialog.deleteLater()
