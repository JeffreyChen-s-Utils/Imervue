"""Qt smoke tests for the safety_review ScanAllDialog subfolder option.

``ScanAllDialog`` is a plain ``QDialog`` (no ``QOpenGLWidget``), so the
headless-CI skip marker is not required. These cover the "include subfolders"
wiring end to end: the checkbox re-scans recursively, remembers the source
root, and threads it into the batch worker only for a separate-output run.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from safety_review._dialogs import ScanAllDialog
from safety_review._workers import _BatchWorker


def _png(path: Path, color=(90, 120, 160)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path, format="PNG")
    return str(path)


def _tree(tmp_path):
    """A folder with one top-level image and one nested image."""
    _png(tmp_path / "top.png")
    _png(tmp_path / "sub" / "deep.png")
    return tmp_path


def _dialog(qapp):
    gui = SimpleNamespace(main_window=None)
    return ScanAllDialog(gui, initial_paths=None, get_frozen_env=None)


def test_recursive_off_scans_only_top_level(qapp, tmp_path):
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    dlg._rescan_current_folder()
    assert {Path(p).name for p in dlg._paths} == {"top.png"}
    assert dlg._source_root is None
    dlg.deleteLater()


def test_recursive_on_scans_whole_tree_and_sets_root(qapp, tmp_path):
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    dlg._recursive_check.setChecked(True)  # fires _on_recursive_toggled
    assert {Path(p).name for p in dlg._paths} == {"top.png", "deep.png"}
    assert dlg._source_root == str(tmp_path)
    assert dlg._start_btn.isEnabled()
    dlg.deleteLater()


def test_toggling_recursive_off_again_drops_root_and_nested(qapp, tmp_path):
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    dlg._recursive_check.setChecked(True)
    dlg._recursive_check.setChecked(False)
    assert {Path(p).name for p in dlg._paths} == {"top.png"}
    assert dlg._source_root is None
    dlg.deleteLater()


def test_worker_gets_source_root_for_separate_output(qapp, tmp_path):
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    dlg._recursive_check.setChecked(True)
    worker = dlg._make_worker(
        output_dir=str(tmp_path / "out"), overwrite=False,
        mode="real", conf=0.25, expand=0, style="mosaic", categories=None)
    assert isinstance(worker, _BatchWorker)
    assert worker._source_root == str(tmp_path)
    dlg.deleteLater()


def test_worker_drops_source_root_when_overwriting(qapp, tmp_path):
    # Overwrite writes each file back in place, so mirroring is irrelevant and
    # the root must not be threaded through (keeps the flat path clean).
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    dlg._recursive_check.setChecked(True)
    worker = dlg._make_worker(
        output_dir=None, overwrite=True,
        mode="real", conf=0.25, expand=0, style="mosaic", categories=None)
    assert worker._source_root is None
    dlg.deleteLater()
