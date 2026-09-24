"""Keep process-wide QApplication appearance from leaking between tests.

``QApplication.setFont`` and ``QApplication.setStyleSheet`` change every widget
built afterwards, and under ``pytest-xdist --dist loadfile`` one worker runs
many files in one process. ``test_ui_scale`` left the app font at about 72 px,
and a later file's ``QTreeWidget.setColumnWidth(0, 68)`` came back as 107,
because the header's minimum section size grows with the font. A theme
stylesheet does the same to button widths. The conftest autouse fixture wraps
every test in :func:`app_appearance_restored`.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator


@contextlib.contextmanager
def app_appearance_restored() -> Iterator[None]:
    """Restore the QApplication font and stylesheet on exit if the body changed them.

    A no-op when PySide6 is missing or no QApplication exists on entry (there
    is no default to go back to); it never creates one.
    """
    try:
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
    except ImportError:
        yield
        return
    app = QApplication.instance()
    if app is None:
        yield
        return
    font, style_sheet = QFont(app.font()), app.styleSheet()
    try:
        yield
    finally:
        if app.styleSheet() != style_sheet:
            app.setStyleSheet(style_sheet)
        if app.font() != font:
            app.setFont(font)
