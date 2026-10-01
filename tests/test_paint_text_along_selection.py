"""Paint's Manga > Text Along Selection… lays text along the selection's outline.

``paint/text_on_selection.py`` and the ``paint/text_on_path.py`` engine it
drives were tested but unreachable. The Manga menu entry takes the text and its
style from the Add Text dialog and draws it on a new "Text" layer.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Imervue.paint.document import PaintDocument
from Imervue.paint.manga_menu import commit_text_along_selection
from Imervue.paint.text_render import TextRenderOptions


def _workspace(selection):
    doc = PaintDocument()
    doc.load_image(np.full((120, 160, 4), 255, np.uint8))
    doc.set_selection(selection)
    updates = []
    canvas = SimpleNamespace(document=lambda: doc, update=lambda: updates.append(1))
    return SimpleNamespace(canvas=lambda: canvas), doc, updates


def _ring() -> np.ndarray:
    selection = np.zeros((120, 160), bool)
    selection[20:100, 30:130] = True
    return selection


def test_the_text_is_drawn_on_a_new_layer_along_the_outline(qapp):
    workspace, doc, updates = _workspace(_ring())
    options = TextRenderOptions(text="ALONG THE EDGE", size=14, color=(200, 0, 0))
    assert commit_text_along_selection(workspace, options) is True
    layer = doc.layers()[-1]
    assert layer.name == "Text"
    ys, xs = np.nonzero(layer.image[..., 3])
    assert len(ys) > 0
    near_edge = (np.abs(ys - 20) < 20) | (np.abs(ys - 100) < 20) | (np.abs(xs - 30) < 20) | (np.abs(xs - 130) < 20)
    assert near_edge.mean() > 0.9                              # glyphs hug the outline
    assert updates == [1]


def test_without_a_selection_or_text_nothing_is_added(qapp):
    workspace, doc, _ = _workspace(None)
    assert commit_text_along_selection(workspace, TextRenderOptions(text="hi")) is False
    workspace, doc, _ = _workspace(_ring())
    assert commit_text_along_selection(workspace, TextRenderOptions(text="   ")) is False
    assert len(doc.layers()) == 1


def test_a_selection_too_small_to_follow_adds_nothing(qapp):
    selection = np.zeros((120, 160), bool)
    selection[50, 50] = True
    workspace, doc, _ = _workspace(selection)
    assert commit_text_along_selection(workspace, TextRenderOptions(text="x")) is False
    assert len(doc.layers()) == 1
