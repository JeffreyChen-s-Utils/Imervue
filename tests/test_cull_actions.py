"""Tests for cull_actions.resolve_cull_targets — target resolution order.

The action helpers themselves toggle persistent state and toast, but the
priority resolution (multi-select → deep-zoom → arrow-key focus → hover → none) is pure and
covered here with a fake view.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.cull_actions import resolve_cull_targets


def _view(**kw):
    base = {
        "tile_grid_mode": False,
        "tile_selection_mode": False,
        "selected_tiles": set(),
        "deep_zoom": None,
        "model": SimpleNamespace(images=[]),
        "current_index": 0,
        "_hover_last_path": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_no_target_returns_empty():
    assert resolve_cull_targets(_view()) == []


def test_multi_selected_tiles_take_priority():
    view = _view(
        tile_grid_mode=True,
        tile_selection_mode=True,
        selected_tiles={"a", "b"},
        deep_zoom=object(),
        model=SimpleNamespace(images=["x"]),
    )
    assert set(resolve_cull_targets(view)) == {"a", "b"}


def test_deep_zoom_image_when_no_selection():
    view = _view(
        deep_zoom=object(),
        model=SimpleNamespace(images=["x", "y", "z"]),
        current_index=1,
    )
    assert resolve_cull_targets(view) == ["y"]


def test_hovered_tile_when_grid_and_no_selection():
    view = _view(tile_grid_mode=True, _hover_last_path="hov.png")
    assert resolve_cull_targets(view) == ["hov.png"]


def test_deep_zoom_out_of_range_index_falls_through():
    view = _view(
        deep_zoom=object(),
        model=SimpleNamespace(images=["x"]),
        current_index=5,
    )
    # Index out of range → no deep-zoom target, no hover → empty.
    assert resolve_cull_targets(view) == []


def test_empty_selection_set_falls_through_to_hover():
    view = _view(
        tile_grid_mode=True,
        tile_selection_mode=True,
        selected_tiles=set(),
        _hover_last_path="hov.png",
    )
    assert resolve_cull_targets(view) == ["hov.png"]



def test_the_tile_the_arrow_keys_are_on_beats_the_hovered_one():
    view = _view(tile_grid_mode=True, model=SimpleNamespace(images=["a", "b", "c"]),
                 focused_tile_index=1, focus_ring_visible=True, _hover_last_path="c")
    assert resolve_cull_targets(view) == ["b"]


def test_a_hidden_focus_ring_leaves_the_hovered_tile():
    """Moving the mouse hides the ring: the mouse is what the user is pointing with now."""
    view = _view(tile_grid_mode=True, model=SimpleNamespace(images=["a", "b", "c"]),
                 focused_tile_index=1, focus_ring_visible=False, _hover_last_path="c")
    assert resolve_cull_targets(view) == ["c"]


def test_a_focus_past_the_last_tile_falls_through_to_hover():
    view = _view(tile_grid_mode=True, model=SimpleNamespace(images=["a"]),
                 focused_tile_index=4, focus_ring_visible=True, _hover_last_path="a")
    assert resolve_cull_targets(view) == ["a"]


def test_selection_and_deep_zoom_still_come_before_the_focus():
    images = SimpleNamespace(images=["a", "b", "c"])
    selected = _view(tile_grid_mode=True, tile_selection_mode=True, selected_tiles={"c"},
                     model=images, focused_tile_index=0, focus_ring_visible=True)
    zoomed = _view(deep_zoom=object(), model=images, current_index=2,
                   focused_tile_index=0, focus_ring_visible=True)
    assert resolve_cull_targets(selected) == ["c"]
    assert resolve_cull_targets(zoomed) == ["c"]
