"""Keep the process-wide QApplication font from leaking between tests.

``QApplication.setFont`` changes the default font of every widget built
afterwards, and under ``pytest-xdist --dist loadfile`` one worker runs many
files in one process. ``test_ui_scale`` scales the app font to 200 %, and a
later file's ``QTreeWidget.setColumnWidth(0, 68)`` came back as 107, because
the header's minimum section size grows with the font. The conftest autouse
fixture wraps every test in :func:`app_font_restored`.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator


@contextlib.contextmanager
def app_font_restored() -> Iterator[None]:
    """Restore the QApplication font on exit if the body changed it.

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
    saved = QFont(app.font()) if app is not None else None
    try:
        yield
    finally:
        if saved is not None and app.font() != saved:
            app.setFont(saved)
