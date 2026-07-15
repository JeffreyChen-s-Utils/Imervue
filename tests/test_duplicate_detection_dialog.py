"""Qt smoke test for the duplicate-detection 'Select Redundant' wizard action.

Plain QDialog (no QOpenGLWidget) → no headless-CI skip. The ranking itself is
covered in test_dedupe_resolver; this checks the dialog probes real dimensions
and selects the redundant rows (keeping the best) for the user to review.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt

from Imervue.gui.duplicate_detection_dialog import DuplicateDetectionDialog


def _dialog():
    # The dialog parents itself to viewer.main_window; None makes it top-level.
    return DuplicateDetectionDialog(SimpleNamespace(main_window=None))


def _png(path, w, h, color=(120, 50, 200)):
    Image.new("RGB", (w, h), color).save(path)
    return str(path)


def _entry(path):
    return path, os.path.getsize(path)


def _selected_paths(dlg):
    return {it.data(0, Qt.ItemDataRole.UserRole) for it in dlg._tree.selectedItems()}


def test_select_redundant_keeps_highest_resolution(qapp, tmp_path):
    small = _png(tmp_path / "small.png", 100, 100)
    big = _png(tmp_path / "big.png", 200, 200)
    dlg = _dialog()
    dlg._on_result([[_entry(small), _entry(big)]])
    dlg._select_redundant()
    assert _selected_paths(dlg) == {small}


def test_select_redundant_equal_res_keeps_larger_file(qapp, tmp_path):
    # Same dimensions; the noisy image compresses to a larger file → it's kept.
    lean = _png(tmp_path / "lean.png", 200, 200, color=(0, 0, 0))
    rich = str(tmp_path / "rich.png")
    noise = np.random.default_rng(0).integers(0, 256, (200, 200, 3), dtype=np.uint8)
    Image.fromarray(noise).save(rich)
    dlg = _dialog()
    dlg._on_result([[_entry(lean), _entry(rich)]])
    dlg._select_redundant()
    assert _selected_paths(dlg) == {lean}


def test_select_redundant_across_multiple_groups(qapp, tmp_path):
    g1_small = _png(tmp_path / "g1s.png", 100, 100)
    g1_big = _png(tmp_path / "g1b.png", 300, 300)
    g2_small = _png(tmp_path / "g2s.png", 50, 50)
    g2_big = _png(tmp_path / "g2b.png", 80, 80)
    dlg = _dialog()
    dlg._on_result([
        [_entry(g1_small), _entry(g1_big)],
        [_entry(g2_small), _entry(g2_big)],
    ])
    dlg._select_redundant()
    assert _selected_paths(dlg) == {g1_small, g2_small}


def _select_path(dlg, path):
    for gi in range(dlg._tree.topLevelItemCount()):
        group = dlg._tree.topLevelItem(gi)
        for ci in range(group.childCount()):
            child = group.child(ci)
            if child.data(0, Qt.ItemDataRole.UserRole) == path:
                child.setSelected(True)


def test_delete_selected_runs_on_a_worker_and_prunes_the_tree(qapp, tmp_path, monkeypatch):
    """The trash calls must run off the GUI thread; the tree updates on finish."""
    from _instant_worker import InstantDeleteWorker
    from PySide6.QtWidgets import QMessageBox

    from Imervue.system import trash_ops

    InstantDeleteWorker.created = []
    monkeypatch.setattr(trash_ops, "FileDeleteWorker", InstantDeleteWorker)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes)

    keep = _png(tmp_path / "keep.png", 50, 50)
    drop = _png(tmp_path / "drop.png", 50, 50)
    dlg = _dialog()
    dlg._on_result([[_entry(keep), _entry(drop)]])
    _select_path(dlg, drop)

    dlg._delete_selected()

    assert len(InstantDeleteWorker.created) == 1
    assert InstantDeleteWorker.created[0].paths == [drop]
    remaining = {
        dlg._tree.topLevelItem(0).child(ci).data(0, Qt.ItemDataRole.UserRole)
        for ci in range(dlg._tree.topLevelItem(0).childCount())
    }
    assert remaining == {keep}
    assert dlg._delete_btn.isEnabled() is True
    assert dlg._delete_worker is None
    assert "1" in dlg._status_label.text()


def test_delete_selected_declined_confirm_spawns_nothing(qapp, tmp_path, monkeypatch):
    from _instant_worker import InstantDeleteWorker
    from PySide6.QtWidgets import QMessageBox

    from Imervue.system import trash_ops

    InstantDeleteWorker.created = []
    monkeypatch.setattr(trash_ops, "FileDeleteWorker", InstantDeleteWorker)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.No)

    target = _png(tmp_path / "t.png", 50, 50)
    other = _png(tmp_path / "o.png", 50, 50)
    dlg = _dialog()
    dlg._on_result([[_entry(target), _entry(other)]])
    _select_path(dlg, target)

    dlg._delete_selected()
    assert InstantDeleteWorker.created == []


def test_delete_reenables_scan_after_finishing(qapp, tmp_path, monkeypatch):
    """Scan is disabled for the delete's duration and re-enabled on finish, so a
    scan can't clear the tree out from under the in-flight delete worker."""
    from _instant_worker import InstantDeleteWorker
    from PySide6.QtWidgets import QMessageBox

    from Imervue.system import trash_ops

    InstantDeleteWorker.created = []
    monkeypatch.setattr(trash_ops, "FileDeleteWorker", InstantDeleteWorker)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes)

    keep = _png(tmp_path / "keep.png", 50, 50)
    drop = _png(tmp_path / "drop.png", 50, 50)
    dlg = _dialog()
    dlg._on_result([[_entry(keep), _entry(drop)]])
    _select_path(dlg, drop)
    dlg._delete_selected()
    # The instant worker finished synchronously → Scan is back on.
    assert dlg._scan_btn.isEnabled() is True


class _DeadItem:
    def parent(self):
        raise RuntimeError("Internal C++ object already deleted")


def test_on_delete_finished_survives_a_deleted_item():
    enabled: dict = {}

    def _btn(name):
        return SimpleNamespace(setEnabled=lambda v: enabled.__setitem__(name, v))

    fake = SimpleNamespace(
        _pending_delete_items={"a.png": _DeadItem()},
        _delete_worker=None,
        _delete_btn=_btn("delete"),
        _scan_btn=_btn("scan"),
        _select_redundant_btn=_btn("redundant"),
        _status_label=SimpleNamespace(setText=lambda _t: None),
        _lang={},
    )
    DuplicateDetectionDialog._on_delete_finished(fake, ["a.png"], [])  # no crash
    assert enabled == {"delete": True, "scan": True, "redundant": True}
    assert fake._pending_delete_items == {}
