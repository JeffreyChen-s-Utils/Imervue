"""Tests for the Preferences dialog and the VRAM-budget helpers."""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.vram_budget import (
    VRAM_MAX_MB,
    VRAM_MIN_MB,
    clamp_detected_bytes,
    compute_user_override_bytes,
    mipmap_texture_bytes,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# compute_user_override_bytes
# ---------------------------------------------------------------------------


def test_user_override_returns_none_when_auto_on():
    settings = {"vram_limit_auto": True, "vram_limit_mb": 4096}
    assert compute_user_override_bytes(settings) is None


def test_user_override_returns_bytes_when_auto_off():
    settings = {"vram_limit_auto": False, "vram_limit_mb": 2048}
    assert compute_user_override_bytes(settings) == 2048 * 1024 * 1024


@pytest.mark.parametrize(
    "user_mb,expected_mb",
    [
        (10, VRAM_MIN_MB),     # below floor → clamp up
        (16384, VRAM_MAX_MB),  # above ceiling → clamp down
        (256, 256),            # exactly floor
        (8192, 8192),          # exactly ceiling
        (1024, 1024),          # mid-range untouched
    ],
)
def test_user_override_clamps_to_safe_range(user_mb, expected_mb):
    settings = {"vram_limit_auto": False, "vram_limit_mb": user_mb}
    assert compute_user_override_bytes(settings) == expected_mb * 1024 * 1024


def test_user_override_handles_garbage_value():
    settings = {"vram_limit_auto": False, "vram_limit_mb": "not-a-number"}
    assert compute_user_override_bytes(settings) is None


def test_user_override_default_when_key_missing():
    """Missing key with auto off → falls back to documented default."""
    settings = {"vram_limit_auto": False}
    # Default is 1536 MB and that's mid-range so no clamping
    assert compute_user_override_bytes(settings) == 1536 * 1024 * 1024


# ---------------------------------------------------------------------------
# clamp_detected_bytes
# ---------------------------------------------------------------------------


def test_clamp_detected_floor():
    assert clamp_detected_bytes(0) == VRAM_MIN_MB * 1024 * 1024


def test_clamp_detected_ceiling():
    huge = 32 * 1024 * 1024 * 1024
    assert clamp_detected_bytes(huge) == VRAM_MAX_MB * 1024 * 1024


def test_clamp_detected_passthrough():
    mid = 2 * 1024 * 1024 * 1024
    assert clamp_detected_bytes(mid) == mid


# ---------------------------------------------------------------------------
# mipmap_texture_bytes
# ---------------------------------------------------------------------------


def test_mipmap_bytes_is_four_thirds_of_base():
    """The full mipmap chain converges to 4/3 the base texture
    size. For a clean power-of-two, the math is exact."""
    # 64 × 64 × 4 = 16384 base → 16384 * 4 // 3 = 21845 (ceil)
    base = 64 * 64 * 4
    out = mipmap_texture_bytes(64, 64)
    assert out > base   # overhead > 0
    # Should be close to 4/3 × base, within the integer-ceil tolerance.
    assert abs(out - base * 4 / 3) <= 1


def test_mipmap_bytes_grows_quadratically_with_side():
    """Doubling each side quadruples the total — same shape as
    a flat texture, mipmap just scales the constant. Small +/-
    tolerance because the ceiling-up at each call adds at most
    a couple of bytes."""
    small = mipmap_texture_bytes(256, 256)
    big = mipmap_texture_bytes(512, 512)
    assert abs(big - small * 4) <= 4


def test_mipmap_bytes_zero_for_empty_image():
    """Defensive: zero-dimension input → 0 cost. The texture
    upload path skips these but the budget helper still needs to
    answer cleanly."""
    assert mipmap_texture_bytes(0, 100) == 0
    assert mipmap_texture_bytes(100, 0) == 0
    assert mipmap_texture_bytes(0, 0) == 0


def test_mipmap_bytes_negative_returns_zero():
    """A stale image reference might briefly produce negative
    dims during teardown — must not feed negative numbers into
    the VRAM accounting."""
    assert mipmap_texture_bytes(-1, 100) == 0
    assert mipmap_texture_bytes(100, -1) == 0


def test_mipmap_bytes_custom_bytes_per_pixel():
    """RGB (3 bpp) should land at 3/4 of RGBA's total — tunable
    for codecs that don't store alpha."""
    rgba = mipmap_texture_bytes(64, 64, bytes_per_pixel=4)
    rgb = mipmap_texture_bytes(64, 64, bytes_per_pixel=3)
    assert abs(rgb - rgba * 3 / 4) <= 1


def test_mipmap_bytes_zero_bpp_is_safe():
    """0 bytes-per-pixel is meaningless but mustn't crash."""
    assert mipmap_texture_bytes(64, 64, bytes_per_pixel=0) == 0


def test_mipmap_bytes_rounds_up_not_down():
    """Integer ceiling: any non-zero remainder of base × 4 / 3
    must add one byte. Catches a regression where the float
    rounding causes under-accounting."""
    # base = 7 (odd) → base * 4 = 28 → 28/3 ≈ 9.33 → must ceil to 10.
    assert mipmap_texture_bytes(7, 1, bytes_per_pixel=1) == 10


# ---------------------------------------------------------------------------
# Preferences dialog persistence
# ---------------------------------------------------------------------------


def test_preferences_dialog_persists_vram_settings(qapp):
    from Imervue.gui.preferences_dialog import PreferencesDialog
    user_setting_dict["vram_limit_auto"] = True
    user_setting_dict["vram_limit_mb"] = 1536

    dlg = PreferencesDialog()
    dlg._auto_vram.setChecked(False)
    dlg._vram_spin.setValue(3072)
    dlg._accept()

    assert user_setting_dict["vram_limit_auto"] is False
    assert user_setting_dict["vram_limit_mb"] == 3072


def test_preferences_dialog_round_trip_auto(qapp):
    from Imervue.gui.preferences_dialog import PreferencesDialog
    user_setting_dict["vram_limit_auto"] = False
    user_setting_dict["vram_limit_mb"] = 2048

    dlg = PreferencesDialog()
    assert dlg._auto_vram.isChecked() is False
    assert dlg._vram_spin.value() == 2048
    assert dlg._vram_spin.isEnabled()

    dlg._auto_vram.setChecked(True)
    assert dlg._vram_spin.isEnabled() is False
    dlg._accept()
    assert user_setting_dict["vram_limit_auto"] is True


def test_preferences_dialog_spinbox_range(qapp):
    from Imervue.gui.preferences_dialog import PreferencesDialog
    dlg = PreferencesDialog()
    assert dlg._vram_spin.minimum() == VRAM_MIN_MB
    assert dlg._vram_spin.maximum() == VRAM_MAX_MB


# ---------------------------------------------------------------------------
# Wrapper + reject path
# ---------------------------------------------------------------------------


def test_open_preferences_dialog_smoke(qapp, monkeypatch):
    """The wrapper builds + opens the dialog without raising."""
    from Imervue.gui import preferences_dialog as mod
    monkeypatch.setattr(mod.PreferencesDialog, "exec", lambda self: 0)
    mod.open_preferences_dialog(parent=None)


def test_preferences_dialog_reject_does_not_persist(qapp):
    """Closing the dialog without OK keeps user_setting_dict untouched."""
    from Imervue.gui.preferences_dialog import PreferencesDialog
    user_setting_dict["vram_limit_auto"] = True
    user_setting_dict["vram_limit_mb"] = 1536
    user_setting_dict["ui_scale_percent"] = 100

    dlg = PreferencesDialog()
    dlg._vram_spin.setValue(4096)
    dlg._auto_vram.setChecked(False)
    dlg._ui_scale_spin.setValue(180)
    # Reject — no _accept call, no persistence
    dlg.reject()

    assert user_setting_dict["vram_limit_auto"] is True
    assert user_setting_dict["vram_limit_mb"] == 1536
    assert user_setting_dict["ui_scale_percent"] == 100


def test_round_trip_persists_through_dict(qapp):
    """OK twice — persisted values survive a fresh dialog instance."""
    from Imervue.gui.preferences_dialog import PreferencesDialog

    dlg1 = PreferencesDialog()
    dlg1._auto_vram.setChecked(False)
    dlg1._vram_spin.setValue(2560)
    dlg1._ui_scale_spin.setValue(130)
    dlg1._accept()

    dlg2 = PreferencesDialog()
    assert dlg2._auto_vram.isChecked() is False
    assert dlg2._vram_spin.value() == 2560
    assert dlg2._ui_scale_spin.value() == 130
