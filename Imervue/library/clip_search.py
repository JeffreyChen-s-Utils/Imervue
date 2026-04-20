"""
CLIP-based semantic image search — "find photos that match a phrase".

The module is structured around a small :class:`SemanticEmbedder` protocol so the
heavy ML backend (``open_clip_torch``) stays an optional runtime dependency:

* In production we lazily wire up :class:`OpenClipEmbedder`, which loads a ViT-B/32
  CLIP checkpoint via ``open_clip`` on first use.
* In tests (and when torch is unavailable) callers inject a ``FakeEmbedder`` so
  the ranking logic can be exercised without pulling in 2 GB of PyTorch wheels.

The :class:`ClipSearchIndex` stores one L2-normalised float32 embedding per image
path and persists them as a single ``.npz`` archive next to the library DB —
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
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

logger = logging.getLogger("Imervue.library.clip_search")

_EMBED_DIM_DEFAULT = 512
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
    """Pluggable embedder — text and images map into the same vector space."""

    dim: int

    def embed_text(self, text: str) -> np.ndarray:
        """Return an L2-normalised 1-D float32 vector of length ``dim``."""

    def embed_image(self, path: str | Path) -> np.ndarray | None:
        """Return an L2-normalised 1-D float32 vector, or ``None`` on failure."""


def _l2_normalise(vec: np.ndarray) -> np.ndarray:
    """Return a unit-norm copy of ``vec`` (or the same zero vector unchanged)."""
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return vec
    return vec / norm


# ---------------------------------------------------------------------------
# OpenCLIP backend (optional)
# ---------------------------------------------------------------------------


@dataclass
class OpenClipConfig:
    """Runtime configuration for the lazy open_clip backend."""

    model_name: str = "ViT-B-32"
    pretrained: str = "openai"
    device: str = "auto"  # "auto" | "cuda" | "cpu"


def _available_backends() -> list[str]:
    """Return the list of optional backends importable in this interpreter."""
    found: list[str] = []
    try:
        import open_clip  # noqa: F401 — availability probe
        import torch  # noqa: F401
        found.append("open_clip")
    except ImportError:
        pass
    return found


def is_available() -> bool:
    """True if at least one real embedding backend can be constructed."""
    return bool(_available_backends())


class OpenClipEmbedder:
    """Adapter around ``open_clip`` — imports are deferred to first use."""

    def __init__(self, config: OpenClipConfig | None = None) -> None:
        self._config = config or OpenClipConfig()
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._torch = None
        self._device = None
        self.dim = _EMBED_DIM_DEFAULT

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import open_clip
        import torch
        device = self._config.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        model, _, preprocess = open_clip.create_model_and_transforms(
            self._config.model_name, pretrained=self._config.pretrained,
        )
        model.eval().to(device)
        self._model = model
        self._preprocess = preprocess
        self._tokenizer = open_clip.get_tokenizer(self._config.model_name)
        self._torch = torch
        self._device = device
        out_dim = getattr(model, "text_projection", None)
        if out_dim is not None and hasattr(out_dim, "shape"):
            self.dim = int(out_dim.shape[-1])

    def embed_text(self, text: str) -> np.ndarray:
        self._ensure_loaded()
        tokens = self._tokenizer([text]).to(self._device)
        with self._torch.no_grad():
            feats = self._model.encode_text(tokens)
        return _l2_normalise(feats[0].cpu().numpy().astype(np.float32))

    def embed_image(self, path: str | Path) -> np.ndarray | None:
        self._ensure_loaded()
        try:
            from PIL import Image
            with Image.open(path) as im:
                tensor = self._preprocess(im.convert("RGB")).unsqueeze(0)
        except (OSError, ValueError) as exc:
            logger.debug("CLIP image decode failed for %s: %s", path, exc)
            return None
        tensor = tensor.to(self._device)
        with self._torch.no_grad():
            feats = self._model.encode_image(tensor)
        return _l2_normalise(feats[0].cpu().numpy().astype(np.float32))


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
    :class:`SemanticEmbedder`. Production code uses :class:`OpenClipEmbedder`;
    tests pass a ``FakeEmbedder`` so the ranking / persistence logic is
    exercised without torch installed.
    """

    def __init__(
        self,
        embedder: SemanticEmbedder | None,
        cache_path: Path | str | None = None,
    ) -> None:
        self._embedder = embedder
        self._cache_path = Path(cache_path) if cache_path else _default_cache_path()
        self._paths: list[str] = []
        self._index: dict[str, int] = {}
        self._matrix: np.ndarray = np.zeros((0, 0), dtype=np.float32)

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

    def contains(self, path: str | Path) -> bool:
        return str(path) in self._index

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
        self._paths.pop(idx)
        self._matrix = np.delete(self._matrix, idx, axis=0)
        # Re-index trailing entries shifted up by one row.
        for shifted_key in self._paths[idx:]:
            self._index[shifted_key] -= 1
        return True

    def clear(self) -> None:
        self._paths.clear()
        self._index.clear()
        self._matrix = np.zeros((0, 0), dtype=np.float32)

    # ---- query ------------------------------------------------------

    def query_text(self, text: str, top_k: int = 50) -> list[SearchHit]:
        """Rank stored images by cosine similarity to ``text``."""
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
        scores = self._matrix @ query
        count = min(top_k, scores.shape[0])
        # argpartition is O(N) vs argsort's O(N log N) — matters for big libs.
        partition = np.argpartition(-scores, count - 1)[:count]
        ordered = partition[np.argsort(-scores[partition])]
        return [SearchHit(path=self._paths[int(i)], score=float(scores[int(i)]))
                for i in ordered]

    # ---- persistence ------------------------------------------------

    def save(self, path: Path | str | None = None) -> Path:
        """Write the index to an ``.npz`` archive — returns the final path."""
        target = Path(path) if path else self._cache_path
        target.parent.mkdir(parents=True, exist_ok=True)
        paths_arr = np.array(self._paths, dtype=object)
        np.savez(
            target,
            paths=paths_arr,
            matrix=self._matrix,
            dim=np.array([self._matrix.shape[1]], dtype=np.int32),
        )
        return target

    def load(self, path: Path | str | None = None) -> bool:
        """Replace the in-memory index from disk. False if no cache exists."""
        source = Path(path) if path else self._cache_path
        if not source.exists():
            return False
        try:
            data = np.load(source, allow_pickle=True)
            paths = [str(p) for p in data["paths"].tolist()]
            matrix = np.asarray(data["matrix"], dtype=np.float32)
        except (OSError, ValueError, KeyError, EOFError, pickle.UnpicklingError) as exc:
            logger.warning("Failed to load CLIP cache %s: %s", source, exc)
            return False
        if matrix.ndim != 2 or matrix.shape[0] != len(paths):
            logger.warning("Malformed CLIP cache at %s", source)
            return False
        self._paths = paths
        self._matrix = matrix
        self._index = {p: i for i, p in enumerate(paths)}
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
    """Return the shared index, lazily creating an OpenCLIP-backed one if possible."""
    global _default_index
    if _default_index is not None:
        return _default_index
    embedder: SemanticEmbedder | None = None
    if is_available():
        embedder = OpenClipEmbedder()
    _default_index = ClipSearchIndex(embedder)
    _default_index.load()
    return _default_index


def reset_default_index() -> None:
    """Drop the cached singleton — primarily for tests."""
    global _default_index
    _default_index = None
