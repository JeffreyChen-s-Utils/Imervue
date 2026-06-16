"""Qt smoke tests for the semantic-search dialog.

Torch-free: a fake embedder (image topic = text token) makes ranking
deterministic. Plain QDialog — no QOpenGLWidget, so no headless-CI skip.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import Qt

from Imervue.gui.semantic_search_dialog import SemanticSearchDialog
from Imervue.library.clip_search import ClipSearchIndex, _l2_normalise


class _FakeEmbedder:
    dim = 8

    def _vec(self, token: str) -> np.ndarray:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        raw = np.frombuffer(digest[: self.dim * 2], dtype=np.int16).astype(np.float32)
        return _l2_normalise(raw[: self.dim])

    def embed_text(self, text: str) -> np.ndarray:
        return self._vec(text.strip().lower())

    def embed_image(self, path) -> np.ndarray:
        return self._vec(str(path).split("::", 1)[0])


def _ready_index() -> ClipSearchIndex:
    index = ClipSearchIndex(_FakeEmbedder())
    for path in ("beach::a.png", "beach::b.png", "city::c.png"):
        index.add(path)
    return index


def _dialog() -> SemanticSearchDialog:
    return SemanticSearchDialog(SimpleNamespace(main_window=None), _ready_index())


def _result_paths(dlg) -> list[str]:
    return [dlg._results.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(dlg._results.count())]


def test_search_ranks_matching_topic_first(qapp):
    dlg = _dialog()
    dlg._query.setText("beach")
    dlg._search()
    assert dlg._results.count() == 3
    # Both beach images outrank the city image.
    assert set(_result_paths(dlg)[:2]) == {"beach::a.png", "beach::b.png"}


def test_empty_query_does_nothing(qapp):
    dlg = _dialog()
    dlg._query.setText("   ")
    dlg._search()
    assert dlg._results.count() == 0


def test_query_without_embedder_surfaces_error(qapp):
    dlg = SemanticSearchDialog(
        SimpleNamespace(main_window=None), ClipSearchIndex(embedder=None))
    dlg._query.setText("anything")
    dlg._search()  # query_text raises RuntimeError → caught, shown in status
    assert dlg._status.text()


def test_open_dialog_warns_when_backend_unavailable(qapp, monkeypatch):
    from Imervue.gui import semantic_search_dialog as mod
    from Imervue.library import clip_search

    warned: list[bool] = []
    monkeypatch.setattr(mod, "_warn_unavailable", lambda parent: warned.append(True))
    monkeypatch.setattr(clip_search, "is_available", lambda: False)
    viewer = SimpleNamespace(main_window=None, model=SimpleNamespace(images=[]))
    mod.open_semantic_search_dialog(viewer)
    assert warned == [True]
