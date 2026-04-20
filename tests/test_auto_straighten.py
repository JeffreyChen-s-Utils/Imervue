"""Tests for auto-straighten."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from Imervue.image import auto_straighten, geometry


class TestDetectHorizonAngle:
    def test_rejects_non_rgba(self):
        arr = np.zeros((40, 40, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            auto_straighten.detect_horizon_angle(arr)

    def test_level_image_returns_near_zero(self):
        arr = np.zeros((80, 160, 4), dtype=np.uint8)
        arr[..., 3] = 255
        # Draw a thick horizontal line at y=40 — zero tilt.
        arr[38:42, 10:150, :3] = 255
        angle = auto_straighten.detect_horizon_angle(arr)
        assert abs(angle) < 2.0

    def test_solid_image_returns_zero(self):
        arr = np.full((60, 60, 4), 100, dtype=np.uint8)
        arr[..., 3] = 255
        angle = auto_straighten.detect_horizon_angle(arr)
        assert angle == pytest.approx(0.0)

    def test_tilted_line_detected(self):
        import cv2
        arr = np.zeros((120, 200, 4), dtype=np.uint8)
        arr[..., 3] = 255
        rgb = np.ascontiguousarray(arr[..., :3])
        cv2.line(rgb, (10, 50), (190, 60), (255, 255, 255), 2)
        arr[..., :3] = rgb
        angle = auto_straighten.detect_horizon_angle(arr)
        # Should be within the ±15° cap.
        assert abs(angle) <= 15.0
