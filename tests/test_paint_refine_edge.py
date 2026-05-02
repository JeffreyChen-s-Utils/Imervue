"""Tests for refine_edge — selection-edge finishing pipeline."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.selection_ops import MAX_RADIUS, refine_edge


def _square_selection(h=20, w=20, top=4, left=4, side=12):
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[top:top + side, left:left + side] = True
    return sel


# ---------------------------------------------------------------------------
# Identity / contracts
# ---------------------------------------------------------------------------


def test_refine_edge_returns_float32_in_unit_range():
    sel = _square_selection()
    out = refine_edge(sel)
    assert out.dtype == np.float32
    assert out.shape == sel.shape
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_refine_edge_zero_params_is_bool_to_float_cast():
    sel = _square_selection()
    out = refine_edge(sel)
    expected = sel.astype(np.float32)
    np.testing.assert_array_equal(out, expected)


def test_refine_edge_rejects_non_bool_mask():
    bad = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="bool"):
        refine_edge(bad)


def test_refine_edge_rejects_oversized_feather():
    sel = _square_selection()
    with pytest.raises(ValueError, match=str(MAX_RADIUS)):
        refine_edge(sel, feather=MAX_RADIUS + 1)


def test_refine_edge_clamps_oversized_smooth():
    sel = _square_selection()
    # Oversized smooth shouldn't raise — it just clamps to the cap.
    out = refine_edge(sel, smooth=MAX_RADIUS + 100)
    assert out.shape == sel.shape


# ---------------------------------------------------------------------------
# Shift
# ---------------------------------------------------------------------------


def test_refine_edge_shift_positive_grows_boundary():
    sel = _square_selection()
    out = refine_edge(sel, shift=2)
    assert (out > 0).sum() > sel.sum()


def test_refine_edge_shift_negative_shrinks_boundary():
    sel = _square_selection()
    out = refine_edge(sel, shift=-2)
    assert (out > 0).sum() < sel.sum()


def test_refine_edge_shift_zero_is_identity_alpha():
    sel = _square_selection()
    out = refine_edge(sel, shift=0)
    expected = sel.astype(np.float32)
    np.testing.assert_array_equal(out, expected)


# ---------------------------------------------------------------------------
# Smooth
# ---------------------------------------------------------------------------


def test_refine_edge_smooth_removes_isolated_pixels():
    """A jagged single-pixel spike outside the main shape should be
    smoothed away."""
    sel = _square_selection()
    sel[0, 0] = True   # isolated pixel
    out = refine_edge(sel, smooth=2)
    assert out[0, 0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Feather
# ---------------------------------------------------------------------------


def test_refine_edge_feather_softens_edge():
    """Feather should produce intermediate alpha values along the edge."""
    sel = _square_selection()
    out = refine_edge(sel, feather=2)
    # Some pixels should have intermediate alpha (0 < α < 1).
    intermediate = (out > 0.05) & (out < 0.95)
    assert intermediate.any()


def test_refine_edge_feather_zero_keeps_bool_alpha():
    sel = _square_selection()
    out = refine_edge(sel, feather=0)
    distinct = set(np.unique(out).tolist())
    assert distinct <= {0.0, 1.0}


# ---------------------------------------------------------------------------
# Contrast
# ---------------------------------------------------------------------------


def test_refine_edge_positive_contrast_sharpens_after_feather():
    """A feathered edge with high positive contrast should pull the
    intermediate alpha values toward 0 or 1 — strict-binary count
    (α < 0.05 or α > 0.95) goes up."""
    sel = _square_selection()
    feathered = refine_edge(sel, feather=3)
    sharpened = refine_edge(sel, feather=3, contrast=1.0)
    binary_before = ((feathered < 0.05) | (feathered > 0.95)).sum()
    binary_after = ((sharpened < 0.05) | (sharpened > 0.95)).sum()
    assert binary_after >= binary_before


def test_refine_edge_negative_contrast_softens():
    """Negative contrast should produce a less binary alpha than
    feather alone."""
    sel = _square_selection()
    feathered = refine_edge(sel, feather=3)
    softened = refine_edge(sel, feather=3, contrast=-0.8)
    intermediate_feathered = ((feathered > 0.05) & (feathered < 0.95)).sum()
    intermediate_softened = ((softened > 0.05) & (softened < 0.95)).sum()
    assert intermediate_softened >= intermediate_feathered


def test_refine_edge_contrast_clamped_to_unit_range():
    sel = _square_selection()
    out = refine_edge(sel, feather=3, contrast=0.99)
    assert out.min() >= 0.0
    assert out.max() <= 1.0


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------


def test_refine_edge_combined_pipeline_runs():
    """All four ops at once shouldn't crash and should produce a
    valid alpha mask."""
    sel = _square_selection()
    out = refine_edge(
        sel, smooth=1, feather=2, contrast=0.5, shift=1,
    )
    assert out.shape == sel.shape
    assert out.dtype == np.float32
    assert out.min() >= 0.0
    assert out.max() <= 1.0
