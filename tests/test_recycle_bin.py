"""Tests for the Recycle Bin dialog and its undo-stack manipulation helpers."""
from __future__ import annotations

from Imervue.gui.recycle_bin_dialog import (
    list_pending_entries,
    remove_path_from_action,
)


# ---------------------------------------------------------------------------
# list_pending_entries
# ---------------------------------------------------------------------------


def test_list_pending_entries_empty():
    assert list_pending_entries([]) == []


def test_list_pending_entries_skips_non_delete():
    stack = [
        {"mode": "rotate", "deleted_paths": ["/a"]},
        {"mode": "delete", "deleted_paths": ["/b"], "indices": [3], "restored": False},
    ]
    entries = list_pending_entries(stack)
    assert len(entries) == 1
    assert entries[0]["path"] == "/b"
    assert entries[0]["original_index"] == 3


def test_list_pending_entries_skips_restored():
    stack = [
        {"mode": "delete", "deleted_paths": ["/a"], "indices": [0], "restored": True},
        {"mode": "delete", "deleted_paths": ["/b"], "indices": [1], "restored": False},
    ]
    entries = list_pending_entries(stack)
    assert [e["path"] for e in entries] == ["/b"]


def test_list_pending_entries_explodes_multi_path_action():
    """A bulk-tile delete creates one action holding many paths — flatten them."""
    stack = [{
        "mode": "delete",
        "deleted_paths": ["/a", "/b", "/c"],
        "indices": [0, 1, 2],
        "restored": False,
    }]
    entries = list_pending_entries(stack)
    assert len(entries) == 3
    assert entries[0]["action_idx"] == 0
    assert entries[0]["path_idx"] == 0
    assert entries[2]["path_idx"] == 2
    assert entries[2]["original_index"] == 2


def test_list_pending_entries_handles_misaligned_indices():
    """If the indices array is shorter, fall back to 0 — never raise."""
    stack = [{
        "mode": "delete",
        "deleted_paths": ["/a", "/b"],
        "indices": [5],
        "restored": False,
    }]
    entries = list_pending_entries(stack)
    assert entries[0]["original_index"] == 5
    assert entries[1]["original_index"] == 0


# ---------------------------------------------------------------------------
# remove_path_from_action
# ---------------------------------------------------------------------------


def test_remove_path_returns_path_and_index():
    action = {
        "mode": "delete",
        "deleted_paths": ["/a", "/b", "/c"],
        "indices": [0, 1, 2],
        "restored": False,
    }
    out = remove_path_from_action(action, 1)
    assert out == ("/b", 1)
    assert action["deleted_paths"] == ["/a", "/c"]
    assert action["indices"] == [0, 2]
    assert action.get("restored") is False


def test_remove_path_marks_action_restored_when_emptied():
    action = {
        "mode": "delete",
        "deleted_paths": ["/only"],
        "indices": [0],
        "restored": False,
    }
    remove_path_from_action(action, 0)
    assert action["deleted_paths"] == []
    assert action["restored"] is True


def test_remove_path_out_of_range_returns_none():
    action = {
        "mode": "delete",
        "deleted_paths": ["/a"],
        "indices": [0],
        "restored": False,
    }
    assert remove_path_from_action(action, 5) is None
    # State must be untouched
    assert action["deleted_paths"] == ["/a"]


def test_remove_path_negative_index_returns_none():
    action = {
        "mode": "delete",
        "deleted_paths": ["/a"],
        "indices": [0],
        "restored": False,
    }
    assert remove_path_from_action(action, -1) is None


def test_remove_path_handles_short_indices_array():
    """When indices is shorter than deleted_paths, default to 0 — no IndexError."""
    action = {
        "mode": "delete",
        "deleted_paths": ["/a", "/b"],
        "indices": [],
        "restored": False,
    }
    out = remove_path_from_action(action, 0)
    assert out == ("/a", 0)


# ---------------------------------------------------------------------------
# Dialog smoke test (Qt)
# ---------------------------------------------------------------------------


def test_dialog_lists_pending_entries(qapp, tmp_path):
    from Imervue.gui.recycle_bin_dialog import RecycleBinDialog

    f1 = tmp_path / "alpha.png"
    f2 = tmp_path / "beta.png"
    f1.write_bytes(b"x")
    f2.write_bytes(b"y")

    class FakeViewer:
        def __init__(self):
            self.undo_stack = [{
                "mode": "delete",
                "deleted_paths": [str(f1), str(f2)],
                "indices": [0, 1],
                "restored": False,
            }]
            self.model = type("M", (), {"images": []})()
            self.thumbnail_size = 256
            self._load_generation = 0
            self.thread_pool = type("T", (), {"start": lambda *a, **kw: None})()
            self.add_thumbnail = lambda *a, **kw: None

    dlg = RecycleBinDialog(FakeViewer())
    assert dlg._tree.topLevelItemCount() == 2


def test_dialog_purge_removes_file(qapp, tmp_path, monkeypatch):
    """End-to-end purge: mark for purge, confirm, file must be unlinked."""
    from Imervue.gui.recycle_bin_dialog import RecycleBinDialog
    from PySide6.QtWidgets import QMessageBox

    target = tmp_path / "doomed.png"
    target.write_bytes(b"bytes")

    class FakeViewer:
        def __init__(self):
            self.undo_stack = [{
                "mode": "delete",
                "deleted_paths": [str(target)],
                "indices": [0],
                "restored": False,
            }]
            self.model = type("M", (), {"images": []})()
            self.thumbnail_size = 256
            self._load_generation = 0
            self.thread_pool = type("T", (), {"start": lambda *a, **kw: None})()
            self.add_thumbnail = lambda *a, **kw: None

    viewer = FakeViewer()
    dlg = RecycleBinDialog(viewer)

    # Auto-confirm the warning dialog
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **kw: QMessageBox.StandardButton.Yes,
    )
    dlg._tree.selectAll()
    dlg._purge_selected()

    assert not target.exists()
    # The action should have been emptied → marked restored
    assert viewer.undo_stack[0]["restored"] is True


def test_dialog_restore_reinserts_into_image_list(qapp, tmp_path):
    from Imervue.gui.recycle_bin_dialog import RecycleBinDialog

    p = tmp_path / "alpha.png"
    p.write_bytes(b"x")

    class FakeViewer:
        def __init__(self):
            self.undo_stack = [{
                "mode": "delete",
                "deleted_paths": [str(p)],
                "indices": [2],
                "restored": False,
            }]
            self.model = type("M", (), {"images": ["/x", "/y", "/z"]})()
            self.thumbnail_size = 256
            self._load_generation = 0
            self.thread_pool = type("T", (), {"start": lambda *a, **kw: None})()
            self.add_thumbnail = lambda *a, **kw: None

    viewer = FakeViewer()
    dlg = RecycleBinDialog(viewer)
    dlg._tree.selectAll()
    dlg._restore_selected()

    # Path should be inserted at index 2 of the model images
    assert viewer.model.images[2] == str(p)
    assert viewer.undo_stack[0]["restored"] is True
