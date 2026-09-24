"""Open a ``QPainter`` on a ``QPdfWriter`` and fail loudly when the file cannot be written."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPainter, QPdfWriter


def begin_pdf_painter(writer: QPdfWriter, out_path: str | Path) -> QPainter:
    """Return a painter already begun on *writer*; the caller must ``end()`` it.

    ``QPdfWriter`` never raises: an unwritable target (missing directory, a
    directory at that path, a file locked by a PDF viewer) only makes
    ``QPainter.begin`` return ``False``, and painting on then produces nothing.
    Raises ``OSError`` in that case so callers report the failure instead of
    announcing a file that was never written.
    """
    painter = QPainter()
    if not painter.begin(writer):
        raise OSError(f"Cannot write the PDF to {out_path}")
    return painter
