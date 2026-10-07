"""Tests for the persistent thumbnail disk cache."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.image import thumbnail_disk_cache as tdc


@pytest.fixture(autouse=True)
def _join_inventories(monkeypatch):
    original, instances = tdc.ThumbnailDiskCache.__init__, []
    def initialize(cache, *args, **kwargs):
        original(cache, *args, **kwargs)
        instances.append(cache)
    monkeypatch.setattr(tdc.ThumbnailDiskCache, "__init__", initialize)
    yield
    for cache in instances:
        cache.close()


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

    def test_depends_on_the_key_version(self, source_image, monkeypatch):
        """Bumping the version retires entries baked the old way (v2: EXIF-upright)."""
        before = tdc.ThumbnailDiskCache._key(source_image, 128)
        monkeypatch.setattr(tdc, "_KEY_VERSION", tdc._KEY_VERSION + 1)
        assert tdc.ThumbnailDiskCache._key(source_image, 128) != before

    def test_a_raw_entry_has_its_own_version(self, tmp_path, monkeypatch):
        """Portrait RAW previews were cached on their side: only RAW entries are retired."""
        raw = tmp_path / "IMG_1.CR3"
        raw.write_bytes(b"x")
        raw_before = tdc.ThumbnailDiskCache._key(str(raw), 128)
        png = tmp_path / "a.png"
        Image.fromarray(np.zeros((4, 4, 3), np.uint8)).save(str(png))
        png_before = tdc.ThumbnailDiskCache._key(str(png), 128)
        monkeypatch.setattr(tdc, "_RAW_KEY_VERSION", tdc._RAW_KEY_VERSION + 1)
        assert tdc.ThumbnailDiskCache._key(str(raw), 128) != raw_before
        assert tdc.ThumbnailDiskCache._key(str(png), 128) == png_before

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

    def test_file_overwrite_invalidates_same_path_entry(self, cache_dir, source_image):
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, _thumb())
        Path(source_image).write_bytes(b"different payload with different size")
        assert c.get(source_image, 128) is None


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
        big.close()

        # New instance with a tiny limit must evict on scan.
        tiny = tdc.ThumbnailDiskCache(max_total_bytes=1)
        assert tiny.wait_ready(5)
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
        cache = tdc.ThumbnailDiskCache()
        assert cache.wait_ready(5)
        assert not legacy.exists()


class TestCacheDirResolution:
    def test_returns_pathlike_object(self, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", r"C:\fake\local")
        result = tdc._get_cache_dir()
        assert isinstance(result, Path)
        # Ends with the documented subpath on Windows, or the XDG-ish one
        # on other platforms — either way the parent chain reflects Imervue.
        assert "Imervue" in str(result) or "imervue" in str(result)


# ---------------------------------------------------------------------------
# Narrowed failure handling — expected failures are skipped, bugs propagate
# ---------------------------------------------------------------------------


class TestPutFailures:
    @pytest.mark.parametrize("bad", [
        "not an array",                                   # no dtype -> AttributeError
        np.zeros((4,), dtype=np.uint8),                   # 1-D -> IndexError on shape[2]
        np.zeros((4, 4, 2), dtype=np.uint8),              # 2 channels -> ValueError
        np.zeros((4, 4, 5), dtype=np.uint8),              # 5 channels -> ValueError
    ])
    def test_non_image_array_is_ignored(self, cache_dir, source_image, bad):
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, bad)
        assert c.get(source_image, 128) is None
        assert c.total_bytes() == 0

    @pytest.mark.parametrize("shape", [(8, 8), (8, 8, 3), (8, 8, 4)])
    @pytest.mark.filterwarnings("error:'mode' parameter:DeprecationWarning")
    def test_supported_shapes_are_cached_as_rgba(self, cache_dir, source_image, shape):
        """No Pillow-13-removed ``mode`` conversion on the way in."""
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, np.full(shape, 200, dtype=np.uint8))
        got = c.get(source_image, 128)
        assert got.shape == (8, 8, 4)
        assert got[0, 0].tolist() == [200, 200, 200, 255 if len(shape) < 3 or shape[2] == 3 else 200]

    def test_write_failure_is_ignored(self, cache_dir, source_image, monkeypatch):
        def fail_save(self, *_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(Image.Image, "save", fail_save)
        c = tdc.ThumbnailDiskCache()
        c.put(source_image, 128, _thumb())
        assert c.total_bytes() == 0

    def test_unexpected_write_error_propagates(self, cache_dir, source_image, monkeypatch):
        def boom(self, *_a, **_k):
            raise RuntimeError("bug")

        monkeypatch.setattr(Image.Image, "save", boom)
        c = tdc.ThumbnailDiskCache()
        with pytest.raises(RuntimeError):
            c.put(source_image, 128, _thumb())


def test_a_grey_thumbnail_baked_before_the_grey_fixes_is_not_served(cache_dir, tmp_path, monkeypatch):
    """A 16-bit grey scan was cached almost white; the fix must not keep serving that copy."""
    scan = tmp_path / "scan.png"
    Image.new("I;16", (32, 32), 32896).save(scan)
    shipped = tdc._KEY_VERSION
    monkeypatch.setattr(tdc, "_KEY_VERSION", 3)          # the version those were baked under
    cache = tdc.ThumbnailDiskCache()
    cache.put(str(scan), 128, np.full((32, 32, 4), 255, dtype=np.uint8))
    assert cache.get(str(scan), 128) is not None
    monkeypatch.setattr(tdc, "_KEY_VERSION", shipped)   # the cache folder stays the test's
    assert shipped > 3
    assert tdc.ThumbnailDiskCache().get(str(scan), 128) is None


def _pause_inventory(monkeypatch):
    from threading import Event
    entered, release = Event(), Event()
    original = tdc.ThumbnailDiskCache._index_entry
    def paused(cache, entry, generation):
        # Capture the old stat before a foreground put/get/clear changes the file.
        if entry.name.endswith(".png"):
            observed = entry.stat(follow_symlinks=False)
            entered.set()
            release.wait(5)
            class Entry:
                name = entry.name
                def is_file(self, **_kwargs):
                    return True
                def stat(self, **_kwargs):
                    return observed
            return original(cache, Entry(), generation)
        return original(cache, entry, generation)
    monkeypatch.setattr(tdc.ThumbnailDiskCache, "_index_entry", paused)
    return entered, release


def test_reads_and_rewrites_win_over_stale_inventory(cache_dir, source_image, monkeypatch):
    seed = tdc.ThumbnailDiskCache()
    seed.put(source_image, 128, _thumb())
    seed.close()
    entered, release = _pause_inventory(monkeypatch)
    cache = tdc.ThumbnailDiskCache()
    try:
        assert entered.wait(2) and not cache.wait_ready(0)
        assert cache.get(source_image, 128).shape == (32, 32, 4)
        cache.put(source_image, 128, _thumb(64))
        assert cache.get(source_image, 128).shape == (64, 64, 4)
        release.set()
        assert cache.wait_ready(3)
        assert cache.total_bytes() == sum(p.stat().st_size for p in cache_dir.glob("*.png"))
        assert len(cache._files) == 1
    finally:
        release.set()
        cache.close()


@pytest.mark.parametrize("action", ["clear", "corrupt"])
def test_stale_scan_cannot_resurrect_removed_files(cache_dir, source_image, monkeypatch, action):
    seed = tdc.ThumbnailDiskCache()
    seed.put(source_image, 128, _thumb())
    seed.close()
    entered, release = _pause_inventory(monkeypatch)
    cache = tdc.ThumbnailDiskCache()
    try:
        assert entered.wait(2)
        if action == "clear":
            cache.clear()
        else:
            next(cache_dir.glob("*.png")).write_bytes(b"corrupt")
            assert cache.get(source_image, 128) is None
        release.set()
        assert cache.wait_ready(3)
        assert cache.total_bytes() == 0 and not cache._files
        assert not list(cache_dir.glob("*.png"))
    finally:
        release.set()
        cache.close()


def test_scan_respects_quota_and_cleans_legacy_files(cache_dir, source_image):
    seed = tdc.ThumbnailDiskCache()
    seed.put(source_image, 128, _thumb())
    seed.put(source_image, 256, _thumb())
    seed.close()
    (cache_dir / "old.npy").write_bytes(b"legacy")
    (cache_dir / "unmanaged.txt").write_bytes(b"keep")
    (cache_dir / "directory.png").mkdir()
    cache = tdc.ThumbnailDiskCache(max_total_bytes=1)
    assert cache.wait_ready(3)
    assert cache.total_bytes() == 0
    assert not (cache_dir / "old.npy").exists()
    assert (cache_dir / "unmanaged.txt").read_bytes() == b"keep"
    assert (cache_dir / "directory.png").is_dir()


def test_clear_failure_retains_actual_accounting(cache_dir, source_image, monkeypatch):
    cache = tdc.ThumbnailDiskCache()
    cache.put(source_image, 128, _thumb())
    assert cache.wait_ready(3)
    real = Path.unlink
    def locked(path, **kwargs):
        if path.suffix == ".png":
            raise PermissionError("locked")
        return real(path, **kwargs)
    monkeypatch.setattr(Path, "unlink", locked)
    cache.clear()
    assert cache.total_bytes() == sum(p.stat().st_size for p in cache_dir.glob("*.png"))
    assert cache.total_bytes() > 0


def test_failed_atomic_rewrite_keeps_previous_thumbnail(cache_dir, source_image, monkeypatch):
    cache = tdc.ThumbnailDiskCache()
    cache.put(source_image, 128, _thumb())
    assert cache.wait_ready(3)
    before = cache.total_bytes()
    def fail(image, stage, **_kwargs):
        Path(stage).write_bytes(b"partial")
        raise OSError("disk full")
    monkeypatch.setattr(Image.Image, "save", fail)
    cache.put(source_image, 128, _thumb(64))
    assert cache.get(source_image, 128).shape == (32, 32, 4)
    assert cache.total_bytes() == before
    assert len(list(cache_dir.iterdir())) == 1


def test_negative_quota_and_inventory_error(cache_dir, monkeypatch, caplog):
    with pytest.raises(ValueError, match="nonnegative"):
        tdc.ThumbnailDiskCache(-1)
    def fail(_path):
        raise OSError("offline")
    monkeypatch.setattr(tdc.os, "scandir", fail)
    with caplog.at_level("DEBUG", logger="Imervue.thumbnail_cache"):
        cache = tdc.ThumbnailDiskCache()
        assert cache.wait_ready(3) and cache.total_bytes() == 0
    assert "offline" in caplog.text


def test_corruption_error_cannot_delete_parallel_valid_rewrite(cache_dir, source_image, monkeypatch):
    cache = tdc.ThumbnailDiskCache()
    cache.put(source_image, 128, _thumb())
    assert cache.wait_ready(3)
    original = Image.open
    def raced(*_args, **_kwargs):
        cache.put(source_image, 128, _thumb(64))
        raise OSError("old corrupt image")
    monkeypatch.setattr(Image, "open", raced)
    assert cache.get(source_image, 128) is None
    monkeypatch.setattr(Image, "open", original)
    assert cache.get(source_image, 128).shape == (64, 64, 4)
    assert cache.total_bytes() == sum(p.stat().st_size for p in cache_dir.glob("*.png"))


def test_locked_corrupt_and_legacy_files_remain_accounted(cache_dir, source_image, monkeypatch):
    cache = tdc.ThumbnailDiskCache()
    cache.put(source_image, 128, _thumb())
    assert cache.wait_ready(3)
    next(cache_dir.glob("*.png")).write_bytes(b"bad")
    (cache_dir / "old.npy").write_bytes(b"legacy")
    real = Path.unlink
    def locked(path, **kwargs):
        if path.suffix in {".png", ".npy"}:
            raise PermissionError("locked")
        return real(path, **kwargs)
    monkeypatch.setattr(Path, "unlink", locked)
    assert cache.get(source_image, 128) is None
    assert cache.total_bytes() == 3
    resumed = tdc.ThumbnailDiskCache()
    assert resumed.wait_ready(3)
    assert resumed.total_bytes() == 9


def test_new_put_after_clear_survives_old_scanner(cache_dir, source_image, monkeypatch):
    seed = tdc.ThumbnailDiskCache()
    seed.put(source_image, 128, _thumb())
    seed.close()
    entered, release = _pause_inventory(monkeypatch)
    cache = tdc.ThumbnailDiskCache()
    try:
        assert entered.wait(2)
        cache.clear()
        cache.put(source_image, 128, _thumb(64))
        release.set()
        assert cache.wait_ready(3)
        assert cache.get(source_image, 128).shape == (64, 64, 4)
        assert cache.total_bytes() == sum(p.stat().st_size for p in cache_dir.glob("*.png"))
    finally:
        release.set()
        cache.close()


def test_unexpected_inventory_error_is_logged_and_finishes(cache_dir, monkeypatch, caplog):
    def bug(_path):
        raise RuntimeError("inventory bug")
    monkeypatch.setattr(tdc.os, "scandir", bug)
    cache = tdc.ThumbnailDiskCache()
    assert cache.wait_ready(3)
    assert "inventory failed unexpectedly" in caplog.text
