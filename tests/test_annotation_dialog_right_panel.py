"""Characterisation tests for ``AnnotationDialog``'s right properties panel.

Pins the panel's top-level order, the colour button, the Undo / Redo row and
the brush grid (positions, exclusivity, default and wiring), so restructuring
``_build_right_panel`` cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy

from Imervue.gui import annotation_dialog as mod
from Imervue.gui.annotation_dialog import AnnotationDialog

_BRUSHES = [("pen", "✒ Pen"), ("marker", "🖊 Marker"), ("pencil", "✏ Pencil"),
            ("highlighter", "🖍 Highlighter"), ("spray", "💨 Spray")]


@pytest.fixture
def dlg(qapp, monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})
    base = Image.fromarray(np.full((40, 60, 4), 255, dtype=np.uint8), "RGBA")
    dialog = AnnotationDialog(base, source_path="")
    yield dialog
    dialog.deleteLater()


def _panel(dlg) -> QFrame:
    return dlg.findChild(QFrame, "annotationRightPanel")


def _items(dlg):
    layout = _panel(dlg).layout()
    out = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            out.append(item.widget())
        elif item.layout() is not None:
            out.append(item.layout())
        elif item.spacerItem() is not None:
            out.append(("space", item.spacerItem().sizeHint().height()))
    return out


def _describe(x):
    if isinstance(x, tuple):
        return x
    if isinstance(x, QLabel):
        return ("label", x.text())
    return type(x).__name__


def test_panel_frame(dlg):
    panel = _panel(dlg)
    assert panel is not None
    assert panel.width() == dlg._RIGHT_PANEL_WIDTH  # noqa: SLF001
    margins = panel.layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (12, 12, 12, 12)
    assert panel.layout().spacing() == 6


def test_panel_order(dlg):
    items = [_describe(x) for x in _items(dlg)]
    assert items[0] == ("label", "Properties")
    assert items[1][0] == "label"  # current-tool readout
    assert items[2:] == [
        ("space", 6), ("label", "Color"), "QToolButton", ("space", 4),
        ("label", "Stroke Width"), "QHBoxLayout", ("space", 8),
        ("label", "History"), "QHBoxLayout", ("space", 8),
        ("label", "Brush"), "QGridLayout", ("space", 4),
        ("label", "Opacity"), "QHBoxLayout", ("space", 4),
        ("label", "Spacing"), "QHBoxLayout", ("space", 0),
    ]


def test_title_and_tool_readout_fonts(dlg):
    title, readout = _items(dlg)[:2]
    assert title.font().pointSize() == 12
    assert title.font().bold()
    assert readout is dlg._current_tool_label  # noqa: SLF001
    assert readout.font().pointSize() == 10
    assert readout.styleSheet() == "color: #cccccc;"


def test_section_labels_use_the_panel_style(dlg):
    sections = [x for x in _items(dlg)[2:] if isinstance(x, QLabel)]
    assert all(label.objectName() == mod._QSS_PANEL_SECTION for label in sections)  # noqa: SLF001


def test_colour_button(dlg):
    button = _items(dlg)[4]
    assert button is dlg._color_btn  # noqa: SLF001
    assert button.text() == "Color"
    assert button.minimumHeight() == button.maximumHeight() == 44
    assert button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert not button.autoRaise()
    assert dlg._color == (255, 0, 0, 255)  # noqa: SLF001


def test_history_row_drives_the_undo_stack(dlg):
    row = _items(dlg)[10]
    assert isinstance(row, QHBoxLayout)
    assert row.spacing() == 6
    undo, redo = (row.itemAt(i).widget() for i in range(row.count()))
    assert (undo.text(), redo.text()) == ("↶ Undo", "↷ Redo")
    assert undo.maximumHeight() == 36 and redo.maximumHeight() == 36
    stack = dlg._undo_stack  # noqa: SLF001
    stack.push(QUndoCommand("probe"))
    undo.click()
    assert stack.index() == 0
    redo.click()
    assert stack.index() == 1


def test_brush_grid_layout_and_default(dlg):
    grid = _items(dlg)[13]
    assert isinstance(grid, QGridLayout)
    assert grid.spacing() == 4
    placed = {}
    for i in range(grid.count()):
        row, col, _rs, _cs = grid.getItemPosition(i)
        placed[(row, col)] = grid.itemAt(i).widget().text()
    assert placed == {divmod(i, 2): text for i, (_k, text) in enumerate(_BRUSHES)}
    buttons = dlg._brush_buttons  # noqa: SLF001
    assert list(buttons) == [k for k, _t in _BRUSHES]
    assert [k for k, b in buttons.items() if b.isChecked()] == ["pen"]
    assert all(b.isCheckable() and b.maximumHeight() == 30 for b in buttons.values())
    assert dlg._brush_button_group.exclusive()  # noqa: SLF001
    assert set(dlg._brush_button_group.buttons()) == set(buttons.values())  # noqa: SLF001


def test_brush_button_selects_brush_on_canvas(dlg, monkeypatch):
    chosen = []
    monkeypatch.setattr(dlg._canvas, "set_brush_type", chosen.append)  # noqa: SLF001
    dlg._brush_buttons["spray"].click()  # noqa: SLF001
    assert chosen == ["spray"]
    assert [k for k, b in dlg._brush_buttons.items() if b.isChecked()] == ["spray"]  # noqa: SLF001
