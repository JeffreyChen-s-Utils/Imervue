"""Qt smoke tests for the develop-preset browser dialog.

Plain QDialog (no QOpenGLWidget), so no headless-CI skip. The input / confirm
dialogs and the recipe store are monkeypatched so nothing prompts or writes to
disk; the underlying CRUD/apply logic is covered in test_develop_presets.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QInputDialog, QMessageBox

from Imervue.gui import develop_presets_dialog as mod
from Imervue.gui.develop_presets_dialog import DevelopPresetsDialog
from Imervue.image.recipe import Recipe
from Imervue.user_settings.user_setting_dict import user_setting_dict


def _viewer(reload_calls):
    return SimpleNamespace(
        model=SimpleNamespace(images=["a.png", "b.png"]),
        current_index=0,
        selected_tiles=set(),
        main_window=None,
        reload_current_image_with_recipe=lambda: reload_calls.append(True),
    )


def _seed(name="Existing", exposure=0.5):
    user_setting_dict["develop_presets"] = {name: Recipe(exposure=exposure).to_dict()}


def test_list_shows_existing_presets(qapp):
    _seed()
    dlg = DevelopPresetsDialog(_viewer([]))
    assert [dlg._list.item(i).text() for i in range(dlg._list.count())] == ["Existing"]


def test_save_current_as_adds_a_preset(qapp, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Warm", True))
    monkeypatch.setattr(mod.recipe_store, "get_for_path", lambda _p: Recipe(exposure=1.0))
    dlg = DevelopPresetsDialog(_viewer([]))
    dlg._save_current_as()
    assert "Warm" in user_setting_dict["develop_presets"]


def test_save_cancelled_adds_nothing(qapp, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    dlg = DevelopPresetsDialog(_viewer([]))
    dlg._save_current_as()
    assert user_setting_dict.get("develop_presets", {}) == {}


def test_delete_removes_selected_preset(qapp, monkeypatch):
    _seed()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dlg = DevelopPresetsDialog(_viewer([]))
    dlg._list.setCurrentRow(0)
    dlg._delete()
    assert user_setting_dict["develop_presets"] == {}


def test_apply_to_current_writes_recipe_and_reloads(qapp, monkeypatch):
    _seed(exposure=0.7)
    writes: list[tuple] = []
    reloads: list[bool] = []
    monkeypatch.setattr(
        mod.recipe_store, "set_for_path",
        lambda path, recipe: writes.append((path, recipe.exposure)))
    dlg = DevelopPresetsDialog(_viewer(reloads))
    dlg._list.setCurrentRow(0)
    dlg._apply_current()
    assert writes == [("a.png", 0.7)]
    assert reloads == [True]


def test_apply_to_selection_targets_selected_tiles(qapp, monkeypatch):
    _seed(exposure=0.2)
    writes: list[str] = []
    monkeypatch.setattr(
        mod.recipe_store, "set_for_path", lambda path, recipe: writes.append(path))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    viewer = _viewer([])
    viewer.selected_tiles = {"b.png", "c.png"}
    dlg = DevelopPresetsDialog(viewer)
    dlg._list.setCurrentRow(0)
    dlg._apply_selection()
    assert sorted(writes) == ["b.png", "c.png"]


def test_no_selection_apply_is_noop(qapp):
    _seed()
    dlg = DevelopPresetsDialog(_viewer([]))
    # Nothing selected in the list → no recipe → apply does nothing, no raise.
    dlg._apply_current()
