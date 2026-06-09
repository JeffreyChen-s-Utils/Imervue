"""Tests for view_state — per-image zoom/pan memory and random jump."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view import view_state


def _view(images, current=0):
    return SimpleNamespace(
        model=SimpleNamespace(images=list(images)),
        current_index=current,
        zoom=2.0,
        dz_offset_x=10,
        dz_offset_y=20,
        _view_memory={},
        tile_grid_mode=True,
        loaded=[],
        load_deep_zoom_image=lambda p: None,
    )


def test_save_then_restore_round_trip():
    view = _view(["a", "b"], current=1)
    view_state.save_view_state(view)
    # Mutate then restore.
    view.zoom, view.dz_offset_x, view.dz_offset_y = 99, 99, 99
    view_state.restore_view_state(view, "b")
    assert view.zoom == 2.0
    assert view.dz_offset_x == 10
    assert view.dz_offset_y == 20


def test_restore_unknown_path_resets_to_default():
    view = _view(["a"])
    view_state.restore_view_state(view, "never-seen")
    assert view.zoom == 1.0
    assert view.dz_offset_x == 0
    assert view.dz_offset_y == 0


def test_save_with_empty_images_noop():
    view = _view([])
    view_state.save_view_state(view)
    assert view._view_memory == {}


def test_save_out_of_range_index_noop():
    view = _view(["a"], current=5)
    view_state.save_view_state(view)
    assert view._view_memory == {}


def test_jump_to_random_empty_noop():
    loaded = []
    view = _view([])
    view.load_deep_zoom_image = loaded.append
    view_state.jump_to_random(view)
    assert loaded == []


def test_jump_to_random_single_image_loads_it():
    loaded = []
    view = _view(["only.png"])
    view.load_deep_zoom_image = loaded.append
    view_state.jump_to_random(view)
    assert loaded == ["only.png"]
    assert view.current_index == 0


def test_jump_to_random_avoids_current(monkeypatch):
    loaded = []
    view = _view(["a", "b", "c"], current=1)
    view.load_deep_zoom_image = loaded.append
    # Force the choice to be deterministic.
    monkeypatch.setattr(
        "random.choice", lambda choices: choices[0]
    )
    view_state.jump_to_random(view)
    # choices exclude index 1 → first candidate is index 0 ("a").
    assert loaded == ["a"]
    assert view.current_index == 0
    assert view.tile_grid_mode is False
