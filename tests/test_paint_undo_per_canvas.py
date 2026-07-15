"""Tests for the per-canvas paint undo stack.

A single shared undo stack stayed bound to the first document forever, so after
a tab switch or opening a file Ctrl+Z applied one document's history to another
(a silent, destructive corruption). The ``_undo_stack`` property now resolves to
the active canvas's own stack and rebinds when the canvas's document is replaced.

The property getter is exercised unbound on light fakes — no real workspace or
GL canvas is constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.paint.paint_workspace import PaintWorkspace


class _FakeDoc:
    def layers(self):
        return []

    def selection(self):
        return None


class _FakeCanvas:
    def __init__(self, doc):
        self._doc = doc

    def document(self):
        return self._doc


def _stack(ws):
    return PaintWorkspace._undo_stack.fget(ws)


def test_stack_is_stable_per_canvas():
    canvas = _FakeCanvas(_FakeDoc())
    ws = SimpleNamespace(_canvas=canvas, _undo_stacks={})
    first = _stack(ws)
    assert _stack(ws) is first          # same canvas + doc → same stack


def test_each_canvas_gets_its_own_stack():
    canvas_a = _FakeCanvas(_FakeDoc())
    canvas_b = _FakeCanvas(_FakeDoc())
    ws = SimpleNamespace(_canvas=canvas_a, _undo_stacks={})
    stack_a = _stack(ws)
    ws._canvas = canvas_b
    stack_b = _stack(ws)
    assert stack_b is not stack_a       # different canvas → different history
    ws._canvas = canvas_a
    assert _stack(ws) is stack_a        # switching back keeps canvas A's history


def test_stack_rebinds_when_document_replaced_wholesale():
    canvas = _FakeCanvas(_FakeDoc())
    ws = SimpleNamespace(_canvas=canvas, _undo_stacks={})
    first = _stack(ws)
    canvas._doc = _FakeDoc()            # open file / new document
    second = _stack(ws)
    assert second is not first          # history cleared for the new document
    assert second.document is canvas._doc


def test_in_place_mutation_keeps_the_same_stack():
    # A brush dab mutates the document in place (same object) → same history.
    doc = _FakeDoc()
    canvas = _FakeCanvas(doc)
    ws = SimpleNamespace(_canvas=canvas, _undo_stacks={})
    first = _stack(ws)
    assert canvas.document() is doc     # object identity unchanged
    assert _stack(ws) is first
