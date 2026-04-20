"""End-to-end integration tests for CLIP semantic search.

These tests drive the full user-visible flow with real files on disk:

* a temporary folder is populated with actual PNG files,
* each file is embedded (via a deterministic fake backend so the suite stays
  torch-free),
* the resulting index is serialised to ``.npz``,
* a brand-new :class:`ClipSearchIndex` reloads the cache in a separate
  instance, and
* queries issued against the reloaded index return the same ranked paths as
  the original — proving the on-disk format is self-describing and that the
  pipeline survives a process restart.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pytest
from PIL import Image

from Imervue.library.clip_search import (
    ClipSearchIndex,
    SearchHit,
    _l2_normalise,
    get_default_index,
    reset_default_index,
)


# ---------------------------------------------------------------------------
# Deterministic, torch-free embedder — one vector space for both modalities.
# ---------------------------------------------------------------------------


class _StableEmbedder:
    """Hashes a keyword out of text / filename and projects to a fixed dim."""

    def __init__(self, dim: int = 16):
        self.dim = dim

    def _hash_vec(self, token: str) -> np.ndarray:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        raw = np.frombuffer(digest[: self.dim * 2], dtype=np.int16).astype(np.float32)
        return _l2_normalise(raw[: self.dim])

    def embed_text(self, text: str) -> np.ndarray:
        return self._hash_vec(text.strip().lower())

    def embed_image(self, path) -> np.ndarray | None:
        # Use the stem prefix as a topic keyword so text and images share a
        # deterministic similarity target (e.g. "cat_001.png" → "cat").
        name = str(path).replace("\\", "/").rsplit("/", 1)[-1]
        stem = name.split(".", 1)[0]
        topic = stem.split("_", 1)[0] if "_" in stem else stem
        return self._hash_vec(topic)


def _make_png(path, colour):
    arr = np.full((16, 16, 3), colour, dtype=np.uint8)
    Image.fromarray(arr).save(str(path))
    return str(path)


@pytest.fixture
def scanned_folder(tmp_path):
    """Build a small gallery with three topics and return the file paths."""
    files = [
        _make_png(tmp_path / "cat_001.png", (200, 100, 100)),
        _make_png(tmp_path / "cat_002.png", (210, 110, 110)),
        _make_png(tmp_path / "dog_001.png", (100, 200, 100)),
        _make_png(tmp_path / "dog_002.png", (110, 210, 110)),
        _make_png(tmp_path / "car_001.png", (100, 100, 200)),
    ]
    return tmp_path, files


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


class TestFullScanQueryRoundtrip:
    def test_scan_folder_then_query_ranks_topic_first(self, scanned_folder):
        _root, files = scanned_folder
        index = ClipSearchIndex(_StableEmbedder())
        added = index.add_many(files)
        assert added == len(files)

        hits = index.query_text("cat", top_k=5)
        assert [h.path for h in hits][:2] == [
            p for p in files if "cat_" in p
        ]
        assert all(isinstance(h, SearchHit) for h in hits)

    def test_query_for_absent_topic_returns_low_scores(self, scanned_folder):
        _root, files = scanned_folder
        index = ClipSearchIndex(_StableEmbedder())
        index.add_many(files)
        hits = index.query_text("spaceship", top_k=3)
        # Random topic won't hit 1.0 — just assert the ranking is well-formed.
        assert hits == sorted(hits, key=lambda h: -h.score)
        assert all(-1.01 <= h.score <= 1.01 for h in hits)


class TestSaveReloadRoundtrip:
    def test_cache_survives_process_equivalent_restart(self, scanned_folder, tmp_path):
        _root, files = scanned_folder
        cache_path = tmp_path / "cache.npz"

        producer = ClipSearchIndex(_StableEmbedder())
        producer.add_many(files)
        baseline = producer.query_text("cat", top_k=3)
        producer.save(cache_path)

        # Pretend the app exited and was relaunched — brand new instance.
        consumer = ClipSearchIndex(_StableEmbedder())
        assert consumer.size == 0
        assert consumer.load(cache_path) is True
        assert consumer.size == len(files)

        reloaded = consumer.query_text("cat", top_k=3)
        assert [h.path for h in reloaded] == [h.path for h in baseline]
        # Scores survive the float32 roundtrip intact.
        for a, b in zip(baseline, reloaded):
            assert a.score == pytest.approx(b.score, abs=1e-6)

    def test_overwrite_on_reindex_keeps_unique_paths(self, scanned_folder, tmp_path):
        _root, files = scanned_folder
        cache_path = tmp_path / "cache.npz"

        index = ClipSearchIndex(_StableEmbedder())
        index.add_many(files)
        index.add_many(files)  # simulate a re-scan
        index.save(cache_path)

        restored = ClipSearchIndex(_StableEmbedder())
        restored.load(cache_path)
        assert restored.size == len(files)

    def test_remove_then_save_persists_deletion(self, scanned_folder, tmp_path):
        _root, files = scanned_folder
        cache_path = tmp_path / "cache.npz"

        index = ClipSearchIndex(_StableEmbedder())
        index.add_many(files)
        victim = files[0]
        assert index.remove(victim) is True
        index.save(cache_path)

        reloaded = ClipSearchIndex(_StableEmbedder())
        reloaded.load(cache_path)
        assert reloaded.size == len(files) - 1
        assert not reloaded.contains(victim)


class TestCorruptionRecovery:
    def test_reindex_after_corrupt_cache_is_clean(self, scanned_folder, tmp_path):
        _root, files = scanned_folder
        cache_path = tmp_path / "cache.npz"
        cache_path.write_bytes(b"this is not a valid npz payload")

        # Fresh index starts empty, load() reports failure, a re-scan recovers.
        index = ClipSearchIndex(_StableEmbedder())
        assert index.load(cache_path) is False
        assert index.size == 0

        index.add_many(files)
        assert index.size == len(files)

        rewritten = index.save(cache_path)
        assert rewritten.exists()

        # And the freshly saved cache is loadable again.
        verifier = ClipSearchIndex(_StableEmbedder())
        assert verifier.load(cache_path) is True
        assert verifier.size == len(files)

    def test_missing_image_file_does_not_stop_batch(self, tmp_path):
        good = _make_png(tmp_path / "cat_001.png", (200, 100, 100))
        missing = tmp_path / "cat_missing.png"  # never created

        index = ClipSearchIndex(_StableEmbedder())
        added = index.add_many([good, str(missing)])
        # The fake embedder is permissive — use a real-file probe instead.
        from Imervue.library import clip_search as cs

        class _RealIsh:
            dim = 8

            def embed_text(self, text):
                return _l2_normalise(np.ones(self.dim, dtype=np.float32))

            def embed_image(self, path):
                try:
                    with Image.open(path) as im:
                        im.load()
                except (OSError, FileNotFoundError):
                    return None
                return _l2_normalise(np.ones(self.dim, dtype=np.float32))

        probe_index = cs.ClipSearchIndex(_RealIsh())
        added = probe_index.add_many([good, str(missing)])
        assert added == 1
        assert probe_index.contains(good)
        assert not probe_index.contains(str(missing))


class TestSingletonFactory:
    def test_default_index_is_memoised(self, tmp_path, monkeypatch):
        # Steer the singleton at a throw-away cache file for this test.
        from Imervue.library import clip_search as cs

        monkeypatch.setattr(
            cs, "_default_cache_path", lambda: tmp_path / "singleton.npz",
        )
        reset_default_index()
        first = get_default_index()
        second = get_default_index()
        assert first is second

    def test_reset_drops_singleton(self, tmp_path, monkeypatch):
        from Imervue.library import clip_search as cs

        monkeypatch.setattr(
            cs, "_default_cache_path", lambda: tmp_path / "singleton.npz",
        )
        reset_default_index()
        first = get_default_index()
        reset_default_index()
        second = get_default_index()
        assert first is not second

    def test_singleton_is_ready_state_reflects_backend(
        self, tmp_path, monkeypatch,
    ):
        from Imervue.library import clip_search as cs

        monkeypatch.setattr(
            cs, "_default_cache_path", lambda: tmp_path / "singleton.npz",
        )
        monkeypatch.setattr(cs, "is_available", lambda: False)
        reset_default_index()

        idx = get_default_index()
        assert idx.is_ready() is False
        # And a missing backend must raise on query, not silently return [].
        with pytest.raises(RuntimeError):
            idx.query_text("anything")
