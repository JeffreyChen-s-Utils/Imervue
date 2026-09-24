"""Characterisation tests for ``AnnotationEditorWidget``'s frame and menu bar.

Pins the root layout (menu bar, toolbox | canvas frame | right panel body,
status bar), the canvas frame, the editor style sheet's rules, the signal
wiring done at construction, and every File / Edit / Modify menu entry with
its shortcut, so splitting the constructor and the menu builder cannot drop,
reorder or rewire anything.
"""
from __future__ import annotations

import re

import numpy as np
import pytest
from PIL import Image
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QStatusBar

from Imervue.gui import annotation_dialog as mod
from Imervue.gui.annotation_dialog import AnnotationEditorWidget

_STYLE_SELECTORS = [
    "QFrame#annotationCanvasFrame",
    "QFrame#annotationLeftToolbox,\nQFrame#annotationRightPanel",
    "QFrame#annotationRightPanel",
    "QFrame#annotationLeftToolbox QToolButton,\nQFrame#annotationRightPanel QToolButton",
    "QFrame#annotationLeftToolbox QToolButton:hover,\nQFrame#annotationRightPanel QToolButton:hover",
    "QFrame#annotationLeftToolbox QToolButton:checked",
    "QFrame#annotationRightPanel QLabel",
    "QFrame#annotationRightPanel QLabel#panelSection",
    "QFrame#annotationRightPanel QSpinBox,\nQFrame#annotationRightPanel QSlider",
]


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


def _base():
    return Image.fromarray(np.full((20, 30, 4), 255, dtype=np.uint8), "RGBA")


@pytest.fixture
def editor(qapp):
    widget = AnnotationEditorWidget(_base())
    yield widget
    widget.deleteLater()


def _selectors(style: str) -> list[str]:
    blocks = re.findall(r"([^{}]+)\{", style)
    return ["\n".join(line.strip() for line in b.strip().splitlines()) for b in blocks]


def test_root_layout(editor):
    root = editor.layout()
    assert root.menuBar() is editor._menu_bar  # noqa: SLF001
    margins = root.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
    assert root.spacing() == 0
    assert root.count() == 2
    body = root.itemAt(0).layout()
    assert isinstance(body, QHBoxLayout) and root.stretch(0) == 1
    assert body.spacing() == 0
    status = root.itemAt(1).widget()
    assert isinstance(status, QStatusBar) and status is editor._status_bar  # noqa: SLF001
    toolbox, frame, panel = (body.itemAt(i).widget() for i in range(3))
    assert toolbox is editor._left_toolbox and panel is editor._right_panel  # noqa: SLF001
    assert [body.stretch(i) for i in range(3)] == [0, 1, 0]
    assert isinstance(frame, QFrame) and frame.objectName() == "annotationCanvasFrame"


def test_canvas_frame(editor):
    frame = editor.findChild(QFrame, "annotationCanvasFrame")
    assert frame.frameShape() == QFrame.Shape.NoFrame
    inner = frame.layout()
    margins = inner.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (8, 8, 8, 8)
    assert inner.spacing() == 0
    assert inner.itemAt(0).widget() is editor._canvas and inner.stretch(0) == 1  # noqa: SLF001


def test_style_sheet_rules(editor):
    style = editor.styleSheet()
    assert _selectors(style) == _STYLE_SELECTORS
    assert "#0a6cbc" in style and "#9cdcfe" in style and "#1e1e1e" in style


def test_construction_wiring(editor):
    assert editor._undo_stack.parent() is editor  # noqa: SLF001
    assert editor._source_path == "" and editor._on_saved is None  # noqa: SLF001
    editor._canvas.cursor_image_pos.emit(3, 4)  # noqa: SLF001


def test_default_tool_is_applied(qapp):
    widget = AnnotationEditorWidget(_base(), default_tool="mosaic")
    try:
        assert widget._canvas._tool == "mosaic"  # noqa: SLF001
    finally:
        widget.deleteLater()


def _menu_entries(menu: QMenu):
    return [("-" if a.isSeparator() else a.text(), a.shortcut().toString())
            for a in menu.actions()]


def test_menu_bar(editor):
    menus = [a.menu() for a in editor._menu_bar.actions()]  # noqa: SLF001
    assert [m.title() for m in menus] == ["File", "Edit"]
    file_menu, edit_menu = menus
    assert _menu_entries(file_menu) == [
        ("Save", "Ctrl+S"), ("Save As...", "Ctrl+Shift+S"), ("Copy to Clipboard", "Ctrl+C"),
        ("-", ""), ("Save Project...", ""), (mod._LOAD_PROJECT_FALLBACK, ""),  # noqa: SLF001
        ("-", ""), ("Close", "Ctrl+W"),
    ]
    entries = _menu_entries(edit_menu)
    assert [text for text, _ in entries][2:] == ["-", "Delete Selection"]
    assert entries[0][1] == QKeySequence(QKeySequence.StandardKey.Undo).toString()
    assert entries[1][1] == QKeySequence(QKeySequence.StandardKey.Redo).toString()
    assert entries[3][1] == "Del"


def test_file_menu_actions_call_their_handlers(qapp, monkeypatch):
    calls = []
    for name in ("_save", "_save_as", "_copy_to_clipboard", "_save_project",
                 "_load_project", "_delete_selected"):
        monkeypatch.setattr(AnnotationEditorWidget, name,
                            lambda self, *_a, n=name: calls.append(n))
    widget = AnnotationEditorWidget(_base())
    closed = []
    widget.close_requested.connect(lambda: closed.append(True))
    try:
        file_menu, edit_menu = (a.menu() for a in widget._menu_bar.actions())  # noqa: SLF001
        for action in file_menu.actions():
            if not action.isSeparator():
                action.trigger()
        edit_menu.actions()[3].trigger()
        assert calls == ["_save", "_save_as", "_copy_to_clipboard", "_save_project",
                         "_load_project", "_delete_selected"]
        assert closed == [True]
    finally:
        widget.deleteLater()


def test_modify_menu_only_with_a_target(qapp, monkeypatch):
    from Imervue.gui import modify_actions_widget
    from PySide6.QtWidgets import QWidget

    class _StubModify(QWidget):
        def __init__(self, main_gui, parent=None, on_triggered=None):
            super().__init__(parent)
            self.main_gui = main_gui
            self.on_triggered = on_triggered

    monkeypatch.setattr(modify_actions_widget, "ModifyActionsWidget", _StubModify)
    target = object()
    widget = AnnotationEditorWidget(_base(), modify_target=target)
    try:
        menus = [a.menu() for a in widget._menu_bar.actions()]  # noqa: SLF001
        assert [m.title() for m in menus] == ["File", "Edit", "Modify"]
        (action,) = menus[2].actions()
        stub = action.defaultWidget()
        assert isinstance(stub, _StubModify) and stub.main_gui is target
        assert stub.on_triggered == menus[2].close
    finally:
        widget.deleteLater()
