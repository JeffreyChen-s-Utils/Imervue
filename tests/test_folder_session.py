"""Tests for the folder-session deep-zoom restore decision.

``deep_zoom_restore_target`` / ``should_retry_deep_zoom_restore`` are pure —
they decide which image (if any) to reopen in deep zoom on startup and whether
to keep waiting for the async folder scan — so they are tested without the
GL-backed viewer.
"""
from __future__ import annotations

from Imervue.sessions.folder_session import (
    deep_zoom_restore_target,
    should_retry_deep_zoom_restore,
)

_IMAGES = ["a.png", "b.png", "c.png"]


def test_returns_current_image_when_deep_zoom_saved():
    state = {"deep_zoom": True, "current": "b.png"}
    assert deep_zoom_restore_target(state, _IMAGES) == "b.png"


def test_none_when_flag_unset():
    assert deep_zoom_restore_target({"deep_zoom": False, "current": "b.png"}, _IMAGES) is None
    assert deep_zoom_restore_target({}, _IMAGES) is None


def test_none_when_no_current_stored():
    assert deep_zoom_restore_target({"deep_zoom": True}, _IMAGES) is None
    assert deep_zoom_restore_target({"deep_zoom": True, "current": ""}, _IMAGES) is None


def test_none_when_target_not_in_images_yet():
    # Scan hasn't surfaced the target (or it was deleted) → don't open it.
    assert deep_zoom_restore_target({"deep_zoom": True, "current": "z.png"}, _IMAGES) is None
    assert deep_zoom_restore_target({"deep_zoom": True, "current": "b.png"}, []) is None


def test_retry_while_target_missing_and_flag_set():
    # Empty list = scan still running → keep waiting.
    assert should_retry_deep_zoom_restore({"deep_zoom": True, "current": "b.png"}, []) is True
    assert should_retry_deep_zoom_restore({"deep_zoom": True, "current": "z.png"}, _IMAGES) is True


def test_no_retry_once_target_present():
    assert should_retry_deep_zoom_restore({"deep_zoom": True, "current": "b.png"}, _IMAGES) is False


def test_no_retry_when_flag_unset_or_no_target():
    assert should_retry_deep_zoom_restore({"deep_zoom": False, "current": "b.png"}, []) is False
    assert should_retry_deep_zoom_restore({"deep_zoom": True, "current": ""}, []) is False
