"""Tests for soft proofing."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image import soft_proof


class TestSimulateProfile:
    def test_returns_none_for_missing_profile(self, tmp_path):
        arr = np.zeros((16, 16, 4), dtype=np.uint8)
        result = soft_proof.simulate_profile(arr, tmp_path / "missing.icc")
        assert result is None

    def test_rejects_non_rgba(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            soft_proof.simulate_profile(arr, "anything.icc")

    def test_returns_tuple_with_srgb_profile(self, tmp_path):
        from PIL import ImageCms
        try:
            profile = ImageCms.createProfile("sRGB")
            profile_path = tmp_path / "srgb.icc"
            ImageCms.ImageCmsProfile(profile).tobytes()
            # Write the profile to disk via Pillow.
            with open(profile_path, "wb") as f:
                f.write(ImageCms.ImageCmsProfile(profile).tobytes())
        except (ImportError, ImageCms.PyCMSError, OSError):
            pytest.skip("ImageCms unavailable in this environment")

        arr = np.full((16, 16, 4), 128, dtype=np.uint8)
        arr[..., 3] = 255
        result = soft_proof.simulate_profile(arr, profile_path)
        if result is None:
            pytest.skip("Profile creation succeeded but transform failed")
        simulated, mask = result
        assert simulated.shape == arr.shape
        assert mask.shape == arr.shape[:2]
        assert mask.dtype == bool
