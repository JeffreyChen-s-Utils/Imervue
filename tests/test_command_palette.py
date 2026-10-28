"""Tests for command-palette fuzzy scoring."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMainWindow


@pytest.fixture
def palette_window(cp, monkeypatch):
    monkeypatch.setitem(cp.settings.user_setting_dict, cp._HISTORY_KEY, {})
    monkeypatch.setattr(cp.settings, "schedule_save", lambda: None)
    window = QMainWindow()
    menu = window.menuBar().addMenu("File")
    first = menu.addAction("Alpha")
    first.setObjectName("file.alpha")
    second = menu.addAction("Beta")
    second.setObjectName("file.beta")
    yield window, first, second
    window.deleteLater()


def test_unavailable_command_stays_open_with_reason(cp, palette_window):
    window, first, _ = palette_window
    first.setEnabled(False)
    first.setProperty("disabledReason", "Open an image first")
    dialog = cp.CommandPaletteDialog(window)
    dialog.show()
    dialog._input.setText("Alpha")
    assert "Open an image first" in dialog._list.item(0).text()
    QTest.keyClick(dialog._input, Qt.Key.Key_Return)
    assert dialog.isVisible()
    assert dialog._feedback.text() == "Open an image first"
    assert not cp._history()
    dialog.close()


def test_command_usage_persists_and_ranks_against_unused_commands(cp, palette_window):
    window, _, second = palette_window
    invoked = []
    second.triggered.connect(lambda: invoked.append(True))
    dialog = cp.CommandPaletteDialog(window)
    dialog.show()
    dialog._input.setText("Beta")
    QTest.keyClick(dialog._input, Qt.Key.Key_Return)
    assert invoked == [True]
    assert not dialog.isVisible()
    reopened = cp.CommandPaletteDialog(window)
    assert reopened._list.item(0).data(Qt.ItemDataRole.UserRole) is second
    assert cp._history()["file.beta"][0] == 1
    assert cp._usage_score((5, 100), 100) > cp._usage_score((1, 100), 100)
    assert cp._usage_score((1, 100), 100) > cp._usage_score((1, 0), 100)
    reopened.close()


def test_palette_identity_survives_locale_and_separators(cp, qapp, monkeypatch):
    window = QMainWindow()
    menu = window.menuBar().addMenu("File")
    first = menu.addAction("Open")
    menu.addSeparator()
    second = menu.addAction("Open")
    monkeypatch.setattr(cp.language_wrapper, "language_word_dict",
                        {"menu_file": "File", "menu_open": "Open"})
    identities = [entry.identity for entry in cp._collect_all_entries(window)]
    assert len(set(identities)) == 2
    menu.setTitle("檔案")
    first.setText("開啟")
    second.setText("開啟")
    menu.insertSeparator(first)
    monkeypatch.setattr(cp.language_wrapper, "language_word_dict",
                        {"menu_file": "檔案", "menu_open": "開啟"})
    assert [entry.identity for entry in cp._collect_all_entries(window)] == identities
    window.deleteLater()


def test_command_history_is_bounded_and_rejects_invalid_rows(cp, monkeypatch):
    monkeypatch.setattr(cp.settings, "schedule_save", lambda: None)
    value = {f"command.{i}": [1, i] for i in range(100)}
    value.update(bad=[False, 0], nan=[1, float("nan")], wrong="bad")
    monkeypatch.setitem(cp.settings.user_setting_dict, cp._HISTORY_KEY, value)
    cp._record_command("new.command")
    assert len(cp._history()) == cp._MAX_HISTORY
    assert "new.command" in cp._history()
    assert not {"bad", "nan", "wrong"}.intersection(cp._history())


def test_real_empty_menus_explain_why_their_commands_are_unavailable(cp, monkeypatch):
    from Imervue.external import editors
    from Imervue.menu.file_menu import _populate_open_in_editor_menu
    from Imervue.menu.filter_menu import _build_album_filter, _build_tag_filter
    from Imervue.menu.recent_menu import build_recent_menu
    from Imervue.user_settings import tags

    monkeypatch.setattr(tags, "get_all_tags", lambda: {})
    monkeypatch.setattr(tags, "get_all_albums", lambda: {})
    monkeypatch.setattr(editors, "load_editors", lambda: [])
    monkeypatch.setitem(cp.settings.user_setting_dict, "user_recent_folders", [])
    monkeypatch.setitem(cp.settings.user_setting_dict, "user_recent_images", [])
    monkeypatch.setitem(cp.settings.user_setting_dict, cp._HISTORY_KEY, {})
    window = QMainWindow()
    for name, builder in (("Tags", _build_tag_filter), ("Albums", _build_album_filter),
                          ("Editors", _populate_open_in_editor_menu), ("File", build_recent_menu)):
        builder(window, window.menuBar().addMenu(name))
    dialog = cp.CommandPaletteDialog(window)
    try:
        dialog.show()
        unavailable = 0
        for index in range(dialog._list.count()):
            item = dialog._list.item(index)
            action = item.data(Qt.ItemDataRole.UserRole)
            if action.isEnabled():
                continue
            reason = action.property("disabledReason")
            assert reason and reason != cp._unavailable_reason(cp.QAction())
            dialog._list.setCurrentRow(index)
            QTest.keyClick(dialog._list, Qt.Key.Key_Return)
            assert dialog.isVisible()
            assert dialog._feedback.text() == reason
            unavailable += 1
        assert unavailable == 5
        assert not cp._history()
    finally:
        dialog.close()
        window.deleteLater()


@pytest.fixture
def cp(qapp):
    from Imervue.gui import command_palette as m
    return m


class TestFuzzyScore:
    def test_empty_query_is_zero(self, cp):
        assert cp.fuzzy_score("", "anything") == 0

    def test_exact_prefix_scores_high(self, cp):
        s_prefix = cp.fuzzy_score("open", "open file")
        s_other = cp.fuzzy_score("open", "close file")
        assert s_prefix > s_other

    def test_subsequence_match_still_scores(self, cp):
        # q=oof should match "open file" as o..p..e..n..f becomes o..f..
        # A weak but non-zero score is fine.
        s = cp.fuzzy_score("of", "open file")
        assert s > 0

    def test_no_match_returns_negative(self, cp):
        assert cp.fuzzy_score("xyzqq", "open file") == -1
