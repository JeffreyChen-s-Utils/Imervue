"""Qt smoke tests for the liquify dialog."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.liquify_dialog import LiquifyDialog


def _gradient_image(h: int = 64, w: int = 64) -> np.ndarray:
    """Image with a horizontal red gradient so warp effects are visible."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = np.linspace(0, 255, w, dtype=np.uint8)[None, :]
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_dialog_rejects_non_rgba(qapp):
    bad = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        LiquifyDialog(bad)


def test_dialog_default_state(qapp):
    dialog = LiquifyDialog(_gradient_image())
    try:
        # Default brush is the first WARP_KIND.
        from Imervue.paint.liquify import WARP_KINDS
        assert dialog.kind() == WARP_KINDS[0]
        # Strength slider is 0..100; default = 50 → engine 0.5.
        assert dialog.strength() == pytest.approx(0.5)
        assert dialog.radius() > 0
    finally:
        dialog.deleteLater()


def test_dialog_working_image_starts_as_copy_of_input(qapp):
    src = _gradient_image()
    dialog = LiquifyDialog(src)
    try:
        np.testing.assert_array_equal(dialog.working_image(), src)
        # Must be a copy, not the same buffer — accept must commit
        # the dialog's edits without surprising the caller.
        assert dialog.working_image() is not src
    finally:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# apply_warp_at
# ---------------------------------------------------------------------------


def test_apply_push_warp_modifies_pixels(qapp):
    dialog = LiquifyDialog(_gradient_image())
    try:
        before = dialog.working_image().copy()
        dialog.apply_warp_at((32.0, 32.0), drag_dx=10.0, drag_dy=0.0)
        assert (dialog.working_image() != before).any()
    finally:
        dialog.deleteLater()


def test_apply_pinch_changes_kind_drives_engine(qapp):
    dialog = LiquifyDialog(_gradient_image())
    try:
        # Switch to pinch via the combo-box index lookup.
        dialog._kind_combo.setCurrentIndex(1)  # noqa: SLF001
        before = dialog.working_image().copy()
        dialog.apply_warp_at((32.0, 32.0), drag_dx=0.0, drag_dy=0.0)
        # Pinch is a no-arg warp — applying with drag=0 still moves
        # pixels because the engine pulls them toward the centre.
        assert (dialog.working_image() != before).any()
    finally:
        dialog.deleteLater()


def test_apply_zero_strength_is_no_op(qapp):
    """Strength 0 means the engine warp has no effect — the working
    image stays bit-identical to the original."""
    dialog = LiquifyDialog(_gradient_image())
    try:
        dialog._strength_slider.setValue(0)  # noqa: SLF001
        before = dialog.working_image().copy()
        dialog.apply_warp_at((32.0, 32.0), drag_dx=10.0, drag_dy=10.0)
        np.testing.assert_array_equal(dialog.working_image(), before)
    finally:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# Reset behaviour
# ---------------------------------------------------------------------------


def test_reset_restores_original_buffer(qapp):
    src = _gradient_image()
    dialog = LiquifyDialog(src)
    try:
        dialog.apply_warp_at((32.0, 32.0), drag_dx=10.0, drag_dy=0.0)
        assert (dialog.working_image() != src).any()
        dialog._on_reset()  # noqa: SLF001
        np.testing.assert_array_equal(dialog.working_image(), src)
    finally:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# Strength conversion
# ---------------------------------------------------------------------------


def test_strength_slider_drives_engine_value(qapp):
    dialog = LiquifyDialog(_gradient_image())
    try:
        dialog._strength_slider.setValue(75)  # noqa: SLF001
        assert dialog.strength() == pytest.approx(0.75)
    finally:
        dialog.deleteLater()


def test_radius_slider_drives_radius(qapp):
    dialog = LiquifyDialog(_gradient_image())
    try:
        dialog._radius_slider.setValue(30)  # noqa: SLF001
        assert dialog.radius() == 30
    finally:
        dialog.deleteLater()
