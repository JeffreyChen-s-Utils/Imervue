"""Tests for the custom brush tip loader."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.custom_brush import (
    is_supported_extension,
    load_brush_tip,
)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_load_brush_tip_rejects_zero_size(tmp_path):
    p = tmp_path / "x.png"
    Image.new("RGBA", (4, 4), (0, 0, 0, 255)).save(str(p))
    with pytest.raises(ValueError):
        load_brush_tip(p, size=0)


def test_load_brush_tip_missing_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        load_brush_tip(tmp_path / "missing.png", size=8)


def test_load_brush_tip_corrupt_image_raises_oserror(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a real png")
    with pytest.raises(OSError):
        load_brush_tip(bad, size=8)


# ---------------------------------------------------------------------------
# Alpha-channel path
# ---------------------------------------------------------------------------


def _save_alpha_tip(path, size, alpha_centre):
    """Write an RGBA tip with white background and a higher-alpha centre."""
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    pixels = np.array(img)
    pixels[size // 2, size // 2] = (255, 255, 255, alpha_centre)
    Image.fromarray(pixels, mode="RGBA").save(str(path))


def test_load_brush_tip_uses_alpha_when_varies(tmp_path):
    p = tmp_path / "tip.png"
    _save_alpha_tip(p, size=16, alpha_centre=255)
    kernel = load_brush_tip(p, size=8)
    assert kernel.shape == (8, 8)
    assert kernel.dtype == np.float32
    assert kernel.min() >= 0.0
    assert kernel.max() <= 1.0


def test_load_brush_tip_resizes_to_requested_size(tmp_path):
    p = tmp_path / "tip.png"
    _save_alpha_tip(p, size=64, alpha_centre=255)
    kernel = load_brush_tip(p, size=12)
    assert kernel.shape == (12, 12)


def test_load_brush_tip_normalised_to_unit_range(tmp_path):
    p = tmp_path / "tip.png"
    _save_alpha_tip(p, size=16, alpha_centre=255)
    kernel = load_brush_tip(p, size=8)
    assert kernel.max() <= 1.0


# ---------------------------------------------------------------------------
# Luminance fallback
# ---------------------------------------------------------------------------


def test_load_brush_tip_falls_back_to_luminance_for_solid_alpha(tmp_path):
    """A black-shape-on-white PNG with full alpha should still produce a
    sensible kernel via the luma fallback."""
    p = tmp_path / "tip.png"
    img = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    pixels = np.array(img)
    pixels[8, 8, :3] = 0      # one black centre pixel
    Image.fromarray(pixels, mode="RGBA").save(str(p))
    kernel = load_brush_tip(p, size=8)
    # Some pixel is brighter than zero — the luma inversion picked up
    # the black centre.
    assert kernel.max() > 0.5


def test_load_brush_tip_pure_white_luma_yields_zero_kernel(tmp_path):
    """Pure-white RGBA with full alpha has no shape — kernel should be all zero
    (no paint deposited) rather than crashing."""
    p = tmp_path / "tip.png"
    Image.new("RGBA", (8, 8), (255, 255, 255, 255)).save(str(p))
    kernel = load_brush_tip(p, size=4)
    assert kernel.shape == (4, 4)
    assert kernel.max() == 0.0


# ---------------------------------------------------------------------------
# is_supported_extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,expected", [
    ("a.png", True),
    ("b.PNG", True),
    ("c.jpg", True),
    ("d.jpeg", True),
    ("e.webp", True),
    ("f.tiff", True),
    ("g.tif", True),
    ("h.txt", False),
    ("no_extension", False),
])
def test_is_supported_extension(name, expected):
    assert is_supported_extension(name) is expected
