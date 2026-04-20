"""Tests for HDR merge."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("cv2")

from Imervue.image import hdr_merge as hm


def _make_bracket(tmp_path, n=3, w=32, h=24, base=120):
    paths = []
    for i in range(n):
        ev = (i - (n - 1) / 2) * 2.0
        gain = 2.0 ** ev
        val = int(np.clip(base * gain, 0, 255))
        arr = np.full((h, w, 3), val, dtype=np.uint8)
        p = tmp_path / f"ev{i}.png"
        Image.fromarray(arr).save(str(p))
        paths.append(str(p))
    return paths


class TestMergeHdr:
    def test_mertens_merge_returns_rgba(self, tmp_path):
        paths = _make_bracket(tmp_path)
        out = hm.merge_hdr(paths, hm.HdrOptions(method="mertens", align=False))
        assert out.dtype == np.uint8
        assert out.ndim == 3
        assert out.shape[2] == 4
        assert (out[..., 3] == 255).all()

    def test_debevec_requires_exposure_times(self, tmp_path):
        paths = _make_bracket(tmp_path)
        with pytest.raises(ValueError):
            hm.merge_hdr(paths, hm.HdrOptions(method="debevec", align=False))

    def test_debevec_merge_succeeds_with_times(self, tmp_path):
        paths = _make_bracket(tmp_path, n=3)
        out = hm.merge_hdr(
            paths,
            hm.HdrOptions(method="debevec", align=False),
            exposure_times=[1 / 60, 1 / 15, 1 / 4],
        )
        assert out.shape[2] == 4

    def test_rejects_single_image(self, tmp_path):
        paths = _make_bracket(tmp_path, n=1)
        with pytest.raises(ValueError):
            hm.merge_hdr(paths)

    def test_rejects_mixed_sizes(self, tmp_path):
        p1 = tmp_path / "a.png"
        p2 = tmp_path / "b.png"
        Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8)).save(p1)
        Image.fromarray(np.zeros((20, 20, 3), dtype=np.uint8)).save(p2)
        with pytest.raises(ValueError):
            hm.merge_hdr([str(p1), str(p2)], hm.HdrOptions(align=False))

    def test_result_is_between_extremes(self, tmp_path):
        paths = _make_bracket(tmp_path, n=3, base=128)
        out = hm.merge_hdr(paths, hm.HdrOptions(method="mertens", align=False))
        # Merged value should be roughly around the middle exposure (not 0 or 255).
        mean = out[..., :3].mean()
        assert 30 <= mean <= 230
