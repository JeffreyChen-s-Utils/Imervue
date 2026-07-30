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
from types import SimpleNamespace

from PySide6.QtCore import QItemSelectionModel, QPoint, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from _instant_worker import FailingDeleteWorker, InstantDeleteWorker
from Imervue.gui.file_tree_view import (
    _FileTreeView,
    _dedupe_paths,
    _partition_delete_batch,
)

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


def test_search_text_hides_non_matching_rows(qapp, tmp_path):
    files = _make_files(tmp_path, 3)
    tree, _main, _model = _make_tree(files)
    tree.set_search_text("img_1")
    assert tree.isRowHidden(0, tree.rootIndex()) is True
    assert tree.isRowHidden(1, tree.rootIndex()) is False
    assert tree.isRowHidden(2, tree.rootIndex()) is True
    tree.set_search_text("")
    assert tree.isRowHidden(0, tree.rootIndex()) is False
    assert tree.isRowHidden(2, tree.rootIndex()) is False
    tree.deleteLater()


def test_search_keeps_parent_visible_for_matching_child(qapp, tmp_path):
    parent = tmp_path / "album"
    child = parent / "target.png"
    tree, _main, model = _make_tree([parent])
    child_item = QStandardItem(child.name)
    child_item.setData(str(child), Qt.ItemDataRole.UserRole)
    model.item(0, 0).appendRow(child_item)
    tree.expand(model.index(0, 0))

    tree.set_search_text("target")
    assert tree.isRowHidden(0, tree.rootIndex()) is False
    assert tree.isRowHidden(0, model.index(0, 0)) is False
    tree.deleteLater()


def test_tree_sort_persists_choice(qapp):
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    old_sort = user_setting_dict.get("tree_sort_by")
    old_ascending = user_setting_dict.get("tree_sort_ascending")
    tree, _main, _model = _make_tree([])
    try:
        tree.set_tree_sort("size", False)
        assert user_setting_dict["tree_sort_by"] == "size"
        assert user_setting_dict["tree_sort_ascending"] is False
        assert tree.header().sortIndicatorSection() == 1
        assert tree.header().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    finally:
        if old_sort is None:
            user_setting_dict.pop("tree_sort_by", None)
        else:
            user_setting_dict["tree_sort_by"] = old_sort
        if old_ascending is None:
            user_setting_dict.pop("tree_sort_ascending", None)
        else:
            user_setting_dict["tree_sort_ascending"] = old_ascending
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
    _use_instant_worker(monkeypatch)
    files = _make_files(tmp_path, 1)
    tree, main, _model = _make_tree(files)
    tree._delete_paths([str(files[0])])  # noqa: SLF001
    assert InstantDeleteWorker.created[0].paths == [str(files[0])]
    assert len(main.toast.calls) == 1
    # Single-file message names the file.
    assert "img_0.png" in main.toast.calls[0][1]
    tree.deleteLater()


def test_delete_paths_batch_uses_single_summary_toast(qapp, tmp_path, monkeypatch):
    _use_instant_worker(monkeypatch)
    files = _make_files(tmp_path, 3)
    tree, main, _model = _make_tree(files)
    tree._delete_paths([str(f) for f in files])  # noqa: SLF001
    assert InstantDeleteWorker.created[0].paths == [str(f) for f in files]
    # Exactly one summary toast mentioning the count — no per-file spam.
    assert len(main.toast.calls) == 1
    assert "3" in main.toast.calls[0][1]
    tree.deleteLater()


def test_delete_selected_deletes_all_selected_rows(qapp, tmp_path, monkeypatch):
    _use_instant_worker(monkeypatch)
    files = _make_files(tmp_path, 3)
    tree, _main, model = _make_tree(files)
    _select_rows(tree, model, [0, 1, 2])
    tree._delete_selected()  # noqa: SLF001
    assert set(InstantDeleteWorker.created[0].paths) == {str(f) for f in files}
    tree.deleteLater()


# ---------------------------------------------------------------
# Large-batch delete — must never block the GUI thread
# ---------------------------------------------------------------
class TestPartitionDeleteBatch:
    def test_splits_list_files_folders_and_loose_files(self, tmp_path):
        folder = tmp_path / "sub"
        folder.mkdir()
        listed = tmp_path / "listed.png"
        listed.write_bytes(b"")
        loose = tmp_path / "loose.png"
        loose.write_bytes(b"")
        in_list, folders, loose_out = _partition_delete_batch(
            [str(folder), str(listed), str(loose)], [str(listed)])
        assert in_list == [str(listed)]
        assert folders == [str(folder)]
        assert loose_out == [str(loose)]

    def test_empty_batch(self):
        assert _partition_delete_batch([], []) == ([], [], [])

    def test_missing_path_counts_as_loose_file(self, tmp_path):
        gone = str(tmp_path / "gone.png")
        assert _partition_delete_batch([gone], []) == ([], [], [gone])


def _use_instant_worker(monkeypatch, worker_cls=InstantDeleteWorker):
    """Swap the OS-trash worker for the synchronous stand-in.

    Every batch delete is backgrounded now, so a test that leaves the real
    worker in place would hand files to the actual recycle bin.
    """
    from Imervue.system import trash_ops
    InstantDeleteWorker.created = []
    monkeypatch.setattr(trash_ops, "FileDeleteWorker", worker_cls)


def _big_batch_tree(tmp_path, monkeypatch, count, listed=0,
                    worker_cls=InstantDeleteWorker):
    _use_instant_worker(monkeypatch, worker_cls)
    files = [str(f) for f in _make_files(tmp_path, count)]
    tree, main, _model = _make_tree(files)
    viewer = main.viewer
    viewer.model.images = files[:listed]
    viewer.undo_stack = []
    viewer.tile_textures = {}
    viewer.tile_cache = {}
    viewer.tile_grid_mode = True
    viewer.tile_rects = []
    viewer.update = lambda: None
    return tree, main, files


def test_two_file_batch_still_goes_to_the_worker(qapp, tmp_path, monkeypatch):
    # A per-file send2trash costs ~0.27 s whatever its size, so even the
    # smallest multi-file batch must be grouped onto the worker instead of
    # looping on the GUI thread.
    trashed = []
    monkeypatch.setattr(_TRASH_PATH, lambda p: trashed.append(p) or True)
    tree, _main, files = _big_batch_tree(tmp_path, monkeypatch, 2)
    tree._delete_paths(files)  # noqa: SLF001
    assert trashed == []
    assert len(InstantDeleteWorker.created) == 1
    assert InstantDeleteWorker.created[0].paths == files
    tree.deleteLater()


def test_single_file_delete_never_blocks_the_gui_thread(qapp, tmp_path, monkeypatch):
    # Even one file is a ~0.27 s shell round-trip, so it goes to the worker
    # too — nothing reaches the inline trash call any more.
    trashed = []
    monkeypatch.setattr(_TRASH_PATH, lambda p: trashed.append(p) or True)
    tree, _main, files = _big_batch_tree(tmp_path, monkeypatch, 1)
    tree._delete_paths(files)  # noqa: SLF001
    assert trashed == []
    assert len(InstantDeleteWorker.created) == 1
    assert InstantDeleteWorker.created[0].paths == files
    tree.deleteLater()


def test_deletes_during_a_running_worker_merge_into_one_batch(
        qapp, tmp_path, monkeypatch):
    # A grouped shell call costs the same as a single-file one, so a burst
    # of Delete presses must coalesce instead of spawning a thread each.
    from _instant_worker import DeferredDeleteWorker

    tree, _main, files = _big_batch_tree(
        tmp_path, monkeypatch, 3, worker_cls=DeferredDeleteWorker)
    for path in files:
        tree._delete_paths([path])  # noqa: SLF001

    created = InstantDeleteWorker.created
    assert len(created) == 1                 # two asks queued behind the first
    assert created[0].paths == [files[0]]

    created[0].finish()                      # in-flight worker lands

    assert len(created) == 2
    assert created[1].paths == files[1:]     # both queued asks in one call
    tree.deleteLater()


def test_queued_deletes_each_get_their_own_toast(qapp, tmp_path, monkeypatch):
    from _instant_worker import DeferredDeleteWorker

    tree, main, files = _big_batch_tree(
        tmp_path, monkeypatch, 2, worker_cls=DeferredDeleteWorker)
    for path in files:
        tree._delete_paths([path])  # noqa: SLF001
    created = InstantDeleteWorker.created
    created[0].finish()
    created[1].finish()

    # One per-file toast per request, each naming its own file.
    messages = [msg for _kind, msg in main.toast.calls]
    assert len(messages) == 2
    assert "img_0.png" in messages[0]
    assert "img_1.png" in messages[1]
    tree.deleteLater()


def test_a_failed_single_delete_reports_no_success_toast(
        qapp, tmp_path, monkeypatch):
    tree, main, files = _big_batch_tree(
        tmp_path, monkeypatch, 1, worker_cls=FailingDeleteWorker)
    tree._delete_paths(files)  # noqa: SLF001
    kinds = [kind for kind, _msg in main.toast.calls]
    assert kinds == ["warning"]
    tree.deleteLater()


def test_large_batch_routes_loose_files_to_the_worker(qapp, tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr(_TRASH_PATH, lambda p: trashed.append(p) or True)
    tree, main, files = _big_batch_tree(
        tmp_path, monkeypatch, 12, listed=4)
    tree._delete_paths(files)  # noqa: SLF001
    viewer = main.viewer
    # Viewer-list files soft-deleted in one pass with a single undo entry.
    assert viewer.model.images == []
    assert len(viewer.undo_stack) == 1
    assert viewer.undo_stack[0]["deleted_paths"] == files[:4]
    assert viewer.undo_stack[0]["indices"] == [0, 1, 2, 3]
    # Loose files never hit the synchronous trash path...
    assert trashed == []
    # ...they went to the background worker instead.
    assert len(InstantDeleteWorker.created) == 1
    assert InstantDeleteWorker.created[0].paths == files[4:]
    # One summary toast counts the whole batch.
    assert len(main.toast.calls) == 1
    assert str(len(files)) in main.toast.calls[0][1]
    tree.deleteLater()


def test_large_batch_without_loose_files_toasts_immediately(qapp, tmp_path, monkeypatch):
    count = 10
    tree, main, files = _big_batch_tree(tmp_path, monkeypatch, count, listed=count)
    tree._delete_paths(files)  # noqa: SLF001
    assert InstantDeleteWorker.created == []
    assert len(main.toast.calls) == 1
    assert str(count) in main.toast.calls[0][1]
    tree.deleteLater()


def test_worker_failures_surface_a_warning_toast(qapp, tmp_path, monkeypatch):
    tree, main, files = _big_batch_tree(
        tmp_path, monkeypatch, 12,
        worker_cls=FailingDeleteWorker)
    tree._delete_paths(files)  # noqa: SLF001
    kinds = [kind for kind, _msg in main.toast.calls]
    assert "warning" in kinds
    tree.deleteLater()


def test_folder_batch_refreshes_hidden_rows_once(qapp, tmp_path, monkeypatch):
    # refresh_pending_hidden costs a model lookup per pending path, so calling
    # it inside the per-folder loop made a folder batch quadratic.
    _use_instant_worker(monkeypatch)
    folders = []
    for i in range(5):
        folder = tmp_path / f"album_{i}"
        folder.mkdir()
        folders.append(str(folder))
    tree, main, _model = _make_tree(folders)
    main.viewer.undo_stack = []
    calls = []
    monkeypatch.setattr(tree, "refresh_pending_hidden", lambda: calls.append(1))

    tree._delete_paths(folders)  # noqa: SLF001

    assert len(calls) == 1
    assert len(main.viewer.undo_stack) == len(folders)
    assert all(a["mode"] == "delete_external" for a in main.viewer.undo_stack)
    tree.deleteLater()


def test_batch_undo_entry_restores_original_positions(qapp, tmp_path, monkeypatch):
    # The single batch undo entry must round-trip through undo_delete.
    from Imervue.gpu_image_view.actions.delete import undo_delete
    count = 12
    tree, main, files = _big_batch_tree(tmp_path, monkeypatch, count, listed=count)
    viewer = main.viewer
    original = list(viewer.model.images)
    tree._delete_paths(files)  # noqa: SLF001
    assert viewer.model.images == []
    viewer.thumbnail_size = 256
    viewer._load_generation = 0
    viewer.active_tile_workers = set()
    viewer.thread_pool = SimpleNamespace(start=lambda *a, **kw: None)
    viewer.add_thumbnail = lambda *a, **kw: None
    viewer.deep_zoom = None
    undo_delete(viewer)
    assert viewer.model.images == original
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
