"""Tests for ``tests/_app_font.py``, the guard against app-font leaks between tests."""
from __future__ import annotations

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTreeWidget

from Imervue.system.ui_scale import apply_ui_scale
from tests._app_font import app_font_restored


def _first_column_width() -> int:
    tree = QTreeWidget()
    try:
        tree.setHeaderLabels(["", "Filename"])
        tree.setColumnWidth(0, 68)
        return tree.columnWidth(0)
    finally:
        tree.deleteLater()


def test_scaled_font_no_longer_widens_a_later_tree_column(qapp):
    baseline = _first_column_width()
    big = QFont(qapp.font())
    big.setPixelSize(72)  # test_ui_scale's stacked scalings left about this; 68 became 107
    with app_font_restored():
        qapp.setFont(big)
        # The leak this guards against: a large app font widens the header's minimum section.
        assert _first_column_width() > baseline
    assert _first_column_width() == baseline == 68


def test_font_is_restored_even_when_the_body_raises(qapp):
    before = QFont(qapp.font())
    with pytest.raises(RuntimeError, match="boom"), app_font_restored():
        apply_ui_scale(qapp, 150)
        raise RuntimeError("boom")
    assert qapp.font() == before


def test_untouched_font_is_left_alone(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(qapp, "setFont", lambda font: calls.append(font))
    with app_font_restored():
        pass
    assert calls == []


def test_no_application_is_a_no_op(monkeypatch):
    from PySide6.QtWidgets import QApplication
    monkeypatch.setattr(QApplication, "instance", staticmethod(lambda: None))
    with app_font_restored():
        pass
