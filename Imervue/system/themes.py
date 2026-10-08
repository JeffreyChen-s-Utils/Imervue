"""Built-in colour themes for the main window.

A theme is a Qt stylesheet (QSS) registered under a name, and for the two
modern themes also a colour set that becomes the application palette on the
Fusion style (:mod:`Imervue.system.modern_theme`). The active theme name lives
in ``user_setting_dict["theme"]`` and is applied to the ``QApplication``
instance at startup. Switching themes requires a restart because
already-laid-out widgets cache their palette.

A profile that never chose a theme gets ``DEFAULT_THEME_NAME`` (Modern Dark).
``SYSTEM_THEME_NAME`` is the platform's native look: no stylesheet, and the
style and palette the application started with.
"""
from __future__ import annotations

from dataclasses import dataclass

from Imervue.system.modern_theme import (
    FUSION_STYLE,
    MODERN_DARK,
    MODERN_LIGHT,
    ThemeColours,
    build_palette,
    build_stylesheet,
)


@dataclass(frozen=True)
class Theme:
    """One named theme. Stylesheet is QSS applied to the QApplication."""

    name: str
    label: str          # English name shown in the Preferences combo
    stylesheet: str     # full QSS string; empty means "no override"
    colours: ThemeColours | None = None   # set: Fusion style with this palette
    label_key: str = ""                   # translation key of the label, if it has one


# ---------------------------------------------------------------------------
# Theme palettes
# ---------------------------------------------------------------------------
# Colour values are picked from the canonical published palettes:
#   Dracula:   https://draculatheme.com/contribute
#   Nord:      https://www.nordtheme.com/docs/colors-and-palettes
#   Solarized: https://ethanschoonover.com/solarized/

_DRACULA = """
QWidget { background-color: #282a36; color: #f8f8f2; }
QToolTip { color: #f8f8f2; background-color: #44475a; border: 1px solid #6272a4; }
QMenu, QMenuBar { background-color: #282a36; color: #f8f8f2; }
QMenu::item:selected, QMenuBar::item:selected { background-color: #44475a; }
QPushButton { background-color: #44475a; color: #f8f8f2; border: 1px solid #6272a4;
              padding: 4px 12px; border-radius: 3px; }
QPushButton:hover { background-color: #6272a4; }
QPushButton:pressed { background-color: #bd93f9; color: #282a36; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #44475a; color: #f8f8f2; border: 1px solid #6272a4;
    padding: 2px 4px; border-radius: 2px;
}
QListWidget, QTreeWidget, QTableWidget, QTreeView, QListView, QTableView {
    background-color: #21222c; color: #f8f8f2; border: 1px solid #44475a;
    alternate-background-color: #282a36;
}
QHeaderView::section { background-color: #44475a; color: #f8f8f2;
                       padding: 4px; border: 1px solid #6272a4; }
QScrollBar:vertical, QScrollBar:horizontal { background: #21222c; }
QScrollBar::handle { background: #6272a4; border-radius: 4px; }
QTabBar::tab { background: #21222c; color: #f8f8f2; padding: 6px 14px; }
QTabBar::tab:selected { background: #44475a; color: #ff79c6; }
QStatusBar { background-color: #21222c; color: #f8f8f2; }
"""

_NORD = """
QWidget { background-color: #2e3440; color: #d8dee9; }
QToolTip { color: #2e3440; background-color: #d8dee9; border: 1px solid #4c566a; }
QMenu, QMenuBar { background-color: #2e3440; color: #e5e9f0; }
QMenu::item:selected, QMenuBar::item:selected { background-color: #434c5e; }
QPushButton { background-color: #3b4252; color: #e5e9f0; border: 1px solid #4c566a;
              padding: 4px 12px; border-radius: 3px; }
QPushButton:hover { background-color: #4c566a; }
QPushButton:pressed { background-color: #88c0d0; color: #2e3440; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #3b4252; color: #e5e9f0; border: 1px solid #4c566a;
    padding: 2px 4px; border-radius: 2px;
}
QListWidget, QTreeWidget, QTableWidget, QTreeView, QListView, QTableView {
    background-color: #292e39; color: #d8dee9; border: 1px solid #3b4252;
    alternate-background-color: #2e3440;
}
QHeaderView::section { background-color: #3b4252; color: #e5e9f0;
                       padding: 4px; border: 1px solid #4c566a; }
QScrollBar:vertical, QScrollBar:horizontal { background: #292e39; }
QScrollBar::handle { background: #4c566a; border-radius: 4px; }
QTabBar::tab { background: #292e39; color: #d8dee9; padding: 6px 14px; }
QTabBar::tab:selected { background: #3b4252; color: #88c0d0; }
QStatusBar { background-color: #292e39; color: #d8dee9; }
"""

_SOLARIZED_DARK = """
QWidget { background-color: #002b36; color: #93a1a1; }
QToolTip { color: #002b36; background-color: #93a1a1; border: 1px solid #586e75; }
QMenu, QMenuBar { background-color: #002b36; color: #93a1a1; }
QMenu::item:selected, QMenuBar::item:selected { background-color: #073642; }
QPushButton { background-color: #073642; color: #93a1a1; border: 1px solid #586e75;
              padding: 4px 12px; border-radius: 3px; }
QPushButton:hover { background-color: #586e75; color: #fdf6e3; }
QPushButton:pressed { background-color: #268bd2; color: #fdf6e3; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #073642; color: #93a1a1; border: 1px solid #586e75;
    padding: 2px 4px; border-radius: 2px;
}
QListWidget, QTreeWidget, QTableWidget, QTreeView, QListView, QTableView {
    background-color: #002b36; color: #93a1a1; border: 1px solid #073642;
    alternate-background-color: #073642;
}
QHeaderView::section { background-color: #073642; color: #93a1a1;
                       padding: 4px; border: 1px solid #586e75; }
QScrollBar:vertical, QScrollBar:horizontal { background: #073642; }
QScrollBar::handle { background: #586e75; border-radius: 4px; }
QTabBar::tab { background: #073642; color: #93a1a1; padding: 6px 14px; }
QTabBar::tab:selected { background: #002b36; color: #b58900; }
QStatusBar { background-color: #073642; color: #93a1a1; }
"""

_SOLARIZED_LIGHT = """
QWidget { background-color: #fdf6e3; color: #586e75; }
QToolTip { color: #fdf6e3; background-color: #586e75; border: 1px solid #93a1a1; }
QMenu, QMenuBar { background-color: #fdf6e3; color: #586e75; }
QMenu::item:selected, QMenuBar::item:selected { background-color: #eee8d5; }
QPushButton { background-color: #eee8d5; color: #586e75; border: 1px solid #93a1a1;
              padding: 4px 12px; border-radius: 3px; }
QPushButton:hover { background-color: #93a1a1; color: #fdf6e3; }
QPushButton:pressed { background-color: #268bd2; color: #fdf6e3; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #ffffff; color: #586e75; border: 1px solid #93a1a1;
    padding: 2px 4px; border-radius: 2px;
}
QListWidget, QTreeWidget, QTableWidget, QTreeView, QListView, QTableView {
    background-color: #ffffff; color: #586e75; border: 1px solid #eee8d5;
    alternate-background-color: #fdf6e3;
}
QHeaderView::section { background-color: #eee8d5; color: #586e75;
                       padding: 4px; border: 1px solid #93a1a1; }
QScrollBar:vertical, QScrollBar:horizontal { background: #eee8d5; }
QScrollBar::handle { background: #93a1a1; border-radius: 4px; }
QTabBar::tab { background: #eee8d5; color: #586e75; padding: 6px 14px; }
QTabBar::tab:selected { background: #fdf6e3; color: #b58900; }
QStatusBar { background-color: #eee8d5; color: #586e75; }
"""


SYSTEM_THEME_NAME = "default"

THEMES: dict[str, Theme] = {
    "modern_dark": Theme(
        name="modern_dark", label="Modern Dark", stylesheet=build_stylesheet(MODERN_DARK),
        colours=MODERN_DARK, label_key="theme_modern_dark",
    ),
    "modern_light": Theme(
        name="modern_light", label="Modern Light", stylesheet=build_stylesheet(MODERN_LIGHT),
        colours=MODERN_LIGHT, label_key="theme_modern_light",
    ),
    SYSTEM_THEME_NAME: Theme(
        name=SYSTEM_THEME_NAME, label="System default", stylesheet="",
        label_key="theme_system_default",
    ),
    "dracula": Theme(name="dracula", label="Dracula", stylesheet=_DRACULA),
    "nord": Theme(name="nord", label="Nord", stylesheet=_NORD),
    "solarized_dark": Theme(
        name="solarized_dark", label="Solarized Dark", stylesheet=_SOLARIZED_DARK,
    ),
    "solarized_light": Theme(
        name="solarized_light", label="Solarized Light", stylesheet=_SOLARIZED_LIGHT,
    ),
}

DEFAULT_THEME_NAME = "modern_dark"
# Settings flag: this profile has been moved to the modern default once.
MODERN_OFFERED_KEY = "theme_modern_offered"

# Style name and palette the application started with, kept the first time a
# theme replaces them so the system theme can put them back.
_native_look: dict = {}


def list_themes() -> list[Theme]:
    """Return the registered themes in stable display order."""
    return list(THEMES.values())


def get_theme(name: str) -> Theme:
    """Return the theme for ``name``, falling back to the default."""
    return THEMES.get(name) or THEMES[DEFAULT_THEME_NAME]


def theme_label(theme: Theme) -> str:
    """The theme's name in the current language (its English label without a translation)."""
    if not theme.label_key:
        return theme.label
    from Imervue.multi_language.language_wrapper import language_wrapper
    return language_wrapper.language_word_dict.get(theme.label_key, theme.label)


def apply_theme(app, name: str) -> str:
    """Apply the named theme to ``app`` and return the name actually used."""
    theme = get_theme(name)
    # While a stylesheet is set, ``app.style()`` is Qt's stylesheet proxy and has
    # no name to restore later, so the old sheet goes before the style is read.
    app.setStyleSheet("")
    if theme.colours is not None:
        if not _native_look:
            _native_look["style"] = app.style().objectName()
            _native_look["palette"] = app.palette()
        app.setStyle(FUSION_STYLE)
        app.setPalette(build_palette(theme.colours))
    elif _native_look:
        app.setStyle(_native_look["style"])
        app.setPalette(_native_look["palette"])
        _native_look.clear()
    app.setStyleSheet(theme.stylesheet)
    return theme.name


def offer_modern_theme(settings: dict) -> bool:
    """Move a profile still on the system look to the modern default, once.

    Preferences stored ``"default"`` on every OK, so that value does not show
    the system look was chosen. The first launch with the modern themes
    switches it; the flag set here makes a later pick of *System default* in
    Preferences stay. Returns whether the theme was changed.
    """
    if settings.get(MODERN_OFFERED_KEY):
        return False
    settings[MODERN_OFFERED_KEY] = True
    if settings.get("theme", SYSTEM_THEME_NAME) != SYSTEM_THEME_NAME:
        return False
    settings["theme"] = DEFAULT_THEME_NAME
    return True


def load_and_apply_theme(app) -> str:
    """Read ``theme`` from user settings and apply to ``app``."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    offer_modern_theme(user_setting_dict)
    name = user_setting_dict.get("theme", DEFAULT_THEME_NAME)
    return apply_theme(app, str(name))
