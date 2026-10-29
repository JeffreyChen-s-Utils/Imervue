"""Contracts for the Image Organizer paths the other organizer tests leave open.

Pins the planner's fallbacks, the worker's collision naming, the dialog's
Preview / Start / progress flow and the entry point, so the dialog can be split
into planning, worker and UI modules without changing what any of them do.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt

from Imervue.gui import image_organizer_dialog as mod
from Imervue.gui.image_organizer_dialog import (
    RULE_COUNT,
    RULE_DATE,
    RULE_SIZE,
    RULE_TYPE,
    ImageOrganizerDialog,
    _get_size_bucket,
    _OrganizerWorker,
    plan_organization,
)

_MB = 1024 * 1024
_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def dialog(qapp, monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    dlg = ImageOrganizerDialog(SimpleNamespace(main_window=None))
    yield dlg
    dlg.deleteLater()


def _write(path, size: int = 3) -> str:
    path.write_bytes(b"x" * size)
    return str(path)


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def test_an_unknown_rule_puts_everything_in_other(tmp_path):
    paths = [_write(tmp_path / "a.png"), _write(tmp_path / "b.png")]
    assert plan_organization(paths, "nonsense") == {"other": paths}


def test_an_empty_path_list_plans_nothing():
    assert plan_organization([], RULE_TYPE) == {}


def test_count_buckets_are_zero_padded_and_keep_order(tmp_path):
    paths = [_write(tmp_path / f"{i}.png") for i in range(5)]
    plan = plan_organization(paths, RULE_COUNT, count_per_folder=2)
    assert plan == {"001": paths[:2], "002": paths[2:4], "003": paths[4:]}
    assert list(plan) == ["001", "002", "003"]


def test_a_missing_file_has_an_unknown_size(tmp_path):
    assert _get_size_bucket(str(tmp_path / "gone.png"), 5.0, 1.0) == "unknown"


@pytest.mark.parametrize(("size", "bucket"), [
    (2 * _MB, "large"), (2 * _MB - 1, "medium"), (_MB, "medium"), (_MB - 1, "small"),
])
def test_size_thresholds_are_inclusive(tmp_path, size, bucket):
    path = tmp_path / "a.png"
    with open(path, "wb") as fh:
        fh.truncate(size)
    assert _get_size_bucket(str(path), 2.0, 1.0) == bucket


def test_a_type_without_extension_is_other(tmp_path):
    path = _write(tmp_path / "noext")
    assert plan_organization([path], RULE_TYPE) == {"OTHER": [path]}


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def test_collisions_count_upwards_past_taken_names(tmp_path):
    for name in ("img.png", "img_1.png", "img_2.png"):
        _write(tmp_path / name)
    resolved = _OrganizerWorker._resolve_collision(str(tmp_path / "img.png"))  # noqa: SLF001
    assert resolved == os.path.join(str(tmp_path), "img_3.png")


def test_a_free_name_is_kept(tmp_path):
    dest = str(tmp_path / "free.png")
    assert _OrganizerWorker._resolve_collision(dest) == dest  # noqa: SLF001


def test_a_missing_source_fails_only_itself_and_progress_counts_all(tmp_path):
    good = _write(tmp_path / "good.png")
    out = tmp_path / "out"
    worker = _OrganizerWorker(
        {"a": [str(tmp_path / "missing.png")], "b": [good]}, str(out), move=False)
    progress, results, moves = [], [], []
    worker.progress.connect(lambda c, t, n: progress.append((c, t, n)))
    worker.result_ready.connect(lambda s, f: results.append((s, f)))
    worker.files_moved.connect(moves.append)
    worker.run()
    assert progress == [(1, 2, "missing.png"), (2, 2, "good.png")]
    assert results == [(1, 1)]
    assert moves == []
    assert (out / "b" / "good.png").exists()
    assert os.path.exists(good)


def test_a_move_reports_every_moved_file(tmp_path):
    a = _write(tmp_path / "a.png")
    b = _write(tmp_path / "b.png")
    out = tmp_path / "out"
    worker = _OrganizerWorker({"g": [a, b]}, str(out), move=True)
    moves = []
    worker.files_moved.connect(moves.append)
    worker.run()
    assert moves == [{a: str(out / "g" / "a.png"), b: str(out / "g" / "b.png")}]
    assert not os.path.exists(a)


# ---------------------------------------------------------------------------
# Dialog: preview
# ---------------------------------------------------------------------------

def test_plan_kwargs_only_use_the_date_option_for_the_date_rule(dialog):
    dialog._date_combo.setCurrentIndex(1)  # noqa: SLF001
    dialog._size_large_spin.setValue(9)  # noqa: SLF001
    dialog._size_small_spin.setValue(2)  # noqa: SLF001
    dialog._count_spin.setValue(7)  # noqa: SLF001
    assert dialog._current_plan_kwargs() == {  # noqa: SLF001
        "rule": RULE_DATE, "year_only": True, "large_mb": 9, "small_mb": 2,
        "count_per_folder": 7,
    }
    dialog._rule_combo.setCurrentIndex(dialog._rule_combo.findData(RULE_SIZE))  # noqa: SLF001
    assert dialog._current_plan_kwargs()["year_only"] is False  # noqa: SLF001


def test_preview_of_a_missing_source_does_nothing(dialog, tmp_path):
    dialog._src_edit.setText(str(tmp_path / "missing"))  # noqa: SLF001
    dialog._status_label.setText("before")  # noqa: SLF001
    dialog._do_preview()  # noqa: SLF001
    assert dialog._status_label.text() == "before"  # noqa: SLF001
    assert not dialog._start_btn.isEnabled()  # noqa: SLF001


def test_preview_of_an_empty_folder_says_so(dialog, tmp_path):
    dialog._src_edit.setText(str(tmp_path))  # noqa: SLF001
    dialog._do_preview()  # noqa: SLF001
    assert dialog._status_label.text() == "No images found in source folder."  # noqa: SLF001
    assert dialog._tree.topLevelItemCount() == 0  # noqa: SLF001
    assert not dialog._start_btn.isEnabled()  # noqa: SLF001


def test_preview_lists_sorted_groups_and_enables_start(dialog, tmp_path):
    for name in ("b.png", "a.jpg", "c.png"):
        _write(tmp_path / name)
    dialog._src_edit.setText(str(tmp_path))  # noqa: SLF001
    dialog._rule_combo.setCurrentIndex(dialog._rule_combo.findData(RULE_TYPE))  # noqa: SLF001
    dialog._do_preview()  # noqa: SLF001
    tree = dialog._tree  # noqa: SLF001
    groups = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    assert [(g.text(0), g.text(1)) for g in groups] == [("JPG", "1"), ("PNG", "2")]
    assert [groups[1].child(i).text(0) for i in range(groups[1].childCount())] == [
        "b.png", "c.png"]
    assert not groups[0].flags() & Qt.ItemFlag.ItemIsSelectable
    assert not groups[0].isExpanded()
    assert dialog._status_label.text() == "3 images into 2 subfolder(s)"  # noqa: SLF001
    assert dialog._start_btn.isEnabled()  # noqa: SLF001
    assert set(dialog._last_plan) == {"JPG", "PNG"}  # noqa: SLF001


# ---------------------------------------------------------------------------
# Dialog: execute
# ---------------------------------------------------------------------------

def test_start_without_output_or_plan_does_not_run(dialog, tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(_OrganizerWorker, "start", lambda self: started.append(self))
    dialog._last_plan = {"g": ["a.png"]}  # noqa: SLF001
    dialog._do_start()  # noqa: SLF001
    dialog._out_edit.setText(str(tmp_path))  # noqa: SLF001
    dialog._last_plan = {}  # noqa: SLF001
    dialog._do_start()  # noqa: SLF001
    assert started == []
    assert dialog._worker is None  # noqa: SLF001


def test_start_runs_the_plan_and_restores_the_buttons(dialog, tmp_path, pump_until):
    src = tmp_path / "src"
    src.mkdir()
    a = _write(src / "a.png")
    out = tmp_path / "out" / "deep"
    dialog._out_edit.setText(str(out))  # noqa: SLF001
    dialog._last_plan = {"g": [a]}  # noqa: SLF001
    dialog._start_btn.setEnabled(True)  # noqa: SLF001
    dialog._do_start()  # noqa: SLF001
    worker = dialog._worker  # noqa: SLF001
    try:
        assert not dialog._preview_btn.isEnabled()  # noqa: SLF001
        assert worker is not None
        assert pump_until(lambda: dialog._worker is None)  # noqa: SLF001
    finally:
        if worker is not None:
            worker.wait(5000)
    assert (out / "g" / "a.png").exists()
    assert os.path.exists(a)
    assert dialog._status_label.text() == "Done — 1 organized, 0 failed."  # noqa: SLF001
    assert dialog._start_btn.isEnabled()  # noqa: SLF001
    assert dialog._preview_btn.isEnabled()  # noqa: SLF001
    assert dialog._progress.isHidden()  # noqa: SLF001


def test_progress_updates_bar_and_status(dialog):
    dialog._on_progress(2, 5, "x.png")  # noqa: SLF001
    assert (dialog._progress.maximum(), dialog._progress.value()) == (5, 2)  # noqa: SLF001
    assert dialog._status_label.text() == "Processing: x.png"  # noqa: SLF001


def test_files_moved_are_followed(dialog, monkeypatch):
    seen = []
    monkeypatch.setattr(mod, "follow_saved_data", seen.append)
    dialog._on_files_moved({"a": "b"})  # noqa: SLF001
    assert seen == [{"a": "b"}]


def test_browse_out_keeps_the_field_on_cancel(dialog, monkeypatch):
    dialog._out_edit.setText("kept")  # noqa: SLF001
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory", lambda *_a: "")
    dialog._browse_out()  # noqa: SLF001
    assert dialog._out_edit.text() == "kept"  # noqa: SLF001
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory", lambda *_a: "D:/x")
    dialog._browse_out()  # noqa: SLF001
    assert dialog._out_edit.text() == "D:/x"  # noqa: SLF001


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def test_entry_point_opens_on_the_model_folder(monkeypatch, tmp_path):
    seen = []

    class _Fake:
        def __init__(self, gui, folder):
            seen.append((gui, folder))

        def exec(self):
            seen.append("exec")

    monkeypatch.setattr(mod, "ImageOrganizerDialog", _Fake)
    gui = SimpleNamespace(model=SimpleNamespace(folder_path=str(tmp_path)))
    mod.open_image_organizer(gui)
    bare = SimpleNamespace()
    mod.open_image_organizer(bare)
    assert seen == [(gui, str(tmp_path)), "exec", (bare, None), "exec"]


def test_split_names_stay_importable_from_the_dialog_module():
    for name in ("_scan_folder", "_get_image_date", "_get_resolution_bucket",
                 "_get_type_bucket", "_get_size_bucket", "plan_organization",
                 "_OrganizerWorker", "RULE_DATE", "RULE_RESOLUTION", "RULE_TYPE",
                 "RULE_SIZE", "RULE_COUNT", "follow_saved_data", "QFileDialog",
                 "language_wrapper", "open_image_organizer", "ImageOrganizerDialog"):
        assert hasattr(mod, name), name


def test_the_re_exports_are_the_owning_modules_objects():
    from Imervue.gui import image_organizer_plan as plan
    from Imervue.gui import image_organizer_worker as worker
    assert mod.plan_organization is plan.plan_organization
    assert mod._scan_folder is plan._scan_folder  # noqa: SLF001
    assert mod._OrganizerWorker is worker._OrganizerWorker  # noqa: SLF001


def test_the_planner_imports_no_qt():
    code = ("import sys, Imervue.gui.image_organizer_plan; "
            "print(any(m.startswith('PySide6') for m in sys.modules))")
    done = subprocess.run([sys.executable, "-c", code], cwd=_ROOT, capture_output=True,
                          text=True, timeout=120, check=True)
    assert done.stdout.strip() == "False"
