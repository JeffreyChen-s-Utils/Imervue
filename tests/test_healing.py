"""Tests for healing brush / spot removal."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from Imervue.image import healing


class TestHealingSpot:
    def test_round_trip(self):
        s = healing.HealingSpot(x=10, y=20, radius=5, method="telea")
        back = healing.HealingSpot.from_dict(s.to_dict())
        assert back == s

    def test_from_dict_clamps_unknown_method(self):
        s = healing.HealingSpot.from_dict({"x": 1, "y": 2, "r": 3, "m": "xxx"})
        assert s.method == "telea"

    def test_spots_from_dict_list_skips_garbage(self):
        items = [
            {"x": 1, "y": 1, "r": 2},
            "not a dict",
            {},
            {"x": 5, "y": 5, "r": 1, "m": "ns"},
        ]
        spots = healing.spots_from_dict_list(items)
        assert len(spots) == 2
        assert spots[1].method == "ns"


class TestApplyHealing:
    def test_no_spots_passes_through(self):
        rng = np.random.default_rng(0)
        arr = rng.integers(0, 256, (16, 16, 4), dtype=np.uint8)
        out = healing.apply_healing(arr, [])
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            healing.apply_healing(
                arr, [healing.HealingSpot(5, 5, 2)],
            )

    def test_inpaint_removes_synthetic_spot(self):
        arr = np.full((40, 40, 4), 120, dtype=np.uint8)
        arr[..., 3] = 255
        arr[18:22, 18:22, :3] = 0  # 4x4 black dust spot
        out = healing.apply_healing(
            arr, [healing.HealingSpot(x=20, y=20, radius=4, method="telea")],
        )
        patch = out[18:22, 18:22, :3]
        # After inpaint the patch should be close to the surrounding gray.
        assert abs(int(patch.mean()) - 120) < 20

    def test_alpha_channel_preserved(self):
        arr = np.full((20, 20, 4), 100, dtype=np.uint8)
        arr[..., 3] = 200
        out = healing.apply_healing(
            arr, [healing.HealingSpot(10, 10, 3, "ns")],
        )
        assert (out[..., 3] == 200).all()
