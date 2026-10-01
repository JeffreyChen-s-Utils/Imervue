"""The Swatches dock shows the recent colours or a named palette; you can keep and delete palettes.

``paint/color_palette.py`` (built-in Standard / Pastel / Manga palettes plus
your own, persisted) was tested but unreachable. The Swatches dock now has a
palette box over its grid, **Save as Palette…** keeps the recent colours under a
name, **Delete Palette** removes one of yours, and Filter > Match Swatches uses
whatever the dock shows.
"""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.color_palette import (
    BUILT_IN_PALETTES,
    RECENT_COLOURS,
    Palette,
    is_built_in,
    load_palettes,
    palette_colours,
    save_palettes,
)
from Imervue.paint.swatch_panel import SwatchPanel
from Imervue.user_settings.user_setting_dict import user_setting_dict

_RECENT = [(10, 20, 30), (40, 50, 60), (70, 80, 90)]


@pytest.fixture(autouse=True)
def _clean():
    for key in ("paint_state", "paint_color_palettes"):
        user_setting_dict.pop(key, None)
    ts.reset_tool_state()
    yield
    for key in ("paint_state", "paint_color_palettes"):
        user_setting_dict.pop(key, None)
    ts.reset_tool_state()


@pytest.fixture
def state():
    s = ts.load_tool_state()
    for rgb in _RECENT:
        s.set_foreground(rgb, commit=True)
    return s


@pytest.fixture
def panel(qapp, state):
    widget = SwatchPanel(state)
    yield widget
    widget.deleteLater()


def _grid_tips(panel: SwatchPanel) -> list[str]:
    return [panel._grid.itemAt(i).widget().toolTip() for i in range(panel._grid.count())]


def test_palette_colours_follow_the_choice():
    assert palette_colours(RECENT_COLOURS, _RECENT) == _RECENT
    assert palette_colours("Manga", _RECENT) == list(BUILT_IN_PALETTES[2].colors)
    assert palette_colours("deleted since", _RECENT) == _RECENT


def test_only_the_shipped_palettes_are_built_in():
    assert is_built_in("Pastel") and not is_built_in("mine")


def test_the_box_lists_recent_then_every_palette(panel):
    box = panel._palette_box
    assert [box.itemData(i) for i in range(box.count())] == [
        RECENT_COLOURS, *(p.name for p in BUILT_IN_PALETTES)]
    assert panel._grid.count() == len(set(_RECENT))


def test_choosing_a_palette_shows_it_and_is_remembered(panel, state):
    panel._palette_box.setCurrentIndex(panel._palette_box.findData("Manga"))
    assert state.swatch_palette == "Manga"
    assert panel._grid.count() == len(BUILT_IN_PALETTES[2].colors)
    assert not panel._clear_btn.isEnabled()
    assert not panel._delete_palette_btn.isEnabled()          # built-in palettes stay
    assert ts.ToolState.from_dict(state.to_dict()).swatch_palette == "Manga"


def test_saving_the_recent_colours_as_a_palette(panel, state):
    assert panel.save_recent_as_palette("  Sunset ") is True
    (saved,) = load_palettes()
    assert saved.name == "Sunset"
    assert set(saved.colors) == set(_RECENT)
    assert state.swatch_palette == "Sunset"
    assert panel._palette_box.currentData() == "Sunset"
    assert panel._delete_palette_btn.isEnabled()


@pytest.mark.parametrize("name", ["", "   ", "Manga"])
def test_an_empty_or_taken_name_is_refused(panel, name):
    assert panel.save_recent_as_palette(name) is False
    assert load_palettes() == []


def test_nothing_to_save_without_recent_colours(qapp):
    widget = SwatchPanel(ts.load_tool_state())
    try:
        assert not widget._save_palette_btn.isEnabled()
        assert widget.save_recent_as_palette("Empty") is False
    finally:
        widget.deleteLater()


def test_deleting_your_palette_goes_back_to_the_recent_colours(panel, state):
    save_palettes([Palette("Mine", ((1, 2, 3),)), Palette("Other", ((4, 5, 6),))])
    state.set_swatch_palette("Mine")
    assert panel.delete_palette("Mine") is True
    assert [p.name for p in load_palettes()] == ["Other"]
    assert state.swatch_palette == RECENT_COLOURS
    assert panel.delete_palette("Manga") is False
    assert panel.delete_palette("nope") is False


def test_a_new_recent_colour_shows_only_while_recent_is_chosen(panel, state):
    state.set_swatch_palette("Pastel")
    count = panel._grid.count()
    state.set_foreground((200, 1, 1), commit=True)
    assert panel._grid.count() == count
    state.set_swatch_palette(RECENT_COLOURS)
    assert "#C80101  (200,1,1)" in _grid_tips(panel)
