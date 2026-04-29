"""Tests for the four auto-colour-balance algorithms."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.auto_color_balance import (
    METHODS,
    AutoBalanceOptions,
    auto_balance,
    gray_world,
    percentile_stretch,
    simplified_retinex,
    white_patch,
)


def _solid(h, w, rgb):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


def _gradient(h, w, ramp_axis="x"):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    if ramp_axis == "x":
        ramp = np.linspace(0, 255, w, dtype=np.uint8)
        arr[..., 0] = ramp
        arr[..., 1] = ramp
        arr[..., 2] = ramp
    else:
        ramp = np.linspace(0, 255, h, dtype=np.uint8)[:, None]
        arr[..., 0] = ramp
        arr[..., 1] = ramp
        arr[..., 2] = ramp
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Constants registry
# ---------------------------------------------------------------------------


def test_methods_registry_has_all_four():
    assert set(METHODS) == {
        "gray_world", "white_patch", "percentile_stretch", "simplified_retinex",
    }


# ---------------------------------------------------------------------------
# gray_world
# ---------------------------------------------------------------------------


def test_gray_world_neutralises_warm_cast():
    """A reddish image should land closer to neutral after gray-world."""
    base = _solid(16, 16, (200, 100, 80))
    out = gray_world(base)
    means_before = base[..., :3].astype(np.float32).reshape(-1, 3).mean(axis=0)
    means_after = out[..., :3].astype(np.float32).reshape(-1, 3).mean(axis=0)
    spread_before = float(means_before.max() - means_before.min())
    spread_after = float(means_after.max() - means_after.min())
    assert spread_after < spread_before


def test_gray_world_handles_black_image():
    base = _solid(8, 8, (0, 0, 0))
    out = gray_world(base)
    assert np.array_equal(out, base)


def test_gray_world_neutral_input_unchanged():
    base = _solid(8, 8, (128, 128, 128))
    out = gray_world(base)
    assert np.array_equal(out, base)


# ---------------------------------------------------------------------------
# white_patch
# ---------------------------------------------------------------------------


def test_white_patch_pushes_brightest_to_white():
    """A dim image's 99th percentile should land near 255 after white-patch."""
    base = _solid(32, 32, (100, 100, 100))
    out = white_patch(base)
    high = np.percentile(out[..., :3].astype(np.float32).reshape(-1, 3), 99, axis=0)
    assert (high >= 250).all()


def test_white_patch_handles_black_image():
    base = _solid(8, 8, (0, 0, 0))
    out = white_patch(base)
    assert np.array_equal(out, base)


# ---------------------------------------------------------------------------
# percentile_stretch
# ---------------------------------------------------------------------------


def test_percentile_stretch_expands_compressed_range():
    """An image with compressed [50, 150] range should land closer to [0, 255]."""
    base = _solid(16, 16, (100, 100, 100))
    base[..., :3] = np.clip(
        base[..., :3].astype(np.int16)
        + np.random.default_rng(3).integers(-50, 50, base[..., :3].shape),
        50, 150,
    ).astype(np.uint8)
    out = percentile_stretch(base, percentile=1.0)
    assert int(out[..., :3].max()) >= 240
    assert int(out[..., :3].min()) <= 15


def test_percentile_stretch_flat_input_unchanged():
    """If a channel has zero spread, the output for that channel is unchanged."""
    base = _solid(8, 8, (128, 128, 128))
    out = percentile_stretch(base, percentile=1.0)
    assert np.array_equal(out, base)


# ---------------------------------------------------------------------------
# simplified_retinex
# ---------------------------------------------------------------------------


def test_retinex_returns_correct_shape_and_dtype():
    base = _gradient(32, 32)
    out = simplified_retinex(base, radius=8)
    assert out.shape == base.shape
    assert out.dtype == np.uint8


def test_retinex_preserves_alpha():
    base = _solid(16, 16, (100, 80, 60))
    base[..., 3] = 80
    out = simplified_retinex(base, radius=4)
    assert (out[..., 3] == 80).all()


def test_retinex_radius_clamped():
    base = _solid(16, 16, (100, 100, 100))
    # Out-of-range radius shouldn't raise
    out = simplified_retinex(base, radius=999)
    assert out.shape == base.shape


# ---------------------------------------------------------------------------
# auto_balance dispatch
# ---------------------------------------------------------------------------


def test_auto_balance_zero_intensity_is_identity():
    base = _solid(8, 8, (200, 100, 80))
    out = auto_balance(base, AutoBalanceOptions(intensity=0.0))
    assert np.array_equal(out, base)


def test_auto_balance_unknown_method_returns_input():
    base = _solid(8, 8, (200, 100, 80))
    out = auto_balance(base, AutoBalanceOptions(method="bogus"))
    assert np.array_equal(out, base)


def test_auto_balance_partial_blend():
    """50% intensity should sit between input and full output."""
    base = _solid(16, 16, (200, 100, 80))
    full = auto_balance(base, AutoBalanceOptions(method="gray_world", intensity=1.0))
    half = auto_balance(base, AutoBalanceOptions(method="gray_world", intensity=0.5))
    # Each channel of half should fall between base and full (inclusive)
    for ch in range(3):
        b_v, h_v, f_v = (
            int(base[0, 0, ch]),
            int(half[0, 0, ch]),
            int(full[0, 0, ch]),
        )
        lo, hi = sorted([b_v, f_v])
        assert lo - 1 <= h_v <= hi + 1


def test_auto_balance_rejects_non_rgba():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        auto_balance(arr)


# ---------------------------------------------------------------------------
# Dialog smoke
# ---------------------------------------------------------------------------


def test_dialog_loads_and_saves(qapp, tmp_path):
    from PIL import Image

    from Imervue.gui.auto_color_balance_dialog import AutoColorBalanceDialog

    src = tmp_path / "subject.png"
    Image.fromarray(_solid(32, 32, (200, 100, 80)), mode="RGBA").save(str(src))

    class FakeViewer:
        model = type("M", (), {"images": [str(src)]})()
        current_index = 0
        main_window = None

    dlg = AutoColorBalanceDialog(FakeViewer(), str(src))
    # Pick gray-world and commit
    for i in range(dlg._method.count()):
        if dlg._method.itemData(i) == "gray_world":
            dlg._method.setCurrentIndex(i)
            break
    dlg._commit()

    out = tmp_path / "subject_balanced.png"
    assert out.exists()
