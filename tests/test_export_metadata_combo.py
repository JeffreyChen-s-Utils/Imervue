"""Tests for the export dialogs' shared metadata-policy row."""
from __future__ import annotations

import pytest

from Imervue.gui import export_metadata_combo as mod
from Imervue.image.export_metadata import DEFAULT_METADATA_POLICY, SETTING_KEY
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _no_disk_write(monkeypatch):
    saves = []
    monkeypatch.setattr(mod, "schedule_save", lambda: saves.append(1))
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    user_setting_dict.pop(SETTING_KEY, None)
    yield saves
    user_setting_dict.pop(SETTING_KEY, None)


def _row(qapp):
    layout, combo = mod.metadata_row()
    widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
    return layout, combo, widgets


def test_label_items_and_default(qapp):
    _layout, combo, (label, same) = _row(qapp)
    assert label.text() == "Metadata:" and same is combo
    assert [combo.itemData(i) for i in range(combo.count())] == ["all", "no_location", "none"]
    assert combo.currentData() == DEFAULT_METADATA_POLICY
    label.deleteLater()
    combo.deleteLater()


def test_remembered_choice_is_restored(qapp):
    user_setting_dict[SETTING_KEY] = "none"
    _layout, combo, (label, _) = _row(qapp)
    assert combo.currentData() == "none"
    label.deleteLater()
    combo.deleteLater()


def test_corrupt_setting_falls_back_to_the_default(qapp):
    user_setting_dict[SETTING_KEY] = ["not", "a", "policy"]
    _layout, combo, (label, _) = _row(qapp)
    assert combo.currentData() == DEFAULT_METADATA_POLICY
    label.deleteLater()
    combo.deleteLater()


def test_changing_the_choice_is_saved(qapp, _no_disk_write):
    _layout, combo, (label, _) = _row(qapp)
    combo.setCurrentIndex(combo.findData("all"))
    assert user_setting_dict[SETTING_KEY] == "all"
    assert _no_disk_write == [1]
    label.deleteLater()
    combo.deleteLater()
