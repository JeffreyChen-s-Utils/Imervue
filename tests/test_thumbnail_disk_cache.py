"""Tests for the persistent thumbnail disk cache."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.image import thumbnail_disk_cache as tdc


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Point the cache at a per-test temp directory."""
    target = tmp_path / "thumbs"
    monkeypatch.setattr(tdc, "_get_cache_dir", lambda: target)
    return target


@pytest.fixture
def source_image(tmp_path):
    """Write a small PNG to disk so _key() can stat it."""
    path = tmp_path / "src.png"
    arr = np.full((32, 32, 3), 128, dtype=np.uint8)
    Image.fromarray(arr).save(str(path))
    return str(path)


def _thumb(n: int = 32) -> np.ndarray:
    return np.full((n, n, 4), 200, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


class TestKey:
    def test_depends_on_path(self, tmp_path):
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        Image.fromarray(np.zeros((4, 4, 3), np.uint8)).save(str(a))
        Image.fromarray(np.zeros((4, 4, 3), np.uint8)).save(str(b))
        assert tdc.ThumbnailDiskCache._key(str(a), 128) != \
               tdc.ThumbnailDiskCache._key(str(b), 128)

    def test_depends_on_size(self, source_image):
        assert tdc.ThumbnailDiskCache._key(source_image, 128) != \
               tdc.ThumbnailDiskCache._key(source_image, 256)

    def test_depends_on_recipe_hash(self, source_image):
        assert tdc.ThumbnailDiskCache._key(source_image, 128, "rA") != \
               tdc.ThumbnailDiskCache._key(source_image, 128, "rB")

    def test_missing_file_returns_empty_string(self, tmp_path):
        ghost = tmp_path / "does_not_exist.png"
        assert tdc.ThumbnailDiskCache._key(str(ghost), 128) == ""


# ---------------------------------------------------------------------------
# Put / get round-trip
# ---------------------------------------------------------------------------


class TestPutGetRoundtrip:
    def test_rgba_round_trip(self, cache_dir, source_image):
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, _thumb())
        got = c.get(source_image, 128)
        assert got is not None
        assert got.shape == (32, 32, 4)
        assert got.dtype == np.uint8

    def test_rgb_is_normalised_to_rgba(self, cache_dir, source_image):
        rgb = np.full((32, 32, 3), 50, dtype=np.uint8)
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, rgb)
        got = c.get(source_image, 128)
        assert got.shape[2] == 4

    def test_grayscale_is_normalised_to_rgba(self, cache_dir, source_image):
        gray = np.full((32, 32), 77, dtype=np.uint8)
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, gray)
        got = c.get(source_image, 128)
        assert got.shape[2] == 4

    def test_miss_returns_none(self, cache_dir, source_image):
        c = tdc.ThumbnailDiskCache()
        assert c.get(source_image, 128) is None

    def test_recipe_hash_separates_entries(self, cache_dir, source_image):
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, _thumb(), recipe_hash="A")
        assert c.get(source_image, 128, recipe_hash="A") is not None
        assert c.get(source_image, 128, recipe_hash="B") is None


# ---------------------------------------------------------------------------
# Bookkeeping
# ---------------------------------------------------------------------------


class TestBookkeeping:
    def test_total_bytes_grows_after_put(self, cache_dir, source_image):
        c = tdc.ThumbnailDiskCache()
        before = c.total_bytes()
        c.put(source_image, 128, _thumb())
        assert c.total_bytes() > before

    def test_clear_removes_files(self, cache_dir, source_image):
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, _thumb())
        assert any(cache_dir.iterdir())
        c.clear()
        assert list(cache_dir.iterdir()) == []
        assert c.total_bytes() == 0


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def _make_sources(self, tmp_path: Path, count: int) -> list[str]:
        paths = []
        for i in range(count):
            p = tmp_path / f"src_{i}.png"
            # Use different pixel values so each image has a distinct mtime/size.
            arr = np.full((32, 32, 3), (i * 7) % 255, dtype=np.uint8)
            Image.fromarray(arr).save(str(p))
            paths.append(str(p))
        return paths

    def test_over_budget_triggers_eviction(self, cache_dir, tmp_path):
        c = tdc.ThumbnailDiskCache(max_total_bytes=4000)
        sources = self._make_sources(tmp_path, 20)
        for src in sources:
            c.put(src, 128, _thumb(64))
        # After inserting >>budget worth of entries, the cache must stay
        # below the high-water mark (max_bytes) and around the low-water
        # mark (EVICT_RATIO * max_bytes).
        assert c.total_bytes() <= 4000

    def test_rescan_initial_eviction_when_lowered(
        self, cache_dir, tmp_path, source_image,
    ):
        big = tdc.ThumbnailDiskCache(max_total_bytes=10 * 1024 * 1024)
        big.put(source_image, 128, _thumb(128))
        big.put(source_image, 256, _thumb(128))
        del big

        # New instance with a tiny limit must evict on scan.
        tiny = tdc.ThumbnailDiskCache(max_total_bytes=1)
        assert tiny.total_bytes() <= 1


# ---------------------------------------------------------------------------
# Corruption handling
# ---------------------------------------------------------------------------


class TestCorruption:
    def test_unreadable_cache_file_is_purged(
        self, cache_dir, source_image,
    ):
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, _thumb())

        # Corrupt every file in the cache dir.
        for f in cache_dir.iterdir():
            f.write_bytes(b"not a png")

        assert c.get(source_image, 128) is None
        # Corrupted files are evicted from bookkeeping.
        assert c.total_bytes() == 0


class TestLegacyCleanup:
    def test_npy_files_are_removed_on_scan(self, cache_dir):
        cache_dir.mkdir(parents=True, exist_ok=True)
        legacy = cache_dir / "abc123.npy"
        legacy.write_bytes(b"legacy payload")
        _c = tdc.ThumbnailDiskCache()
        assert not legacy.exists()


class TestCacheDirResolution:
    def test_returns_pathlike_object(self, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", r"C:\fake\local")
        result = tdc._get_cache_dir()
        assert isinstance(result, Path)
        # Ends with the documented subpath on Windows, or the XDG-ish one
        # on other platforms — either way the parent chain reflects Imervue.
        assert "Imervue" in str(result) or "imervue" in str(result)
