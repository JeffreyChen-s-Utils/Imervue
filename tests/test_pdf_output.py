"""Tests for ``begin_pdf_painter``: a writable target paints, an unwritable one raises."""
from __future__ import annotations

import pytest
from PySide6.QtGui import QPdfWriter

from Imervue.export.pdf_output import begin_pdf_painter


def test_writable_target_returns_an_active_painter(qapp, tmp_path):
    out = tmp_path / "ok.pdf"
    writer = QPdfWriter(str(out))
    painter = begin_pdf_painter(writer, out)
    try:
        assert painter.isActive()
        painter.drawText(10, 10, "x")
    finally:
        painter.end()
    assert out.read_bytes().startswith(b"%PDF-")


@pytest.mark.parametrize("make_target", [
    lambda tmp: tmp / "no_such_dir" / "x.pdf",
    lambda tmp: (tmp / "a_dir.pdf").mkdir() or tmp / "a_dir.pdf",
])
def test_unwritable_target_raises_oserror(qapp, tmp_path, make_target):
    out = make_target(tmp_path)
    with pytest.raises(OSError, match=out.name):
        begin_pdf_painter(QPdfWriter(str(out)), out)
