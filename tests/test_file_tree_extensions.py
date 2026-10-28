"""User-visible sorting, recursive search and saved file-tree position behavior."""
import os
import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from dataclasses import asdict
import json

import pytest
from PySide6.QtCore import QItemSelectionModel, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileSystemModel, QMenu
from Imervue.gui.folder_thumbnail_model import FolderThumbnailModel

from Imervue.gui.file_tree_preferences import root_key
from Imervue.gui.file_tree_preferences import TreeSortSettings
from Imervue.gui.file_tree_state import TreeViewState
from Imervue.gui.file_tree_search import scan_matches
from Imervue.gui.file_tree_sort import FileTreeSortProxy
from Imervue.gui.file_tree_view import _FileTreeView
from Imervue.user_settings import user_setting_dict as settings


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


@pytest.mark.parametrize("state", [
    TreeSortSettings("type", False, False),
    TreeViewState(("C:/photos/a",), ("C:/photos/a/1.png",), "C:/photos/a/1.png",
                  "C:/photos/a/1.png", -5, 40),
])
def test_tree_settings_round_trip_json(state):
    assert type(state).from_dict(json.loads(json.dumps(asdict(state)))) == state


@pytest.mark.parametrize("value", [None, "wrong", [], {"key": "unknown"}])
def test_sort_settings_reject_malformed_shape(value):
    assert TreeSortSettings.from_dict(value) == TreeSortSettings()


def test_tree_state_discards_malformed_values():
    assert TreeViewState.from_dict({
        "expanded": "not a list", "selected": [None, 3], "current": [],
        "top_visible": {}, "top_offset": "7", "horizontal_scroll": True,
    }) == TreeViewState()


@pytest.fixture
def make_tree(qapp, monkeypatch):
    monkeypatch.setattr(settings, "schedule_save", lambda: None)
    trees = []

    def make(root):
        tree = _FileTreeView(SimpleNamespace())
        source = FolderThumbnailModel()
        source.setOption(QFileSystemModel.Option.DontWatchForChanges, True)
        source.setOption(QFileSystemModel.Option.DontUseCustomDirectoryIcons, True)
        proxy = FileTreeSortProxy(source)
        tree.setModel(proxy)
        tree.set_root_path(str(root))
        for col in (1, 2, 3):
            tree.hideColumn(col)
        tree.resize(300, 200)
        tree.show()
        trees.append(tree)
        return tree

    yield make
    for tree in trees:
        tree.shutdown()
        tree.close()
        tree.deleteLater()
    qapp.processEvents()


def names(tree):
    model = tree.model()
    root = tree.rootIndex()
    return [model.filePath(model.index(i, 0, root)).replace("\\", "/").rsplit("/", 1)[-1]
            for i in range(model.rowCount(root))]


def test_metadata_tooltip_reports_actual_file_details(make_tree, tmp_path):
    file = tmp_path / "image.png"
    file.write_bytes(b"12345")
    tree = make_tree(tmp_path)
    index = tree.model().index(str(file))
    info = tree.model().sourceModel().fileInfo(tree.model().mapToSource(index))
    tooltip = index.data(Qt.ItemDataRole.ToolTipRole)
    assert "5 bytes" in tooltip
    assert info.lastModified().toString("yyyy-MM-dd HH:mm:ss") in tooltip
    if info.birthTime().isValid():
        assert info.birthTime().toString("yyyy-MM-dd HH:mm:ss") in tooltip
    assert str(file).replace("\\", "/") in tooltip.replace("\\", "/")


@pytest.mark.parametrize("ascending", [True, False])
def test_type_sort_and_folders_first_toggle(make_tree, tmp_path, ascending):
    for name in ("b.PNG", "c.jpg", "a.png"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "z-folder").mkdir()
    tree = make_tree(tmp_path)
    wait_for(lambda: len(names(tree)) == 4)
    tree.set_tree_sort("type", ascending)
    assert names(tree) == (["z-folder", "c.jpg", "a.png", "b.PNG"] if ascending else
                           ["z-folder", "b.PNG", "a.png", "c.jpg"])
    tree.set_folders_first(False)
    assert names(tree) == (["z-folder", "c.jpg", "a.png", "b.PNG"] if ascending else
                           ["b.PNG", "a.png", "c.jpg", "z-folder"])


def test_folder_override_inherits_resets_and_survives_new_tree(make_tree, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    tree = make_tree(a)
    tree.set_tree_sort("name", True)
    tree.set_folder_sort_override(True)
    tree.set_tree_sort("modified", False)
    tree.set_folders_first(False)
    tree.set_root_path(str(b))
    assert tree._sort_settings.key == "name"
    assert tree._sort_settings.ascending
    tree.set_tree_sort("size", False)
    tree.set_root_path(str(a))
    assert tree._sort_settings.key == "modified"
    assert not tree._sort_settings.folders_first
    restarted = make_tree(a)
    assert restarted._sort_settings == tree._sort_settings
    restarted.set_folder_sort_override(False)
    assert restarted._sort_settings.key == "size"
    assert root_key(str(a)) not in settings.user_setting_dict["tree_folder_sort_overrides"]


def test_options_menu_changes_folders_first(make_tree, tmp_path):
    tree = make_tree(tmp_path)
    controls = tree.create_sort_controls()
    menu = QMenu()
    tree._populate_sort_options(menu)
    menu.actions()[0].trigger()
    assert not tree._sort_settings.folders_first
    assert settings.user_setting_dict["tree_sort_folders_first"] is False
    controls.deleteLater()


def test_recursive_search_finds_unloaded_descendant_and_locates(make_tree, tmp_path):
    folder = tmp_path / "nested" / "deeper"
    folder.mkdir(parents=True)
    target = folder / "Needle.png"
    target.write_bytes(b"x")
    (folder / "Needle.txt").write_text("not an image")
    tree = make_tree(tmp_path)
    panel = tree.create_search_controls()
    search = tree._recursive_search
    tree.set_search_text("needle")
    assert search.worker is None
    search.include.setChecked(True)
    wait_for(lambda: search.results.count() == 1 and search.worker is None)
    assert search.results.item(0).text() == str(Path("nested/deeper/Needle.png"))
    search.results.setCurrentRow(0)
    search.locate_button.click()
    wait_for(lambda: not search._locate_path)
    assert Path(tree.model().filePath(tree.currentIndex())) == target
    assert tree.isExpanded(tree.model().index(str(folder)))
    panel.deleteLater()


def test_cancel_and_new_query_ignore_old_batches(make_tree, tmp_path):
    (tmp_path / "old.png").write_bytes(b"x")
    (tmp_path / "new.png").write_bytes(b"x")
    tree = make_tree(tmp_path)
    panel = tree.create_search_controls()
    search = tree._recursive_search
    search.include.setChecked(True)
    tree.set_search_text("old")
    old_generation = search.generation
    search.cancel()
    tree.set_search_text("new")
    search._accept_batch(old_generation, [str(tmp_path / "old.png")])
    wait_for(lambda: search.results.count() == 1 and search.worker is None)
    assert search.results.item(0).text() == "new.png"
    panel.deleteLater()


def test_scan_cancel_and_missing_directory(tmp_path):
    cancelled = Event()
    cancelled.set()
    batches = []
    assert scan_matches(str(tmp_path), "", cancelled, batches.append) == 0
    assert not batches
    cancelled.clear()
    assert scan_matches(str(tmp_path / "gone"), "", cancelled, batches.append) == 1


def test_scan_does_not_follow_symlink_cycle(tmp_path):
    (tmp_path / "photo.png").write_bytes(b"x")
    try:
        os.symlink(tmp_path, tmp_path / "loop", target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is not permitted")
    batches = []
    scan_matches(str(tmp_path), "photo", Event(), batches.extend)
    assert batches == [str(tmp_path / "photo.png")]


def test_refresh_and_restart_restore_expansion_multiselection_and_scroll(make_tree, tmp_path):
    nested = tmp_path / "nested" / "deep"
    nested.mkdir(parents=True)
    for i in range(50):
        (nested / f"img{i:02}.png").write_bytes(b"x")
    tree = make_tree(tmp_path)
    model = tree.model()
    tree.expand(model.index(str(nested.parent)))
    tree.expand(model.index(str(nested)))
    wait_for(lambda: model.rowCount(model.index(str(nested))) == 50)
    paths = [nested / "img30.png", nested / "img31.png"]
    tree.setCurrentIndex(model.index(str(paths[0])))
    tree.selectionModel().select(model.index(str(paths[1])),
                                QItemSelectionModel.SelectionFlag.Select
                                | QItemSelectionModel.SelectionFlag.Rows)
    tree.scrollTo(model.index(str(paths[0])))
    QTest.qWait(50)
    top = model.filePath(tree.indexAt(QPoint(1, 1)))
    tree.refresh()
    wait_for(lambda: tree._tree_state.pending is None)
    assert {Path(p) for p in tree._selected_paths()} == set(paths)
    assert tree.isExpanded(model.index(str(nested)))
    assert model.filePath(tree.indexAt(QPoint(1, 1))) == top
    tree._tree_state.save()
    restarted = make_tree(tmp_path)
    wait_for(lambda: restarted._tree_state.pending is None)
    assert {Path(p) for p in restarted._selected_paths()} == set(paths)
    assert restarted.isExpanded(restarted.model().index(str(nested)))
    assert restarted.model().filePath(restarted.indexAt(QPoint(1, 1))) == top


def test_restore_skips_deleted_expanded_folder(make_tree, tmp_path):
    removed = tmp_path / "gone"
    removed.mkdir()
    tree = make_tree(tmp_path)
    tree.expand(tree.model().index(str(removed)))
    tree._tree_state.save()
    removed.rmdir()
    tree.refresh()
    wait_for(lambda: tree._tree_state.pending is None)


def test_context_folder_jump_preserves_previous_selection(make_tree, tmp_path):
    from Imervue.menu.right_click_menu import jump_to_folder
    destination = tmp_path / "destination"
    destination.mkdir()
    files = [tmp_path / "one.png", tmp_path / "two.png"]
    for file in files:
        file.write_bytes(b"x")
    tree = make_tree(tmp_path)
    wait_for(lambda: len(names(tree)) == 3)
    tree.setCurrentIndex(tree.model().index(str(files[0])))
    tree.selectionModel().select(tree.model().index(str(files[1])),
                                QItemSelectionModel.SelectionFlag.Select
                                | QItemSelectionModel.SelectionFlag.Rows)
    gui = SimpleNamespace(main_window=SimpleNamespace(model=tree.model(), tree=tree))
    jump_to_folder(gui, destination)
    tree.set_root_path(str(tmp_path))
    wait_for(lambda: tree._tree_state.pending is None)
    assert {Path(p) for p in tree._selected_paths()} == set(files)


def test_scan_excludes_hidden_and_pending_deleted_folders(tmp_path):
    for folder in ("visible", ".hidden", "deleted"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "photo.png").write_bytes(b"x")
    matches = []
    scan_matches(str(tmp_path), "photo", Event(), matches.extend,
                 excluded=frozenset({os.path.normcase(str(tmp_path / "deleted"))}))
    assert matches == [str(tmp_path / "visible" / "photo.png")]


def test_existing_results_are_removed_when_folder_is_soft_deleted(make_tree, tmp_path):
    folder = tmp_path / "deleted"
    folder.mkdir()
    photo = folder / "photo.png"
    photo.write_bytes(b"x")
    tree = make_tree(tmp_path)
    panel = tree.create_search_controls()
    search = tree._recursive_search
    search._accept_batch(search.generation, [str(photo)])
    assert search.results.count() == 1
    tree._hidden_paths = {str(folder)}
    search.exclude_hidden()
    assert search.results.count() == 0
    search.locate(str(photo))
    assert not search._locate_path
    panel.deleteLater()


def test_missing_birth_time_is_not_presented_as_creation_time(make_tree, tmp_path, monkeypatch):
    from PySide6.QtCore import QDateTime
    file = tmp_path / "photo.png"
    file.write_bytes(b"x")
    tree = make_tree(tmp_path)
    source = tree.model().sourceModel()
    original = source.fileInfo
    monkeypatch.setattr(source, "fileInfo", lambda index: SimpleNamespace(
        filePath=original(index).filePath, birthTime=QDateTime,
        lastModified=original(index).lastModified, size=original(index).size, isDir=lambda: False))
    tooltip = tree.model().index(str(file)).data(Qt.ItemDataRole.ToolTipRole)
    assert "Created: Unavailable" in tooltip


def test_restore_waits_for_delayed_root_loaded_signal(make_tree, tmp_path):
    from PySide6.QtCore import QTimer
    file = tmp_path / "photo.png"
    file.write_bytes(b"x")
    tree = make_tree(tmp_path)
    wait_for(lambda: root_key(str(tmp_path)) in tree._tree_state._loaded)
    tree.setCurrentIndex(tree.model().index(str(file)))
    tree._tree_state.save()
    state = tree._tree_state
    tree.model().directoryLoaded.disconnect(state._directory_loaded)
    tree.refresh()
    QTest.qWait(150)
    assert state.pending is not None
    QTimer.singleShot(50, lambda: state._directory_loaded(str(tmp_path)))
    wait_for(lambda: state.pending is None)
    assert tree._selected_paths() == [tree.model().filePath(tree.model().index(str(file)))]


def test_shutdown_cancels_scan_without_waiting_for_blocked_io(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from Imervue.gui import file_tree_search as module
    started, release = Event(), Event()

    def blocking_scan(_root, _query, cancelled, _emit, **_kwargs):
        started.set()
        release.wait(3)
        assert cancelled.is_set()
        return 0

    monkeypatch.setattr(module, "scan_matches", blocking_scan)
    monkeypatch.setattr(settings, "schedule_save", lambda: None)
    tree = _FileTreeView(SimpleNamespace())
    tree.setModel(FileTreeSortProxy(QFileSystemModel()))
    tree.set_root_path(str(tmp_path))
    panel = tree.create_search_controls()
    search = tree._recursive_search
    search.include.setChecked(True)
    tree.set_search_text("photo")
    search.start()
    worker = search.worker
    try:
        wait_for(started.is_set)
        tree.shutdown()
        assert worker.isRunning()
        assert worker.cancelled.is_set()
        panel.deleteLater()
        tree.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    finally:
        release.set()
        wait_for(lambda: worker not in module._running_scans)
