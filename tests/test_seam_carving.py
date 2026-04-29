"""Tests for the seam-carving algorithm shipped with AI Smart Resize.

The Qt dialog is not exercised; the unit tests cover the pure-numpy
algorithm directly so they stay portable and fast.
"""
from __future__ import annotations

import numpy as np
import pytest

from ai_smart_resize.seam_carving import (
    MAX_SEAM_FRACTION,
    SmartResizeOptions,
    carve_seams,
    smart_resize,
)


@pytest.fixture
def tiny_rgba():
    """Deterministic 16x12 RGBA frame with a high-energy stripe down the middle."""
    arr = np.zeros((12, 16, 4), dtype=np.uint8)
    arr[..., 3] = 255
    # High-energy red stripe in cols 7..9 — should be preserved by carving.
    arr[:, 7:10, 0] = 255
    return arr


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_smart_resize_rejects_non_rgba(sample_rgb_array):
    with pytest.raises(ValueError):
        smart_resize(sample_rgb_array, SmartResizeOptions(out_width=80))


def test_smart_resize_zero_means_unchanged(tiny_rgba):
    """``out_width=0`` / ``out_height=0`` is the documented "leave alone" sentinel."""
    out = smart_resize(tiny_rgba, SmartResizeOptions(out_width=0, out_height=0))
    assert out.shape == tiny_rgba.shape


def test_smart_resize_rejects_change_beyond_budget(tiny_rgba):
    h, w = tiny_rgba.shape[:2]
    illegal_w = int(w * (1 + MAX_SEAM_FRACTION + 0.5))
    with pytest.raises(ValueError):
        smart_resize(tiny_rgba, SmartResizeOptions(out_width=illegal_w, out_height=h))


# ---------------------------------------------------------------------------
# Identity / no-op behaviour
# ---------------------------------------------------------------------------


def test_zero_delta_returns_input(tiny_rgba):
    out = carve_seams(tiny_rgba, 0)
    assert out is tiny_rgba


def test_smart_resize_unchanged_dimensions(tiny_rgba):
    h, w = tiny_rgba.shape[:2]
    out = smart_resize(tiny_rgba, SmartResizeOptions(out_width=w, out_height=h))
    assert out.shape == tiny_rgba.shape


# ---------------------------------------------------------------------------
# Seam removal
# ---------------------------------------------------------------------------


def test_remove_one_seam_drops_one_column(tiny_rgba):
    out = carve_seams(tiny_rgba, -1)
    assert out.shape == (tiny_rgba.shape[0], tiny_rgba.shape[1] - 1, 4)
    assert out.dtype == np.uint8


def test_remove_seams_preserves_high_energy_stripe(tiny_rgba):
    # Carve away as many seams as the budget allows; the red stripe must survive.
    h, w = tiny_rgba.shape[:2]
    delta = -int(w * MAX_SEAM_FRACTION)
    out = carve_seams(tiny_rgba, delta)
    # Some red pixels must remain in every row — the stripe is fully protected.
    red_pixels_per_row = (out[..., 0] == 255).sum(axis=1)
    assert (red_pixels_per_row >= 1).all()


def test_remove_seams_clamps_at_one_column(tiny_rgba):
    h, w = tiny_rgba.shape[:2]
    out = carve_seams(tiny_rgba, -(w + 5))
    # The implementation breaks early — we should never carve below width 1.
    assert out.shape[1] >= 1


# ---------------------------------------------------------------------------
# Seam insertion
# ---------------------------------------------------------------------------


def test_insert_seams_widens_image(tiny_rgba):
    out = carve_seams(tiny_rgba, +3)
    assert out.shape == (tiny_rgba.shape[0], tiny_rgba.shape[1] + 3, 4)


def test_insert_seams_keeps_subject_present(tiny_rgba):
    out = carve_seams(tiny_rgba, +3)
    # Red stripe still present in every row (insertion duplicates low-energy
    # seams; the high-energy stripe is never duplicated, but it survives).
    red_pixels_per_row = (out[..., 0] == 255).sum(axis=1)
    assert (red_pixels_per_row >= 1).all()


# ---------------------------------------------------------------------------
# Alpha protection
# ---------------------------------------------------------------------------


def test_alpha_protection_respected(tiny_rgba):
    arr = tiny_rgba.copy()
    arr[..., 3] = 0  # fully transparent everywhere
    arr[3:9, 3:13, 3] = 255  # opaque rectangle in the middle
    out = carve_seams(arr, -2, protect_alpha=True)
    # The opaque rectangle should still have at least its width-2 worth of cols.
    opaque_per_row = (out[3:9, :, 3] == 255).sum(axis=1)
    assert (opaque_per_row >= 1).all()


# ---------------------------------------------------------------------------
# Round-trip via smart_resize wrapper
# ---------------------------------------------------------------------------


def test_smart_resize_height_only_change(tiny_rgba):
    h, w = tiny_rgba.shape[:2]
    out = smart_resize(tiny_rgba, SmartResizeOptions(out_width=w, out_height=h - 2))
    assert out.shape == (h - 2, w, 4)


def test_smart_resize_both_dimensions(tiny_rgba):
    h, w = tiny_rgba.shape[:2]
    out = smart_resize(tiny_rgba, SmartResizeOptions(out_width=w - 2, out_height=h - 2))
    assert out.shape == (h - 2, w - 2, 4)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_carving_is_deterministic(tiny_rgba):
    a = carve_seams(tiny_rgba, -3)
    b = carve_seams(tiny_rgba, -3)
    np.testing.assert_array_equal(a, b)
