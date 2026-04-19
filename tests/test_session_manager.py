"""Tests for session capture / save / load / restore."""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def sm():
    from Imervue.sessions import session_manager as m
    return m


class _FakeModel:
    def __init__(self, images):
        self.images = list(images)


class _FakeViewer:
    def __init__(self, images=(), current_index=-1, selected=()):
        self.model = _FakeModel(images)
        self.current_index = current_index
        self.selected_tiles = set(selected)
        self.tile_grid_mode = False


class _FakeTabBar:
    def __init__(self, idx=0):
        self._idx = idx

    def currentIndex(self):  # NOSONAR:python:S100 - fakes Qt QTabBar.currentIndex camelCase API
        return self._idx


class _FakeUI:
    def __init__(self, viewer, tabs=(), tab_idx=0):
        self.viewer = viewer
        self._image_tabs = list(tabs)
        self._tab_bar = _FakeTabBar(tab_idx)


class TestCapture:
    def test_capture_empty_ui(self, sm):
        ui = _FakeUI(_FakeViewer())
        snap = sm.capture_session(ui)
        assert snap["version"] == sm.SESSION_VERSION
        assert snap["tabs"] == []
        assert snap["current_image"] == ""
        assert snap["selection"] == []

    def test_capture_current_image_from_index(self, sm):
        ui = _FakeUI(_FakeViewer(images=["/a.jpg", "/b.jpg"], current_index=1))
        snap = sm.capture_session(ui)
        assert snap["current_image"] == "/b.jpg"

    def test_capture_rejects_invalid_index(self, sm):
        ui = _FakeUI(_FakeViewer(images=["/a.jpg"], current_index=5))
        snap = sm.capture_session(ui)
        assert snap["current_image"] == ""

    def test_capture_selection_only_strings(self, sm):
        viewer = _FakeViewer(selected={"/a.jpg", 42, "/b.jpg"})
        ui = _FakeUI(viewer)
        snap = sm.capture_session(ui)
        assert set(snap["selection"]) == {"/a.jpg", "/b.jpg"}


class TestSaveLoad:
    def test_save_adds_extension(self, sm, tmp_path):
        ui = _FakeUI(_FakeViewer())
        written = sm.save_session_to_path(ui, tmp_path / "work")
        assert str(written).endswith(sm.SESSION_EXT)
        assert written.exists()

    def test_load_roundtrip(self, sm, tmp_path):
        ui = _FakeUI(_FakeViewer(images=["/a.jpg"], current_index=0))
        written = sm.save_session_to_path(ui, tmp_path / "work")
        data = sm.load_session_from_path(written)
        assert data["current_image"] == "/a.jpg"

    def test_load_rejects_wrong_version(self, sm, tmp_path):
        bad = tmp_path / "wrong.json"
        bad.write_text(json.dumps({"version": 999}))
        with pytest.raises(ValueError):
            sm.load_session_from_path(bad)


class TestSanitize:
    def test_strips_control_chars_from_paths(self, sm, tmp_path):
        payload = {
            "version": sm.SESSION_VERSION,
            "current_image": "/a/b\x00c.jpg",
            "selection": ["/ok.jpg", "bad\nname.jpg"],
            "tabs": [{"path": "/ok.jpg", "title": "hi"}],
        }
        f = tmp_path / "s.json"
        f.write_text(json.dumps(payload))
        data = sm.load_session_from_path(f)
        assert data["current_image"] == ""
        assert data["selection"] == ["/ok.jpg"]

    def test_rejects_non_string_paths(self, sm, tmp_path):
        payload = {
            "version": sm.SESSION_VERSION,
            "current_image": 42,
            "selection": [None, "/good.jpg"],
        }
        f = tmp_path / "s.json"
        f.write_text(json.dumps(payload))
        data = sm.load_session_from_path(f)
        assert data["current_image"] == ""
        assert data["selection"] == ["/good.jpg"]

    def test_title_is_clamped(self, sm, tmp_path):
        payload = {
            "version": sm.SESSION_VERSION,
            "tabs": [{"path": "/x.jpg", "title": "t" * 10000}],
        }
        f = tmp_path / "s.json"
        f.write_text(json.dumps(payload))
        data = sm.load_session_from_path(f)
        assert len(data["tabs"][0]["title"]) <= 256
