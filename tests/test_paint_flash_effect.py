"""Tests for the action-flash / starburst renderer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.flash_effect import (
    DEFAULT_FLASH_SPIKES,
    FLASH_SPIKES_MAX,
    FLASH_SPIKES_MIN,
    FlashOptions,
    render_flash,
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_default_options_pass():
    opts = FlashOptions()
    assert opts.spikes == DEFAULT_FLASH_SPIKES


def test_rejects_spikes_below_min():
    with pytest.raises(ValueError, match="spikes"):
        FlashOptions(spikes=FLASH_SPIKES_MIN - 1)


def test_rejects_spikes_above_max():
    with pytest.raises(ValueError, match="spikes"):
        FlashOptions(spikes=FLASH_SPIKES_MAX + 1)


def test_rejects_outer_radius_too_small():
    with pytest.raises(ValueError, match="outer_radius_ratio"):
        FlashOptions(outer_radius_ratio=0.0)


def test_rejects_outer_radius_above_max():
    with pytest.raises(ValueError, match="outer_radius_ratio"):
        FlashOptions(outer_radius_ratio=2.0)


def test_rejects_inner_above_outer():
    with pytest.raises(ValueError, match="inner_radius_ratio"):
        FlashOptions(inner_radius_ratio=0.5, outer_radius_ratio=0.4)


def test_rejects_negative_inner():
    with pytest.raises(ValueError, match="inner_radius_ratio"):
        FlashOptions(inner_radius_ratio=-0.1)


def test_rejects_halo_radius_above_max():
    with pytest.raises(ValueError, match="halo_radius_ratio"):
        FlashOptions(halo_radius_ratio=2.5)


def test_rejects_halo_opacity_above_one():
    with pytest.raises(ValueError, match="halo_opacity"):
        FlashOptions(halo_opacity=1.5)


def test_rejects_color_with_wrong_length():
    with pytest.raises(ValueError, match="color"):
        FlashOptions(color=(0, 0))   # type: ignore[arg-type]


def test_rejects_color_component_out_of_range():
    with pytest.raises(ValueError, match="color"):
        FlashOptions(color=(0, 0, 999))


# ---------------------------------------------------------------------------
# render_flash — output shape + canvas validation
# ---------------------------------------------------------------------------


def test_render_returns_rgba_buffer():
    out = render_flash((48, 48), FlashOptions())
    assert out.shape == (48, 48, 4)
    assert out.dtype == np.uint8


def test_render_rejects_non_positive_canvas():
    with pytest.raises(ValueError):
        render_flash((0, 16), FlashOptions())


# ---------------------------------------------------------------------------
# Centre + halo behaviour
# ---------------------------------------------------------------------------


def test_centre_pixel_is_solid():
    """Inside the burst the alpha is fully opaque."""
    out = render_flash((48, 48), FlashOptions())
    assert out[24, 24, 3] == 255


def test_far_corner_has_no_halo_when_halo_zero():
    out = render_flash((48, 48), FlashOptions(halo_opacity=0.0))
    assert out[0, 0, 3] == 0


def test_halo_falls_off_with_distance():
    """Closer pixels to centre have higher halo alpha than farther ones."""
    out = render_flash((48, 48), FlashOptions(
        spikes=12, outer_radius_ratio=0.06,   # tiny burst — most ring is halo
        inner_radius_ratio=0.0,
        halo_radius_ratio=1.0, halo_opacity=0.8,
    ))
    near = int(out[24, 30, 3])
    far = int(out[24, 47, 3])
    assert near > far


def test_color_propagates_to_burst_pixels():
    out = render_flash((48, 48), FlashOptions(color=(200, 50, 30)))
    inside = out[24, 24]
    assert tuple(inside[:3]) == (200, 50, 30)


def test_rotation_changes_spike_pattern():
    """A non-trivial rotation produces a different alpha mask along
    the spike pattern."""
    a = render_flash((48, 48), FlashOptions(rotation_deg=0.0))
    b = render_flash((48, 48), FlashOptions(rotation_deg=15.0))
    # Sample a ring of pixels around the rim — at least one of them
    # must differ between the two rotations.
    rim_a = a[6, :, 3]
    rim_b = b[6, :, 3]
    assert not np.array_equal(rim_a, rim_b)


def test_explicit_centre_shifts_burst():
    """A non-default centre moves the solid-burst region away from
    the canvas centre."""
    out = render_flash((48, 48), FlashOptions(
        center=(8, 8), halo_opacity=0.0,
    ))
    # Pixel at the requested centre is solid; canvas centre is empty.
    assert out[8, 8, 3] == 255
    assert out[24, 24, 3] == 0


# ---------------------------------------------------------------------------
# Spike count
# ---------------------------------------------------------------------------


def test_more_spikes_produce_more_alternations():
    """Counting alpha alternations along a ring around the centre
    grows with spike count — basic shape sanity."""
    def alternations(arr: np.ndarray) -> int:
        # Count transparent↔opaque transitions along a ring of pixels
        # at radius 12 from the centre (24, 24) of a 48×48 canvas.
        ring = []
        for theta in np.linspace(0, 2 * np.pi, 200, endpoint=False):
            x = int(round(24 + 12 * np.cos(theta)))
            y = int(round(24 + 12 * np.sin(theta)))
            ring.append(int(arr[y, x] > 0))
        return sum(1 for i in range(len(ring)) if ring[i] != ring[i - 1])

    a = render_flash((48, 48), FlashOptions(
        spikes=8, halo_opacity=0.0, inner_radius_ratio=0.05,
        outer_radius_ratio=0.4,
    ))
    b = render_flash((48, 48), FlashOptions(
        spikes=24, halo_opacity=0.0, inner_radius_ratio=0.05,
        outer_radius_ratio=0.4,
    ))
    assert alternations(b[..., 3]) > alternations(a[..., 3])
