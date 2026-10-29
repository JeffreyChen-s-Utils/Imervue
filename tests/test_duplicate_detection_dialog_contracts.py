"""Contract tests for the duplicate-detection dialog, its scan worker and clustering.

Pins what the existing tests leave open: group ordering, the worker's progress /
error signals and abort paths, the dialog's scan start / result / finish states,
size formatting, the delete flow's pending and failure states, and the names the
dialog module keeps re-exporting. Plain QDialog (no QOpenGLWidget) → no CI skip.
"""
from __future__ import annotations

import logging
import os
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import Qt

from Imervue.gui import duplicate_detection_dialog as mod
from Imervue.gui.duplicate_detection_dialog import DuplicateDetectionDialog, _ScanWorker

_LOGGER_NAME = "Imervue.duplicate_detection"


def _png(path, color, size=(16, 16)):
    Image.new("RGB", size, color).save(path)
    return str(path)


def _dialog(folder=None):
    return DuplicateDetectionDialog(SimpleNamespace(main_window=None), folder)


@pytest.fixture
def english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def dlg(qapp, english):
    dialog = _dialog()
    yield dialog
    dialog.deleteLater()


def _answer(monkeypatch, *, yes):
    """Auto-answer the delete confirmation; returns the (title, question) pairs asked."""
    from PySide6.QtWidgets import QMessageBox
    asked = []
    button = QMessageBox.StandardButton.Yes if yes else QMessageBox.StandardButton.No

    def question(_parent, title, text, *_a, **_k):
        asked.append((title, text))
        return button

    monkeypatch.setattr(QMessageBox, "question", question)
    return asked


def _children(dialog, gi=0):
    group = dialog._tree.topLevelItem(gi)
    return [group.child(ci) for ci in range(group.childCount())]


def _child_paths(dialog, gi=0):
    return [c.data(0, Qt.ItemDataRole.UserRole) for c in _children(dialog, gi)]


# ---------------------------------------------------------------------------
# Re-exports
# ---------------------------------------------------------------------------

def test_dialog_module_keeps_its_public_names():
    for name in ("DuplicateDetectionDialog", "open_duplicate_detection", "_ScanWorker",
                 "_make_thumbnail", "_dhash", "_hamming_distance", "language_wrapper",
                 "_IMAGE_EXTS", "_METHOD_EXACT", "_flatten_hash_map", "_build_clusters"):
        assert hasattr(mod, name), name
    assert mod._METHOD_EXACT == "exact"
    assert {".png", ".jpg", ".gif", ".tif"} <= mod._IMAGE_EXTS


# ---------------------------------------------------------------------------
# Clustering helpers (Qt-free)
# ---------------------------------------------------------------------------

def test_flatten_keeps_key_then_item_order():
    flat = mod._flatten_hash_map({"7": [("a", 1), ("b", 2)], "3": [("c", 3)]})
    assert flat == [(7, "a", 1), (7, "b", 2), (3, "c", 3)]


def test_build_clusters_drops_singletons_and_keeps_scan_order():
    entries = [(0, "a", 1), (0, "b", 2), (0, "c", 3), (0, "d", 4)]
    parent = [0, 1, 2, 3]
    mod._union(parent, 0, 2)
    mod._union(parent, 1, 3)
    assert mod._build_clusters(entries, parent) == [[("a", 1), ("c", 3)], [("b", 2), ("d", 4)]]
    assert mod._build_clusters(entries, [0, 1, 2, 3]) == []
    assert mod._build_clusters([], []) == []


def test_find_root_compresses_the_path():
    parent = [0, 0, 1, 2]
    assert mod._find_root(parent, 3) == 0
    assert parent[3] in (0, 1)  # halved on the way up
    mod._union(parent, 3, 3)  # same root → unchanged
    assert mod._find_root(parent, 3) == 0


# ---------------------------------------------------------------------------
# Scan worker
# ---------------------------------------------------------------------------

def test_exact_groups_follow_first_seen_order(tmp_path):
    red = (200, 10, 10)
    blue = (10, 10, 200)
    _png(tmp_path / "a.png", blue)
    _png(tmp_path / "b.png", red)
    _png(tmp_path / "c.png", blue)
    _png(tmp_path / "d.png", red)
    _png(tmp_path / "e.png", (1, 2, 3))
    worker = _ScanWorker(str(tmp_path), "exact", 5, recursive=False)
    progress, results = [], []
    worker.progress.connect(lambda *a: progress.append(a))
    worker.result_ready.connect(results.append)
    worker.run()
    names = [[os.path.basename(p) for p, _s in g] for g in results[0]]
    assert names == [["a.png", "c.png"], ["b.png", "d.png"]]
    assert progress == [(i + 1, 5, n) for i, n in enumerate(
        ["a.png", "b.png", "c.png", "d.png", "e.png"])]
    sizes = {s for g in results[0] for _p, s in g}
    assert all(isinstance(s, int) and s > 0 for s in sizes)


def test_unreadable_file_is_skipped_by_the_perceptual_scan(tmp_path):
    _png(tmp_path / "a.png", (9, 9, 9))
    _png(tmp_path / "b.png", (9, 9, 9))
    (tmp_path / "c.png").write_bytes(b"not a png")
    worker = _ScanWorker(str(tmp_path), "perceptual", 0, recursive=False)
    results = []
    worker.result_ready.connect(results.append)
    worker.run()
    assert [sorted(os.path.basename(p) for p, _s in g) for g in results[0]] == [
        ["a.png", "b.png"]]


def test_unexpected_error_emits_error_and_logs(tmp_path, monkeypatch):
    _png(tmp_path / "a.png", (9, 9, 9))
    worker = _ScanWorker(str(tmp_path), "exact", 5, recursive=False)
    monkeypatch.setattr(_ScanWorker, "_file_hash", staticmethod(
        lambda _p: (_ for _ in ()).throw(RuntimeError("kaput"))))
    logged = []
    monkeypatch.setattr(logging.getLogger(_LOGGER_NAME), "exception",
                        lambda msg, *a, **k: logged.append(msg))
    errors, results = [], []
    worker.error.connect(errors.append)
    worker.result_ready.connect(results.append)
    worker.run()
    assert errors == ["kaput"] and results == []
    assert logged == ["Duplicate scan failed"]


def test_abort_during_hashing_emits_nothing(tmp_path, monkeypatch):
    for name in ("a.png", "b.png", "c.png"):
        _png(tmp_path / name, (9, 9, 9))
    worker = _ScanWorker(str(tmp_path), "exact", 5, recursive=False)
    real = _ScanWorker._file_hash

    def hash_then_abort(path):
        worker.abort()
        return real(path)

    monkeypatch.setattr(_ScanWorker, "_file_hash", staticmethod(hash_then_abort))
    progress, results = [], []
    worker.progress.connect(lambda *a: progress.append(a))
    worker.result_ready.connect(results.append)
    worker.run()
    assert results == [] and len(progress) == 1


def test_abort_during_clustering_returns_no_groups():
    worker = _ScanWorker("", "perceptual", 64, recursive=False)
    worker.abort()
    assert worker._cluster_perceptual({"1": [("a", 1)], "2": [("b", 2)]}) == []


def test_perceptual_threshold_is_inclusive():
    worker = _ScanWorker("", "perceptual", 2, recursive=False)
    groups = worker._cluster_perceptual({"0": [("a", 1)], "3": [("b", 2)], "7": [("c", 3)]})
    assert groups == [[("a", 1), ("b", 2), ("c", 3)]]  # 0-3 and 3-7 are 2 bits apart
    worker = _ScanWorker("", "perceptual", 1, recursive=False)
    assert worker._cluster_perceptual({"0": [("a", 1)], "3": [("b", 2)]}) == []


def test_file_hash_is_the_md5_of_the_bytes(tmp_path):
    import hashlib
    path = tmp_path / "x.bin"
    path.write_bytes(b"x" * 20000)
    assert _ScanWorker._file_hash(str(path)) == hashlib.md5(
        b"x" * 20000, usedforsecurity=False).hexdigest()


# ---------------------------------------------------------------------------
# Dialog: scan lifecycle
# ---------------------------------------------------------------------------

def test_initial_folder_is_used_only_when_it_exists(qapp, english, tmp_path):
    good = _dialog(str(tmp_path))
    bad = _dialog(str(tmp_path / "missing"))
    try:
        assert good._folder_edit.text() == str(tmp_path)
        assert bad._folder_edit.text() == ""
        assert good.windowTitle() == "Find Duplicate Images"
        assert good._worker is None and good._delete_worker is None
    finally:
        good.deleteLater()
        bad.deleteLater()


def test_start_scan_ignores_a_missing_folder(dlg, tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(_ScanWorker, "start", lambda self: started.append(self))
    dlg._start_scan()
    dlg._folder_edit.setText(str(tmp_path / "missing"))
    dlg._start_scan()
    assert started == [] and dlg._worker is None and dlg._scan_btn.isEnabled()


def test_start_scan_configures_the_worker_and_finish_restores(dlg, tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(_ScanWorker, "start", lambda self: started.append(self))
    dlg._on_result([[(_png(tmp_path / "a.png", (1, 1, 1)), 10),
                     (_png(tmp_path / "b.png", (1, 1, 1)), 10)]])
    dlg._folder_edit.setText(f"  {tmp_path}  ")
    dlg._method_combo.setCurrentIndex(1)
    dlg._threshold_spin.setValue(9)
    dlg._recursive_check.setChecked(True)
    dlg._start_scan()
    worker = dlg._worker
    assert started == [worker]
    assert (worker._folder, worker._method, worker._threshold, worker._recursive) == (
        str(tmp_path), "perceptual", 9, True)
    assert dlg._tree.topLevelItemCount() == 0 and dlg._groups == []
    assert not any(b.isEnabled() for b in (dlg._scan_btn, dlg._delete_btn,
                                           dlg._select_redundant_btn))
    assert not dlg._progress.isHidden() and dlg._progress.value() == 0
    dlg._on_progress(3, 7, "pic.png")
    assert (dlg._progress.value(), dlg._progress.maximum()) == (3, 7)
    assert dlg._status_label.text() == "Scanning: pic.png"
    dlg._on_finished()
    assert dlg._progress.isHidden() and dlg._scan_btn.isEnabled() and dlg._worker is None


def test_result_tree_rows(dlg, tmp_path):
    a = _png(tmp_path / "a.png", (1, 1, 1))
    b = _png(tmp_path / "b.png", (1, 1, 1))
    c = str(tmp_path / "gone.png")
    dlg._on_result([[(a, 512), (b, 2048)], [(a, 1), (c, 3 * 1024 * 1024)]])
    assert dlg._status_label.text() == "2 group(s) of duplicates found"
    assert dlg._tree.topLevelItemCount() == 2
    group = dlg._tree.topLevelItem(1)
    assert group.text(1) == "Group 2 (2 images)" and group.isExpanded()
    assert not group.flags() & Qt.ItemFlag.ItemIsSelectable
    rows = [(ch.text(1), ch.text(2), ch.text(3)) for ch in _children(dlg, 0)]
    assert rows == [("a.png", a, "512 B"), ("b.png", b, "2.0 KB")]
    gone = _children(dlg, 1)[1]
    assert gone.icon(0).isNull() and gone.text(3) == "3.0 MB"
    assert not _children(dlg, 0)[0].icon(0).isNull()
    assert dlg._delete_btn.isEnabled() and dlg._select_redundant_btn.isEnabled()


def test_empty_result_and_error(dlg):
    dlg._on_result([])
    assert dlg._status_label.text() == "No duplicates found."
    assert not dlg._delete_btn.isEnabled() and not dlg._select_redundant_btn.isEnabled()
    dlg._on_error("disk on fire")
    assert dlg._status_label.text() == "Error: disk on fire"


@pytest.mark.parametrize(("size", "text"), [
    (0, "0 B"), (1023, "1023 B"), (1024, "1.0 KB"), (1024 * 1024 - 1, "1024.0 KB"),
    (1024 * 1024, "1.0 MB"), (5 * 1024 * 1024 * 1024, "5120.0 MB"),
])
def test_format_size_boundaries(size, text):
    assert DuplicateDetectionDialog._format_size(size) == text


def test_open_duplicate_detection_passes_the_browsed_folder(monkeypatch):
    seen = []

    class FakeDialog:
        def __init__(self, gui, folder):
            seen.append((gui, folder))

        def exec(self):
            seen.append("exec")

    monkeypatch.setattr(mod, "DuplicateDetectionDialog", FakeDialog)
    with_model = SimpleNamespace(model=SimpleNamespace(folder_path="/pics"))
    mod.open_duplicate_detection(with_model)
    bare = SimpleNamespace()
    mod.open_duplicate_detection(bare)
    assert seen == [(with_model, "/pics"), "exec", (bare, None), "exec"]


# ---------------------------------------------------------------------------
# Dialog: selection and delete flow
# ---------------------------------------------------------------------------

def test_select_redundant_replaces_the_selection_and_reports_count(dlg, tmp_path):
    small = _png(tmp_path / "s.png", (1, 1, 1), (10, 10))
    big = _png(tmp_path / "b.png", (1, 1, 1), (20, 20))
    dlg._on_result([[(small, 5), (big, 5)]])
    _children(dlg)[1].setSelected(True)
    dlg._select_redundant()
    assert {i.data(0, Qt.ItemDataRole.UserRole) for i in dlg._tree.selectedItems()} == {small}
    assert dlg._status_label.text() == (
        "1 redundant file(s) selected — review, then Delete Selected")
    assert dlg._select_paths({"nowhere"}) == 0
    assert DuplicateDetectionDialog._probe_dims(str(tmp_path / "none.png")) == (0, 0)
    assert DuplicateDetectionDialog._probe_dims(big) == (20, 20)


def test_delete_skips_missing_files_without_asking(dlg, tmp_path, monkeypatch):
    asked = _answer(monkeypatch, yes=True)
    a = _png(tmp_path / "a.png", (1, 1, 1))
    gone = str(tmp_path / "gone.png")
    dlg._on_result([[(a, 1), (gone, 1)]])
    _children(dlg)[1].setSelected(True)
    dlg._delete_selected()
    assert asked == [] and dlg._delete_worker is None


def test_delete_in_flight_disables_buttons_and_tracks_items(dlg, tmp_path, monkeypatch):
    from _instant_worker import DeferredDeleteWorker, InstantDeleteWorker

    from Imervue.system import trash_ops

    InstantDeleteWorker.created = []
    monkeypatch.setattr(trash_ops, "FileDeleteWorker", DeferredDeleteWorker)
    questions = _answer(monkeypatch, yes=True)
    a = _png(tmp_path / "a.png", (1, 1, 1))
    b = _png(tmp_path / "b.png", (2, 1, 1))
    c = _png(tmp_path / "c.png", (3, 1, 1))
    dlg._on_result([[(a, 1), (b, 1), (c, 1)]])
    for child in _children(dlg)[1:]:
        child.setSelected(True)
    dlg._delete_selected()
    assert questions == [("Confirm Delete", "Move 2 file(s) to trash?")]
    worker = InstantDeleteWorker.created[0]
    assert sorted(worker.paths) == sorted([b, c]) and dlg._delete_worker is worker
    assert sorted(dlg._pending_delete_items) == sorted([b, c])
    assert not any(x.isEnabled() for x in (dlg._scan_btn, dlg._delete_btn,
                                           dlg._select_redundant_btn))
    worker.finish()
    assert _child_paths(dlg) == [a]
    assert dlg._status_label.text() == "2 file(s) deleted"


def test_failed_delete_is_kept_logged_and_not_counted(dlg, tmp_path, monkeypatch):
    from _instant_worker import FailingDeleteWorker

    from Imervue.system import trash_ops

    monkeypatch.setattr(trash_ops, "FileDeleteWorker", FailingDeleteWorker)
    _answer(monkeypatch, yes=True)
    warned = []
    monkeypatch.setattr(logging.getLogger(_LOGGER_NAME), "warning",
                        lambda msg, *a, **k: warned.append(msg % a))
    a = _png(tmp_path / "a.png", (1, 1, 1))
    b = _png(tmp_path / "b.png", (2, 1, 1))
    dlg._on_result([[(a, 1), (b, 1)]])
    _children(dlg)[1].setSelected(True)
    dlg._delete_selected()
    assert _child_paths(dlg) == [a, b]
    assert warned == [f"Failed to delete {b}"]
    assert dlg._status_label.text() == "0 file(s) deleted"
    assert dlg._pending_delete_items == {} and dlg._delete_worker is None
    assert all(x.isEnabled() for x in (dlg._scan_btn, dlg._delete_btn,
                                       dlg._select_redundant_btn))


def test_delete_finished_ignores_unknown_and_parentless_items(dlg):
    orphan = SimpleNamespace(parent=lambda: None)
    dlg._pending_delete_items = {"orphan": orphan}
    dlg._on_delete_finished(["orphan", "stranger"], [])
    assert dlg._status_label.text() == "2 file(s) deleted"
    assert dlg._pending_delete_items == {}

