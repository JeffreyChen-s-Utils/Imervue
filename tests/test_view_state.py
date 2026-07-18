"""Tests for view_state — per-image zoom/pan memory and random jump."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.gpu_image_view import view_state


def _view(images, current=0, deep_path=None):
    return SimpleNamespace(
        model=SimpleNamespace(images=list(images)),
        current_index=current,
        _deep_zoom_path=deep_path,
        zoom=2.0,
        dz_offset_x=10,
        dz_offset_y=20,
        _view_memory={},
        tile_grid_mode=True,
        loaded=[],
        load_deep_zoom_image=lambda p: None,
    )


def test_save_then_restore_round_trip():
    view = _view(["a", "b"], current=1, deep_path="b")
    view_state.save_view_state(view)
    # Mutate then restore.
    view.zoom, view.dz_offset_x, view.dz_offset_y = 99, 99, 99
    view_state.restore_view_state(view, "b")
    assert view.zoom == 2.0
    assert view.dz_offset_x == 10
    assert view.dz_offset_y == 20


def test_save_keys_on_displayed_path_not_current_index():
    # The bug: navigation advances current_index to the *incoming* image
    # before the load runs, so keying the save on it saved the outgoing
    # image's zoom under the incoming slot. Save must key on the displayed
    # (outgoing) path instead.
    view = _view(["a", "b"], current=1, deep_path="a")
    view_state.save_view_state(view)
    assert "a" in view._view_memory
    assert "b" not in view._view_memory
    assert view._view_memory["a"]["zoom"] == pytest.approx(2.0)


def test_restore_unknown_path_resets_to_default():
    view = _view(["a"])
    view_state.restore_view_state(view, "never-seen")
    assert view.zoom == 1.0
    assert view.dz_offset_x == 0
    assert view.dz_offset_y == 0


def test_save_without_displayed_path_is_noop():
    # Nothing on screen (fresh entry / after exit-to-grid) → nothing to save.
    view = _view(["a"], deep_path=None)
    view_state.save_view_state(view)
    assert view._view_memory == {}


def test_save_records_base_dims_when_deep_zoom_present():
    # The base level array is (h, w, 4); dims are stored width-first so a later
    # reload can detect a rotate/crop and force a refit.
    view = _view(["a"], current=0, deep_path="a")
    view.deep_zoom = SimpleNamespace(levels=[np.zeros((300, 400, 4), dtype=np.uint8)])
    view_state.save_view_state(view)
    assert view._view_memory["a"]["dims"] == (400, 300)


def test_save_records_none_dims_without_deep_zoom():
    view = _view(["a"], current=0, deep_path="a")  # no deep_zoom attribute
    view_state.save_view_state(view)
    assert view._view_memory["a"]["dims"] is None


def test_resolve_loaded_index_fast_path_when_index_already_matches():
    # current_index already points at the loaded path → return it, no lookup.
    assert view_state.resolve_loaded_index(["a", "b", "c"], 1, "b") == 1


def test_resolve_loaded_index_relocates_after_reorder():
    # The scan re-sorted the list under the in-flight load; current_index is now
    # stale. Re-locate the path instead of dropping the finished image.
    assert view_state.resolve_loaded_index(["b", "a", "c"], 0, "c") == 2


def test_resolve_loaded_index_relocates_when_index_out_of_range():
    # A shorter list left current_index past the end — still locate the path.
    assert view_state.resolve_loaded_index(["a", "b"], 5, "a") == 0


def test_resolve_loaded_index_none_when_path_left_the_folder():
    # Path genuinely removed → the one case where discarding the load is right.
    assert view_state.resolve_loaded_index(["a", "b"], 0, "gone") is None


def test_resolve_loaded_index_none_for_empty_list():
    assert view_state.resolve_loaded_index([], 0, "a") is None


def test_resolve_loaded_index_negative_current_relocates():
    # A NO_FOCUS-style negative index must not index from the tail; re-locate.
    assert view_state.resolve_loaded_index(["a", "b"], -1, "b") == 1


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


def test_save_records_locked_flag_for_a_user_zoom():
    # A deliberate zoom-in (_user_locked_view True) is remembered as locked so
    # the next load preserves it.
    view = _view(["a"], current=0, deep_path="a")
    view._user_locked_view = True
    view_state.save_view_state(view)
    assert view._view_memory["a"]["locked"] is True


def test_save_records_unlocked_for_a_fit_view():
    # A whole-image fit (_user_locked_view False) is remembered unlocked so the
    # next load re-fits it to the current canvas instead of opening too big.
    view = _view(["a"], current=0, deep_path="a")
    view._user_locked_view = False
    view_state.save_view_state(view)
    assert view._view_memory["a"]["locked"] is False


def test_save_defaults_locked_false_when_flag_absent():
    view = _view(["a"], current=0, deep_path="a")   # no _user_locked_view attr
    view_state.save_view_state(view)
    assert view._view_memory["a"]["locked"] is False
