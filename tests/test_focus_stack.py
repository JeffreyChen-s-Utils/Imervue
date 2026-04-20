"""Tests for focus stacking."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("cv2")

from Imervue.image import focus_stack as fs


def _image_with_sharp_patch(h=32, w=32, patch_xy=(0, 0), patch_size=16):
    """Image that is uniform gray except for a noisy (sharp) patch."""
    arr = np.full((h, w, 3), 120, dtype=np.uint8)
    x, y = patch_xy
    rng = np.random.default_rng(x * 1000 + y)
    noise = rng.integers(0, 256, (patch_size, patch_size, 3), dtype=np.uint8)
    arr[y:y + patch_size, x:x + patch_size] = noise
    return arr


def _save(tmp_path, name, arr):
    p = tmp_path / name
    Image.fromarray(arr).save(p)
    return str(p)


class TestStackFocusValidation:
    def test_rejects_single_image(self, tmp_path):
        p = _save(tmp_path, "a.png", np.zeros((16, 16, 3), dtype=np.uint8))
        with pytest.raises(ValueError):
            fs.stack_focus([p])

    def test_rejects_mismatched_sizes(self, tmp_path):
        p1 = _save(tmp_path, "a.png", np.zeros((16, 16, 3), dtype=np.uint8))
        p2 = _save(tmp_path, "b.png", np.zeros((20, 20, 3), dtype=np.uint8))
        with pytest.raises(ValueError):
            fs.stack_focus([p1, p2], fs.FocusStackOptions(align=False))


class TestStackFocusOutput:
    def test_returns_rgba_uint8_same_size(self, tmp_path):
        p1 = _save(tmp_path, "a.png", _image_with_sharp_patch(patch_xy=(2, 2)))
        p2 = _save(tmp_path, "b.png", _image_with_sharp_patch(patch_xy=(14, 14)))
        out = fs.stack_focus([p1, p2], fs.FocusStackOptions(align=False))
        assert out.dtype == np.uint8
        assert out.shape == (32, 32, 4)
        assert (out[..., 3] == 255).all()

    def test_fused_has_detail_from_both_planes(self, tmp_path):
        # Each source has a sharp patch in a different location; the fused
        # output should preserve the sharp (non-uniform) region of each.
        p1 = _save(tmp_path, "a.png", _image_with_sharp_patch(patch_xy=(2, 2)))
        p2 = _save(tmp_path, "b.png", _image_with_sharp_patch(patch_xy=(14, 14)))
        out = fs.stack_focus([p1, p2], fs.FocusStackOptions(align=False))
        patch1_std = out[2:18, 2:18, 0].std()
        patch2_std = out[14:30, 14:30, 0].std()
        assert patch1_std > 20
        assert patch2_std > 20
