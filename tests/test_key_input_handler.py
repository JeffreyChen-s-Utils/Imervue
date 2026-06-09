"""Tests for KeyInputHandler — keyboard routing (no shortcut dispatch path).

Covers the hard-wired keys: F8 HUD toggle, F1-F5 colour labels, Escape
handling, and arrow-key navigation. A fake view records the effects.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt

from Imervue.gpu_image_view.key_input_handler import KeyInputHandler


def _view(**kw):
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
    }
    base.update(kw)
    view = SimpleNamespace(**base)
    view.update = lambda: setattr(view, "updates", view.updates + 1)
    view._apply_color_label = view.applied_labels.append
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


def test_arrow_scrolls_grid():
    view = _view(tile_grid_mode=True, thumbnail_size=256, grid_offset_x=0, grid_offset_y=0)
    view.devicePixelRatio = lambda: 1.0
    handler = KeyInputHandler(view)
    consumed = handler._handle_builtin(Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
    assert consumed is True
    # Up → positive y move_step (256).
    assert view.grid_offset_y == 256


def test_non_builtin_key_returns_false():
    view = _view()
    handler = KeyInputHandler(view)
    assert handler._handle_builtin(Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier) is False
