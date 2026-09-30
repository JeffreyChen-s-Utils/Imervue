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

import json
import logging
import os
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

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


def _signature(path: str) -> list[int] | None:
    """``[size, mtime_ns]`` of *path*, None when it can't be stat'ed: an embedding's freshness."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return [stat.st_size, stat.st_mtime_ns]


def _valid_signatures(raw, count: int) -> list[list[int] | None]:
    """The cached signatures, or all None (stale) for a cache written before they were kept."""
    if not isinstance(raw, list) or len(raw) != count:
        return [None] * count
    return [sig if isinstance(sig, list) and len(sig) == 2 and all(isinstance(v, int) for v in sig)
            else None for sig in raw]


def _l2_normalise(vec: np.ndarray) -> np.ndarray:
    """Return a unit-norm copy of ``vec`` (or the same zero vector unchanged)."""
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return vec
    return vec / norm


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


class ClipSearchIndex:
    """In-memory matrix of L2-normalised image embeddings + on-disk cache.

    The index is backend-agnostic: callers pass any object implementing
    :class:`SemanticEmbedder`. Production code uses the ONNX CLIP embedder;
    tests pass a ``FakeEmbedder`` so the ranking / persistence logic is
    exercised without a model. An embedder's ``model_id`` names its vector
    space: a cache written by another model is not loaded.
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

    def contains(self, path: str | Path) -> bool:
        return str(path) in self._index

    def is_current(self, path: str | Path) -> bool:
        """Whether *path* is indexed from the file as it is now (same size and modified time)."""
        key = str(path)
        recorded = self._signatures.get(key)
        return key in self._index and recorded is not None and recorded == _signature(key)

    # ---- mutation ---------------------------------------------------

    def add(self, path: str | Path, embedding: np.ndarray | None = None) -> bool:
        """Embed (or accept a precomputed vector for) ``path`` and store it.

        Returns ``True`` if the row was added or replaced, ``False`` if the
        embedding could not be produced (e.g. unreadable file).
        """
        key = str(path)
        if embedding is None:
            if self._embedder is None:
                return False
            embedding = self._embedder.embed_image(path)
            if embedding is None:
                return False
        vec = _l2_normalise(embedding)
        if vec.size == 0:
            return False
        self._append_or_replace(key, vec)
        self._signatures[key] = _signature(key)
        return True

    def add_many(self, paths: list[str] | list[Path]) -> int:
        """Embed a batch of paths — returns the count successfully added."""
        count = 0
        for p in paths:
            if self.add(p):
                count += 1
        return count

    def remove(self, path: str | Path) -> bool:
        key = str(path)
        idx = self._index.pop(key, None)
        if idx is None:
            return False
        self._signatures.pop(key, None)
        self._paths.pop(idx)
        self._matrix = np.delete(self._matrix, idx, axis=0)
        # Re-index trailing entries shifted up by one row.
        for shifted_key in self._paths[idx:]:
            self._index[shifted_key] -= 1
        return True

    def clear(self) -> None:
        self._paths.clear()
        self._index.clear()
        self._signatures.clear()
        self._matrix = np.zeros((0, 0), dtype=np.float32)

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

    # ---- persistence ------------------------------------------------

    def save(self, path: Path | str | None = None) -> Path:
        """Write the index to an ``.npz`` archive — returns the final path.

        The paths are stored as UTF-8 JSON bytes rather than an object array,
        so :meth:`load` never has to unpickle anything.
        """
        target = Path(path) if path else self._cache_path
        target.parent.mkdir(parents=True, exist_ok=True)
        paths_json = np.frombuffer(json.dumps(self._paths).encode("utf-8"), dtype=np.uint8)
        signatures = [self._signatures.get(p) for p in self._paths]
        sigs_json = np.frombuffer(json.dumps(signatures).encode("utf-8"), dtype=np.uint8)
        model = np.frombuffer(self._model_id.encode("utf-8"), dtype=np.uint8)
        np.savez(
            target,
            paths_json=paths_json,
            sigs_json=sigs_json,
            model=model,
            matrix=self._matrix,
            dim=np.array([self._matrix.shape[1]], dtype=np.int32),
        )
        return target

    def load(self, path: Path | str | None = None) -> bool:
        """Replace the in-memory index from disk. False if no usable cache exists.

        Loads with ``allow_pickle=False``, so a tampered cache cannot run code.
        A cache written before the paths moved to JSON (an object array) is
        rejected like a corrupt one, and the index is rebuilt; so is one whose
        embeddings came from another model than this index's embedder.
        """
        source = Path(path) if path else self._cache_path
        if not source.exists():
            return False
        try:
            with np.load(source, allow_pickle=False) as data:
                paths = json.loads(data["paths_json"].tobytes().decode("utf-8"))
                matrix = np.asarray(data["matrix"], dtype=np.float32)
                sigs = (json.loads(data["sigs_json"].tobytes().decode("utf-8"))
                        if "sigs_json" in data.files else None)
                # No model recorded: written before the id was kept (the old torch backend).
                model = (data["model"].tobytes().decode("utf-8")
                         if "model" in data.files else "")
        # ValueError also covers bad JSON / UTF-8 and a pickled object array.
        except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile) as exc:
            logger.warning("Failed to load CLIP cache %s: %s", source, exc)
            return False
        if not (isinstance(paths, list) and all(isinstance(p, str) for p in paths)):
            logger.warning("Malformed CLIP cache at %s", source)
            return False
        if matrix.ndim != 2 or matrix.shape[0] != len(paths):
            logger.warning("Malformed CLIP cache at %s", source)
            return False
        if model != self._model_id:
            logger.info("CLIP cache %s is from model %r, not %r: rebuilding",
                        source, model, self._model_id)
            return False
        self._paths = paths
        self._matrix = matrix
        self._index = {p: i for i, p in enumerate(paths)}
        self._signatures = dict(zip(paths, _valid_signatures(sigs, len(paths)), strict=True))
        return True

    # ---- helpers ----------------------------------------------------

    def _append_or_replace(self, key: str, vec: np.ndarray) -> None:
        if self._matrix.size == 0:
            self._matrix = vec.reshape(1, -1).astype(np.float32)
            self._paths.append(key)
            self._index[key] = 0
            return
        dim = self._matrix.shape[1]
        if vec.size != dim:
            raise ValueError(
                f"Embedding dim {vec.size} does not match index dim {dim}"
            )
        existing = self._index.get(key)
        if existing is not None:
            self._matrix[existing] = vec
            return
        self._matrix = np.vstack([self._matrix, vec.astype(np.float32)])
        self._paths.append(key)
        self._index[key] = len(self._paths) - 1


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
