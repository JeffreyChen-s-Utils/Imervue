"""Contracts of the CLIP index: row bookkeeping, ranking edges and the cache format."""
from __future__ import annotations

import json
import logging

import numpy as np
import pytest

from Imervue.library.clip_search import ClipSearchIndex, SearchHit, _l2_normalise

_LOGGER = "Imervue.library.clip_search"


class _AxisEmbedder:
    """Text ``"a<i>"`` and image ``.../a<i>...`` both map onto unit axis ``i``."""

    def __init__(self, dim: int = 4, model_id: str = "axis"):
        self.dim = dim
        self.model_id = model_id

    def _axis(self, token: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        vec[int(token.rsplit("a", 1)[-1][0]) % self.dim] = 1.0
        return vec

    def embed_text(self, text: str) -> np.ndarray:
        return self._axis(text)

    def embed_image(self, path) -> np.ndarray | None:
        return self._axis(str(path))


def _vec(*values: float) -> np.ndarray:
    return np.array(values, dtype=np.float32)


def _bytes(obj) -> np.ndarray:
    return np.frombuffer(json.dumps(obj).encode("utf-8"), dtype=np.uint8)


def _write_cache(path, *, paths, matrix, model="axis", sigs=None, extra=None):
    arrays = {"paths_json": _bytes(paths), "matrix": np.asarray(matrix, dtype=np.float32),
              "model": np.frombuffer(model.encode("utf-8"), dtype=np.uint8)}
    if sigs is not None:
        arrays["sigs_json"] = _bytes(sigs)
    arrays.update(extra or {})
    np.savez(path, **arrays)
    return path


class TestRowBookkeeping:
    def test_removing_a_middle_row_shifts_the_later_rows_up(self, tmp_path):
        index = ClipSearchIndex(_AxisEmbedder(), cache_path=tmp_path / "c.npz")
        for name in ("a0", "a1", "a2", "a3"):
            index.add(name)
        assert index.remove("a1") is True
        assert index.size == 3
        hits = index.query_text("a3", top_k=1)
        assert hits == [SearchHit(path="a3", score=pytest.approx(1.0))]
        assert index.query_text("a2", top_k=1)[0].path == "a2"
        assert not index.contains("a1")

    def test_a_replaced_row_keeps_its_position_and_takes_the_new_vector(self, tmp_path):
        index = ClipSearchIndex(None, cache_path=tmp_path / "c.npz")
        assert index.add("x", _vec(1, 0)) is True
        assert index.add("y", _vec(0, 1)) is True
        assert index.add("x", _vec(0, 3)) is True
        assert index.size == 2
        np.testing.assert_allclose(index._matrix, [[0, 1], [0, 1]])  # noqa: SLF001

    def test_a_precomputed_vector_is_accepted_without_an_embedder(self, tmp_path):
        index = ClipSearchIndex(None, cache_path=tmp_path / "c.npz")
        assert index.add("p", _vec(3, 4)) is True
        np.testing.assert_allclose(index._matrix[0], [0.6, 0.8])  # noqa: SLF001

    def test_without_an_embedder_nothing_is_embedded(self, tmp_path):
        index = ClipSearchIndex(None, cache_path=tmp_path / "c.npz")
        assert index.add("p") is False
        assert index.size == 0

    def test_an_empty_vector_is_refused(self, tmp_path):
        index = ClipSearchIndex(None, cache_path=tmp_path / "c.npz")
        assert index.add("p", np.zeros(0, dtype=np.float32)) is False
        assert index.size == 0

    def test_a_path_that_cannot_be_stated_is_never_current(self, tmp_path):
        index = ClipSearchIndex(None, cache_path=tmp_path / "c.npz")
        index.add(str(tmp_path / "gone.png"), _vec(1, 0))
        assert index.contains(str(tmp_path / "gone.png"))
        assert not index.is_current(str(tmp_path / "gone.png"))
        assert not index.is_current(str(tmp_path / "never.png"))


class TestRanking:
    @pytest.fixture
    def index(self, tmp_path):
        idx = ClipSearchIndex(_AxisEmbedder(), cache_path=tmp_path / "c.npz")
        idx.add("a0", _vec(1, 0, 0, 0))
        idx.add("a1", _vec(0.8, 0.6, 0, 0))
        idx.add("a2", _vec(0, 0, 1, 0))
        return idx

    def test_scores_come_back_best_first(self, index):
        hits = index.query_text("a0", top_k=3)
        assert [h.path for h in hits] == ["a0", "a1", "a2"]
        assert [h.score for h in hits] == pytest.approx([1.0, 0.8, 0.0])

    def test_a_top_k_below_one_still_returns_one(self, index):
        assert [h.path for h in index.query_text("a0", top_k=0)] == ["a0"]
        assert [h.path for h in index.query_text("a0", top_k=-5)] == ["a0"]

    def test_a_numeric_string_top_k_is_accepted(self, index):
        assert len(index.query_text("a0", top_k="2")) == 2

    def test_a_restriction_to_unknown_paths_finds_nothing(self, index):
        assert index.query_text("a0", within={"elsewhere"}) == []
        assert index.query_text("a0", within=set()) == []

    def test_a_restriction_ranks_only_its_paths(self, index):
        hits = index.query_text("a0", top_k=5, within={"a2", "a1"})
        assert [h.path for h in hits] == ["a1", "a2"]

    def test_a_query_of_another_dimension_is_an_error(self, tmp_path):
        index = ClipSearchIndex(_AxisEmbedder(dim=3), cache_path=tmp_path / "c.npz")
        index.add("p", _vec(1, 0, 0, 0))
        with pytest.raises(ValueError, match="Query dim 3 does not match index dim 4"):
            index.query_text("a0")

    def test_the_embedder_check_precedes_the_blank_text_check(self, tmp_path):
        index = ClipSearchIndex(None, cache_path=tmp_path / "c.npz")
        with pytest.raises(RuntimeError, match="no embedder"):
            index.query_text("   ")

    def test_whitespace_text_is_an_empty_result(self, index):
        assert index.query_text(" \t ") == []


class TestCacheFormat:
    def test_save_writes_json_paths_signatures_model_and_dim(self, tmp_path):
        index = ClipSearchIndex(_AxisEmbedder(model_id="m-1"), cache_path=tmp_path / "c.npz")
        index.add("a0", _vec(1, 0, 0, 0))
        target = index.save()
        assert target == tmp_path / "c.npz"
        with np.load(target, allow_pickle=False) as data:
            assert sorted(data.files) == ["dim", "matrix", "model", "paths_json", "sigs_json"]
            assert json.loads(data["paths_json"].tobytes()) == ["a0"]
            assert json.loads(data["sigs_json"].tobytes()) == [None]
            assert data["model"].tobytes().decode("utf-8") == "m-1"
            assert data["dim"].tolist() == [4]
            assert data["matrix"].dtype == np.float32

    def test_save_to_an_explicit_path_leaves_the_default_alone(self, tmp_path):
        index = ClipSearchIndex(None, cache_path=tmp_path / "default.npz")
        index.add("p", _vec(1, 0))
        assert index.save(tmp_path / "sub" / "other.npz") == tmp_path / "sub" / "other.npz"
        assert not (tmp_path / "default.npz").exists()

    def test_an_explicit_load_path_wins(self, tmp_path):
        writer = ClipSearchIndex(_AxisEmbedder(), cache_path=tmp_path / "w.npz")
        writer.add("a1", _vec(0, 1, 0, 0))
        writer.save(tmp_path / "elsewhere.npz")
        reader = ClipSearchIndex(_AxisEmbedder(), cache_path=tmp_path / "missing.npz")
        assert reader.load() is False
        assert reader.load(tmp_path / "elsewhere.npz") is True
        assert reader.contains("a1")

    @pytest.mark.parametrize("paths, matrix", [
        (["a", 3], np.zeros((2, 2))),
        (["a", "b"], np.zeros((3, 2))),
        (["a"], np.zeros(2)),
    ])
    def test_a_malformed_cache_is_refused_and_logged(self, tmp_path, caplog, paths, matrix):
        source = _write_cache(tmp_path / "c.npz", paths=paths, matrix=matrix)
        index = ClipSearchIndex(_AxisEmbedder(), cache_path=source)
        index.add("kept", _vec(1, 0, 0, 0))
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            assert index.load() is False
        assert [r.getMessage() for r in caplog.records if r.name == _LOGGER] == [
            f"Malformed CLIP cache at {source}"]
        assert index.contains("kept")

    def test_a_cache_missing_its_matrix_is_refused_with_a_warning(self, tmp_path, caplog):
        source = tmp_path / "c.npz"
        np.savez(source, paths_json=_bytes([]))
        index = ClipSearchIndex(_AxisEmbedder(), cache_path=source)
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            assert index.load() is False
        assert any(r.getMessage().startswith(f"Failed to load CLIP cache {source}: ")
                   for r in caplog.records if r.name == _LOGGER)

    def test_bad_json_in_the_paths_is_refused(self, tmp_path):
        source = tmp_path / "c.npz"
        np.savez(source, paths_json=np.frombuffer(b"[not json", dtype=np.uint8),
                 matrix=np.zeros((0, 4), dtype=np.float32))
        assert ClipSearchIndex(_AxisEmbedder(), cache_path=source).load() is False

    def test_a_model_mismatch_is_logged_at_info(self, tmp_path, caplog):
        source = _write_cache(tmp_path / "c.npz", paths=["a"], matrix=np.ones((1, 4)),
                              model="other")
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            assert ClipSearchIndex(_AxisEmbedder(), cache_path=source).load() is False
        records = [r for r in caplog.records if r.name == _LOGGER]
        assert [r.levelno for r in records] == [logging.INFO]
        assert records[0].getMessage() == (
            f"CLIP cache {source} is from model 'other', not 'axis': rebuilding")

    def test_each_malformed_signature_on_its_own_is_dropped(self, tmp_path):
        stamp = tmp_path / "a.png"
        stamp.write_bytes(b"x")
        st = stamp.stat()
        good = [st.st_size, st.st_mtime_ns]
        paths = [str(stamp), "b", "c", "d", "e"]
        sigs = [good, [1], [1, "2"], "no", [1.5, 2]]
        source = _write_cache(tmp_path / "c.npz", paths=paths, matrix=np.ones((5, 4)), sigs=sigs)
        index = ClipSearchIndex(_AxisEmbedder(), cache_path=source)
        assert index.load() is True
        assert index._signatures == {  # noqa: SLF001
            str(stamp): good, "b": None, "c": None, "d": None, "e": None}
        assert index.is_current(stamp)

    @pytest.mark.parametrize("sigs", [{"a": [1, 2]}, [[1, 2], [3, 4]]])
    def test_signatures_of_the_wrong_shape_are_all_stale(self, tmp_path, sigs):
        source = _write_cache(tmp_path / "c.npz", paths=["a"], matrix=np.ones((1, 4)), sigs=sigs)
        index = ClipSearchIndex(_AxisEmbedder(), cache_path=source)
        assert index.load() is True
        assert index._signatures == {"a": None}  # noqa: SLF001

    def test_a_loaded_matrix_is_float32_and_queryable(self, tmp_path):
        source = _write_cache(tmp_path / "c.npz", paths=["a0", "a1"],
                              matrix=np.eye(2, 4, dtype=np.float64))
        index = ClipSearchIndex(_AxisEmbedder(), cache_path=source)
        assert index.load() is True
        assert index._matrix.dtype == np.float32  # noqa: SLF001
        assert index.query_text("a1", top_k=1)[0].path == "a1"


def test_l2_normalise_flattens_and_casts():
    out = _l2_normalise(np.array([[3, 4]], dtype=np.int64))
    assert out.shape == (2,)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, [0.6, 0.8])
