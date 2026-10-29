"""On-disk cache of :class:`Imervue.library.clip_search.ClipSearchIndex`.

One ``.npz`` archive holds the paths and freshness signatures as UTF-8 JSON
bytes, the embedding matrix, its dimension and the id of the model that made
it. It is read with ``allow_pickle=False``, so nothing is ever unpickled. The
host class owns the state (``_paths``, ``_index``, ``_matrix``, ``_signatures``,
``_model_id``, ``_cache_path``); the mixin adds no ``__init__``.
"""
from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

import numpy as np

# The index's own logger: cache warnings have always been reported under it.
logger = logging.getLogger("Imervue.library.clip_search")


def _valid_signatures(raw, count: int) -> list[list[int] | None]:
    """The cached signatures, or all None (stale) for a cache written before they were kept."""
    if not isinstance(raw, list) or len(raw) != count:
        return [None] * count
    return [sig if isinstance(sig, list) and len(sig) == 2 and all(isinstance(v, int) for v in sig)
            else None for sig in raw]


class ClipIndexCacheMixin:
    """``save`` / ``load`` of the index as a pickle-free ``.npz`` archive."""

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
