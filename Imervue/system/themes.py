"""Built-in colour themes for the main window.

A theme is just a Qt stylesheet (QSS) string registered under a name. The
active theme name lives in ``user_setting_dict["theme"]`` and is applied
to the ``QApplication`` instance at startup. Switching themes requires
a restart because already-laid-out widgets cache their palette.

The default theme is the empty string, meaning "use the platform's native
look" — that keeps existing users on whatever they had before this
feature shipped.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """One named theme. Stylesheet is QSS applied to the QApplication."""

    name: str
    label: str          # human-readable name shown in the Preferences combo
    stylesheet: str     # full QSS string; empty means "no override"


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


THEMES: dict[str, Theme] = {
    "default": Theme(name="default", label="System default", stylesheet=""),
    "dracula": Theme(name="dracula", label="Dracula", stylesheet=_DRACULA),
    "nord": Theme(name="nord", label="Nord", stylesheet=_NORD),
    "solarized_dark": Theme(
        name="solarized_dark", label="Solarized Dark", stylesheet=_SOLARIZED_DARK,
    ),
    "solarized_light": Theme(
        name="solarized_light", label="Solarized Light", stylesheet=_SOLARIZED_LIGHT,
    ),
}

DEFAULT_THEME_NAME = "default"


def list_themes() -> list[Theme]:
    """Return the registered themes in stable display order."""
    return list(THEMES.values())


def get_theme(name: str) -> Theme:
    """Return the theme for ``name``, falling back to the default."""
    return THEMES.get(name) or THEMES[DEFAULT_THEME_NAME]


def apply_theme(app, name: str) -> str:
    """Apply the named theme to ``app`` and return the name actually used."""
    theme = get_theme(name)
    app.setStyleSheet(theme.stylesheet)
    return theme.name


def load_and_apply_theme(app) -> str:
    """Read ``theme`` from user settings and apply to ``app``."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    name = user_setting_dict.get("theme", DEFAULT_THEME_NAME)
    return apply_theme(app, str(name))
