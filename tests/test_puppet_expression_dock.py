"""Tests for the expression selector dock — list rebuild, button
state, and round-trip toggle into the canvas's active-expression
stack.

The dock instantiates a canvas internally (it listens to
``document_loaded``); these tests use the same canvas constructor via
PuppetWorkspace so the wiring is exercised end-to-end.
"""
from __future__ import annotations

from puppet.canvas import PuppetCanvas
from puppet.document import Drawable, Expression, ExpressionParam, PuppetDocument
from puppet.expression_dock import ExpressionDock


def _doc_with_expressions(names: tuple[str, ...]) -> PuppetDocument:
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            indices=[0, 1, 2],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            draw_order=0,
        ),
    ]
    doc.expressions = [
        Expression(
            name=name,
            params=[ExpressionParam(id="ParamMouthForm", value=0.5, mode="additive")],
        )
        for name in names
    ]
    return doc


def test_dock_shows_empty_state_with_no_expressions(qapp):
    canvas = PuppetCanvas()
    dock = ExpressionDock(canvas)
    try:
        assert dock.buttons() == {}
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_rebuilds_when_document_loads(qapp):
    canvas = PuppetCanvas()
    dock = ExpressionDock(canvas)
    try:
        canvas.load_document(_doc_with_expressions(("smile", "surprise")))
        names = set(dock.buttons().keys())
        assert names == {"smile", "surprise"}
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_toggle_expression_adds_then_removes_from_canvas_stack(qapp):
    canvas = PuppetCanvas()
    dock = ExpressionDock(canvas)
    try:
        canvas.load_document(_doc_with_expressions(("smile",)))
        active = dock.toggle_expression("smile")
        assert active is True
        assert "smile" in canvas.active_expressions()
        active = dock.toggle_expression("smile")
        assert active is False
        assert "smile" not in canvas.active_expressions()
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_toggle_emits_signal(qapp):
    canvas = PuppetCanvas()
    dock = ExpressionDock(canvas)
    try:
        canvas.load_document(_doc_with_expressions(("wink",)))
        events: list[tuple[str, bool]] = []
        dock.expression_toggled.connect(
            lambda name, active: events.append((name, active)),
        )
        dock.toggle_expression("wink")
        dock.toggle_expression("wink")
        assert events == [("wink", True), ("wink", False)]
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_button_reflects_active_state_after_document_reload(qapp):
    """If the canvas already has an expression active when a document
    is (re)loaded, the dock's button must show as checked — otherwise
    the user sees the puppet posing but no UI indicator that it's the
    expression."""
    canvas = PuppetCanvas()
    dock = ExpressionDock(canvas)
    try:
        canvas.load_document(_doc_with_expressions(("smile",)))
        canvas.add_expression("smile")
        # Trigger a rebuild as though the document was reloaded
        canvas.document_loaded.emit()
        button = dock.buttons()["smile"]
        assert button.isChecked() is True
    finally:
        dock.deleteLater()
        canvas.deleteLater()
