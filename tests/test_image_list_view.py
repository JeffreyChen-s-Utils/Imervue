"""Tests for ImageListModel / ImageListView."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt


@pytest.fixture
def list_mod(qapp):
    from Imervue.gui.image_list_view import ImageListModel, ImageListView
    return ImageListModel, ImageListView


class TestImageListModel:
    def test_empty_model_has_zero_rows(self, list_mod):
        model_cls, _ = list_mod
        m = model_cls()
        assert m.rowCount() == 0
        assert m.columnCount() == model_cls.COL_COUNT

    def test_set_paths_resets(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        m = model_cls()
        a = str(tmp_path / "a.png")
        b = str(tmp_path / "b.png")
        m.set_paths([a, b])
        assert m.rowCount() == 2
        assert m.path_at(0) == a
        assert m.path_at(1) == b

    def test_name_display_uses_basename(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        path = str(tmp_path / "sub" / "pic.jpg")
        m = model_cls([path])
        idx = m.index(0, model_cls.COL_NAME)
        assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "pic.jpg"

    def test_type_display_is_upper_extension(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        m = model_cls([str(tmp_path / "pic.PnG")])
        idx = m.index(0, model_cls.COL_TYPE)
        assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "PNG"

    def test_sort_by_name(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        m = model_cls([
            str(tmp_path / "charlie.png"),
            str(tmp_path / "alpha.png"),
            str(tmp_path / "beta.png"),
        ])
        m.sort(model_cls.COL_NAME, Qt.SortOrder.AscendingOrder)
        names = [Path(m.path_at(i)).name for i in range(m.rowCount())]
        assert names == ["alpha.png", "beta.png", "charlie.png"]

    def test_user_role_returns_path(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        p = str(tmp_path / "x.png")
        m = model_cls([p])
        idx = m.index(0, 0)
        assert m.data(idx, Qt.ItemDataRole.UserRole) == p

    def test_rating_display_is_empty_when_unrated(self, list_mod, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        model_cls, _ = list_mod
        p = str(tmp_path / "unrated.png")
        user_setting_dict.pop("image_ratings", None)
        m = model_cls([p])
        idx = m.index(0, model_cls.COL_RATING)
        assert m.data(idx, Qt.ItemDataRole.DisplayRole) == ""

    def test_rating_display_uses_filled_and_empty_stars(self, list_mod, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        model_cls, _ = list_mod
        p = str(tmp_path / "rated.png")
        user_setting_dict["image_ratings"] = {p: 3}
        try:
            m = model_cls([p])
            idx = m.index(0, model_cls.COL_RATING)
            value = m.data(idx, Qt.ItemDataRole.DisplayRole)
            assert value == "\u2605\u2605\u2605\u2606\u2606"
        finally:
            user_setting_dict.pop("image_ratings", None)

    def test_sort_by_rating_is_numeric(self, list_mod, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        model_cls, _ = list_mod
        low = str(tmp_path / "low.png")
        mid = str(tmp_path / "mid.png")
        high = str(tmp_path / "high.png")
        user_setting_dict["image_ratings"] = {low: 1, mid: 3, high: 5}
        try:
            m = model_cls([mid, low, high])
            m.sort(model_cls.COL_RATING, Qt.SortOrder.DescendingOrder)
            order = [Path(m.path_at(i)).name for i in range(m.rowCount())]
            assert order == ["high.png", "mid.png", "low.png"]
        finally:
            user_setting_dict.pop("image_ratings", None)


class TestImageListViewBasics:
    def test_view_builds_with_empty_model(self, list_mod, qapp):
        _, view_cls = list_mod
        # MainWindow mock: only tolerates attribute access
        from unittest.mock import MagicMock
        v = view_cls(MagicMock())
        assert v.selected_paths() == []


# ---------------------------------------------------------------------------
# Phase 21 — empty-state hint when the model carries no rows.
# ---------------------------------------------------------------------------


def test_empty_state_hint_renders_when_no_paths(qapp):
    """The view paints a centred message when there are no images
    so users opening an empty folder don't stare at a blank table."""
    from Imervue.gui.image_list_view import ImageListView
    view = ImageListView(main_window=None)
    try:
        view.set_paths([])
        assert view._model.rowCount() == 0  # noqa: SLF001
        # The paint-event branch can be exercised by triggering a
        # repaint into a QImage — verifying it doesn't crash on the
        # empty path is the contract.
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QImage, QPaintEvent
        view.resize(200, 80)
        img = QImage(view.size(), QImage.Format.Format_RGB32)
        img.fill(0)
        evt = QPaintEvent(QRect(0, 0, 200, 80))
        view.paintEvent(evt)
    finally:
        view.deleteLater()


def test_empty_state_hint_skipped_with_paths(qapp, tmp_path):
    """A populated model never enters the hint branch — the table
    paints rows normally."""
    from PIL import Image as PILImage
    from Imervue.gui.image_list_view import ImageListView
    img_path = tmp_path / "x.png"
    PILImage.new("RGB", (4, 4)).save(img_path)
    view = ImageListView(main_window=None)
    try:
        view.set_paths([str(img_path)])
        assert view._model.rowCount() == 1  # noqa: SLF001
    finally:
        view.deleteLater()


def test_ctrl_c_copies_selected_paths_to_clipboard(qapp, tmp_path):
    """Ctrl+C on a selection writes the file paths to the system
    clipboard so the user can paste them elsewhere — common QoL
    in file browsers."""
    from PIL import Image as PILImage
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from Imervue.gui.image_list_view import ImageListView

    images = []
    for name in ("a.png", "b.png"):
        p = tmp_path / name
        PILImage.new("RGB", (4, 4)).save(p)
        images.append(str(p))
    view = ImageListView(main_window=None)
    try:
        view.set_paths(images)
        view.selectAll()
        QApplication.clipboard().clear()
        evt = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_C,
            Qt.KeyboardModifier.ControlModifier,
        )
        view.keyPressEvent(evt)
        clipboard = QApplication.clipboard().text()
        assert "a.png" in clipboard
        assert "b.png" in clipboard
    finally:
        view.deleteLater()


def test_context_menu_no_op_on_empty_selection(qapp):
    """Right-clicking with nothing selected mustn't raise — the
    handler returns early so the menu never appears."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QContextMenuEvent
    from Imervue.gui.image_list_view import ImageListView
    view = ImageListView(main_window=None)
    try:
        view.set_paths([])
        evt = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            QPoint(10, 10),
            QPoint(10, 10),
        )
        view.contextMenuEvent(evt)
    finally:
        view.deleteLater()


def test_reveal_path_handles_unknown_target(qapp, tmp_path, monkeypatch):
    """Reveal delegates to QDesktopServices. The opener is stubbed so the
    test never launches a real file-manager window (which would otherwise
    pop open — and stay open — on every test run)."""
    from PySide6.QtGui import QDesktopServices

    from Imervue.gui.image_list_view import ImageListView
    opened: list = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl",
        lambda url: bool(opened.append(url)) or True,
    )
    view = ImageListView(main_window=None)
    try:
        view._reveal_path(str(tmp_path / "nope.png"))  # noqa: SLF001
    finally:
        view.deleteLater()
    assert opened, "reveal should delegate to QDesktopServices.openUrl"
