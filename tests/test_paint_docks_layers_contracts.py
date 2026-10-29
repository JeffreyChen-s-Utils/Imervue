"""Contract tests for ``LayerDock``'s rows and user-action handlers.

Pins what each row shows for a representative stack (hidden, labelled,
grouped, clipped, masked and alpha-locked layers), the search filter's row
order, and the document command plus ``edit_committed`` emission (or the
lack of one) behind every handler, so splitting the dock into mixins cannot
change a row or drop a signal.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt

from Imervue.paint.adjustments import ADJUSTMENT_KINDS, DEFAULT_PARAMS
from Imervue.paint.docks import layers
from Imervue.paint.docks.layers import LayerDock
from Imervue.paint.document import PaintDocument

_USER_ROLE = Qt.ItemDataRole.UserRole


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(layers.language_wrapper, "language_word_dict", {})


def _document(names=("Background",)):
    document = PaintDocument()
    document.load_image(np.zeros((8, 8, 4), dtype=np.uint8))
    document.layer_at(0).name = names[0]
    for name in names[1:]:
        document.add_layer(name=name)
    return document


@pytest.fixture
def doc():
    """Four layers covering group, clipping, mask, hidden, label and alpha lock."""
    document = _document(("Background", "Ink", "Shade", "Notes"))
    ink = document.layer_at(1)
    ink.group = "Art"
    ink.lock_alpha = True
    shade = document.layer_at(2)
    shade.clip = True
    shade.group = "Art"
    shade.mask = np.full((8, 8), 255, dtype=np.uint8)
    notes = document.layer_at(3)
    notes.visible = False
    notes.locked = True
    notes.color_label = "red"
    document.set_active_layer(1)
    return document


@pytest.fixture
def dock(qapp, doc):
    widget = LayerDock(doc)
    emitted = []
    widget.edit_committed.connect(lambda: emitted.append(True))
    widget.emitted = emitted
    yield widget
    widget.deleteLater()


def _rows(widget):
    lst = widget._list  # noqa: SLF001
    out = []
    for row in range(lst.count()):
        item = lst.item(row)
        out.append((item.text(), item.data(_USER_ROLE),
                    item.checkState() == Qt.CheckState.Checked))
    return out


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------


def test_rows_are_newest_first_with_visibility_and_label(dock):
    assert _rows(dock) == [
        ("🟥 Notes", 3, False),
        ("Shade", 2, True),
        ("Ink", 1, True),
        ("Background", 0, True),
    ]


def test_row_flags_icons_and_current_row(dock):
    lst = dock._list  # noqa: SLF001
    for row in range(lst.count()):
        item = lst.item(row)
        assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable
        assert item.flags() & Qt.ItemFlag.ItemIsEditable
        assert not item.icon().isNull()
    assert lst.currentRow() == 2
    assert dock._lock_alpha_btn.isChecked()  # noqa: SLF001
    assert dock._lock_alpha_btn.isEnabled()  # noqa: SLF001


def test_refresh_reflects_active_opacity_and_blend(qapp, doc):
    doc.layer_at(1).opacity = 0.37
    doc.layer_at(1).blend_mode = "multiply"
    widget = LayerDock(doc)
    try:
        assert widget._opacity.value() == 37  # noqa: SLF001
        assert widget._blend.currentData() == "multiply"  # noqa: SLF001
    finally:
        widget.deleteLater()


def test_search_filters_rows_and_keeps_order(dock):
    dock._search.setText("a")  # noqa: SLF001
    assert [r[1] for r in _rows(dock)] == [2, 0]
    assert dock._list.currentRow() == -1  # noqa: SLF001  (active Ink filtered out)
    dock._search.setText("   ")  # noqa: SLF001
    assert [r[1] for r in _rows(dock)] == [3, 2, 1, 0]
    assert dock._list.currentRow() == 2  # noqa: SLF001


def test_filtered_row_click_selects_true_layer(dock, doc):
    dock._search.setText("a")  # noqa: SLF001
    dock._list.setCurrentRow(1)  # noqa: SLF001
    assert doc.active_layer_index() == 0
    assert dock.emitted == []
    assert dock._row_to_layer_index(5) == -1  # noqa: SLF001


def test_row_changed_ignores_negative_and_suspended(dock, doc):
    dock._on_row_changed(-1)  # noqa: SLF001
    assert doc.active_layer_index() == 1
    dock._suspend = True  # noqa: SLF001
    dock._on_row_changed(0)  # noqa: SLF001
    assert doc.active_layer_index() == 1


# ---------------------------------------------------------------------------
# Inline edits
# ---------------------------------------------------------------------------


def test_rename_strips_chip_and_commits_once(dock, doc):
    item = dock._list.item(0)  # noqa: SLF001
    item.setText("🟥 Remarks")
    assert doc.layer_at(3).name == "Remarks"
    assert dock.emitted == [True]
    assert dock._list.item(0).text() == "🟥 Remarks"  # noqa: SLF001


def test_visibility_toggle_commits(dock, doc):
    dock._list.item(1).setCheckState(Qt.CheckState.Unchecked)  # noqa: SLF001
    assert doc.layer_at(2).visible is False
    assert dock.emitted == [True]


def test_unchanged_item_commits_nothing(dock, doc):
    dock._on_item_changed(dock._list.item(3))  # noqa: SLF001
    assert dock.emitted == []
    assert doc.layer_at(0).name == "Background"


def test_opacity_blend_and_lock_commit(dock, doc):
    dock._opacity.setValue(40)  # noqa: SLF001
    assert doc.layer_at(1).opacity == pytest.approx(0.4)
    dock._blend.setCurrentIndex(dock._blend.findData("screen"))  # noqa: SLF001
    assert doc.layer_at(1).blend_mode == "screen"
    dock._lock_alpha_btn.setChecked(False)  # noqa: SLF001
    assert doc.layer_at(1).lock_alpha is False
    assert dock.emitted == [True, True, True]


def test_blend_same_mode_commits_nothing(dock):
    dock._on_blend_changed()  # noqa: SLF001
    assert dock.emitted == []


def test_suspended_handlers_commit_nothing(dock, doc):
    dock._suspend = True  # noqa: SLF001
    dock._on_opacity_changed(10)  # noqa: SLF001
    dock._on_blend_changed()  # noqa: SLF001
    dock._on_lock_alpha_toggled(False)  # noqa: SLF001
    dock._on_item_changed(dock._list.item(0))  # noqa: SLF001
    assert dock.emitted == []
    assert doc.layer_at(1).lock_alpha is True


# ---------------------------------------------------------------------------
# Stack actions
# ---------------------------------------------------------------------------


def test_add_remove_duplicate_commit(dock, doc):
    dock._on_add()  # noqa: SLF001
    assert doc.layer_count == 5
    assert doc.active_layer_index() == 2
    dock._on_duplicate()  # noqa: SLF001
    assert doc.layer_count == 6
    dock._on_remove()  # noqa: SLF001
    assert doc.layer_count == 5
    assert dock.emitted == [True, True, True]
    assert dock._list.count() == 5  # noqa: SLF001


def test_remove_keeps_last_layer(qapp):
    document = _document()
    widget = LayerDock(document)
    emitted = []
    widget.edit_committed.connect(lambda: emitted.append(True))
    try:
        widget._on_remove()  # noqa: SLF001
        assert document.layer_count == 1
        assert emitted == []
    finally:
        widget.deleteLater()


def test_move_commits_only_when_index_changes(dock, doc):
    dock._on_move(up=True)  # noqa: SLF001
    assert doc.active_layer_index() == 2
    assert [r[0] for r in _rows(dock)] == ["🟥 Notes", "Ink", "Shade", "Background"]
    doc.set_active_layer(3)
    dock._on_move(up=True)  # noqa: SLF001
    assert doc.active_layer_index() == 3
    assert dock.emitted == [True]


def test_actions_without_document_do_nothing(qapp):
    widget = LayerDock()
    emitted = []
    widget.edit_committed.connect(lambda: emitted.append(True))
    try:
        widget._on_add()  # noqa: SLF001
        widget._on_remove()  # noqa: SLF001
        widget._on_duplicate()  # noqa: SLF001
        widget._on_move(up=True)  # noqa: SLF001
        widget._on_row_changed(0)  # noqa: SLF001
        widget._on_opacity_changed(5)  # noqa: SLF001
        widget._on_blend_changed()  # noqa: SLF001
        widget._on_lock_alpha_toggled(True)  # noqa: SLF001
        widget._add_adjustment_layer("levels", {})  # noqa: SLF001
        widget.refresh()
        assert widget._row_to_layer_index(0) == -1  # noqa: SLF001
        assert widget._unique_adjustment_name("brightness_contrast") == "Brightness Contrast"  # noqa: SLF001
        assert emitted == []
    finally:
        widget.deleteLater()


def test_add_on_empty_document_does_nothing(qapp):
    widget = LayerDock(PaintDocument())
    emitted = []
    widget.edit_committed.connect(lambda: emitted.append(True))
    try:
        widget._on_add()  # noqa: SLF001
        widget._add_adjustment_layer("levels", {})  # noqa: SLF001
        assert emitted == []
        assert not widget._lock_alpha_btn.isEnabled()  # noqa: SLF001
    finally:
        widget.deleteLater()


# ---------------------------------------------------------------------------
# Adjustment layers
# ---------------------------------------------------------------------------


def test_adjustment_menu_entries_follow_catalogue(dock):
    adj_button = dock.widget().layout().itemAt(2).layout().itemAt(5).widget()
    labels = [a.text() for a in adj_button.menu().actions()]
    assert labels == [k.replace("_", " ").title() for k in ADJUSTMENT_KINDS]


def test_adjustment_menu_adds_named_layers(dock, doc):
    actions = dock.widget().layout().itemAt(2).layout().itemAt(5).widget().menu().actions()
    kind = ADJUSTMENT_KINDS[0]
    actions[0].trigger()
    actions[0].trigger()
    prefix = kind.replace("_", " ").title()
    names = [layer.name for layer in doc.layers()]
    assert f"{prefix} 1" in names
    assert f"{prefix} 2" in names
    added = doc.active_layer()
    assert added.adjustment.kind == kind
    assert added.adjustment.params == dict(DEFAULT_PARAMS.get(kind, {}))
    assert dock.emitted == [True, True]
    assert dock._list.currentItem().text() == f"{prefix} 2"  # noqa: SLF001
    assert [r[0] for r in _rows(dock)] == [
        "🟥 Notes", "Shade", f"{prefix} 2", f"{prefix} 1", "Ink", "Background",
    ]


# ---------------------------------------------------------------------------
# Document rebinding and shortcuts
# ---------------------------------------------------------------------------


def test_set_document_rebinds_listener(dock, doc):
    other = _document(("Solo",))
    dock.set_document(other)
    assert [r[0] for r in _rows(dock)] == ["Solo"]
    doc.layer_at(0).name = "Changed"
    doc.add_layer(name="Late")
    assert [r[0] for r in _rows(dock)] == ["Solo"]
    dock.set_document(other)
    dock.set_document(None)
    assert dock._list.count() == 0  # noqa: SLF001
    other.add_layer(name="Ignored")
    assert dock._list.count() == 0  # noqa: SLF001


def test_show_shortcuts_relabels_tooltips(dock):
    class _Shortcuts:
        def get(self, action_id):
            return {"paint.layer.add": "Ctrl+J"}.get(action_id, "")

    dock.show_shortcuts(_Shortcuts())
    tips = [b.toolTip() for b, _label, _aid in dock._shortcut_buttons]  # noqa: SLF001
    assert tips == ["Add layer (Ctrl+J)", "Delete layer", "Move layer up",
                    "Move layer down", "Duplicate layer"]
