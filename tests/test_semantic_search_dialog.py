"""Qt smoke tests for the semantic-search dialog.

Torch-free: a fake embedder (image topic = text token) makes ranking
deterministic. Plain QDialog — no QOpenGLWidget, so no headless-CI skip.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
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


def test_index_build_worker_breaks_on_interruption(qapp):
    """A cancelled index build stops at its next per-image check instead of
    embedding the whole folder, so the dialog's wait() returns promptly."""
    from Imervue.gui.semantic_search_dialog import _IndexBuildWorker
    added: list = []
    fake_index = SimpleNamespace(add=lambda p: added.append(p))

    class _Interrupted(_IndexBuildWorker):
        def isInterruptionRequested(self):   # noqa: N802 - Qt API
            return True

    worker = _Interrupted(fake_index, ["/a.png", "/b.png"])
    done: list = []
    worker.done.connect(lambda: done.append(True))
    worker.run()

    assert added == []          # broke before embedding any path
    assert done == [True]       # still emits done so the dialog re-enables


def test_dialog_uses_worker_host_mixin():
    from Imervue.plugin.worker_host import WorkerHostMixin
    assert issubclass(SemanticSearchDialog, WorkerHostMixin)
    assert "closeEvent" not in SemanticSearchDialog.__dict__


def test_unavailable_notice_is_translated(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from Imervue.gui import semantic_search_dialog as mod
    from Imervue.multi_language.japanese import japanese_word_dict
    from Imervue.multi_language.language_wrapper import language_wrapper

    monkeypatch.setattr(language_wrapper, "language_word_dict", japanese_word_dict)
    shown: list = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda _parent, title, text: shown.append((title, text)))
    mod._warn_unavailable(None)
    assert shown == [(japanese_word_dict["semantic_search_title"],
                      japanese_word_dict["semantic_search_unavailable"])]
    assert "open_clip_torch" in shown[0][1]



class _CountingEmbedder(_FakeEmbedder):
    def __init__(self):
        self.embedded: list = []

    def embed_image(self, path) -> np.ndarray:
        self.embedded.append(str(path))
        return super().embed_image(path)


def _folder(tmp_path, names):
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(name.encode())
        paths.append(str(path))
    return paths


def test_a_second_search_of_a_folder_embeds_nothing_again(qapp, tmp_path):
    """Every dialog embedded the whole folder again: minutes of CLIP per open."""
    from Imervue.gui.semantic_search_dialog import _IndexBuildWorker
    embedder = _CountingEmbedder()
    index = ClipSearchIndex(embedder, cache_path=tmp_path / "cache.npz")
    paths = _folder(tmp_path, ["a.png", "b.png"])
    _IndexBuildWorker(index, paths).run()
    assert sorted(embedder.embedded) == sorted(paths)
    assert (tmp_path / "cache.npz").is_file()           # kept for the next run

    embedder.embedded.clear()
    reloaded = ClipSearchIndex(embedder, cache_path=tmp_path / "cache.npz")
    assert reloaded.load()
    _IndexBuildWorker(reloaded, paths).run()
    assert embedder.embedded == []


def test_only_a_changed_file_is_embedded_again(qapp, tmp_path):
    import os

    from Imervue.gui.semantic_search_dialog import _IndexBuildWorker
    embedder = _CountingEmbedder()
    index = ClipSearchIndex(embedder, cache_path=tmp_path / "cache.npz")
    paths = _folder(tmp_path, ["a.png", "b.png"])
    _IndexBuildWorker(index, paths).run()
    embedder.embedded.clear()
    later = os.stat(paths[1]).st_mtime + 5
    Path(paths[1]).write_bytes(b"edited")
    os.utime(paths[1], (later, later))
    _IndexBuildWorker(index, paths).run()
    assert embedder.embedded == [paths[1]]


def test_results_come_from_the_folder_searched(qapp, tmp_path, monkeypatch):
    """The cache holds earlier folders too; the dialog ranks only the one it was opened on."""
    from Imervue.gui import semantic_search_dialog as mod
    monkeypatch.setattr(mod._IndexBuildWorker, "start", lambda self: self.run())
    index = ClipSearchIndex(_FakeEmbedder(), cache_path=tmp_path / "cache.npz")
    index.add("beach::elsewhere.png")
    dlg = SemanticSearchDialog(SimpleNamespace(main_window=None), index,
                               build_paths=["beach::here.png", "city::here.png"])
    try:
        dlg._query.setText("beach")
        dlg._search()
        found = _result_paths(dlg)
        status = dlg._status.text()
    finally:
        dlg.deleteLater()
    assert found == ["beach::here.png", "city::here.png"]
    assert "2" in status


def test_the_dialog_uses_the_cached_index(qapp, monkeypatch):
    from Imervue.gui import semantic_search_dialog as mod
    from Imervue.library import clip_search
    shared = ClipSearchIndex(_FakeEmbedder())
    opened: list = []
    monkeypatch.setattr(clip_search, "is_available", lambda: True)
    monkeypatch.setattr(clip_search, "get_default_index", lambda: shared)
    monkeypatch.setattr(mod.SemanticSearchDialog, "exec", lambda self: opened.append(self._index))
    monkeypatch.setattr(mod._IndexBuildWorker, "start", lambda self: None)
    viewer = SimpleNamespace(main_window=None, model=SimpleNamespace(images=["a.png"]))
    mod.open_semantic_search_dialog(viewer)
    assert opened == [shared]
