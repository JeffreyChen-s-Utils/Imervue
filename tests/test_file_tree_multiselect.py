"""Tests for _FileTreeView multi-select: batch delete, copy paths, menu routing.

``_dedupe_paths`` is pure and tested directly. The view behaviour runs under
the ``qapp`` fixture with a synchronous ``QStandardItemModel`` stand-in (the
real ``QFileSystemModel`` populates asynchronously, which makes selection
flaky) so selection / delete dispatch is deterministic. ``_FileTreeView`` is a
plain ``QTreeView`` — not a ``QOpenGLWidget`` — so the headless-CI skip marker
is not required.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QPoint, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from Imervue.gui.file_tree_view import _FileTreeView, _dedupe_paths

_TRASH_PATH = "Imervue.gpu_image_view.actions.keyboard_actions._send_to_trash"


# ---------------------------------------------------------------
# _dedupe_paths (pure)
# ---------------------------------------------------------------
class TestDedupePaths:
    def test_preserves_order(self):
        assert _dedupe_paths(["a", "b", "c"]) == ["a", "b", "c"]

    def test_drops_later_duplicates(self):
        assert _dedupe_paths(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]

    def test_drops_empty_strings(self):
        assert _dedupe_paths(["", "a", "", "b"]) == ["a", "b"]

    def test_empty_input(self):
        assert _dedupe_paths([]) == []

    def test_accepts_generator(self):
        assert _dedupe_paths(p for p in ["x", "x", "y"]) == ["x", "y"]


# ---------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------
class _FakeFsModel(QStandardItemModel):
    """Synchronous stand-in for QFileSystemModel exposing ``filePath``."""

    def filePath(self, index):  # noqa: N802 — mirrors QFileSystemModel
        item = self.itemFromIndex(index.siblingAtColumn(0))
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else ""


class _ToastSpy:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, msg):
        self.calls.append(("info", msg))

    def success(self, msg):
        self.calls.append(("success", msg))

    def warning(self, msg):
        self.calls.append(("warning", msg))

    def error(self, msg):
        self.calls.append(("error", msg))


class _FakeViewerModel:
    def __init__(self):
        self.images: list[str] = []


class _FakeViewer:
    def __init__(self):
        self.model = _FakeViewerModel()


class _StubMainWindow:
    def __init__(self):
        self.viewer = _FakeViewer()
        self.toast = _ToastSpy()


def _make_tree(files):
    main = _StubMainWindow()
    tree = _FileTreeView(main)
    model = _FakeFsModel()
    for path in files:
        item = QStandardItem(Path(path).name)
        item.setData(str(path), Qt.ItemDataRole.UserRole)
        model.appendRow(item)
    tree.setModel(model)
    return tree, main, model


def _select_rows(tree, model, rows):
    sel = tree.selectionModel()
    sel.clearSelection()
    flags = (
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows
    )
    for row in rows:
        sel.select(model.index(row, 0), flags)


def _make_files(tmp_path, count):
    files = []
    for i in range(count):
        f = tmp_path / f"img_{i}.png"
        f.write_bytes(b"")
        files.append(f)
    return files


# ---------------------------------------------------------------
# Selection
# ---------------------------------------------------------------
def test_extended_selection_mode_enabled(qapp):
    tree, _main, _model = _make_tree([])
    assert tree.selectionMode() == _FileTreeView.SelectionMode.ExtendedSelection
    tree.deleteLater()


def test_selected_paths_returns_chosen_rows(qapp, tmp_path):
    files = _make_files(tmp_path, 3)
    tree, _main, model = _make_tree(files)
    _select_rows(tree, model, [0, 2])
    assert tree._selected_paths() == [str(files[0]), str(files[2])]  # noqa: SLF001
    tree.deleteLater()


def test_selected_paths_empty_when_nothing_selected(qapp, tmp_path):
    files = _make_files(tmp_path, 2)
    tree, _main, _model = _make_tree(files)
    assert tree._selected_paths() == []  # noqa: SLF001
    tree.deleteLater()


# ---------------------------------------------------------------
# Batch delete
# ---------------------------------------------------------------
def test_delete_paths_empty_is_noop(qapp, monkeypatch):
    trashed = []
    monkeypatch.setattr(_TRASH_PATH, lambda p: trashed.append(p) or True)
    tree, main, _model = _make_tree([])
    tree._delete_paths([])  # noqa: SLF001
    assert trashed == []
    assert main.toast.calls == []
    tree.deleteLater()


def test_delete_paths_skips_missing(qapp, tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr(_TRASH_PATH, lambda p: trashed.append(p) or True)
    tree, _main, _model = _make_tree([])
    missing = str(tmp_path / "gone.png")
    tree._delete_paths([missing])  # noqa: SLF001
    assert trashed == []
    tree.deleteLater()


def test_delete_paths_single_uses_per_file_toast(qapp, tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr(_TRASH_PATH, lambda p: trashed.append(p) or True)
    files = _make_files(tmp_path, 1)
    tree, main, _model = _make_tree(files)
    tree._delete_paths([str(files[0])])  # noqa: SLF001
    assert trashed == [str(files[0])]
    assert len(main.toast.calls) == 1
    # Single-file message names the file.
    assert "img_0.png" in main.toast.calls[0][1]
    tree.deleteLater()


def test_delete_paths_batch_uses_single_summary_toast(qapp, tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr(_TRASH_PATH, lambda p: trashed.append(p) or True)
    files = _make_files(tmp_path, 3)
    tree, main, _model = _make_tree(files)
    tree._delete_paths([str(f) for f in files])  # noqa: SLF001
    assert len(trashed) == 3
    # Exactly one summary toast mentioning the count — no per-file spam.
    assert len(main.toast.calls) == 1
    assert "3" in main.toast.calls[0][1]
    tree.deleteLater()


def test_delete_selected_deletes_all_selected_rows(qapp, tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr(_TRASH_PATH, lambda p: trashed.append(p) or True)
    files = _make_files(tmp_path, 3)
    tree, _main, model = _make_tree(files)
    _select_rows(tree, model, [0, 1, 2])
    tree._delete_selected()  # noqa: SLF001
    assert set(trashed) == {str(f) for f in files}
    tree.deleteLater()


# ---------------------------------------------------------------
# Context-menu routing (no QMenu.exec — builders are stubbed)
# ---------------------------------------------------------------
def _route(tree, model, monkeypatch, *, selected_rows, clicked_row):
    _select_rows(tree, model, selected_rows)
    seen = []
    monkeypatch.setattr(
        tree, "_show_multi_context_menu",
        lambda paths, pos: seen.append(("multi", list(paths))),
    )
    monkeypatch.setattr(
        tree, "_show_single_context_menu",
        lambda path, pos: seen.append(("single", path)),
    )
    monkeypatch.setattr(tree, "indexAt", lambda pos: model.index(clicked_row, 0))
    tree._show_context_menu(QPoint(0, 0))  # noqa: SLF001
    return seen


def test_menu_routes_multi_when_clicked_inside_multiselection(qapp, tmp_path, monkeypatch):
    files = _make_files(tmp_path, 3)
    tree, _main, model = _make_tree(files)
    seen = _route(tree, model, monkeypatch, selected_rows=[0, 1], clicked_row=0)
    assert seen[0][0] == "multi"
    assert set(seen[0][1]) == {str(files[0]), str(files[1])}
    tree.deleteLater()


def test_menu_routes_single_when_clicked_outside_selection(qapp, tmp_path, monkeypatch):
    files = _make_files(tmp_path, 3)
    tree, _main, model = _make_tree(files)
    # Two rows selected, but the right-click landed on a third, unselected row.
    seen = _route(tree, model, monkeypatch, selected_rows=[0, 1], clicked_row=2)
    assert seen == [("single", str(files[2]))]
    tree.deleteLater()


def test_menu_routes_single_when_one_row_selected(qapp, tmp_path, monkeypatch):
    files = _make_files(tmp_path, 2)
    tree, _main, model = _make_tree(files)
    seen = _route(tree, model, monkeypatch, selected_rows=[0], clicked_row=0)
    assert seen == [("single", str(files[0]))]
    tree.deleteLater()
