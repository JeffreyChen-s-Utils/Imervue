"""Tests for the file-tree sort proxy and its pure helpers.

``dirs_first_precedence`` / ``file_sort_value`` / ``normalize_sort_key`` are
pure and tested directly. ``FileTreeSortProxy`` sorting runs under ``qapp``
over a synchronous ``QStandardItemModel`` stand-in exposing ``fileInfo`` (the
real ``QFileSystemModel`` populates asynchronously, which makes row-order
assertions flaky); the facade passthroughs run over a real
``FolderThumbnailModel``. ``_FileTreeView`` is a plain ``QTreeView`` — not a
``QOpenGLWidget`` — so the headless-CI skip marker is not required.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QMenu

from Imervue.gui.file_tree_sort import (
    DEFAULT_TREE_SORT_KEY,
    TREE_SORT_KEYS,
    FileTreeSortProxy,
    dirs_first_precedence,
    file_sort_value,
    normalize_sort_key,
)


# ---------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------
class _Stamp:
    """QDateTime stand-in: comparable + isValid()."""

    def __init__(self, value: int | None) -> None:
        self.value = value

    def isValid(self) -> bool:  # noqa: N802 - mirrors QDateTime
        return self.value is not None

    def __lt__(self, other: _Stamp) -> bool:
        return self.value < other.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Stamp) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class _Info:
    """QFileInfo stand-in with just the members the sorter reads."""

    def __init__(self, name: str, *, is_dir: bool = False, size: int = 0,
                 modified: int = 0, birth: int | None = None) -> None:
        self._name = name
        self._is_dir = is_dir
        self._size = size
        self._modified = modified
        self._birth = birth

    def fileName(self) -> str:  # noqa: N802 - mirrors QFileInfo
        return self._name

    def isDir(self) -> bool:  # noqa: N802 - mirrors QFileInfo
        return self._is_dir

    def size(self) -> int:
        return self._size

    def lastModified(self) -> _Stamp:  # noqa: N802 - mirrors QFileInfo
        return _Stamp(self._modified)

    def birthTime(self) -> _Stamp:  # noqa: N802 - mirrors QFileInfo
        return _Stamp(self._birth)


class _FakeFsSource(QStandardItemModel):
    """Synchronous QFileSystemModel stand-in exposing ``fileInfo``."""

    directoryLoaded = Signal(str)

    def add(self, info: _Info) -> None:
        item = QStandardItem(info.fileName())
        item.setData(info, Qt.ItemDataRole.UserRole)
        self.appendRow(item)

    def fileInfo(self, index) -> _Info:  # noqa: N802 - mirrors QFileSystemModel
        return self.itemFromIndex(index.siblingAtColumn(0)).data(
            Qt.ItemDataRole.UserRole)


def _proxy_names(proxy: FileTreeSortProxy) -> list[str]:
    return [
        proxy.data(proxy.index(row, 0)) for row in range(proxy.rowCount())
    ]


def _sorted_names(infos, key, ascending=True):
    src = _FakeFsSource()
    for info in infos:
        src.add(info)
    proxy = FileTreeSortProxy(src)
    proxy.set_sort_key(key)
    order = (Qt.SortOrder.AscendingOrder if ascending
             else Qt.SortOrder.DescendingOrder)
    proxy.sort(0, order)
    return _proxy_names(proxy)


# ---------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------
class TestNormalizeSortKey:
    def test_supported_keys_pass_through(self):
        for key in TREE_SORT_KEYS:
            assert normalize_sort_key(key) == key

    def test_unknown_and_none_fall_back_to_name(self):
        assert normalize_sort_key("bogus") == DEFAULT_TREE_SORT_KEY
        assert normalize_sort_key(None) == DEFAULT_TREE_SORT_KEY
        assert normalize_sort_key("") == DEFAULT_TREE_SORT_KEY


class TestDirsFirstPrecedence:
    def test_same_kind_defers_to_key_comparison(self):
        assert dirs_first_precedence(True, True, True) is None
        assert dirs_first_precedence(False, False, False) is None

    def test_ascending_puts_directory_first(self):
        assert dirs_first_precedence(True, False, True) is True
        assert dirs_first_precedence(False, True, True) is False

    def test_descending_is_pre_inverted_so_dirs_stay_on_top(self):
        # The proxy negates lessThan for descending sorts; the pre-inverted
        # value keeps directories grouped before files in both orders.
        assert dirs_first_precedence(True, False, False) is False
        assert dirs_first_precedence(False, True, False) is True


class TestFileSortValue:
    def test_size_key_reads_size(self):
        assert file_sort_value(_Info("a", size=42), "size") == 42

    def test_modified_key_reads_mtime(self):
        assert file_sort_value(_Info("a", modified=7), "modified") == _Stamp(7)

    def test_created_key_reads_birth_time(self):
        info = _Info("a", modified=7, birth=3)
        assert file_sort_value(info, "created") == _Stamp(3)

    def test_created_falls_back_to_mtime_without_birth_time(self):
        info = _Info("a", modified=7, birth=None)
        assert file_sort_value(info, "created") == _Stamp(7)

    def test_name_key_defers_to_collator(self):
        assert file_sort_value(_Info("a"), "name") is None


# ---------------------------------------------------------------
# Proxy sorting (deterministic fake source)
# ---------------------------------------------------------------
class TestProxySorting:
    def test_created_ascending_orders_by_birth_time(self, qapp):
        names = _sorted_names(
            [
                _Info("new.png", birth=30),
                _Info("old.png", birth=10),
                _Info("mid.png", birth=20),
            ],
            "created",
        )
        assert names == ["old.png", "mid.png", "new.png"]

    def test_created_descending_reverses(self, qapp):
        names = _sorted_names(
            [_Info("old.png", birth=10), _Info("new.png", birth=30)],
            "created", ascending=False,
        )
        assert names == ["new.png", "old.png"]

    def test_created_mixes_birth_and_mtime_fallback(self, qapp):
        # A file on a filesystem without birth time still lands in order.
        names = _sorted_names(
            [_Info("no-birth.png", modified=20, birth=None),
             _Info("birth.png", birth=10)],
            "created",
        )
        assert names == ["birth.png", "no-birth.png"]

    def test_directories_stay_on_top_in_both_orders(self, qapp):
        infos = [
            _Info("zzz-folder", is_dir=True, birth=99),
            _Info("aaa.png", birth=1),
        ]
        assert _sorted_names(infos, "created") == ["zzz-folder", "aaa.png"]
        assert _sorted_names(infos, "created", ascending=False) == [
            "zzz-folder", "aaa.png",
        ]

    def test_name_sort_is_numeric_aware(self, qapp):
        names = _sorted_names(
            [_Info("img10.png"), _Info("img2.png"), _Info("img1.png")],
            "name",
        )
        assert names == ["img1.png", "img2.png", "img10.png"]

    def test_equal_key_ties_break_by_name(self, qapp):
        names = _sorted_names(
            [_Info("b.png", size=5), _Info("a.png", size=5)],
            "size",
        )
        assert names == ["a.png", "b.png"]

    def test_set_sort_key_resorts_live(self, qapp):
        src = _FakeFsSource()
        src.add(_Info("big-old.png", size=100, birth=1))
        src.add(_Info("small-new.png", size=1, birth=9))
        proxy = FileTreeSortProxy(src)
        proxy.set_sort_key("size")
        proxy.sort(0, Qt.SortOrder.AscendingOrder)
        assert _proxy_names(proxy) == ["small-new.png", "big-old.png"]
        proxy.set_sort_key("created")
        assert _proxy_names(proxy) == ["big-old.png", "small-new.png"]

    def test_unknown_key_clamps_to_name(self, qapp):
        src = _FakeFsSource()
        proxy = FileTreeSortProxy(src)
        proxy.set_sort_key("bogus")
        assert proxy.sort_key() == DEFAULT_TREE_SORT_KEY


# ---------------------------------------------------------------
# QFileSystemModel facade passthroughs (real FolderThumbnailModel source)
# ---------------------------------------------------------------
class TestFacade:
    def test_path_index_and_file_path_round_trip(self, qapp, tmp_path):
        from Imervue.gui.folder_thumbnail_model import FolderThumbnailModel
        target = tmp_path / "a.png"
        target.write_bytes(b"")
        proxy = FileTreeSortProxy(FolderThumbnailModel())
        root = proxy.setRootPath(str(tmp_path))
        assert root.isValid()
        assert Path(proxy.rootPath()) == tmp_path

        idx = proxy.index(str(target))
        assert idx.isValid()
        assert Path(proxy.filePath(idx)) == target
        assert proxy.isDir(proxy.index(str(tmp_path))) is True
        assert proxy.isDir(idx) is False
        assert proxy.fileIcon(idx) is not None
        proxy.deleteLater()

    def test_thumbnail_model_facade_forwards(self, qapp):
        from Imervue.gui.folder_thumbnail_model import FolderThumbnailModel
        proxy = FileTreeSortProxy(FolderThumbnailModel())
        proxy.set_icon_size(64)
        assert proxy.icon_size() == 64
        proxy.clear_missing_previews()  # must not raise
        assert hasattr(proxy.directoryLoaded, "connect")
        proxy.deleteLater()

    def test_name_filters_forward_to_source(self, qapp, tmp_path):
        from Imervue.gui.folder_thumbnail_model import FolderThumbnailModel
        source = FolderThumbnailModel()
        proxy = FileTreeSortProxy(source)
        proxy.setNameFilters(["*.png"])
        proxy.setNameFilterDisables(False)
        assert list(source.nameFilters()) == ["*.png"]
        assert source.nameFilterDisables() is False
        proxy.deleteLater()


# ---------------------------------------------------------------
# _FileTreeView integration — the menu offers "created" and routes it
# through the proxy on column 0.
# ---------------------------------------------------------------
def _restore_sort_settings(old_sort, old_ascending):
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    if old_sort is None:
        user_setting_dict.pop("tree_sort_by", None)
    else:
        user_setting_dict["tree_sort_by"] = old_sort
    if old_ascending is None:
        user_setting_dict.pop("tree_sort_ascending", None)
    else:
        user_setting_dict["tree_sort_ascending"] = old_ascending


def test_set_tree_sort_created_routes_through_proxy(qapp):
    from Imervue.gui.file_tree_view import _FileTreeView
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    old_sort = user_setting_dict.get("tree_sort_by")
    old_ascending = user_setting_dict.get("tree_sort_ascending")
    tree = _FileTreeView(SimpleNamespace())
    proxy = FileTreeSortProxy(_FakeFsSource())
    tree.setModel(proxy)
    try:
        tree.set_tree_sort("created", False)
        assert proxy.sort_key() == "created"
        assert user_setting_dict["tree_sort_by"] == "created"
        # Every named key sorts through the visible Name column.
        assert tree.header().sortIndicatorSection() == 0
        assert tree.header().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    finally:
        _restore_sort_settings(old_sort, old_ascending)
        tree.deleteLater()


def test_sort_menu_offers_created_and_applies_it(qapp):
    from Imervue.gui.file_tree_view import _FileTreeView
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    old_sort = user_setting_dict.get("tree_sort_by")
    old_ascending = user_setting_dict.get("tree_sort_ascending")
    tree = _FileTreeView(SimpleNamespace())
    proxy = FileTreeSortProxy(_FakeFsSource())
    tree.setModel(proxy)
    menu = QMenu()
    try:
        sort_menu = tree._add_sort_menu(menu)  # noqa: SLF001
        sort_actions = [a for a in sort_menu.actions() if a.isCheckable()]
        # 4 sort keys + Ascending/Descending order toggles.
        assert len(sort_actions) == 6
        created_action = sort_actions[list(
            ("name", "modified", "created", "size")).index("created")]
        created_action.trigger()
        assert proxy.sort_key() == "created"
        assert user_setting_dict["tree_sort_by"] == "created"
    finally:
        _restore_sort_settings(old_sort, old_ascending)
        menu.deleteLater()
        tree.deleteLater()
