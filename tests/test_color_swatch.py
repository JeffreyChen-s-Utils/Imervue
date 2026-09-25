"""Tests for the colour swatch button."""
from __future__ import annotations

import pytest
from PySide6.QtGui import QColor

from Imervue.gui import color_swatch as mod
from Imervue.gui.color_swatch import ColorSwatchButton, hex_name, swatch_style


def test_swatch_style_fills_with_the_colour():
    assert "rgb(10, 20, 30)" in swatch_style((10, 20, 30))


@pytest.mark.parametrize(("rgb", "name"), [((0, 0, 0), "#000000"), ((255, 128, 1), "#FF8001")])
def test_hex_name(rgb, name):
    assert hex_name(rgb) == name


def test_the_button_shows_its_colour(qapp):
    button = ColorSwatchButton((255, 255, 255))
    try:
        assert button.rgb() == (255, 255, 255)
        assert button.toolTip() == "#FFFFFF"
        assert "rgb(255, 255, 255)" in button.styleSheet()
    finally:
        button.deleteLater()


def test_channels_are_clamped(qapp):
    button = ColorSwatchButton((300, -5, 12.7))
    try:
        assert button.rgb() == (255, 0, 12)
    finally:
        button.deleteLater()


def test_a_picked_colour_replaces_it(qapp, monkeypatch):
    monkeypatch.setattr(mod.QColorDialog, "getColor", staticmethod(lambda *_a: QColor(0, 0, 0)))
    button = ColorSwatchButton((255, 255, 255))
    try:
        button.click()
        assert button.rgb() == (0, 0, 0)
        assert button.toolTip() == "#000000"
    finally:
        button.deleteLater()


def test_cancelling_the_picker_keeps_the_colour(qapp, monkeypatch):
    monkeypatch.setattr(mod.QColorDialog, "getColor", staticmethod(lambda *_a: QColor()))
    button = ColorSwatchButton((1, 2, 3))
    try:
        button.click()
        assert button.rgb() == (1, 2, 3)
    finally:
        button.deleteLater()
