"""Tests for the Modern Dark / Modern Light colour sets, palette and stylesheet."""
from __future__ import annotations

import re

import pytest

from Imervue.system import modern_theme as mod
from Imervue.system.modern_theme import (
    DISABLED_TEXT_ROLES,
    MODERN_DARK,
    MODERN_LIGHT,
    ThemeColours,
    build_palette,
    build_stylesheet,
    palette_roles,
)

_BOTH = [MODERN_DARK, MODERN_LIGHT]
_HEX = re.compile(r"#[0-9a-f]{6}")


def _luminance(colour: str) -> float:
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("colours", _BOTH)
def test_every_colour_is_a_lowercase_hex_triplet(colours):
    for name, value in vars(colours).items():
        assert _HEX.fullmatch(value), name


def test_dark_is_dark_and_light_is_light():
    assert _luminance(MODERN_DARK.window) < 0.1 < _luminance(MODERN_DARK.text)
    assert _luminance(MODERN_LIGHT.window) > 0.8 > _luminance(MODERN_LIGHT.text)


@pytest.mark.parametrize("colours", _BOTH)
def test_text_is_readable_on_every_background(colours):
    for background in (colours.window, colours.surface, colours.raised):
        assert _contrast(colours.text, background) >= 7.0
    assert _contrast(colours.accent_text, colours.accent) >= 3.0
    # Secondary text is quieter than body text but still legible.
    assert 3.0 <= _contrast(colours.muted, colours.window) < _contrast(colours.text, colours.window)


@pytest.mark.parametrize("colours", _BOTH)
def test_stylesheet_uses_only_the_theme_colours(colours):
    sheet = build_stylesheet(colours)
    assert set(_HEX.findall(sheet)) <= set(vars(colours).values())
    assert colours.accent in sheet and colours.border in sheet


@pytest.mark.parametrize("colours", _BOTH)
def test_stylesheet_has_no_unfilled_placeholder(colours):
    sheet = build_stylesheet(colours)
    assert not re.search(r"\{[a-z_]+\}", sheet)
    assert sheet.count("{") == sheet.count("}")


@pytest.mark.parametrize("selector", [
    "QDockWidget::title", "QMainWindow::separator", "QTabBar::tab:top:selected",
    "QMenu::item:selected", "QPushButton:hover", "QScrollBar::handle",
    "QSlider::handle:horizontal", "QStatusBar", "QToolTip", "QProgressBar::chunk",
])
def test_stylesheet_shapes_the_chrome(selector):
    assert selector in build_stylesheet(MODERN_DARK)


@pytest.mark.parametrize("widget", ["QComboBox", "QAbstractSpinBox", "QSpinBox"])
def test_combo_and_spin_boxes_are_left_to_the_style(widget):
    """A stylesheet border on either replaces its arrows with blank boxes."""
    assert widget not in build_stylesheet(MODERN_DARK)


def test_text_paddings_follow_the_font():
    """Paddings are in ``em`` so the UI scale (a larger font) enlarges them too."""
    sheet = build_stylesheet(MODERN_DARK)
    paddings = re.findall(r"padding: ([^;]+);", sheet)
    assert paddings
    for value in paddings:
        assert "px" not in value, value


def test_the_template_ignores_a_blanket_qwidget_rule():
    """No ``QWidget { background }``: it would paint over custom-drawn widgets."""
    assert not re.search(r"(^|\n)QWidget\s*\{", mod._TEMPLATE)  # noqa: SLF001


def test_palette_roles_cover_what_the_widgets_read():
    roles = palette_roles(MODERN_DARK)
    for role in ("Window", "WindowText", "Base", "Text", "Button", "ButtonText",
                 "Highlight", "HighlightedText", "PlaceholderText", "Mid", "Midlight", "Link"):
        assert role in roles
    assert roles["Window"] == MODERN_DARK.window
    assert roles["Base"] == MODERN_DARK.surface
    assert roles["PlaceholderText"] == MODERN_DARK.muted


@pytest.mark.parametrize("colours", _BOTH)
def test_build_palette_sets_every_role(qapp, colours):
    from PySide6.QtGui import QPalette
    palette = build_palette(colours)
    for name, colour in palette_roles(colours).items():
        role = getattr(QPalette.ColorRole, name)
        assert palette.color(QPalette.ColorGroup.Active, role).name() == colour, name
        if name not in DISABLED_TEXT_ROLES:
            assert palette.color(QPalette.ColorGroup.Inactive, role).name() == colour, name


@pytest.mark.parametrize("colours", _BOTH)
def test_disabled_text_is_muted(qapp, colours):
    from PySide6.QtGui import QPalette
    palette = build_palette(colours)
    disabled = QPalette.ColorGroup.Disabled
    for name in DISABLED_TEXT_ROLES:
        assert palette.color(disabled, getattr(QPalette.ColorRole, name)).name() == colours.muted
    assert palette.color(disabled, QPalette.ColorRole.Highlight).name() == colours.border


def test_a_custom_colour_set_builds_a_stylesheet():
    custom = ThemeColours(
        window="#000000", surface="#111111", raised="#222222", border="#333333",
        text="#ffffff", muted="#888888", accent="#ff0000", accent_text="#000000",
        link="#00ff00",
    )
    sheet = build_stylesheet(custom)
    assert "#ff0000" in sheet and "#4c8dff" not in sheet
