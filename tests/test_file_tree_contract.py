"""Observable contracts for file-tree deletion and callback dispatch."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QModelIndex, Qt, Signal
from PySide6.QtGui import QKeyEvent, QStandardItem

from _instant_worker import DeferredDeleteWorker, InstantDeleteWorker
from Imervue.gui.file_tree_view import _FileTreeView, _TrashRequest
from tests.test_file_tree_multiselect import _FakeFsModel, _big_batch_tree, _select_rows


@pytest.mark.parametrize("batch", [False, True])
def test_duplicate_image_occurrences_keep_single_and_batch_semantics(
    qapp, tmp_path, monkeypatch, batch
):
    tree, main, files = _big_batch_tree(tmp_path, monkeypatch, 2, listed=2)
    viewer = main.viewer
    viewer.model.images[:] = [files[0], files[1], files[0]]
    dispatched = []
    main.plugin_manager = SimpleNamespace(
        dispatch_image_deleted=lambda paths, owner: dispatched.append((list(paths), owner))
    )
    tree._delete_paths(files if batch else files[:1])
    expected = [files[0], files[1], files[0]] if batch else files[:1]
    assert viewer.model.images == ([] if batch else [files[1], files[0]])
    assert viewer.undo_stack == [
        {
            "mode": "delete",
            "deleted_paths": expected,
            "indices": [0, 1, 2] if batch else [0],
            "restored": False,
        }
    ]
    assert dispatched == [(expected, viewer)]
    assert all(Path(path).exists() for path in files)
    tree.deleteLater()


def test_mixed_delete_keeps_soft_deletes_and_reports_completed_loose_files(
    qapp, tmp_path, monkeypatch
):
    tree, main, files = _big_batch_tree(
        tmp_path, monkeypatch, 2, listed=1, worker_cls=DeferredDeleteWorker
    )
    folder = tmp_path / "album"
    folder.mkdir()
    refreshes = []
    monkeypatch.setattr(tree, "refresh_pending_hidden", lambda: refreshes.append(True))
    tree._delete_paths([files[0], str(folder), files[1]])
    assert main.viewer.model.images == []
    assert [entry["mode"] for entry in main.viewer.undo_stack] == ["delete", "delete_external"]
    assert refreshes == [True]
    assert main.toast.calls == []
    worker = InstantDeleteWorker.created[0]
    assert worker.paths == files[1:]
    worker.finish()
    assert main.toast.calls == [("info", "Moved 3 items to trash")]
    assert folder.exists()
    tree.deleteLater()


def test_completion_callback_can_queue_another_delete(qapp, tmp_path, monkeypatch):
    tree, _main, files = _big_batch_tree(tmp_path, monkeypatch, 2, worker_cls=DeferredDeleteWorker)
    completed = []

    def first_done(paths):
        completed.append(paths)
        tree._trash_in_background(_TrashRequest((files[1],), completed.append))

    tree._trash_in_background(_TrashRequest((files[0],), first_done))
    InstantDeleteWorker.created[0].finish()
    assert len(InstantDeleteWorker.created) == 2
    InstantDeleteWorker.created[1].finish()
    assert completed == [[files[0]], [files[1]]]
    assert not tree._trash_workers
    tree.deleteLater()


def test_shutdown_tolerates_completion_mutating_worker_registry():
    view = SimpleNamespace(
        _trash_workers=set(),
        _pending_trash=[],
        _tree_state=SimpleNamespace(save=lambda: None),
        _recursive_search=None,
    )
    flushed = []
    view._flush_pending_trash = lambda: flushed.append(True)

    class CompletingWorker:
        def isRunning(self):  # noqa: N802 - Qt method
            return True

        def wait(self):
            view._trash_workers.remove(self)

    view._trash_workers.add(CompletingWorker())
    _FileTreeView.shutdown(view)
    assert not view._trash_workers
    assert flushed == [True]


def test_delete_key_dispatches_through_instance_override(qapp, tmp_path, monkeypatch):
    tree, _main, files = _big_batch_tree(tmp_path, monkeypatch, 2)
    _select_rows(tree, tree.model(), [0, 1])
    seen = []
    monkeypatch.setattr(tree, "_delete_paths", lambda paths: seen.append(paths))
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    tree.keyPressEvent(event)
    assert seen == [files]
    tree.deleteLater()


def test_subclass_refresh_override_is_used_by_public_refresh(qapp):
    calls = []

    class CustomTree(_FileTreeView):
        def _refresh_tree(self):
            calls.append(self)

    tree = CustomTree(None)
    tree.refresh()
    assert calls == [tree]
    tree.deleteLater()


def test_subclass_sort_columns_remain_the_validation_source(qapp, monkeypatch):
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    class CustomTree(_FileTreeView):
        _TREE_SORT_COLUMNS = {**_FileTreeView._TREE_SORT_COLUMNS, "custom": 2}

    tree = CustomTree(None)
    applied = []
    monkeypatch.setattr(
        tree, "_apply_tree_sort", lambda key, ascending: applied.append((key, ascending))
    )
    tree.set_tree_sort("custom", False)
    assert applied == [("custom", False)]
    assert user_setting_dict["tree_sort_by"] == "custom"
    tree.deleteLater()


def test_reload_and_restore_preserve_search_and_pending_folder_visibility(qapp, tmp_path):
    class LoadedModel(_FakeFsModel):
        directoryLoaded = Signal(str)

        def index(self, row, column=0, parent=None):
            if isinstance(row, str):
                for item_row in range(self.rowCount()):
                    candidate = super().index(item_row, 0)
                    if self.filePath(candidate) == row:
                        return candidate
                return QModelIndex()
            return super().index(row, column, parent or QModelIndex())

    folder = str(tmp_path / "album")
    action = {"mode": "delete_external", "deleted_paths": [folder], "restored": False}
    main = SimpleNamespace(viewer=SimpleNamespace(undo_stack=[action]))
    tree = _FileTreeView(main)
    model = LoadedModel()
    album = QStandardItem("album")
    album.setData(folder, Qt.ItemDataRole.UserRole)
    child = QStandardItem("target.png")
    child.setData(str(Path(folder) / "target.png"), Qt.ItemDataRole.UserRole)
    album.appendRow(child)
    model.appendRow(album)
    tree.setModel(model)
    tree.set_search_text("target")
    assert tree.isRowHidden(0, QModelIndex())
    model.directoryLoaded.emit(folder)
    assert tree.isRowHidden(0, QModelIndex())
    action["restored"] = True
    model.directoryLoaded.emit(folder)
    assert not tree.isRowHidden(0, QModelIndex())
    tree.set_search_text("absent")
    assert tree.isRowHidden(0, QModelIndex())
    tree.set_search_text("")
    assert not tree.isRowHidden(0, QModelIndex())
    tree.deleteLater()


@pytest.mark.parametrize(
    "operation, expected",
    [
        ("folder", "Create failed: denied"),
        ("rename", "Rename failed: denied"),
        ("duplicate", "Duplicate failed: denied"),
    ],
)
@pytest.mark.parametrize("has_toast", [False, True])
def test_filesystem_failures_preserve_notifications_and_source(
    qapp,
    tmp_path,
    monkeypatch,
    operation,
    expected,
    has_toast,
):
    from PySide6.QtWidgets import QInputDialog
    import shutil

    source = tmp_path / "source.png"
    source.write_bytes(b"image")
    messages = []
    main = SimpleNamespace()
    if has_toast:
        main.toast = SimpleNamespace(error=messages.append)
    refreshes = []
    tree = SimpleNamespace(_main_window=main, _refresh_tree=lambda: refreshes.append(True))
    monkeypatch.setattr(QInputDialog, "getText", lambda *_a, **_kw: ("new", True))

    def fail(*_args, **_kwargs):
        raise OSError("denied")

    if operation == "folder":
        monkeypatch.setattr(Path, "mkdir", fail)
        _FileTreeView._create_new_folder(tree, str(tmp_path))
    elif operation == "rename":
        monkeypatch.setattr(Path, "rename", fail)
        _FileTreeView._rename_path(tree, str(source))
    else:
        monkeypatch.setattr(shutil, "copy2", fail)
        _FileTreeView._duplicate_file(tree, str(source))
    assert source.read_bytes() == b"image"
    assert messages == ([expected] if has_toast else [])
    assert refreshes == []
