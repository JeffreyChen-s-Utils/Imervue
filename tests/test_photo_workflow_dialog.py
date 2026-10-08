"""Actual search → compare → cull → preset → export, using Qt widgets and real files."""
from types import SimpleNamespace
import sqlite3
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from Imervue.gui import photo_workflow_dialog as mod
from Imervue.gui.batch_export_dialog import _ExportWorker
from Imervue.gui.library_search_dialog import LibrarySearchDialog
from Imervue.image.develop_presets import DevelopPresetStore
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.library import image_index
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture
def ui(qapp, tmp_path):
    window = QWidget()
    paths = []
    for i, color in enumerate((30, 70, 110)):
        folder = tmp_path / f"folder-{i}"
        folder.mkdir()
        path = folder / f"photo-{i}.png"
        Image.new("RGB", (20, 16), (color, 40, 50)).save(path)
        paths.append(str(path))
        image_index.upsert_image(str(path), width=20, height=16)
    window.viewer = SimpleNamespace(main_window=window, selected_tiles=set(paths),
                                    model=SimpleNamespace(images=paths), current_index=0)
    yield window
    window.deleteLater()


def _highlight(dialog, paths):
    for i in range(dialog._list.count()):
        item = dialog._list.item(i)
        item.setSelected(item.text() in paths)


def test_search_compare_cull_preset_export_and_return_preserve_same_targets(ui, tmp_path, monkeypatch):
    paths = ui.viewer.model.images
    search = LibrarySearchDialog(ui)
    search._name_edit.setText("photo")
    search._run_search()
    assert search._results_list.count() == 3
    search._send_to_workflow()
    dialog = ui._photo_workflow_dialog
    assert set(dialog.workflow.paths) == set(paths)
    assert len({Path(path).parent for path in dialog.workflow.paths}) == 3
    expected = tuple(path for path in dialog.workflow.paths if path != paths[1])
    _highlight(dialog, paths[:2])
    dialog._compare()
    pair = tuple(path for path in dialog.workflow.paths if path in paths[:2])
    assert dialog._comparison._left_path == pair[0]
    assert dialog._comparison._right_path == pair[1]
    dialog._advance_comparison(1)
    assert ui.viewer.current_index == 0
    dialog._back()
    _highlight(dialog, [paths[1]])
    dialog._mark("reject")
    _highlight(dialog, [paths[0]])
    dialog._mark("pick")
    assert image_index.get_cull_state(paths[1]) == "reject"
    assert dialog.workflow.targets() == expected
    dialog._filter.setCurrentIndex(dialog._filter.findData("pick"))
    assert dialog._list.count() == 1
    assert dialog.workflow.targets() == expected
    store = DevelopPresetStore(user_setting_dict)
    store.save("Bright", Recipe(brightness=.25))
    dialog.refresh_presets()
    dialog._develop.setCurrentText("Bright")
    dialog._apply()
    assert recipe_store.get_for_path(paths[0]).brightness == .25
    assert recipe_store.get_for_path(paths[2]).brightness == .25
    assert recipe_store.get_for_path(paths[1]) is None
    dialog._export.setCurrentIndex(dialog._export.findData("web_1600"))
    captured = []

    def export(batch):
        captured.append(tuple(batch._paths))
        output = tmp_path / "output"
        output.mkdir()
        worker = _ExportWorker(batch._paths, str(output), batch._collect_settings())
        worker.run()
        assert worker.job_state.snapshot().status == "succeeded"
        assert batch._collect_settings().quality == 85
        return 0

    monkeypatch.setattr(mod.BatchExportDialog, "exec", export)
    dialog._export_selected()
    assert captured == [expected]
    assert len(list((tmp_path / "output").glob("*.jpg"))) == 2
    assert all(Path(p).is_file() for p in paths)
    dialog.close()
    assert mod.open_photo_workflow(ui) is dialog
    assert dialog.workflow.targets() == expected
    assert dialog.workflow.develop_preset == "Bright" and dialog.workflow.export_preset == "web_1600"
    assert dialog._filter.currentData() == "pick"
    dialog._filter.setCurrentIndex(0)
    assert dialog._list.count() == 3
    search.deleteLater()


def test_checked_hidden_sources_append_and_page_choices_are_retained(ui):
    dialog = mod.open_photo_workflow(ui)
    first = ui.viewer.model.images[0]
    dialog.workflow.choose(first, False)
    extra = [f"extra-{i}.png" for i in range(mod.PAGE_SIZE + 1)]
    dialog.add_paths(extra)
    dialog._step(1)
    assert dialog._list.count() == 4 and first not in dialog.workflow.targets()
    item = dialog._list.item(0)
    item.setCheckState(Qt.CheckState.Unchecked)
    unchecked = item.text()
    dialog._step(-1)
    dialog._step(1)
    assert unchecked not in dialog.workflow.targets()
    dialog._clear()
    assert not dialog.workflow.paths and not dialog.workflow.targets()


def test_external_reject_reconciles_without_reselecting_unchanged_manual_choices(ui):
    dialog = mod.open_photo_workflow(ui)
    paths = ui.viewer.model.images
    dialog.workflow.choose(paths[0], False)
    image_index.set_cull_state(paths[1], "reject")
    assert dialog.refresh_states()
    assert dialog.workflow.targets() == (paths[2],)
    dialog._filter.setCurrentIndex(dialog._filter.findData("pick"))
    assert dialog._list.count() == 0 and dialog.workflow.targets() == (paths[2],)


@pytest.mark.parametrize("operation", ["mark", "add", "refresh", "apply", "export"])
def test_index_errors_preserve_choices_and_report_reason(ui, monkeypatch, operation):
    dialog = mod.open_photo_workflow(ui)
    targets = dialog.workflow.targets()

    def fail(*_args):
        raise sqlite3.OperationalError("locked")

    if operation == "mark":
        _highlight(dialog, targets[:1])
        monkeypatch.setattr(image_index, "set_cull_state", fail)
        dialog._mark("reject")
    else:
        monkeypatch.setattr(image_index, "get_cull_state", fail)
        if operation == "add":
            dialog.add_paths(["new.png"])
        elif operation == "refresh":
            assert not dialog.refresh_states()
        elif operation == "apply":
            dialog._apply()
        else:
            dialog._export_selected()
    assert dialog.workflow.targets() == targets
    assert "locked" in dialog._count.text()


@pytest.mark.parametrize("error", [OSError("read only"), ValueError("invalid"), RuntimeError("closed")])
def test_recipe_failure_keeps_selection_and_preset(ui, monkeypatch, error):
    dialog = mod.open_photo_workflow(ui)
    dialog._compare()
    assert "Highlight" in dialog._count.text()
    DevelopPresetStore(user_setting_dict).save("Preset", Recipe(exposure=.5))
    dialog.refresh_presets()
    dialog._develop.setCurrentText("Preset")

    def fail(*_args):
        raise error

    monkeypatch.setattr(mod, "apply_recipe_to_paths", fail)
    dialog._apply()
    assert str(error) in dialog._count.text()
    assert len(dialog.workflow.targets()) == 3 and dialog.workflow.develop_preset == "Preset"


def test_search_highlighted_subset_and_empty_result_do_not_rewrite_viewer(ui):
    search = LibrarySearchDialog(ui)
    search._send_to_workflow()
    assert not hasattr(ui, "_photo_workflow_dialog")
    search._run_search()
    search._results_list.item(1).setSelected(True)
    search._send_to_workflow()
    dialog = ui._photo_workflow_dialog
    assert len(dialog.workflow.targets()) == 1
    assert len(ui.viewer.model.images) == len(ui.viewer.selected_tiles) == 3
    search.deleteLater()


def test_reopening_library_search_preserves_query_results_and_resets_cancelled_scan_ui(ui, monkeypatch):
    from Imervue.gui.library_search_dialog import open_library_search

    monkeypatch.setattr(LibrarySearchDialog, "exec", lambda _: 0)
    open_library_search(ui)
    search = ui._library_search_dialog
    search._name_edit.setText("photo-1")
    search._run_search()
    assert search._results_list.count() == 1
    search._scan_btn.setEnabled(False)
    search._progress.setVisible(True)
    open_library_search(ui)
    assert ui._library_search_dialog is search
    assert search._name_edit.text() == "photo-1" and search._results_list.count() == 1
    assert search._scan_btn.isEnabled() and search._progress.isHidden()
