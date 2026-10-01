"""Paint's Bucket dock flat-colours every closed region of the line art on a new layer.

``paint/auto_base_color.py`` was tested but unreachable, and its per-pixel
region scan took 10 s on an A4 page at 300 dpi. Regions now come from a
run-based labeller (well under a second there), and the Bucket dock's **Base
colours on a new layer** puts one flat colour per region on a layer under the
line art.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.auto_base_color import (
    auto_base_fill,
    base_colour_layer,
    label_open_regions,
    lineart_ink,
)
from Imervue.paint.document import PaintDocument
from Imervue.paint.workspace_content import ContentOpsMixin
from Imervue.user_settings.user_setting_dict import user_setting_dict
from tests._toast_spy import ToastSpy


@pytest.fixture(autouse=True)
def _clean():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _grid_lineart(h: int = 40, w: int = 60, step: int = 20) -> np.ndarray:
    """Transparent line art: a 2 px grid of lines every *step* px, closing cells."""
    art = np.zeros((h, w, 4), np.uint8)
    for y in range(0, h, step):
        art[y:y + 2, :, 3] = 255
    for x in range(0, w, step):
        art[:, x:x + 2, 3] = 255
    art[-2:, :, 3] = 255
    art[:, -2:, 3] = 255
    return art


# --- the labeller ---------------------------------------------------------------

def test_labels_follow_4_connectivity_and_raster_order():
    open_pixels = np.array([
        [1, 1, 0, 1],
        [0, 1, 0, 1],
        [1, 0, 0, 0],
        [1, 1, 1, 1],
    ], dtype=bool)
    grid, count = label_open_regions(open_pixels)
    assert count == 3
    assert grid.tolist() == [
        [1, 1, 0, 2],
        [0, 1, 0, 2],
        [3, 0, 0, 0],
        [3, 3, 3, 3],
    ]


def test_a_u_shape_joins_into_one_region():
    """Two runs that only meet further down must end up with one label."""
    open_pixels = np.ones((5, 5), dtype=bool)
    open_pixels[:4, 2] = False
    grid, count = label_open_regions(open_pixels)
    assert count == 1
    assert set(np.unique(grid[open_pixels])) == {1}


def test_the_labeller_matches_the_flood_fill_on_noise():
    from Imervue.paint.fill import _contiguous_region
    rng = np.random.default_rng(5)
    open_pixels = rng.random((30, 30)) > 0.4
    grid, count = label_open_regions(open_pixels)
    for label in range(1, count + 1):
        ys, xs = np.nonzero(grid == label)
        np.testing.assert_array_equal(_contiguous_region(open_pixels, int(xs[0]), int(ys[0])),
                                      grid == label)


def test_an_empty_mask_has_no_regions():
    grid, count = label_open_regions(np.zeros((4, 4), dtype=bool))
    assert count == 0 and not grid.any()


# --- the layer --------------------------------------------------------------------

def test_every_closed_cell_gets_a_colour_and_the_lines_stay_clear():
    art = _grid_lineart()
    layer, count = base_colour_layer(art)
    assert count == 6                                   # 3 x 2 cells
    assert (layer[art[..., 3] == 255, 3] == 0).all()    # lines stay transparent
    centres = [tuple(layer[10 + 20 * r, 10 + 20 * c, :3]) for r in range(2) for c in range(3)]
    assert len(set(centres)) == 6


def test_the_space_around_the_drawing_stays_empty():
    art = np.zeros((40, 40, 4), np.uint8)
    art[10:30, 10:12, 3] = art[10:30, 28:30, 3] = 255
    art[10:12, 10:30, 3] = art[28:30, 10:30, 3] = 255
    layer, count = base_colour_layer(art)
    assert count == 1
    assert layer[0, 0, 3] == 0 and layer[20, 20, 3] == 255


def test_the_palette_is_cycled():
    layer, _count = base_colour_layer(_grid_lineart(), palette=[(9, 9, 9), (200, 0, 0)])
    assert {tuple(layer[10 + 20 * r, 10 + 20 * c, :3]) for r in range(2) for c in range(3)} == {
        (9, 9, 9), (200, 0, 0)}


def test_dark_lines_on_white_paper_count_as_ink():
    art = _grid_lineart()
    paper = np.full_like(art, 255)
    paper[art[..., 3] == 255, :3] = 0
    assert lineart_ink(paper)[0, 0, 3] == 255 and lineart_ink(paper)[10, 10, 3] == 0
    assert base_colour_layer(paper)[1] == 6
    assert lineart_ink(art) is art                       # already transparent: unchanged


def test_auto_base_fill_can_leave_out_the_outside():
    art = np.zeros((40, 40, 4), np.uint8)
    art[10:30, 10:12, 3] = art[10:30, 28:30, 3] = 255
    art[10:12, 10:30, 3] = art[28:30, 10:30, 3] = 255
    assert len(auto_base_fill(art)) == 2
    assert len(auto_base_fill(art, exclude_border=True)) == 1


# --- the Bucket dock's verb ------------------------------------------------------------

class _Host(ContentOpsMixin):
    def __init__(self, document: PaintDocument):
        self._doc = document
        self._canvas = SimpleNamespace(document=lambda: document, update=lambda: None)
        self._state = ts.load_tool_state()
        self._undo_stack = SimpleNamespace(commits=0)
        self._undo_stack.commit = lambda: setattr(self._undo_stack, "commits",
                                                  self._undo_stack.commits + 1)
        self.toast = ToastSpy()


def _document(lineart: np.ndarray) -> PaintDocument:
    doc = PaintDocument()
    doc.load_image(np.full(lineart.shape, 255, np.uint8))
    line = doc.add_layer(name="Lines")
    line.image[...] = lineart
    return doc


def test_the_verb_adds_the_layer_right_under_the_line_art():
    doc = _document(_grid_lineart())
    host = _Host(doc)
    assert host._auto_base_colours() == 6
    names = [layer.name for layer in doc.layers()]
    assert names[-1] == "Lines" and names[-2] == "Base colours"
    assert doc.layers()[-2].image[10, 10, 3] == 255
    assert host._undo_stack.commits == 1


def test_the_verb_uses_the_swatches_shown():
    doc = _document(_grid_lineart())
    host = _Host(doc)
    host._state.set_foreground((1, 2, 3), commit=True)
    host._auto_base_colours()
    assert tuple(doc.layers()[-2].image[10, 10, :3]) == (1, 2, 3)


def test_without_closed_regions_nothing_is_added():
    doc = _document(np.zeros((30, 30, 4), np.uint8))
    host = _Host(doc)
    assert host._auto_base_colours() == 0
    assert len(doc.layers()) == 2
    assert host.toast.calls == [("warning", "No closed region found in the line art")]
    assert host._undo_stack.commits == 0
