"""Qt smoke tests for ``ImageOrganizerDialog``'s layout and control wiring.

Pins the dialog's rows (order, widgets, ranges, combo data), the rule-driven
visibility of the option rows, the browse buttons, the copy / move group and
the plan invalidation every plan input triggers, so restructuring
``_build_ui`` cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import (
    QComboBox, QLabel, QLineEdit, QProgressBar, QPushButton, QRadioButton, QSpinBox, QTreeWidget,
)

from Imervue.gui import image_organizer_dialog as mod
from Imervue.gui.image_organizer_dialog import (
    RULE_COUNT, RULE_DATE, RULE_RESOLUTION, RULE_SIZE, RULE_TYPE, ImageOrganizerDialog,
)


@pytest.fixture
def dialog(qapp, monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    dlg = ImageOrganizerDialog(SimpleNamespace(main_window=None))
    yield dlg
    dlg.deleteLater()


def _items(dlg):
    layout = dlg.layout()
    out = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        out.append(item.widget() if item.widget() is not None else item.layout())
    return out


def _row(layout):
    """Row contents: widgets, with ``None`` for a stretch."""
    return [layout.itemAt(i).widget() for i in range(layout.count())]


def _texts(row):
    return [w.text() if isinstance(w, (QLabel, QPushButton, QRadioButton)) else
            type(w).__name__ if w is not None else None for w in row]


def test_top_level_order(dialog):
    kinds = [type(x).__name__ for x in _items(dialog)]
    assert kinds == ["QHBoxLayout"] * 7 + ["QTreeWidget", "QProgressBar", "QLabel", "QHBoxLayout"]
    assert dialog.layout().stretch(7) == 1
    assert dialog.windowTitle() == "Image Organizer"


def test_folder_rows(dialog):
    items = _items(dialog)
    assert _texts(_row(items[0])) == ["Source folder:", "QLineEdit", "Browse..."]
    assert _row(items[0])[1] is dialog._src_edit  # noqa: SLF001
    assert _texts(_row(items[5])) == ["Output folder:", "QLineEdit", "Browse..."]
    assert _row(items[5])[1] is dialog._out_edit  # noqa: SLF001
    assert items[0].stretch(1) == 1 and items[5].stretch(1) == 1


def test_browse_source_fills_output_only_when_empty(dialog, monkeypatch):
    picks = iter(["/a", "/b", "", "/c"])
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *_a, **_k: next(picks)))
    src_browse = _row(_items(dialog)[0])[2]
    out_browse = _row(_items(dialog)[5])[2]
    src_browse.click()
    assert (dialog._src_edit.text(), dialog._out_edit.text()) == ("/a", "/a")  # noqa: SLF001
    src_browse.click()
    assert (dialog._src_edit.text(), dialog._out_edit.text()) == ("/b", "/a")  # noqa: SLF001
    out_browse.click()  # cancelled
    assert dialog._out_edit.text() == "/a"  # noqa: SLF001
    out_browse.click()
    assert dialog._out_edit.text() == "/c"  # noqa: SLF001


def test_rule_combo(dialog):
    row = _row(_items(dialog)[1])
    assert _texts(row) == ["Organize by:", "QComboBox"]
    combo = row[1]
    assert combo is dialog._rule_combo  # noqa: SLF001
    assert [combo.itemData(i) for i in range(combo.count())] == [
        RULE_DATE, RULE_RESOLUTION, RULE_TYPE, RULE_SIZE, RULE_COUNT]


def test_option_rows(dialog):
    items = _items(dialog)
    date_row, size_row, count_row = (_row(items[i]) for i in (2, 3, 4))
    assert _texts(date_row) == ["Group by:", "QComboBox", None]
    assert [date_row[1].itemData(i) for i in range(2)] == [False, True]
    assert _texts(size_row) == ["Large threshold (MB):", "QSpinBox",
                                "Small threshold (MB):", "QSpinBox", None]
    assert _texts(count_row) == ["Images per subfolder:", "QSpinBox", None]
    spins = {
        "large": dialog._size_large_spin, "small": dialog._size_small_spin,  # noqa: SLF001
        "count": dialog._count_spin,  # noqa: SLF001
    }
    assert {k: (s.minimum(), s.maximum(), s.value()) for k, s in spins.items()} == {
        "large": (1, 1000, 5), "small": (0, 999, 1), "count": (1, 10000, 100)}
    assert size_row[1] is spins["large"] and size_row[3] is spins["small"]
    assert count_row[1] is spins["count"]
    assert date_row[1] is dialog._date_combo  # noqa: SLF001


@pytest.mark.parametrize(("rule", "visible"), [
    (RULE_DATE, (True, False, False)), (RULE_RESOLUTION, (False, False, False)),
    (RULE_TYPE, (False, False, False)), (RULE_SIZE, (False, True, False)),
    (RULE_COUNT, (False, False, True)),
])
def test_option_rows_follow_the_rule(dialog, rule, visible):
    combo = dialog._rule_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(rule))
    groups = (dialog._date_row_widgets, dialog._size_row_widgets,  # noqa: SLF001
              dialog._count_row_widgets)  # noqa: SLF001
    assert all(len(g) for g in groups)
    states = tuple({w.isHidden() for w in g} for g in groups)
    assert states == tuple({not v} for v in visible)


def test_mode_row(dialog):
    row = _row(_items(dialog)[6])
    assert _texts(row) == ["Copy files", "Move files", None]
    copy, move = row[0], row[1]
    assert copy.isChecked() and not move.isChecked()
    assert copy.group() is move.group() and copy.group() is not None
    move.setChecked(True)
    assert not copy.isChecked()


def test_tree_progress_status(dialog):
    items = _items(dialog)
    tree, bar, status = items[7], items[8], items[9]
    assert isinstance(tree, QTreeWidget) and tree is dialog._tree  # noqa: SLF001
    header = tree.headerItem()
    assert [header.text(i) for i in range(2)] == ["Subfolder / File", "Count"]
    assert tree.columnWidth(0) == 450
    assert isinstance(bar, QProgressBar) and bar.isHidden()
    assert status is dialog._status_label and status.text() == ""  # noqa: SLF001


def test_button_row(dialog):
    row = _row(_items(dialog)[10])
    assert _texts(row) == ["Preview", "Start", None, "Close"]
    assert row[0] is dialog._preview_btn and row[1] is dialog._start_btn  # noqa: SLF001
    assert not dialog._start_btn.isEnabled()  # noqa: SLF001
    dialog.show()
    row[3].click()
    assert not dialog.isVisible()


@pytest.mark.parametrize("change", [
    lambda d: d._src_edit.setText("/elsewhere"),  # noqa: SLF001
    lambda d: d._date_combo.setCurrentIndex(1),  # noqa: SLF001
    lambda d: d._size_large_spin.setValue(9),  # noqa: SLF001
    lambda d: d._size_small_spin.setValue(3),  # noqa: SLF001
    lambda d: d._count_spin.setValue(7),  # noqa: SLF001
    lambda d: d._rule_combo.setCurrentIndex(2),  # noqa: SLF001
])
def test_every_plan_input_invalidates_the_plan(dialog, change):
    dialog._last_plan = {"stale": ["x"]}  # noqa: SLF001
    dialog._start_btn.setEnabled(True)  # noqa: SLF001
    change(dialog)
    assert dialog._last_plan == {}  # noqa: SLF001
    assert not dialog._start_btn.isEnabled()  # noqa: SLF001


def test_folder_argument_prefills_source(qapp, tmp_path):
    dlg = ImageOrganizerDialog(SimpleNamespace(main_window=None), folder=str(tmp_path))
    try:
        assert dlg._src_edit.text() == str(tmp_path)  # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_widget_types(dialog):
    assert isinstance(dialog._src_edit, QLineEdit)  # noqa: SLF001
    assert isinstance(dialog._rule_combo, QComboBox)  # noqa: SLF001
    assert isinstance(dialog._count_spin, QSpinBox)  # noqa: SLF001
