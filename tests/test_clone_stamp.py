"""Tests for clone stamp."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import clone_stamp


class TestCloneStamp:
    def test_round_trip(self):
        s = clone_stamp.CloneStamp(sx=10, sy=20, dx=30, dy=40, radius=5, feather=0.4)
        back = clone_stamp.CloneStamp.from_dict(s.to_dict())
        assert back == s

    def test_from_dict_clamps_radius(self):
        s = clone_stamp.CloneStamp.from_dict(
            {"sx": 1, "sy": 2, "dx": 3, "dy": 4, "r": 0},
        )
        assert s.radius == 1


class TestApplyCloneStamp:
    def test_empty_list_passes_through(self):
        arr = np.zeros((16, 16, 4), dtype=np.uint8)
        out = clone_stamp.apply_clone_stamp(arr, [])
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            clone_stamp.apply_clone_stamp(
                arr, [clone_stamp.CloneStamp(0, 0, 1, 1, 3)],
            )

    def test_copies_source_to_destination(self):
        arr = np.full((40, 40, 4), 100, dtype=np.uint8)
        arr[..., 3] = 255
        arr[5:15, 5:15, :3] = 200   # bright source patch
        stamp = clone_stamp.CloneStamp(
            sx=10, sy=10, dx=30, dy=30, radius=5, feather=0.0,
        )
        out = clone_stamp.apply_clone_stamp(arr, [stamp])
        # Destination centre should now look like the source (bright).
        assert int(out[30, 30, 0]) > 150
        # Untouched area stays original.
        assert int(out[0, 0, 0]) == 100

    def test_skips_out_of_bounds_source(self):
        arr = np.zeros((20, 20, 4), dtype=np.uint8)
        stamp = clone_stamp.CloneStamp(
            sx=-5, sy=-5, dx=10, dy=10, radius=3,
        )
        out = clone_stamp.apply_clone_stamp(arr, [stamp])
        assert np.array_equal(out, arr)


class TestRoundTripLists:
    def test_stamps_from_dict_list_skips_garbage(self):
        items = [
            {"sx": 1, "sy": 2, "dx": 3, "dy": 4, "r": 5},
            "not a dict",
            {},
        ]
        out = clone_stamp.stamps_from_dict_list(items)
        assert len(out) == 1
