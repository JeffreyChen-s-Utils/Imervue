"""Tests for KeyInputHandler — keyboard routing (no shortcut dispatch path).

Covers the hard-wired keys: F8 HUD toggle, F1-F5 colour labels, Escape
handling, and arrow-key navigation. A fake view records the effects.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt

from Imervue.gpu_image_view.key_input_handler import KeyInputHandler


def _view(**kw):
    images = kw.pop("images", [])
    base = {
        "main_window": SimpleNamespace(),  # no plugin_manager / not fullscreen
        "tile_grid_mode": False,
        "deep_zoom": None,
        "active_deep_zoom_worker": None,
        "selected_tiles": set(),
        "tile_selection_mode": False,
        "_show_osd": False,
        "_show_debug_hud": False,
        "applied_labels": [],
        "updates": 0,
        "focused_tile_index": -1,
        "focus_ring_visible": False,
        "tile_scale": 1.0,
        "tile_padding": 0,
        "grid_offset_x": 0,
        "grid_offset_y": 0,
        "thumbnail_size": 256,
        "current_index": 0,
    }
    base.update(kw)
    view = SimpleNamespace(**base)
    view.update = lambda: setattr(view, "updates", view.updates + 1)
    view._apply_color_label = view.applied_labels.append
    # Thumbnail-wall stand-ins for the keyboard-focus path. Width 800 / cell 256
    # → 3 columns; height 600 → roughly two rows visible.
    view.model = SimpleNamespace(images=images)
    view.width = lambda: 800
    view.height = lambda: 600
    view.devicePixelRatio = lambda: 1.0
    view._tile_renderer = SimpleNamespace(base_size=lambda: view.thumbnail_size or 256)
    view._input = SimpleNamespace(opened=[], toggled=[])
    view._input.enter_deep_zoom = view._input.opened.append
    view._input.toggle_tile_selection = view._input.toggled.append
    return view


def test_f8_toggles_osd():
    handler = KeyInputHandler(_view())
    consumed = handler._handle_builtin(Qt.Key.Key_F8, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    assert handler._view._show_osd is True
    assert handler._view._show_debug_hud is False


def test_ctrl_f8_toggles_debug_hud():
    handler = KeyInputHandler(_view())
    handler._handle_builtin(Qt.Key.Key_F8, Qt.KeyboardModifier.ControlModifier)
    assert handler._view._show_debug_hud is True
    assert handler._view._show_osd is False


def test_color_label_key_applies():
    view = _view()
    handler = KeyInputHandler(view)
    consumed = handler._handle_builtin(Qt.Key.Key_F1, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    assert view.applied_labels == ["red"]


def test_color_label_ignored_with_ctrl():
    view = _view()
    handler = KeyInputHandler(view)
    consumed = handler._handle_builtin(Qt.Key.Key_F2, Qt.KeyboardModifier.ControlModifier)
    assert consumed is False
    assert view.applied_labels == []


def test_escape_clears_tile_selection():
    view = _view(tile_grid_mode=True, selected_tiles={"a"}, tile_selection_mode=True)
    view.main_window.isFullScreen = lambda: False
    handler = KeyInputHandler(view)
    consumed = handler._handle_builtin(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    assert view.selected_tiles == set()
    assert view.tile_selection_mode is False


def test_escape_no_state_not_consumed():
    view = _view()
    view.main_window.isFullScreen = lambda: False
    handler = KeyInputHandler(view)
    consumed = handler._handle_builtin(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert consumed is False


def test_escape_exits_while_a_load_is_in_flight_with_no_image_yet():
    # Waiting on a promoted prefetch worker: deep_zoom/active worker are both
    # None but a load is pending. Escape must still bail back to the wall.
    view = _view(deep_zoom=None, active_deep_zoom_worker=None)
    view._deep_zoom_loading = "b.png"
    view.active_deep_zoom_preview_worker = None
    view.main_window.isFullScreen = lambda: False
    handler = KeyInputHandler(view)
    exited: list = []
    handler.exit_deep_zoom_to_grid = lambda: exited.append(True)
    consumed = handler._handle_builtin(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    assert exited == [True]


def test_escape_exits_during_the_progressive_preview_window():
    # 0–300 ms window: only the preview worker is set, deep_zoom still None.
    view = _view(deep_zoom=None, active_deep_zoom_worker=None)
    view._deep_zoom_loading = None
    view.active_deep_zoom_preview_worker = object()
    view.main_window.isFullScreen = lambda: False
    handler = KeyInputHandler(view)
    exited: list = []
    handler.exit_deep_zoom_to_grid = lambda: exited.append(True)
    consumed = handler._handle_builtin(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    assert exited == [True]


def test_arrow_moves_grid_focus_cursor():
    view = _view(tile_grid_mode=True, images=[f"{i}.png" for i in range(12)])
    handler = KeyInputHandler(view)
    # First Right focuses the first tile (cols=3 for width 800 / cell 256).
    consumed = handler._handle_builtin(Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    assert view.focused_tile_index == 0
    # Right steps one tile, Down moves a whole row.
    handler._handle_builtin(Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
    handler._handle_builtin(Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    assert view.focused_tile_index == 1 + 3


def test_arrow_focus_scrolls_wall_when_tile_offscreen():
    view = _view(tile_grid_mode=True, images=[f"{i}.png" for i in range(12)])
    handler = KeyInputHandler(view)
    # Walk the cursor down past the visible rows; the wall must scroll up
    # (negative offset) to keep the focused tile on screen.
    handler._handle_builtin(Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
    for _ in range(3):
        handler._handle_builtin(Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    assert view.focused_tile_index == 9
    assert view.grid_offset_y < 0


def test_arrow_on_empty_grid_is_a_no_op():
    view = _view(tile_grid_mode=True, images=[])
    handler = KeyInputHandler(view)
    consumed = handler._handle_builtin(Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    assert view.focused_tile_index == -1


def test_enter_opens_focused_tile():
    view = _view(tile_grid_mode=True, images=["a.png", "b.png", "c.png"],
                 focused_tile_index=2)
    handler = KeyInputHandler(view)
    consumed = handler._handle_builtin(Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    assert view._input.opened == ["c.png"]
    assert view._input.toggled == []


def test_enter_toggles_selection_in_selection_mode():
    view = _view(tile_grid_mode=True, tile_selection_mode=True,
                 images=["a.png", "b.png"], focused_tile_index=1)
    handler = KeyInputHandler(view)
    handler._handle_builtin(Qt.Key.Key_Enter, Qt.KeyboardModifier.NoModifier)
    assert view._input.toggled == ["b.png"]
    assert view._input.opened == []


def test_enter_without_focus_not_consumed():
    view = _view(tile_grid_mode=True, images=["a.png"], focused_tile_index=-1)
    handler = KeyInputHandler(view)
    assert handler._handle_builtin(
        Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier) is False


def test_enter_outside_grid_not_consumed():
    view = _view(tile_grid_mode=False, images=["a.png"], focused_tile_index=0)
    handler = KeyInputHandler(view)
    assert handler._handle_builtin(
        Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier) is False


def test_arrow_navigation_shows_focus_ring():
    view = _view(tile_grid_mode=True, images=["a.png", "b.png"])
    handler = KeyInputHandler(view)
    assert view.focus_ring_visible is False
    handler._handle_builtin(Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
    assert view.focus_ring_visible is True


def test_focus_current_if_valid_highlights_viewed_tile():
    view = _view(images=["a.png", "b.png", "c.png"], current_index=2)
    handler = KeyInputHandler(view)
    handler._focus_current_if_valid()
    assert view.focused_tile_index == 2


def test_focus_current_if_valid_keeps_ring_hidden():
    # Esc from deep zoom remembers the position for the next arrow press but
    # must not flash the amber ring at the user.
    view = _view(images=["a.png", "b.png"], current_index=1, focus_ring_visible=True)
    handler = KeyInputHandler(view)
    handler._focus_current_if_valid()
    assert view.focused_tile_index == 1
    assert view.focus_ring_visible is False


def test_focus_current_if_valid_clears_when_index_out_of_range():
    view = _view(images=["a.png"], current_index=5, focused_tile_index=0)
    handler = KeyInputHandler(view)
    handler._focus_current_if_valid()
    assert view.focused_tile_index == -1


def test_loupe_and_reading_keys_are_not_builtin_anymore():
    # L (loupe) and V (reading mode) are now configurable shortcut actions
    # dispatched via shortcut_manager, so _handle_builtin must NOT consume them.
    view = _view(deep_zoom=object())
    handler = KeyInputHandler(view)
    for key in (Qt.Key.Key_L, Qt.Key.Key_V, Qt.Key.Key_W):
        assert handler._handle_builtin(key, Qt.KeyboardModifier.NoModifier) is False


def test_non_builtin_key_returns_false():
    view = _view()
    handler = KeyInputHandler(view)
    assert handler._handle_builtin(Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier) is False


def _grid_restore_view(images, tile_cache, saved_state=None):
    """A minimal stub exercising only what ``_restore_grid_state`` touches."""
    view = SimpleNamespace(
        model=SimpleNamespace(images=list(images)),
        tile_cache=dict(tile_cache),
        tile_grid_mode=False,
        _saved_tile_state=saved_state,
        grid_offset_x=0,
        grid_offset_y=0,
        tile_scale=1.0,
        _reloads=[],
        _cleared=[],
    )
    view.load_tile_grid_async = lambda image_paths: view._reloads.append(list(image_paths))
    view._clear_deep_zoom = lambda: view._cleared.append(True)
    return view


class TestRestoreGridState:
    """Esc back to the wall must reload a cold cache, not paint placeholders."""

    def test_cold_cache_reloads_the_wall(self):
        view = _grid_restore_view(["a.png", "b.png"], {})
        KeyInputHandler(view)._restore_grid_state()
        assert view._reloads == [["a.png", "b.png"]]
        assert view._saved_tile_state is None

    def test_partially_warmed_cache_reloads(self):
        view = _grid_restore_view(["a.png", "b.png"], {"a.png": object()})
        KeyInputHandler(view)._restore_grid_state()
        assert view._reloads == [["a.png", "b.png"]]

    def test_warm_cache_restores_saved_offsets_without_reload(self):
        view = _grid_restore_view(
            ["a.png"],
            {"a.png": object()},
            saved_state={"grid_offset_x": 12, "grid_offset_y": 34, "tile_scale": 1.5},
        )
        KeyInputHandler(view)._restore_grid_state()
        assert view._reloads == []
        assert view._cleared == [True]
        assert view.tile_grid_mode is True
        assert (view.grid_offset_x, view.grid_offset_y, view.tile_scale) == (12, 34, 1.5)
        assert view._saved_tile_state is None

    def test_warm_empty_folder_does_not_reload(self):
        view = _grid_restore_view([], {})
        KeyInputHandler(view)._restore_grid_state()
        assert view._reloads == []
        assert view.tile_grid_mode is True
