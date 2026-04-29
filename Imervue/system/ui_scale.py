"""Application-wide UI scale factor.

Lets the user grow / shrink every Qt widget by adjusting the default
``QApplication`` font. Set once at startup before the main window is
constructed; changing it later requires a restart so that already-laid-out
widgets pick up the new metrics. The value is stored as a percentage
(``ui_scale_percent``) in ``user_setting_dict`` and clamped to
``[UI_SCALE_MIN_PERCENT, UI_SCALE_MAX_PERCENT]`` to prevent unreadable or
runaway sizes.
"""
from __future__ import annotations

UI_SCALE_MIN_PERCENT = 80
UI_SCALE_MAX_PERCENT = 200
UI_SCALE_DEFAULT_PERCENT = 100
UI_SCALE_STEP_PERCENT = 10


def clamp_scale_percent(value: int) -> int:
    """Clamp a raw percentage to the supported ``[80, 200]`` range."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return UI_SCALE_DEFAULT_PERCENT
    return max(UI_SCALE_MIN_PERCENT, min(UI_SCALE_MAX_PERCENT, v))


def scaled_point_size(base_point_size: float, percent: int) -> float:
    """Return ``base_point_size`` scaled by ``percent``, never below 1.0pt."""
    factor = clamp_scale_percent(percent) / 100.0
    return max(1.0, float(base_point_size) * factor)


def apply_ui_scale(app, percent: int) -> int:
    """Apply ``percent`` scale to ``app``'s default font.

    Returns the percent that was actually applied (after clamping). A 100 %
    request is a no-op so users with the default value pay nothing.
    """
    pct = clamp_scale_percent(percent)
    if pct == UI_SCALE_DEFAULT_PERCENT:
        return pct
    font = app.font()
    base_pt = font.pointSizeF()
    if base_pt <= 0:
        # Some platforms only expose pixel sizes; fall back to that path.
        base_px = font.pixelSize()
        if base_px > 0:
            font.setPixelSize(max(1, int(round(base_px * pct / 100.0))))
            app.setFont(font)
        return pct
    font.setPointSizeF(scaled_point_size(base_pt, pct))
    app.setFont(font)
    return pct


def load_and_apply_from_settings(app) -> int:
    """Read ``ui_scale_percent`` from user settings and apply to ``app``."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    pct = user_setting_dict.get("ui_scale_percent", UI_SCALE_DEFAULT_PERCENT)
    return apply_ui_scale(app, pct)
