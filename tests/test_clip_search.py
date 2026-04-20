"""Tests for CLIP semantic search — backend-agnostic, torch-free."""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from Imervue.library.clip_search import (
    ClipSearchIndex,
    SearchHit,
    _l2_normalise,
    is_available,
)


class FakeEmbedder:
    """Deterministic text/image embedder for tests — same space, no torch."""

    def __init__(self, dim: int = 8):
        self.dim = dim

    def _hash_vec(self, token: str) -> np.ndarray:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        raw = np.frombuffer(digest[: self.dim * 2], dtype=np.int16).astype(np.float32)
        return _l2_normalise(raw[: self.dim])

    def embed_text(self, text: str) -> np.ndarray:
        return self._hash_vec(text.strip().lower())

    def embed_image(self, path) -> np.ndarray | None:
        key = str(path)
        if key.endswith(".bad"):
            return None
        # Images matching a specific "topic" share a common token so text-image
        # similarity becomes predictable — everything before "::" is the topic.
        topic = key.split("::", 1)[0] if "::" in key else key
        return self._hash_vec(topic)


@pytest.fixture
def fake_index():
    return ClipSearchIndex(FakeEmbedder())


class TestAddRemove:
    def test_add_stores_row(self, fake_index):
        assert fake_index.add("cat::a.jpg") is True
        assert fake_index.size == 1
        assert fake_index.contains("cat::a.jpg")

    def test_add_replaces_existing(self, fake_index):
        fake_index.add("cat::a.jpg")
        fake_index.add("cat::a.jpg")
        assert fake_index.size == 1

    def test_add_rejects_unreadable(self, fake_index):
        assert fake_index.add("broken.bad") is False
        assert fake_index.size == 0

    def test_add_many_reports_success_count(self, fake_index):
        added = fake_index.add_many([
            "cat::a.jpg", "cat::b.jpg", "broken.bad", "dog::c.jpg",
        ])
        assert added == 3
        assert fake_index.size == 3

    def test_remove_drops_row(self, fake_index):
        fake_index.add_many(["cat::a.jpg", "cat::b.jpg", "dog::c.jpg"])
        assert fake_index.remove("cat::b.jpg") is True
        assert fake_index.size == 2
        assert not fake_index.contains("cat::b.jpg")
        assert fake_index.contains("dog::c.jpg")

    def test_remove_missing_returns_false(self, fake_index):
        assert fake_index.remove("ghost.jpg") is False

    def test_clear_empties_everything(self, fake_index):
        fake_index.add_many(["a::1.jpg", "b::2.jpg"])
        fake_index.clear()
        assert fake_index.size == 0

    def test_add_with_precomputed_embedding(self):
        idx = ClipSearchIndex(embedder=None)
        vec = np.ones(4, dtype=np.float32)
        assert idx.add("manual.jpg", embedding=vec) is True
        assert idx.size == 1

    def test_add_dim_mismatch_raises(self, fake_index):
        fake_index.add("cat::a.jpg")
        wrong = np.zeros(fake_index._matrix.shape[1] + 3, dtype=np.float32)
        with pytest.raises(ValueError):
            fake_index.add("other.jpg", embedding=wrong)


class TestQuery:
    def test_query_ranks_matching_topic_first(self, fake_index):
        fake_index.add_many([
            "cat::one.jpg", "cat::two.jpg",
            "dog::one.jpg", "dog::two.jpg",
            "car::one.jpg",
        ])
        # FakeEmbedder hashes the topic prefix for both modalities, so the two
        # "cat" images should dominate the top of a "cat" query.
        hits = fake_index.query_text("cat", top_k=5)
        assert [h.path for h in hits[:2]] == ["cat::one.jpg", "cat::two.jpg"] or \
               [h.path for h in hits[:2]] == ["cat::two.jpg", "cat::one.jpg"]
        assert hits == sorted(hits, key=lambda h: -h.score)

    def test_query_respects_top_k(self, fake_index):
        fake_index.add_many([f"cat::{i}.jpg" for i in range(10)])
        hits = fake_index.query_text("cat", top_k=3)
        assert len(hits) == 3

    def test_query_on_empty_index_returns_empty(self, fake_index):
        assert fake_index.query_text("anything") == []

    def test_blank_query_returns_empty(self, fake_index):
        fake_index.add("cat::a.jpg")
        assert fake_index.query_text("   ") == []

    def test_query_without_embedder_raises(self):
        idx = ClipSearchIndex(embedder=None)
        with pytest.raises(RuntimeError):
            idx.query_text("hello")

    def test_top_k_clamped_to_size(self, fake_index):
        fake_index.add_many(["cat::1.jpg", "cat::2.jpg"])
        hits = fake_index.query_text("cat", top_k=50)
        assert len(hits) == 2

    def test_hit_is_dataclass_with_score(self, fake_index):
        fake_index.add("cat::a.jpg")
        hit = fake_index.query_text("cat")[0]
        assert isinstance(hit, SearchHit)
        # Float32 self-dot can overshoot 1.0 by ~1e-7; allow the slack.
        assert -1.01 <= hit.score <= 1.01


class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        src = ClipSearchIndex(FakeEmbedder())
        src.add_many(["cat::a.jpg", "dog::b.jpg"])
        saved = src.save(tmp_path / "cache.npz")
        assert saved.exists()

        restored = ClipSearchIndex(FakeEmbedder())
        assert restored.load(saved) is True
        assert restored.size == 2
        assert restored.contains("cat::a.jpg")

    def test_load_missing_returns_false(self, tmp_path):
        idx = ClipSearchIndex(FakeEmbedder())
        assert idx.load(tmp_path / "nope.npz") is False

    def test_load_corrupt_returns_false(self, tmp_path):
        bogus = tmp_path / "bad.npz"
        bogus.write_bytes(b"not a real npz")
        idx = ClipSearchIndex(FakeEmbedder())
        assert idx.load(bogus) is False

    def test_save_creates_parent_dirs(self, tmp_path):
        idx = ClipSearchIndex(FakeEmbedder())
        idx.add("cat::a.jpg")
        nested = tmp_path / "deep" / "tree" / "cache.npz"
        idx.save(nested)
        assert nested.exists()

    def test_reload_preserves_query_order(self, tmp_path):
        src = ClipSearchIndex(FakeEmbedder())
        src.add_many(["cat::a.jpg", "dog::b.jpg", "cat::c.jpg"])
        target = src.save(tmp_path / "c.npz")

        restored = ClipSearchIndex(FakeEmbedder())
        restored.load(target)

        a = src.query_text("cat", top_k=3)
        b = restored.query_text("cat", top_k=3)
        assert [h.path for h in a] == [h.path for h in b]


class TestBackendAvailability:
    def test_is_available_is_boolean(self):
        assert isinstance(is_available(), bool)

    def test_no_embedder_means_not_ready(self):
        idx = ClipSearchIndex(embedder=None)
        assert idx.is_ready() is False

    def test_fake_embedder_is_ready(self, fake_index):
        assert fake_index.is_ready() is True


class TestHelpers:
    def test_l2_normalise_unit_length(self):
        out = _l2_normalise(np.array([3.0, 4.0], dtype=np.float32))
        assert np.isclose(np.linalg.norm(out), 1.0)

    def test_l2_normalise_zero_vector_stays_zero(self):
        out = _l2_normalise(np.zeros(4, dtype=np.float32))
        assert np.all(out == 0)
