"""Characterisation tests for ``LayerDock``'s layout and control wiring.

Pins the dock body's top-level order, the action-button row (glyphs, order,
slots, the adjustment-layer popup), the list's edit triggers and the
opacity / blend controls, so restructuring the constructor cannot drop,
reorder or rewire a control.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QLabel, QLineEdit, QListWidget, QSlider, QToolButton,
)

from Imervue.paint import tool_state as ts
from Imervue.paint.docks import layers
from Imervue.paint.docks.layers import LayerDock
from Imervue.paint.document import PaintDocument


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(layers.language_wrapper, "language_word_dict", {})


@pytest.fixture
def doc():
    document = PaintDocument()
    document.load_image(np.zeros((16, 16, 4), dtype=np.uint8))
    return document


@pytest.fixture
def dock(qapp, doc):
    widget = LayerDock(doc)
    yield widget
    widget.deleteLater()


def _items(dock):
    layout = dock.widget().layout()
    out = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            out.append(item.widget())
        elif item.layout() is not None:
            out.append(item.layout())
        else:
            out.append(None)
    return out


def _row_widgets(row):
    return [row.itemAt(i).widget() for i in range(row.count())]


def test_body_order(dock):
    items = _items(dock)
    kinds = [type(x).__name__ if x is not None else "stretch" for x in items]
    assert kinds == ["QLineEdit", "QListWidget", "QHBoxLayout", "QHBoxLayout",
                     "QLabel", "QSlider", "QLabel", "QComboBox", "stretch"]
    assert items[0] is dock._search  # noqa: SLF001
    assert items[1] is dock._list  # noqa: SLF001
    assert items[4].text() == "Opacity:"
    assert items[5] is dock._opacity  # noqa: SLF001
    assert items[6].text() == "Blend:"
    assert items[7] is dock._blend  # noqa: SLF001
    assert dock.widget().layout().stretch(1) == 1
    assert dock.windowTitle() == "Layers"


def test_search_edit(dock):
    search = dock._search  # noqa: SLF001
    assert isinstance(search, QLineEdit)
    assert search.placeholderText() == "Search layers…"
    assert search.isClearButtonEnabled()
    assert search.toolTip().startswith("Filter the layer list by name")


def test_layer_list_edit_triggers_and_icon_size(dock):
    lst = dock._list  # noqa: SLF001
    assert isinstance(lst, QListWidget)
    triggers = lst.editTriggers()
    assert triggers == (QAbstractItemView.EditTrigger.EditKeyPressed
                        | QAbstractItemView.EditTrigger.SelectedClicked)
    size = dock._thumbnail_size  # noqa: SLF001
    assert (lst.iconSize().width(), lst.iconSize().height()) == (size, size)


def test_action_row_glyphs_and_popup(dock):
    row = _items(dock)[2]
    widgets = _row_widgets(row)
    assert [w.text() for w in widgets[:-1]] == ["+", "−", "↑", "↓", "⧉", "+◐"]
    assert widgets[-1] is None  # trailing stretch
    adj = widgets[5]
    assert adj.popupMode() == QToolButton.ToolButtonPopupMode.InstantPopup
    assert adj.menu() is not None
    assert adj.toolTip() == "Add adjustment layer…"
    assert widgets[1].toolTip() == "Delete layer"


@pytest.mark.parametrize(("glyph", "expected"), [
    ("+", ("add",)), ("−", ("remove",)), ("↑", ("move", True)),
    ("↓", ("move", False)), ("⧉", ("duplicate",)),
])
def test_action_buttons_call_their_handlers(qapp, doc, monkeypatch, glyph, expected):
    calls = []
    monkeypatch.setattr(LayerDock, "_on_add", lambda self: calls.append(("add",)))
    monkeypatch.setattr(LayerDock, "_on_remove", lambda self: calls.append(("remove",)))
    monkeypatch.setattr(LayerDock, "_on_move", lambda self, up: calls.append(("move", up)))
    monkeypatch.setattr(LayerDock, "_on_duplicate", lambda self: calls.append(("duplicate",)))
    widget = LayerDock(doc)
    try:
        button = next(w for w in _row_widgets(_items(widget)[2])
                      if w is not None and w.text() == glyph)
        button.click()
        assert calls == [expected]
    finally:
        widget.deleteLater()


def test_lock_row(dock):
    row = _items(dock)[3]
    widgets = _row_widgets(row)
    assert widgets[0] is dock._lock_alpha_btn  # noqa: SLF001
    assert widgets[1] is None
    assert dock._lock_alpha_btn.text() == "🔒α"  # noqa: SLF001
    assert dock._lock_alpha_btn.toolTip().startswith("Lock transparency")  # noqa: SLF001


def test_opacity_and_blend_controls(dock):
    assert isinstance(dock._opacity, QSlider)  # noqa: SLF001
    assert (dock._opacity.minimum(), dock._opacity.maximum()) == (0, 100)  # noqa: SLF001
    blend = dock._blend  # noqa: SLF001
    assert isinstance(blend, QComboBox)
    assert [blend.itemData(i) for i in range(blend.count())] == list(ts.BLEND_MODES)


def test_without_document_nothing_subscribes(qapp):
    widget = LayerDock()
    try:
        assert not hasattr(widget, "_unsubscribe")
        assert widget._list.count() == 0  # noqa: SLF001
        assert isinstance(_items(widget)[4], QLabel)
    finally:
        widget.deleteLater()


def test_with_document_lists_its_layers(dock, doc):
    assert dock._list.count() == len(doc.layers())  # noqa: SLF001


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class _Shortcuts:
    def __init__(self, table):
        self._table = table

    def get(self, action_id):
        return self._table[action_id]


@pytest.mark.parametrize(("action_id", "table", "expected"), [
    ("", {}, "Delete layer"),
    ("paint.unknown", {}, "Delete layer"),
    ("paint.layer.add", {"paint.layer.add": ""}, "Delete layer"),
    ("paint.layer.add", {"paint.layer.add": None}, "Delete layer"),
    ("paint.layer.add", {"paint.layer.add": "Ctrl+Shift+N"}, "Delete layer (Ctrl+Shift+N)"),
])
def test_with_shortcut(action_id, table, expected):
    assert layers._with_shortcut("Delete layer", _Shortcuts(table), action_id) == expected  # noqa: SLF001


def test_with_shortcut_skips_lookup_without_action_id():
    class _Exploding:
        def get(self, _action_id):
            raise AssertionError("looked up an empty id")

    assert layers._with_shortcut("Label", _Exploding(), "") == "Label"  # noqa: SLF001


def test_blend_mode_combo_labels_and_data(qapp):
    from Imervue.paint.docks._helpers import _blend_mode_combo
    first = ts.BLEND_MODES[0]
    combo = _blend_mode_combo({f"paint_blend_{first}": "FIRST"})
    try:
        assert [combo.itemData(i) for i in range(combo.count())] == list(ts.BLEND_MODES)
        assert combo.itemText(0) == "FIRST"
        idx = next(i for i, m in enumerate(ts.BLEND_MODES) if "_" in m)
        assert combo.itemText(idx) == ts.BLEND_MODES[idx].replace("_", " ").title()
    finally:
        combo.deleteLater()
