"""Tests for metadata-completeness auditing."""
from __future__ import annotations

from Imervue.library import metadata_audit
from Imervue.library.metadata_audit import missing_fields, paths_missing


def test_missing_fields_returns_absent():
    presence = {"location": True, "keywords": False, "title": True, "creator": False}
    assert missing_fields(presence, ["location", "keywords", "creator"]) == [
        "keywords", "creator"]


def test_missing_fields_none_when_all_present():
    assert missing_fields({"keywords": True}, ["keywords"]) == []


def test_paths_missing_filters(monkeypatch):
    presence = {
        "a.jpg": {"keywords": True, "location": True, "title": True, "creator": True},
        "b.jpg": {"keywords": False, "location": True, "title": True, "creator": True},
    }
    monkeypatch.setattr(metadata_audit, "image_metadata_presence", presence.get)
    assert paths_missing(["a.jpg", "b.jpg"], ["keywords"]) == ["b.jpg"]


def test_paths_missing_ignores_unknown_field():
    assert paths_missing(["a.jpg"], ["bogus"]) == []
