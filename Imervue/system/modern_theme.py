"""The Modern Dark / Modern Light look: one colour set, a ``QPalette`` and a stylesheet.

The older themes in :mod:`Imervue.system.themes` are a stylesheet that paints a
background on every ``QWidget``. These two instead run on Qt's Fusion style with
a full palette, so every control (check boxes, spin arrows, item views, custom
painted widgets) takes the colours without a rule of its own, and the stylesheet
only shapes the chrome: flat tabs with an accent underline, dock title bars,
thin scroll bars, rounded inputs and buttons. Combo boxes and spin boxes are
left to Fusion on purpose: a stylesheet border on either replaces their arrows
with blank boxes unless it ships arrow images of its own.

Every length that should follow the text is written in ``em``, so the UI scale
(a larger application font) enlarges paddings together with the text.
"""
from __future__ import annotations

from dataclasses import dataclass

FUSION_STYLE = "Fusion"


@dataclass(frozen=True)
class ThemeColours:
    """The colours one modern theme is built from (``#rrggbb`` strings)."""

    window: str        # window and panel background
    surface: str       # inputs, lists, menus
    raised: str        # buttons, hovered rows
    border: str
    text: str
    muted: str         # disabled and secondary text
    accent: str
    accent_text: str   # text on the accent colour
    link: str


MODERN_DARK = ThemeColours(
    window="#1f2023", surface="#2a2b2f", raised="#34363b", border="#43454b",
    text="#e3e5e8", muted="#8d9199", accent="#4c8dff", accent_text="#ffffff",
    link="#7fb0ff",
)

MODERN_LIGHT = ThemeColours(
    window="#f4f5f7", surface="#ffffff", raised="#e9ebef", border="#d0d4da",
    text="#1f2328", muted="#737a86", accent="#2f6feb", accent_text="#ffffff",
    link="#1f5fd0",
)

_TEMPLATE = """
QToolTip {{ color: {text}; background-color: {raised}; border: 1px solid {border};
           padding: 0.25em 0.5em; }}

QMainWindow::separator {{ background: {window}; width: 5px; height: 5px; }}
QMainWindow::separator:hover {{ background: {accent}; }}
QSplitter::handle {{ background: {window}; }}
QSplitter::handle:hover {{ background: {accent}; }}

QDockWidget {{ font-weight: bold; }}
QDockWidget::title {{ background: {surface}; padding: 0.45em 0.7em; text-align: left;
                     border-bottom: 1px solid {border}; }}

QMenuBar {{ background: {window}; border-bottom: 1px solid {border}; }}
QMenuBar::item {{ background: transparent; padding: 0.35em 0.75em; border-radius: 4px; }}
QMenuBar::item:selected, QMenuBar::item:pressed {{ background: {raised}; }}
QMenu {{ background: {surface}; border: 1px solid {border}; padding: 0.3em; }}
QMenu::item {{ padding: 0.4em 2em 0.4em 2em; border-radius: 4px; }}
QMenu::item:selected {{ background: {accent}; color: {accent_text}; }}
QMenu::item:disabled {{ color: {muted}; background: transparent; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 0.3em 0.5em; }}
QMenu::indicator {{ width: 1em; height: 1em; left: 0.5em; }}

QTabWidget::pane {{ border: 0; border-top: 1px solid {border}; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {muted}; border: 0;
               padding: 0.5em 1.1em; }}
QTabBar::tab:top {{ border-bottom: 2px solid transparent; }}
QTabBar::tab:bottom {{ border-top: 2px solid transparent; }}
QTabBar::tab:hover {{ color: {text}; background: {raised}; }}
QTabBar::tab:selected {{ color: {text}; }}
QTabBar::tab:top:selected {{ border-bottom-color: {accent}; }}
QTabBar::tab:bottom:selected {{ border-top-color: {accent}; }}

QPushButton {{ background: {raised}; border: 1px solid {border}; border-radius: 5px;
              padding: 0.4em 1em; }}
QPushButton:hover {{ border-color: {accent}; }}
QPushButton:pressed, QPushButton:checked {{ background: {accent}; color: {accent_text};
                                            border-color: {accent}; }}
QPushButton:disabled {{ color: {muted}; border-color: {border}; background: {window}; }}
QPushButton:default {{ border-color: {accent}; }}

QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 5px;
              padding: 0.3em 0.5em; }}
QToolButton:hover {{ background: {raised}; border-color: {border}; }}
QToolButton:pressed, QToolButton:checked {{ background: {accent}; color: {accent_text};
                                            border-color: {accent}; }}
QToolButton:disabled {{ color: {muted}; }}

QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {surface}; border: 1px solid {border}; border-radius: 5px;
    padding: 0.25em 0.45em; selection-background-color: {accent};
    selection-color: {accent_text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {accent}; }}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
    color: {muted}; background: {window}; }}

QAbstractItemView {{ background: {surface}; alternate-background-color: {window};
                    border: 1px solid {border}; outline: 0; }}
QHeaderView::section {{ background: {window}; color: {muted}; border: 0;
                       border-bottom: 1px solid {border}; padding: 0.35em 0.6em; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle {{ background: {border}; border-radius: 4px; margin: 2px; }}
QScrollBar::handle:vertical {{ min-height: 2em; }}
QScrollBar::handle:horizontal {{ min-width: 2em; }}
QScrollBar::handle:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSlider::groove:horizontal {{ height: 4px; background: {border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {text}; width: 14px; margin: -5px 0;
                             border-radius: 7px; }}
QSlider::groove:vertical {{ width: 4px; background: {border}; border-radius: 2px; }}
QSlider::add-page:vertical {{ background: {accent}; border-radius: 2px; }}
QSlider::handle:vertical {{ background: {text}; height: 14px; margin: 0 -5px;
                           border-radius: 7px; }}
QSlider::handle:hover {{ background: {accent}; }}
QSlider::handle:disabled {{ background: {muted}; }}
QSlider::sub-page:horizontal:disabled, QSlider::add-page:vertical:disabled {{
    background: {muted}; }}

QProgressBar {{ background: {surface}; border: 1px solid {border}; border-radius: 5px;
               text-align: center; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}

QGroupBox {{ border: 1px solid {border}; border-radius: 6px; margin-top: 0.8em;
            padding-top: 0.6em; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 0.8em; padding: 0 0.3em;
                   color: {muted}; }}

QStatusBar {{ background: {surface}; border-top: 1px solid {border}; }}
QStatusBar::item {{ border: 0; }}
"""


def build_stylesheet(colours: ThemeColours) -> str:
    """The stylesheet that shapes the chrome in *colours*."""
    return _TEMPLATE.format(
        window=colours.window, surface=colours.surface, raised=colours.raised,
        border=colours.border, text=colours.text, muted=colours.muted,
        accent=colours.accent, accent_text=colours.accent_text,
    )


def palette_roles(colours: ThemeColours) -> dict[str, str]:
    """``QPalette.ColorRole`` name -> colour for the active and inactive groups."""
    return {
        "Window": colours.window,
        "WindowText": colours.text,
        "Base": colours.surface,
        "AlternateBase": colours.window,
        "ToolTipBase": colours.raised,
        "ToolTipText": colours.text,
        "Text": colours.text,
        "Button": colours.raised,
        "ButtonText": colours.text,
        "BrightText": colours.accent_text,
        "Highlight": colours.accent,
        "HighlightedText": colours.accent_text,
        "Link": colours.link,
        "LinkVisited": colours.link,
        "PlaceholderText": colours.muted,
        "Light": colours.raised,
        "Midlight": colours.raised,
        "Mid": colours.border,
        "Dark": colours.border,
        "Shadow": colours.window,
    }


# Roles that turn to the muted colour on a disabled widget.
DISABLED_TEXT_ROLES = ("WindowText", "Text", "ButtonText", "HighlightedText")


def build_palette(colours: ThemeColours):
    """A ``QPalette`` carrying *colours*, with muted text for disabled widgets."""
    from PySide6.QtGui import QColor, QPalette
    palette = QPalette()
    for role_name, colour in palette_roles(colours).items():
        palette.setColor(getattr(QPalette.ColorRole, role_name), QColor(colour))
    disabled = QPalette.ColorGroup.Disabled
    for role_name in DISABLED_TEXT_ROLES:
        palette.setColor(disabled, getattr(QPalette.ColorRole, role_name), QColor(colours.muted))
    palette.setColor(disabled, QPalette.ColorRole.Highlight, QColor(colours.border))
    return palette
