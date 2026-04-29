"""Smoke tests for the Reference Panel Qt dialog.

We don't simulate full drag-drop or file-dialog interactions (those are
handled at the OS level); we exercise the parts that talk back to the
persistence layer and verify the visible state stays in sync.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PIL import Image

from Imervue.gui.reference_panel_dialog import (
    ReferencePanelDialog,
    _load_preview_pixmap,
    _load_thumb_icon,
)
from Imervue.library import reference_pins
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_pins():
    user_setting_dict.pop("reference_pins", None)
    yield
    user_setting_dict.pop("reference_pins", None)


@pytest.fixture
def fake_ui(qapp):
    """A real QWidget that quacks like the main window for the dialog parent."""
    from PySide6.QtWidgets import QWidget

    class _FakeUI(QWidget):
        pass

    ui = _FakeUI()
    ui.viewer = MagicMock()
    ui.viewer.model.images = []
    ui.viewer.current_index = -1
    return ui


@pytest.fixture
def png_path(tmp_path):
    path = tmp_path / "ref.png"
    Image.new("RGBA", (32, 32), (200, 50, 50, 255)).save(str(path))
    return str(path)


# ---------------------------------------------------------------------------
# Dialog construction & list refresh
# ---------------------------------------------------------------------------


def test_empty_dialog_shows_zero_count(qapp, fake_ui):
    dlg = ReferencePanelDialog(fake_ui)
    try:
        assert dlg._list.count() == 0
        assert "0" in dlg._count_label.text()
    finally:
        dlg.deleteLater()


def test_dialog_populates_existing_pins(qapp, fake_ui, png_path):
    reference_pins.add(png_path)
    dlg = ReferencePanelDialog(fake_ui)
    try:
        assert dlg._list.count() == 1
        item = dlg._list.item(0)
        assert item.toolTip() == png_path
    finally:
        dlg.deleteLater()


def test_remove_action_drops_selected_entry(qapp, fake_ui, png_path, tmp_path):
    other = str(tmp_path / "other.png")
    Image.new("RGBA", (16, 16), (10, 10, 10, 255)).save(other)
    reference_pins.add(png_path)
    reference_pins.add(other)

    dlg = ReferencePanelDialog(fake_ui)
    try:
        dlg._list.item(0).setSelected(True)
        dlg._on_remove()
        assert reference_pins.get_all() == [other]
        assert dlg._list.count() == 1
    finally:
        dlg.deleteLater()


def test_clear_action_empties_the_list(qapp, fake_ui, png_path):
    reference_pins.add(png_path)
    dlg = ReferencePanelDialog(fake_ui)
    try:
        dlg._on_clear()
        assert dlg._list.count() == 0
        assert reference_pins.count() == 0
    finally:
        dlg.deleteLater()


def test_move_up_reorders_list(qapp, fake_ui, tmp_path):
    paths = []
    for name, colour in (("a.png", (10, 10, 10, 255)), ("b.png", (20, 20, 20, 255))):
        p = tmp_path / name
        Image.new("RGBA", (16, 16), colour).save(str(p))
        paths.append(str(p))
    reference_pins.add_many(paths)

    dlg = ReferencePanelDialog(fake_ui)
    try:
        # Select the second item, move it up.
        dlg._list.item(1).setSelected(True)
        dlg._on_move(up=True)
        assert reference_pins.get_all() == [paths[1], paths[0]]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Preview helpers — module-level so the loader logic is unit-testable
# ---------------------------------------------------------------------------


def test_load_preview_returns_pixmap_on_supported_image(qapp, png_path):
    from PySide6.QtCore import QSize
    pix = _load_preview_pixmap(png_path, QSize(64, 64))
    assert pix is not None
    assert not pix.isNull()


def test_load_preview_returns_none_on_missing_file(qapp, tmp_path):
    from PySide6.QtCore import QSize
    pix = _load_preview_pixmap(str(tmp_path / "missing.png"), QSize(64, 64))
    assert pix is None


def test_load_thumb_icon_returns_none_on_failure(qapp, tmp_path):
    icon = _load_thumb_icon(str(tmp_path / "no-such-file.png"))
    assert icon is None
