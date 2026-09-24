"""Tests for the in-process ``fake_clipboard`` fixture in ``tests/conftest.py``.

Clipboard tests rely on it behaving like ``QClipboard`` for the calls the
product code makes, and on it never touching the OS clipboard.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


def _solid_image(value: int) -> QImage:
    arr = np.full((4, 6, 4), value, dtype=np.uint8)
    return QImage(arr.data, 6, 4, 24, QImage.Format.Format_RGBA8888).copy()


def test_application_clipboard_is_the_fake(fake_clipboard):
    assert QApplication.clipboard() is fake_clipboard


def test_starts_empty(fake_clipboard):
    assert fake_clipboard.text() == ""
    assert fake_clipboard.image().isNull()
    assert not fake_clipboard.mimeData().hasImage()


def test_text_round_trip(fake_clipboard):
    fake_clipboard.setText("#FF0000")
    assert fake_clipboard.text() == "#FF0000"
    assert not fake_clipboard.mimeData().hasImage()


def test_image_round_trip(fake_clipboard):
    fake_clipboard.setImage(_solid_image(200))
    image = fake_clipboard.image()
    assert (image.width(), image.height()) == (6, 4)
    assert fake_clipboard.mimeData().hasImage()


def test_every_change_emits_data_changed_once(fake_clipboard):
    seen: list[int] = []
    fake_clipboard.dataChanged.connect(lambda: seen.append(1))
    fake_clipboard.setImage(_solid_image(1))
    fake_clipboard.setImage(_solid_image(2))
    fake_clipboard.setText("x")
    fake_clipboard.clear()
    assert len(seen) == 4


def test_clear_drops_text_and_image(fake_clipboard):
    fake_clipboard.setText("x")
    fake_clipboard.clear()
    assert fake_clipboard.text() == ""
    assert fake_clipboard.image().isNull()


def test_set_mime_data_replaces_content(fake_clipboard):
    mime = QMimeData()
    mime.setText("from mime")
    fake_clipboard.setMimeData(mime)
    assert fake_clipboard.text() == "from mime"


def test_mode_arguments_are_accepted(fake_clipboard):
    from PySide6.QtGui import QClipboard
    mode = QClipboard.Mode.Clipboard
    fake_clipboard.setText("m", mode)
    assert fake_clipboard.text(mode) == "m"
    assert fake_clipboard.mimeData(mode).text() == "m"
