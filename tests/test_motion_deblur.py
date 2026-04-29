"""Tests for the AI Motion Deblur plugin's algorithm layer."""
from __future__ import annotations

import numpy as np
import pytest

from ai_motion_deblur.deblur import (
    BLEND_MAX,
    PSF_GAUSSIAN_RADIUS_MAX,
    PSF_GAUSSIAN_RADIUS_MIN,
    PSF_MOTION_LENGTH_MAX,
    PSF_MOTION_LENGTH_MIN,
    SNR_DB_MAX,
    SNR_DB_MIN,
    WienerOptions,
    gaussian_psf,
    motion_psf,
    wiener_deblur,
)


# ---------------------------------------------------------------------------
# PSF constructors
# ---------------------------------------------------------------------------


def test_gaussian_psf_normalised_to_unit_sum():
    psf = gaussian_psf(3)
    assert psf.shape == (7, 7)
    assert pytest.approx(1.0, abs=1e-6) == psf.sum()
    assert (psf >= 0).all()


def test_gaussian_psf_clamps_radius_below_min():
    psf = gaussian_psf(PSF_GAUSSIAN_RADIUS_MIN - 5)
    assert psf.shape[0] >= 2 * PSF_GAUSSIAN_RADIUS_MIN + 1


def test_gaussian_psf_clamps_radius_above_max():
    psf = gaussian_psf(PSF_GAUSSIAN_RADIUS_MAX + 100)
    assert psf.shape[0] == 2 * PSF_GAUSSIAN_RADIUS_MAX + 1


def test_motion_psf_horizontal_is_horizontal():
    psf = motion_psf(15, 0)
    centre_row = psf.shape[0] // 2
    assert psf[centre_row, :].sum() == pytest.approx(1.0, abs=1e-6)
    # Other rows have zero energy.
    other_mass = psf.sum() - psf[centre_row, :].sum()
    assert pytest.approx(0.0, abs=1e-6) == other_mass


def test_motion_psf_vertical_is_vertical():
    psf = motion_psf(15, 90)
    centre_col = psf.shape[1] // 2
    assert psf[:, centre_col].sum() == pytest.approx(1.0, abs=1e-6)


def test_motion_psf_normalised():
    psf = motion_psf(20, 45)
    assert pytest.approx(1.0, abs=1e-6) == psf.sum()


def test_motion_psf_clamps_length():
    psf = motion_psf(PSF_MOTION_LENGTH_MAX + 50, 0)
    expected_size = 2 * (PSF_MOTION_LENGTH_MAX // 2) + 1
    assert psf.shape == (expected_size, expected_size)


def test_motion_psf_zero_length_falls_back_to_unit():
    psf = motion_psf(PSF_MOTION_LENGTH_MIN - 10, 0)
    # Implementation clamps to PSF_MOTION_LENGTH_MIN — never returns an empty PSF.
    assert pytest.approx(1.0, abs=1e-6) == psf.sum()


# ---------------------------------------------------------------------------
# Wiener deblur — input validation
# ---------------------------------------------------------------------------


def test_wiener_rejects_non_rgba(sample_rgb_array):
    with pytest.raises(ValueError):
        wiener_deblur(sample_rgb_array)


def test_wiener_rejects_unknown_psf_kind(sample_rgba_array):
    with pytest.raises(ValueError):
        wiener_deblur(sample_rgba_array, WienerOptions(psf_kind="lorentz"))


# ---------------------------------------------------------------------------
# Wiener deblur — happy path / shape preservation
# ---------------------------------------------------------------------------


def test_wiener_returns_same_shape_and_dtype(sample_rgba_array):
    out = wiener_deblur(sample_rgba_array)
    assert out.shape == sample_rgba_array.shape
    assert out.dtype == np.uint8


def test_wiener_preserves_alpha(sample_rgba_array):
    out = wiener_deblur(sample_rgba_array, WienerOptions(psf_kind="motion"))
    np.testing.assert_array_equal(out[..., 3], sample_rgba_array[..., 3])


def test_wiener_blend_zero_returns_copy(sample_rgba_array):
    out = wiener_deblur(sample_rgba_array, WienerOptions(blend=0.0))
    np.testing.assert_array_equal(out, sample_rgba_array)
    assert out is not sample_rgba_array


def test_wiener_blend_clamped_above_one(sample_rgba_array):
    full = wiener_deblur(sample_rgba_array, WienerOptions(blend=BLEND_MAX))
    over = wiener_deblur(sample_rgba_array, WienerOptions(blend=5.0))
    np.testing.assert_array_equal(full, over)


def test_wiener_snr_below_min_clamped(sample_rgba_array):
    inside = wiener_deblur(sample_rgba_array, WienerOptions(snr_db=SNR_DB_MIN))
    under = wiener_deblur(sample_rgba_array, WienerOptions(snr_db=SNR_DB_MIN - 50))
    np.testing.assert_array_equal(inside, under)


def test_wiener_snr_above_max_clamped(sample_rgba_array):
    inside = wiener_deblur(sample_rgba_array, WienerOptions(snr_db=SNR_DB_MAX))
    over = wiener_deblur(sample_rgba_array, WienerOptions(snr_db=SNR_DB_MAX + 50))
    np.testing.assert_array_equal(inside, over)


# ---------------------------------------------------------------------------
# Round-trip: blur → wiener → recover sharper
# ---------------------------------------------------------------------------


def test_wiener_recovers_some_high_frequency_content():
    """A toy synthetic blur → deblur should pull the result closer to the
    original than the blurred version was.
    """
    rng = np.random.default_rng(0xC0FFEE)
    sharp_rgb = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8).astype(np.float32)
    psf = gaussian_psf(2)
    # Convolve via FFT (matches Wiener convention).
    blurred = np.zeros_like(sharp_rgb)
    for c in range(3):
        psf_padded = np.zeros_like(sharp_rgb[..., c])
        psf_padded[:psf.shape[0], :psf.shape[1]] = psf
        psf_padded = np.roll(psf_padded, -(psf.shape[0] // 2), axis=0)
        psf_padded = np.roll(psf_padded, -(psf.shape[1] // 2), axis=1)
        g = np.fft.rfft2(sharp_rgb[..., c])
        h = np.fft.rfft2(psf_padded)
        blurred[..., c] = np.fft.irfft2(g * h, s=sharp_rgb[..., c].shape)
    blurred_clamped = np.clip(blurred, 0, 255).astype(np.uint8)
    rgba = np.concatenate(
        [blurred_clamped, np.full((32, 32, 1), 255, dtype=np.uint8)], axis=-1,
    )
    deblurred = wiener_deblur(rgba, WienerOptions(
        psf_kind="gaussian", gaussian_radius=2, snr_db=40, blend=1.0,
    ))
    sharp_uint8 = np.clip(sharp_rgb, 0, 255).astype(np.uint8)

    error_before = float(np.abs(blurred_clamped.astype(np.int16)
                                - sharp_uint8.astype(np.int16)).mean())
    error_after = float(np.abs(deblurred[..., :3].astype(np.int16)
                               - sharp_uint8.astype(np.int16)).mean())
    assert error_after <= error_before
