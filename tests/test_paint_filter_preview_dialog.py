"""Tests for the generic filter-preview dialog."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.filter_preview_dialog import FilterPreviewDialog


def _gradient_image(h: int = 32, w: int = 32) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = np.linspace(0, 255, w, dtype=np.uint8)[None, :]
    arr[..., 3] = 255
    return arr


def _multiply_filter(image: np.ndarray, value: float) -> np.ndarray:
    """Reference filter — multiply the red channel by ``value``."""
    out = image.copy()
    out[..., 0] = np.clip(
        image[..., 0].astype(np.float32) * float(value), 0, 255,
    ).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_dialog_rejects_non_rgba(qapp):
    bad = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        FilterPreviewDialog(bad, _multiply_filter)


def test_dialog_rejects_inverted_slider_range(qapp):
    image = _gradient_image()
    with pytest.raises(ValueError, match="slider_min"):
        FilterPreviewDialog(image, _multiply_filter, slider_min=10, slider_max=5)


def test_dialog_rejects_default_outside_range(qapp):
    image = _gradient_image()
    with pytest.raises(ValueError, match="slider_default"):
        FilterPreviewDialog(
            image, _multiply_filter,
            slider_min=0, slider_max=10, slider_default=20,
        )


# ---------------------------------------------------------------------------
# Filter execution
# ---------------------------------------------------------------------------


def test_initial_preview_runs_filter_at_default(qapp):
    image = _gradient_image()
    dialog = FilterPreviewDialog(
        image, _multiply_filter,
        slider_min=0, slider_max=200, slider_default=100,
        value_scale=0.01,   # → 1.0 at default
    )
    try:
        # Default slider × scale = 1.0 → image unchanged.
        np.testing.assert_array_equal(dialog.working_image(), image)
    finally:
        dialog.deleteLater()


def test_slider_change_updates_working_image(qapp):
    image = _gradient_image()
    dialog = FilterPreviewDialog(
        image, _multiply_filter,
        slider_min=0, slider_max=200, slider_default=100,
        value_scale=0.01,
    )
    try:
        dialog._slider.setValue(50)  # noqa: SLF001
        # Bypass the debounce by calling the refresh directly.
        dialog._refresh_preview()  # noqa: SLF001
        # 50 × 0.01 = 0.5 → red channel halved.
        assert int(dialog.working_image()[0, 31, 0]) <= 128
    finally:
        dialog.deleteLater()


def test_slider_value_returns_scaled_input(qapp):
    image = _gradient_image()
    dialog = FilterPreviewDialog(
        image, _multiply_filter,
        slider_min=0, slider_max=200, slider_default=100,
        value_scale=0.01,
    )
    try:
        dialog._slider.setValue(150)  # noqa: SLF001
        assert dialog.slider_value() == pytest.approx(1.5)
    finally:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_filter_exception_keeps_previous_working_image(qapp):
    """A filter that raises ValueError mid-drag must not blank the
    working image — the user's previous accepted state stays."""
    def _maybe_raise(image: np.ndarray, value: float) -> np.ndarray:
        if value > 1.0:
            raise ValueError("over the threshold")
        return _multiply_filter(image, value)

    image = _gradient_image()
    dialog = FilterPreviewDialog(
        image, _maybe_raise,
        slider_min=0, slider_max=200, slider_default=50,
        value_scale=0.01,
    )
    try:
        # First valid update.
        dialog._slider.setValue(80)  # noqa: SLF001
        dialog._refresh_preview()  # noqa: SLF001
        good_state = dialog.working_image().copy()
        # Drag past the threshold — filter raises.
        dialog._slider.setValue(150)  # noqa: SLF001
        dialog._refresh_preview()  # noqa: SLF001
        np.testing.assert_array_equal(dialog.working_image(), good_state)
    finally:
        dialog.deleteLater()


def test_label_format_renders_scaled_value(qapp):
    image = _gradient_image()
    dialog = FilterPreviewDialog(
        image, _multiply_filter,
        slider_min=0, slider_max=100, slider_default=50,
        value_scale=0.5, label_format="{:.2f}",
    )
    try:
        # Default 50 × 0.5 = 25.00.
        assert dialog._value_label.text() == "25.00"  # noqa: SLF001
    finally:
        dialog.deleteLater()


def test_working_image_is_independent_buffer(qapp):
    """The dialog must not mutate the source — working_image is the
    filter's output, separate from the input."""
    image = _gradient_image()
    dialog = FilterPreviewDialog(
        image, _multiply_filter,
        slider_min=0, slider_max=100, slider_default=50,
        value_scale=0.01,
    )
    try:
        dialog._slider.setValue(20)  # noqa: SLF001
        dialog._refresh_preview()  # noqa: SLF001
        # Source unchanged.
        np.testing.assert_array_equal(image, _gradient_image())
    finally:
        dialog.deleteLater()
