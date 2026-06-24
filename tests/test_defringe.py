"""Tests for the edge-fringe desaturation filter."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.defringe import ALL, GREEN, PURPLE, apply_defringe

_RGBA = 4


def _edge(left, right, alpha=255, size=8):
    arr = np.zeros((4, size, _RGBA), dtype=np.uint8)
    arr[:, : size // 2, :3] = left
    arr[:, size // 2 :, :3] = right
    arr[..., 3] = alpha
    return arr


def _saturation(pixel):
    mx, mn = int(max(pixel[:3])), int(min(pixel[:3]))
    return (mx - mn) / max(mx, 1)


def test_amount_zero_is_identity():
    arr = _edge((0, 0, 0), (200, 0, 200))
    assert np.array_equal(apply_defringe(arr, amount=0.0), arr)


def test_neutral_edge_unchanged():
    # A black->white edge carries no fringe hue, so nothing is desaturated.
    arr = _edge((0, 0, 0), (200, 200, 200))
    out = apply_defringe(arr, amount=1.0, hue=PURPLE)
    assert np.array_equal(out, arr)


def test_flat_colour_without_edge_unchanged():
    # A uniform magenta field has no luminance edge -> preserved.
    arr = np.zeros((4, 8, _RGBA), dtype=np.uint8)
    arr[..., 0], arr[..., 2], arr[..., 3] = 200, 200, 255
    out = apply_defringe(arr, amount=1.0, hue=PURPLE)
    assert np.array_equal(out, arr)


def test_magenta_edge_is_desaturated():
    arr = _edge((0, 0, 0), (200, 0, 200))
    out = apply_defringe(arr, amount=1.0, hue=PURPLE)
    edge_col = arr.shape[1] // 2  # first magenta column, on the edge
    assert _saturation(out[1, edge_col]) < _saturation(arr[1, edge_col])


def test_magenta_far_from_edge_preserved():
    arr = _edge((0, 0, 0), (200, 0, 200))
    out = apply_defringe(arr, amount=1.0, hue=PURPLE)
    far = arr.shape[1] - 1  # deep in the flat magenta region
    assert _saturation(out[1, far]) == pytest.approx(_saturation(arr[1, far]), abs=0.02)


def test_purple_mode_ignores_green_fringe():
    arr = _edge((0, 0, 0), (0, 200, 0))
    out = apply_defringe(arr, amount=1.0, hue=PURPLE)
    assert np.array_equal(out, arr)


def test_green_mode_desaturates_green_fringe():
    arr = _edge((0, 0, 0), (0, 200, 0))
    out = apply_defringe(arr, amount=1.0, hue=GREEN)
    edge_col = arr.shape[1] // 2
    assert _saturation(out[1, edge_col]) < _saturation(arr[1, edge_col])


def test_all_mode_handles_both_hues():
    magenta = apply_defringe(_edge((0, 0, 0), (200, 0, 200)), amount=1.0, hue=ALL)
    green = apply_defringe(_edge((0, 0, 0), (0, 200, 0)), amount=1.0, hue=ALL)
    edge_col = 4
    assert _saturation(magenta[1, edge_col]) < _saturation((200, 0, 200))
    assert _saturation(green[1, edge_col]) < _saturation((0, 200, 0))


def test_preserves_alpha():
    arr = _edge((0, 0, 0), (200, 0, 200), alpha=140)
    out = apply_defringe(arr, amount=1.0)
    assert np.array_equal(out[..., 3], arr[..., 3])


def test_does_not_mutate_input():
    arr = _edge((0, 0, 0), (200, 0, 200))
    before = arr.copy()
    apply_defringe(arr, amount=1.0)
    assert np.array_equal(arr, before)


def test_rejects_bad_hue():
    with pytest.raises(ValueError, match="hue must be one of"):
        apply_defringe(_edge((0, 0, 0), (200, 0, 200)), hue="cyan")


@pytest.mark.parametrize("bad", [
    np.zeros((4, 5, 2), dtype=np.uint8),
    np.zeros((4, 5, 4), dtype=np.float32),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError, match="HxWx3/4 uint8"):
        apply_defringe(bad)
