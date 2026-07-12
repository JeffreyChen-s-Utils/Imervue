"""Tests for the folder-session deep-zoom restore decision.

``deep_zoom_restore_target`` is pure — it decides which image (if any) to
reopen in deep zoom on startup — so it is tested without the GL-backed viewer.
"""
from __future__ import annotations

from Imervue.sessions.folder_session import deep_zoom_restore_target

_IMAGES = ["a.png", "b.png", "c.png"]


def test_returns_current_image_when_deep_zoom_saved():
    state = {"deep_zoom": True}
    assert deep_zoom_restore_target(state, _IMAGES, 1) == "b.png"


def test_none_when_flag_unset():
    assert deep_zoom_restore_target({"deep_zoom": False}, _IMAGES, 1) is None
    assert deep_zoom_restore_target({}, _IMAGES, 1) is None


def test_none_when_folder_empty():
    assert deep_zoom_restore_target({"deep_zoom": True}, [], 0) is None


def test_none_when_index_out_of_range():
    # Image deleted between sessions → index no longer valid → stay on the wall.
    assert deep_zoom_restore_target({"deep_zoom": True}, _IMAGES, 5) is None
    assert deep_zoom_restore_target({"deep_zoom": True}, _IMAGES, -1) is None


def test_first_and_last_indices_are_in_range():
    assert deep_zoom_restore_target({"deep_zoom": True}, _IMAGES, 0) == "a.png"
    assert deep_zoom_restore_target({"deep_zoom": True}, _IMAGES, 2) == "c.png"
