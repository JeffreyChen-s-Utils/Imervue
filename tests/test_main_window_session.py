"""Regression tests for folder-session capture of the deep-zoom state.

``_save_current_folder_session`` is called unbound on a light duck-typed fake
so no GL-backed main window / viewer is constructed. The key assertion is that
the ``deep_zoom`` flag is written, so a relaunch can return to deep zoom
instead of the tile wall.
"""
from __future__ import annotations

from types import SimpleNamespace

import Imervue.Imervue_main_window as mod
from Imervue.Imervue_main_window import ImervueMainWindow


def _fake(*, deep_zoom_obj, tile_grid_mode):
    return SimpleNamespace(
        _current_view_folder=lambda: "/folder",
        _browse_mode="grid",
        _filter_state=lambda: {},
        _folder_view_sessions={},
        viewer=SimpleNamespace(
            scroll_y=0,
            selected_tiles=set(),
            _current_path=lambda: "/folder/a.png",
            deep_zoom=deep_zoom_obj,
            tile_grid_mode=tile_grid_mode,
        ),
    )


def test_session_records_deep_zoom_true_when_in_deep_zoom(monkeypatch):
    monkeypatch.setattr(mod, "write_user_setting", lambda: None)
    fake = _fake(deep_zoom_obj=object(), tile_grid_mode=False)
    ImervueMainWindow._save_current_folder_session(fake)
    assert fake._folder_view_sessions["/folder"]["deep_zoom"] is True
    assert fake._folder_view_sessions["/folder"]["current"] == "/folder/a.png"


def test_session_records_deep_zoom_false_on_the_tile_wall(monkeypatch):
    monkeypatch.setattr(mod, "write_user_setting", lambda: None)
    fake = _fake(deep_zoom_obj=None, tile_grid_mode=True)
    ImervueMainWindow._save_current_folder_session(fake)
    assert fake._folder_view_sessions["/folder"]["deep_zoom"] is False


def test_session_not_written_without_a_folder(monkeypatch):
    monkeypatch.setattr(mod, "write_user_setting", lambda: None)
    fake = _fake(deep_zoom_obj=object(), tile_grid_mode=False)
    fake._current_view_folder = lambda: ""
    ImervueMainWindow._save_current_folder_session(fake)
    assert fake._folder_view_sessions == {}
