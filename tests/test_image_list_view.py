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
