"""Tests for split toning."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import split_toning


class TestApplySplitToning:
    def test_zero_saturation_passes_through(self):
        arr = np.full((16, 16, 4), 128, dtype=np.uint8)
        out = split_toning.apply_split_toning(
            arr, shadow_saturation=0.0, highlight_saturation=0.0,
        )
        assert out is arr

    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            split_toning.apply_split_toning(arr)

    def test_shadow_tint_affects_darks(self):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        arr[..., 3] = 255
        arr[:, :16, :3] = 40     # shadows on the left
        arr[:, 16:, :3] = 215    # highlights on the right
        out = split_toning.apply_split_toning(
            arr, shadow_hue=0.0, shadow_saturation=1.0,
            highlight_hue=210.0, highlight_saturation=0.0,
        )
        # The shadow side should pick up red (hue=0).
        shadow_r = int(out[16, 4, 0])
        shadow_b = int(out[16, 4, 2])
        assert shadow_r >= shadow_b

    def test_balance_shifts_pivot(self):
        arr = np.full((16, 16, 4), 100, dtype=np.uint8)
        arr[..., 3] = 255
        # Push balance toward highlights — mid-grey should start receiving
        # the highlight tint more strongly.
        out_neg = split_toning.apply_split_toning(
            arr, shadow_saturation=1.0, shadow_hue=0.0, balance=-0.9,
        )
        out_pos = split_toning.apply_split_toning(
            arr, shadow_saturation=1.0, shadow_hue=0.0, balance=0.9,
        )
        # With negative balance, fewer mid-tone pixels are classed as shadow.
        assert int(out_pos[8, 8, 0]) >= int(out_neg[8, 8, 0])
