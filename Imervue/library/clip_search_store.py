"""Row bookkeeping of :class:`Imervue.library.clip_search.ClipSearchIndex`.

The mixin adds, replaces and removes rows of the index's embedding matrix and
keeps the path -> row map and each row's freshness signature in step. The host
class owns the state (``_paths``, ``_index``, ``_matrix``, ``_signatures``,
``_embedder``); the mixin adds no ``__init__``.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np


def _signature(path: str) -> list[int] | None:
    """``[size, mtime_ns]`` of *path*, None when it can't be stat'ed: an embedding's freshness."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return [stat.st_size, stat.st_mtime_ns]


def _l2_normalise(vec: np.ndarray) -> np.ndarray:
    """Return a unit-norm copy of ``vec`` (or the same zero vector unchanged)."""
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return vec
    return vec / norm


class ClipIndexStoreMixin:
    """Membership, freshness and add / replace / remove of the index's rows."""

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
