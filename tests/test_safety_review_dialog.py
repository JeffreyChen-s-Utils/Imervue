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
        mode="real", conf=0.25, expand=0, style="mosaic", categories=None,
        shape="ellipse")
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
        mode="real", conf=0.25, expand=0, style="mosaic", categories=None,
        shape="ellipse")
    assert worker._source_root is None
    dlg.deleteLater()


def test_only_censored_checkbox_hidden_until_output_mode(qapp, tmp_path):
    dlg = _dialog(qapp)
    # isVisibleTo(dlg) reflects the local hidden flag without needing the
    # dialog to be shown (isVisible() would be False for an unshown dialog).
    # Overwrite is the default → the separate-output options stay hidden.
    assert dlg._only_censored_check.isVisibleTo(dlg) is False
    dlg._overwrite_check.setChecked(False)  # fires _on_overwrite_toggled
    assert dlg._only_censored_check.isVisibleTo(dlg) is True
    dlg.deleteLater()


def test_worker_gets_only_censored_flag_for_separate_output(qapp, tmp_path):
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    dlg._overwrite_check.setChecked(False)
    dlg._only_censored_check.setChecked(True)
    worker = dlg._make_worker(
        output_dir=str(tmp_path / "out"), overwrite=False,
        mode="real", conf=0.25, expand=0, style="mosaic", categories=None,
        shape="ellipse")
    assert worker._only_censored is True
    dlg.deleteLater()


def test_only_censored_ignored_when_overwriting(qapp, tmp_path):
    # Even if the box was left checked, overwrite mode must not carry the flag.
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    dlg._only_censored_check.setChecked(True)
    worker = dlg._make_worker(
        output_dir=None, overwrite=True,
        mode="real", conf=0.25, expand=0, style="mosaic", categories=None,
        shape="ellipse")
    assert worker._only_censored is False
    dlg.deleteLater()


def test_shape_combo_defaults_to_ellipse(qapp, tmp_path):
    # Ellipse is the default so censoring hugs the region out of the box.
    from safety_review._constants import SHAPE_ELLIPSE
    dlg = _dialog(qapp)
    assert dlg._shape_combo.currentData() == SHAPE_ELLIPSE
    dlg.deleteLater()


def test_shape_combo_offers_precise(qapp, tmp_path):
    from safety_review._constants import SHAPE_PRECISE
    dlg = _dialog(qapp)
    values = [dlg._shape_combo.itemData(i)
              for i in range(dlg._shape_combo.count())]
    assert SHAPE_PRECISE in values
    dlg.deleteLater()


def test_worker_gets_selected_shape(qapp, tmp_path):
    from safety_review._constants import SHAPE_PRECISE
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    idx = dlg._shape_combo.findData(SHAPE_PRECISE)
    dlg._shape_combo.setCurrentIndex(idx)
    worker = dlg._make_worker(
        output_dir=str(tmp_path / "out"), overwrite=False,
        mode="real", conf=0.25, expand=0, style="mosaic", categories=None,
        shape=dlg._shape_combo.currentData())
    assert worker._shape == SHAPE_PRECISE
    dlg.deleteLater()


def test_failed_folder_is_a_sibling_of_the_scan_folder(qapp, tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(folder))
    assert dlg._failed_folder() == str(tmp_path / "photos_censor_failed")
    dlg.deleteLater()


def test_worker_gets_failed_dir_and_scan_root(qapp, tmp_path):
    _tree(tmp_path)
    dlg = _dialog(qapp)
    dlg._folder_edit.setText(str(tmp_path))
    worker = dlg._make_worker(
        output_dir=str(tmp_path / "out"), overwrite=False,
        mode="real", conf=0.25, expand=0, style="mosaic", categories=None,
        shape="ellipse")
    assert worker._scan_root == str(tmp_path)
    assert worker._failed_dir == str(tmp_path.parent / f"{tmp_path.name}_censor_failed")
    dlg.deleteLater()


def test_no_failed_folder_without_a_scan_folder(qapp, tmp_path):
    dlg = _dialog(qapp)  # folder edit left blank
    assert dlg._failed_folder() is None
    dlg.deleteLater()
