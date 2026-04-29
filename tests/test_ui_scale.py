"""Tests for the application-wide UI scale helper."""
from __future__ import annotations

import pytest

from Imervue.system.ui_scale import (
    UI_SCALE_DEFAULT_PERCENT,
    UI_SCALE_MAX_PERCENT,
    UI_SCALE_MIN_PERCENT,
    apply_ui_scale,
    clamp_scale_percent,
    load_and_apply_from_settings,
    scaled_point_size,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# clamp_scale_percent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (50, UI_SCALE_MIN_PERCENT),
        (300, UI_SCALE_MAX_PERCENT),
        (100, 100),
        (80, 80),
        (200, 200),
        (None, UI_SCALE_DEFAULT_PERCENT),
        ("garbage", UI_SCALE_DEFAULT_PERCENT),
        (150.7, 150),  # int() truncates floats
    ],
)
def test_clamp_scale_percent(value, expected):
    assert clamp_scale_percent(value) == expected


# ---------------------------------------------------------------------------
# scaled_point_size
# ---------------------------------------------------------------------------


def test_scaled_point_size_default_passthrough():
    assert scaled_point_size(10.0, 100) == 10.0


def test_scaled_point_size_doubled():
    assert scaled_point_size(10.0, 200) == 20.0


def test_scaled_point_size_minimum_floor():
    """Tiny base × small percent should still leave at least 1.0pt."""
    assert scaled_point_size(0.1, 80) >= 1.0


def test_scaled_point_size_clamps_runaway_request():
    """A 1000% request still scales to the [80, 200] cap."""
    out = scaled_point_size(10.0, 1000)
    # Clamped to 200% → 20.0pt
    assert out == 20.0


# ---------------------------------------------------------------------------
# apply_ui_scale (requires QApplication)
# ---------------------------------------------------------------------------


def test_apply_ui_scale_noop_at_100(qapp):
    before = qapp.font().pointSizeF()
    out_pct = apply_ui_scale(qapp, 100)
    after = qapp.font().pointSizeF()
    assert out_pct == 100
    assert before == after


def test_apply_ui_scale_grows_font(qapp):
    qapp.setFont(qapp.font())  # snapshot
    before = qapp.font().pointSizeF()
    apply_ui_scale(qapp, 150)
    after = qapp.font().pointSizeF()
    if before > 0:
        assert after > before


def test_apply_ui_scale_clamps_request(qapp):
    """500% request → app font scaled by 200%, function returns 200."""
    out_pct = apply_ui_scale(qapp, 500)
    assert out_pct == UI_SCALE_MAX_PERCENT


def test_apply_ui_scale_handles_pixel_size_font(qapp):
    """When the font reports pixelSize instead of pointSize, scale by px."""
    from PySide6.QtGui import QFont
    pixel_font = QFont(qapp.font())
    pixel_font.setPixelSize(16)
    qapp.setFont(pixel_font)
    apply_ui_scale(qapp, 200)
    assert qapp.font().pixelSize() in (32, 31, 33)  # rounding tolerance


def test_load_and_apply_reads_user_setting(qapp):
    user_setting_dict["ui_scale_percent"] = 120
    out = load_and_apply_from_settings(qapp)
    assert out == 120


# ---------------------------------------------------------------------------
# Preferences dialog
# ---------------------------------------------------------------------------


def test_preferences_dialog_persists_ui_scale(qapp):
    from Imervue.gui.preferences_dialog import PreferencesDialog
    user_setting_dict["ui_scale_percent"] = 100
    dlg = PreferencesDialog()
    dlg._ui_scale_spin.setValue(140)
    dlg._accept()
    assert user_setting_dict["ui_scale_percent"] == 140


def test_preferences_dialog_ui_scale_range(qapp):
    from Imervue.gui.preferences_dialog import PreferencesDialog
    dlg = PreferencesDialog()
    assert dlg._ui_scale_spin.minimum() == UI_SCALE_MIN_PERCENT
    assert dlg._ui_scale_spin.maximum() == UI_SCALE_MAX_PERCENT
