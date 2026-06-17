"""Natural-language ("beach sunset") image search over the current folder.

The semantic index and cosine ranking live in
:mod:`Imervue.library.clip_search`; this is the Qt front-end. Embedding the
folder needs the optional ``open_clip`` backend and is run in a worker so the UI
stays responsive — the text query itself (``query_text``) is instant. Tests
inject a ready index built on a fake embedder, so the dialog's search / display
logic is exercised without torch.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from Imervue.library.clip_search import ClipSearchIndex, SearchHit

logger = logging.getLogger("Imervue.gui.semantic_search_dialog")

_TOP_K = 60


class _IndexBuildWorker(QThread):
    """Embed a list of image paths into the index off the UI thread."""

    progress = Signal(int, int)
    done = Signal()

    def __init__(self, index: ClipSearchIndex, paths: list[str], parent=None) -> None:
        super().__init__(parent)
        self._index = index
        self._paths = paths

    def run(self) -> None:
        total = len(self._paths)
        for done_count, path in enumerate(self._paths, start=1):
            try:
                self._index.add(path)
            except Exception:  # noqa: BLE001 - one bad image must not abort the build
                logger.exception("Failed to embed %s", path)
            self.progress.emit(done_count, total)
        self.done.emit()


class SemanticSearchDialog(QDialog):
    """Type a description, rank the indexed images by semantic similarity.

    When *build_paths* is given the dialog embeds them in a worker first
    (disabling search until ready); when omitted the *index* is assumed ready
    (the path tests take).
    """

    def __init__(self, viewer, index: ClipSearchIndex,
                 build_paths: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._viewer = viewer
        self._index = index
        self._worker: _IndexBuildWorker | None = None
        self.setWindowTitle("Semantic Search")
        self.resize(520, 560)
        self._build_ui()
        if build_paths:
            self._start_build(build_paths)

    def _build_ui(self) -> None:
        self._query = QLineEdit()
        self._query.setPlaceholderText("Describe the photo — e.g. 'beach at sunset'")
        self._query.returnPressed.connect(self._search)
        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._search)
        top = QHBoxLayout()
        top.addWidget(self._query, 1)
        top.addWidget(self._search_btn)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._results = QListWidget()
        self._results.itemActivated.connect(self._open_item)
        self._status = QLabel("")

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._progress)
        layout.addWidget(self._results, 1)
        layout.addWidget(self._status)

    # -- index build --------------------------------------------------

    def _start_build(self, paths: list[str]) -> None:
        self._set_search_enabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, len(paths))
        self._status.setText("Building index…")
        self._worker = _IndexBuildWorker(self._index, paths, self)
        self._worker.progress.connect(lambda done, _t: self._progress.setValue(done))
        self._worker.done.connect(self._on_index_ready)
        self._worker.start()

    def _on_index_ready(self) -> None:
        self._progress.setVisible(False)
        self._set_search_enabled(True)
        self._status.setText(f"Indexed {self._index.size} image(s) — ready to search")

    def _set_search_enabled(self, enabled: bool) -> None:
        self._query.setEnabled(enabled)
        self._search_btn.setEnabled(enabled)

    # -- search -------------------------------------------------------

    def _search(self) -> None:
        text = self._query.text().strip()
        if not text:
            return
        try:
            hits = self._index.query_text(text, top_k=_TOP_K)
        except (RuntimeError, ValueError) as exc:
            self._status.setText(str(exc))
            return
        self._populate(hits)

    def _populate(self, hits: list[SearchHit]) -> None:
        self._results.clear()
        for hit in hits:
            item = QListWidgetItem(f"{Path(hit.path).name}    ({hit.score:.2f})")
            item.setData(Qt.ItemDataRole.UserRole, hit.path)
            item.setToolTip(hit.path)
            self._results.addItem(item)
        self._status.setText(f"{len(hits)} result(s)")

    def _open_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        from Imervue.gpu_image_view.images.image_loader import open_path
        open_path(main_gui=self._viewer, path=path)


def _warn_unavailable(parent) -> None:
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.information(
        parent, "Semantic Search",
        "Natural-language search needs the optional 'open_clip_torch' backend.\n"
        "Install it (pip install open_clip_torch torch) to enable this feature.")


def open_semantic_search_dialog(viewer) -> None:
    """Open natural-language search over the viewer's current folder."""
    from Imervue.library.clip_search import OpenClipEmbedder, is_available
    parent = getattr(viewer, "main_window", viewer)
    if not is_available():
        _warn_unavailable(parent)
        return
    images = [str(p) for p in getattr(viewer.model, "images", [])]
    index = ClipSearchIndex(OpenClipEmbedder())
    SemanticSearchDialog(viewer, index, build_paths=images, parent=parent).exec()
