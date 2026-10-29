"""
CLIP-based semantic image search — "find photos that match a phrase".

The module is structured around a small :class:`SemanticEmbedder` protocol so the
ML backend stays an optional runtime dependency:

* In production the index uses :class:`Imervue.library.clip_onnx.OnnxClipEmbedder`,
  CLIP ViT-B/32 on onnxruntime, downloaded at a pinned revision on first use.
* In tests (and when onnxruntime is missing) callers inject a ``FakeEmbedder`` so
  the ranking logic is exercised without any model.

The :class:`ClipSearchIndex` stores one L2-normalised float32 embedding per image
path and persists them, with the id of the model that made them, as a single
``.npz`` archive next to the library DB —
compact on disk and quick to reload (a single numpy read instead of per-image
base64 decode). Queries embed the text, then dot-product against the stacked
matrix for a true O(N) cosine scan, which is more than fast enough for the
low-hundreds-of-thousands image libraries Imervue targets.

The feature degrades gracefully when no backend is available — the UI checks
:func:`is_available` and disables the search field with an explanatory tooltip.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from Imervue.library.clip_search_cache import ClipIndexCacheMixin
from Imervue.library.clip_search_store import ClipIndexStoreMixin, _l2_normalise

logger = logging.getLogger("Imervue.library.clip_search")

_CACHE_FILENAME = "clip_cache.npz"
_MIN_TOP_K = 1
_MAX_TOP_K = 1000


def _default_cache_path() -> Path:
    """Return the on-disk cache path used by the singleton index."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / _CACHE_FILENAME
    return Path.home() / ".cache" / "imervue" / _CACHE_FILENAME


# ---------------------------------------------------------------------------
# Embedder protocol
# ---------------------------------------------------------------------------


class SemanticEmbedder(Protocol):
    """Pluggable embedder — text and images map into the same vector space.

    An embedder may also have ``model_id`` (names its vector space, kept with
    the cache) and ``prepare()`` (loads the model ahead of the first embed).
    """

    dim: int

    def embed_text(self, text: str) -> np.ndarray:
        """Return an L2-normalised 1-D float32 vector of length ``dim``."""

    def embed_image(self, path: str | Path) -> np.ndarray | None:
        """Return an L2-normalised 1-D float32 vector, or ``None`` on failure."""


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """True when the ONNX CLIP backend's packages are installed (the model downloads on use)."""
    from Imervue.library.clip_onnx import backend_importable
    return backend_importable()


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchHit:
    """One result row — ``score`` is a cosine similarity in [-1, 1]."""

    path: str
    score: float


class ClipSearchIndex(ClipIndexStoreMixin, ClipIndexCacheMixin):
    """In-memory matrix of L2-normalised image embeddings + on-disk cache.

    The index is backend-agnostic: callers pass any object implementing
    :class:`SemanticEmbedder`. Production code uses the ONNX CLIP embedder;
    tests pass a ``FakeEmbedder`` so the ranking / persistence logic is
    exercised without a model. An embedder's ``model_id`` names its vector
    space: a cache written by another model is not loaded. Row bookkeeping
    lives in :class:`ClipIndexStoreMixin`, the ``.npz`` cache in
    :class:`ClipIndexCacheMixin`.
    """

    def __init__(
        self,
        embedder: SemanticEmbedder | None,
        cache_path: Path | str | None = None,
    ) -> None:
        self._embedder = embedder
        self._model_id = str(getattr(embedder, "model_id", ""))
        self._cache_path = Path(cache_path) if cache_path else _default_cache_path()
        self._paths: list[str] = []
        self._index: dict[str, int] = {}
        self._matrix: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        # path -> [size, mtime_ns] when it was embedded; None: unknown, embed again
        self._signatures: dict[str, list[int] | None] = {}

    # ---- state inspection -------------------------------------------

    @property
    def size(self) -> int:
        return len(self._paths)

    @property
    def cache_path(self) -> Path:
        return self._cache_path

    def is_ready(self) -> bool:
        """True iff an embedder is attached and can answer queries."""
        return self._embedder is not None

    def needs_download(self) -> bool:
        """Whether loading the embedder's model will download it first."""
        downloaded = getattr(self._embedder, "is_downloaded", None)
        return downloaded is not None and not downloaded()

    def prepare(self) -> None:
        """Load the embedder's model now (it may download); ``OSError`` when it can't be had."""
        prepare = getattr(self._embedder, "prepare", None)
        if prepare is not None:
            prepare()

    # ---- query ------------------------------------------------------

    def query_text(self, text: str, top_k: int = 50,
                   within: set[str] | None = None) -> list[SearchHit]:
        """Rank stored images by cosine similarity to ``text``, only those in *within* if given."""
        if self._embedder is None:
            raise RuntimeError("Semantic search has no embedder configured")
        if not text or not text.strip():
            return []
        top_k = max(_MIN_TOP_K, min(_MAX_TOP_K, int(top_k)))
        if self._matrix.shape[0] == 0:
            return []
        query = _l2_normalise(self._embedder.embed_text(text))
        if query.size != self._matrix.shape[1]:
            raise ValueError(
                f"Query dim {query.size} does not match index dim "
                f"{self._matrix.shape[1]}"
            )
        if within is None:
            rows = np.arange(len(self._paths))
        else:
            rows = np.array([i for i, p in enumerate(self._paths) if p in within], dtype=np.int64)
        if rows.size == 0:
            return []
        scores = np.full(len(self._paths), -np.inf, dtype=np.float32)
        scores[rows] = self._matrix[rows] @ query
        count = min(top_k, int(rows.size))
        # argpartition is O(N) vs argsort's O(N log N) — matters for big libs.
        partition = np.argpartition(-scores, count - 1)[:count]
        ordered = partition[np.argsort(-scores[partition])]
        return [SearchHit(path=self._paths[int(i)], score=float(scores[int(i)]))
                for i in ordered]


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


_default_index: ClipSearchIndex | None = None


def get_default_index() -> ClipSearchIndex:
    """Return the shared index, backed by the ONNX CLIP embedder when onnxruntime is installed."""
    global _default_index
    if _default_index is not None and (_default_index.is_ready() or not is_available()):
        return _default_index
    embedder: SemanticEmbedder | None = None
    if is_available():
        from Imervue.library.clip_onnx import default_embedder
        embedder = default_embedder()
    _default_index = ClipSearchIndex(embedder)
    _default_index.load()
    return _default_index


def reset_default_index() -> None:
    """Drop the cached singleton — primarily for tests."""
    global _default_index
    _default_index = None
