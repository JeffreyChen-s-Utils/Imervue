"""ImageMetadataIndex.move must not cache a transient stat-failure sentinel.

get() already guards this (a mid-move / AV-locked read returns cacheable=False
and is not stored); move() discarded that flag and cached the sentinel, dropping
the renamed file from the date/size filters for the whole session.
"""
from __future__ import annotations

from Imervue.image.browser_state import ImageMetadataIndex


def test_move_does_not_cache_a_non_cacheable_read(monkeypatch):
    idx = ImageMetadataIndex()
    idx._items["/old"] = object()   # a previously cached meta
    monkeypatch.setattr(
        ImageMetadataIndex, "_read",
        staticmethod(lambda path: (object(), False)),   # transient failure
    )
    idx.move("/old", "/new")
    assert "/old" not in idx._items
    assert "/new" not in idx._items   # sentinel not cached -> re-read next time


def test_move_caches_a_good_read(monkeypatch):
    idx = ImageMetadataIndex()
    idx._items["/old"] = object()
    good = object()
    monkeypatch.setattr(
        ImageMetadataIndex, "_read",
        staticmethod(lambda path: (good, True)),   # cacheable
    )
    idx.move("/old", "/new")
    assert idx._items["/new"] is good


def test_move_carries_the_hash(monkeypatch):
    idx = ImageMetadataIndex()
    idx._items["/old"] = object()
    idx._hashes["/old"] = "abc123"
    monkeypatch.setattr(
        ImageMetadataIndex, "_read", staticmethod(lambda path: (object(), True)))
    idx.move("/old", "/new")
    assert idx._hashes.get("/new") == "abc123"
    assert "/old" not in idx._hashes
