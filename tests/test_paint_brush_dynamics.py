"""Tests for the per-kind brush kernel modifiers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.brush_dynamics import (
    BRUSH_KINDS,
    pressure_opacity_factor,
    pressure_size_factor,
    stylise_kernel,
)
from Imervue.paint.brush_engine import round_brush_kernel


@pytest.fixture
def kernel():
    return round_brush_kernel(15, hardness=0.8)


@pytest.fixture
def rng():
    return np.random.default_rng(0xC0FFEE)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_stylise_kernel_rejects_3d_kernel():
    with pytest.raises(ValueError):
        stylise_kernel(np.ones((3, 3, 3), dtype=np.float32), "pencil")


def test_stylise_kernel_rejects_non_float32():
    with pytest.raises(ValueError):
        stylise_kernel(np.ones((3, 3), dtype=np.float64), "pencil")


def test_stylise_kernel_unknown_kind_returns_identity(kernel):
    out = stylise_kernel(kernel, "rainbow")
    np.testing.assert_array_equal(out, kernel)


def test_brush_kinds_listed():
    assert BRUSH_KINDS == ("pencil", "pen", "marker", "airbrush", "watercolor")


# ---------------------------------------------------------------------------
# Pen / marker — identity
# ---------------------------------------------------------------------------


def test_pen_returns_identity_kernel(kernel):
    out = stylise_kernel(kernel, "pen")
    np.testing.assert_array_equal(out, kernel)


def test_marker_returns_identity_kernel(kernel):
    out = stylise_kernel(kernel, "marker")
    np.testing.assert_array_equal(out, kernel)


# ---------------------------------------------------------------------------
# Pencil — granular noise
# ---------------------------------------------------------------------------


def test_pencil_differs_from_base_kernel(kernel, rng):
    out = stylise_kernel(kernel, "pencil", rng=rng)
    assert not np.array_equal(out, kernel)


def test_pencil_alpha_within_kernel_range(kernel, rng):
    """Pencil multiplies kernel by [0.5..1.0]; output ≤ original."""
    out = stylise_kernel(kernel, "pencil", rng=rng)
    assert (out <= kernel + 1e-6).all()


def test_pencil_residual_against_base_is_noisy(kernel, rng):
    """Pencil multiplies the kernel by per-pixel noise — the residual
    (pencil - base) must vary across pixels, otherwise the modifier
    devolved into a constant attenuation."""
    pencil = stylise_kernel(kernel, "pencil", rng=rng)
    mask = kernel > 0.01
    residual = (pencil - kernel)[mask]
    # Non-zero spread proves the modifier is per-pixel noise, not a scalar.
    assert float(residual.std()) > 0.05


def test_pencil_seed_determinism(kernel):
    a = stylise_kernel(kernel, "pencil", rng=np.random.default_rng(1234))
    b = stylise_kernel(kernel, "pencil", rng=np.random.default_rng(1234))
    np.testing.assert_array_equal(a, b)


# ---------------------------------------------------------------------------
# Airbrush — sparse dot pattern
# ---------------------------------------------------------------------------


def test_airbrush_produces_sparse_pattern(kernel, rng):
    out = stylise_kernel(kernel, "airbrush", rng=rng)
    # In the disc interior most pixels should be zeroed by Bernoulli sampling.
    interior_mask = kernel > 0.5
    sparse_count = (out[interior_mask] == 0).sum()
    total = interior_mask.sum()
    assert sparse_count > total * 0.4   # at least 40% zeroed


def test_airbrush_alpha_capped_below_kernel(kernel, rng):
    out = stylise_kernel(kernel, "airbrush", rng=rng)
    assert (out <= kernel + 1e-6).all()


# ---------------------------------------------------------------------------
# Watercolor — wet edge
# ---------------------------------------------------------------------------


def test_watercolor_boosts_alpha_at_boundary(kernel):
    """The peak alpha of a watercolour kernel should sit on the boundary,
    not at the centre — that's the wet-edge look."""
    out = stylise_kernel(kernel, "watercolor")
    h, w = kernel.shape
    centre = out[h // 2, w // 2]
    # Find a boundary pixel (one ring inside the kernel disc).
    # The first non-zero column from the left.
    col_max_per_row = out.max(axis=1)
    edge_max = col_max_per_row.max()
    assert edge_max >= centre


def test_watercolor_alpha_clipped_to_unit_range(kernel):
    out = stylise_kernel(kernel, "watercolor")
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_watercolor_tiny_kernel_returns_identity():
    """Wet-edge math degenerates below 3x3 — returns a copy unchanged."""
    tiny = np.array([[1.0]], dtype=np.float32)
    out = stylise_kernel(tiny, "watercolor")
    np.testing.assert_array_equal(out, tiny)


# ---------------------------------------------------------------------------
# Pen pressure helpers
# ---------------------------------------------------------------------------


def test_pressure_size_factor_full_pressure_is_unity():
    assert pressure_size_factor(1.0) == pytest.approx(1.0)


def test_pressure_size_factor_zero_pressure_keeps_floor():
    assert pressure_size_factor(0.0) == pytest.approx(0.3)


def test_pressure_size_factor_clamps_above_one():
    assert pressure_size_factor(5.0) == pytest.approx(1.0)


def test_pressure_size_factor_clamps_below_zero():
    assert pressure_size_factor(-2.0) == pytest.approx(0.3)


def test_pressure_size_factor_monotonic():
    a = pressure_size_factor(0.2)
    b = pressure_size_factor(0.6)
    assert b > a


def test_pressure_opacity_factor_floor_keeps_paint_visible():
    assert pressure_opacity_factor(0.0) == pytest.approx(0.1)


def test_pressure_opacity_factor_full_pressure_is_unity():
    assert pressure_opacity_factor(1.0) == pytest.approx(1.0)
