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
        Model, _ = list_mod
        m = Model()
        assert m.rowCount() == 0
        assert m.columnCount() == Model.COL_COUNT

    def test_set_paths_resets(self, list_mod, tmp_path):
        Model, _ = list_mod
        m = Model()
        a = str(tmp_path / "a.png")
        b = str(tmp_path / "b.png")
        m.set_paths([a, b])
        assert m.rowCount() == 2
        assert m.path_at(0) == a
        assert m.path_at(1) == b

    def test_name_display_uses_basename(self, list_mod, tmp_path):
        Model, _ = list_mod
        path = str(tmp_path / "sub" / "pic.jpg")
        m = Model([path])
        idx = m.index(0, Model.COL_NAME)
        assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "pic.jpg"

    def test_type_display_is_upper_extension(self, list_mod, tmp_path):
        Model, _ = list_mod
        m = Model([str(tmp_path / "pic.PnG")])
        idx = m.index(0, Model.COL_TYPE)
        assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "PNG"

    def test_sort_by_name(self, list_mod, tmp_path):
        Model, _ = list_mod
        m = Model([
            str(tmp_path / "charlie.png"),
            str(tmp_path / "alpha.png"),
            str(tmp_path / "beta.png"),
        ])
        m.sort(Model.COL_NAME, Qt.SortOrder.AscendingOrder)
        names = [Path(m.path_at(i)).name for i in range(m.rowCount())]
        assert names == ["alpha.png", "beta.png", "charlie.png"]

    def test_user_role_returns_path(self, list_mod, tmp_path):
        Model, _ = list_mod
        p = str(tmp_path / "x.png")
        m = Model([p])
        idx = m.index(0, 0)
        assert m.data(idx, Qt.ItemDataRole.UserRole) == p


class TestImageListViewBasics:
    def test_view_builds_with_empty_model(self, list_mod, qapp):
        _, View = list_mod
        # MainWindow mock: only tolerates attribute access
        from unittest.mock import MagicMock
        v = View(MagicMock())
        assert v.selected_paths() == []
