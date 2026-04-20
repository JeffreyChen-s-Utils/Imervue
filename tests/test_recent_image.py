"""Tests for recent folder/image tracking with configurable cap."""
from __future__ import annotations

import pytest

from Imervue.user_settings import recent_image as ri


@pytest.fixture
def usd(monkeypatch):
    """Private user_setting_dict view + no-op schedule_save for each test."""
    from Imervue.user_settings import user_setting_dict as usd_mod

    store: dict = {
        "user_recent_folders": [],
        "user_recent_images": [],
    }
    monkeypatch.setattr(usd_mod, "user_setting_dict", store, raising=True)
    monkeypatch.setattr(usd_mod, "schedule_save", lambda: None, raising=True)
    return store


class TestMaxRecent:
    def test_default_when_unset(self, usd):
        assert ri._max_recent() == ri.DEFAULT_MAX_RECENT

    def test_custom_value_respected(self, usd):
        usd["max_recent"] = 25
        assert ri._max_recent() == 25

    def test_non_integer_falls_back_to_default(self, usd):
        usd["max_recent"] = "not a number"
        assert ri._max_recent() == ri.DEFAULT_MAX_RECENT

    def test_below_floor_is_clamped(self, usd):
        usd["max_recent"] = 0
        assert ri._max_recent() == 1

    def test_above_ceiling_is_clamped(self, usd):
        usd["max_recent"] = 10000
        assert ri._max_recent() == 200


class TestSetMaxRecent:
    def test_persists_to_settings(self, usd):
        ri.set_max_recent(30)
        assert usd["max_recent"] == 30

    def test_clamps_low_value(self, usd):
        ri.set_max_recent(-5)
        assert usd["max_recent"] == 1

    def test_clamps_high_value(self, usd):
        ri.set_max_recent(9999)
        assert usd["max_recent"] == 200

    def test_trims_existing_lists(self, usd):
        usd["user_recent_folders"] = [f"/p{i}" for i in range(20)]
        usd["user_recent_images"] = [f"/i{i}.jpg" for i in range(20)]
        ri.set_max_recent(5)
        assert len(usd["user_recent_folders"]) == 5
        assert len(usd["user_recent_images"]) == 5


class TestAddRecentFolder:
    def test_prepends_new_entry(self, usd):
        ri.add_recent_folder("/a")
        ri.add_recent_folder("/b")
        assert usd["user_recent_folders"] == ["/b", "/a"]

    def test_moves_existing_to_front(self, usd):
        ri.add_recent_folder("/a")
        ri.add_recent_folder("/b")
        ri.add_recent_folder("/a")
        assert usd["user_recent_folders"] == ["/a", "/b"]

    def test_respects_cap(self, usd):
        usd["max_recent"] = 3
        for p in ("/1", "/2", "/3", "/4", "/5"):
            ri.add_recent_folder(p)
        assert usd["user_recent_folders"] == ["/5", "/4", "/3"]


class TestAddRecentImage:
    def test_prepends_and_dedupes(self, usd):
        ri.add_recent_image("/a.jpg")
        ri.add_recent_image("/b.jpg")
        ri.add_recent_image("/a.jpg")
        assert usd["user_recent_images"] == ["/a.jpg", "/b.jpg"]

    def test_respects_cap(self, usd):
        usd["max_recent"] = 2
        for p in ("/1.jpg", "/2.jpg", "/3.jpg"):
            ri.add_recent_image(p)
        assert usd["user_recent_images"] == ["/3.jpg", "/2.jpg"]


class TestClearRecent:
    def test_empties_both_lists(self, usd):
        usd["user_recent_folders"] = ["/a", "/b"]
        usd["user_recent_images"] = ["/x.jpg"]
        ri.clear_recent()
        assert usd["user_recent_folders"] == []
        assert usd["user_recent_images"] == []
