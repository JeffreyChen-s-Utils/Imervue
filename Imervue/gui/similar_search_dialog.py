"""
Similar-image search dialog — find visually similar images by pHash.

Uses the current deep-zoom image (or the first selected tile) as the query
and queries ``image_index.similar_by_phash``. Results are shown with their
Hamming distance; double-click opens.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSpinBox,
)

from Imervue.library import image_index
from Imervue.library.phash import compute_phash
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class SimilarSearchDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow, query_path: str):
        super().__init__(ui)
        self._ui = ui
        self._query_path = query_path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("similar_search_title", "Find Similar Images"))
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("similar_search_query", "Query: {name}").format(
                name=Path(query_path).name,
            )
        ))

        row = QHBoxLayout()
        row.addWidget(QLabel(lang.get("similar_search_distance", "Max Hamming distance:")))
        self._dist = QSpinBox()
        self._dist.setRange(0, 64)
        self._dist.setValue(10)
        row.addWidget(self._dist)
        search_btn = QPushButton(lang.get("similar_search_run", "Search"))
        search_btn.clicked.connect(self._run)
        row.addWidget(search_btn)
        row.addStretch()
        layout.addLayout(row)

        self._results = QListWidget()
        self._results.itemDoubleClicked.connect(self._open_selected)
        layout.addWidget(self._results, stretch=1)

        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._run()

    def _run(self) -> None:
        row = image_index.get_image(self._query_path)
        phash = (
            row["phash"] if row and row["phash"] is not None
            else compute_phash(self._query_path)
        )
        if phash is None:
            return
        if row is None or row.get("phash") is None:
            image_index.upsert_image(self._query_path, phash=phash)
        results = image_index.similar_by_phash(
            int(phash), max_distance=self._dist.value(), limit=500)
        self._results.clear()
        for path, dist in results:
            item = QListWidgetItem(f"[{dist:02d}] {path}")
            item.setData(1000, path)
            self._results.addItem(item)

    def _open_selected(self) -> None:
        item = self._results.currentItem()
        if item is None:
            return
        path = item.data(1000)
        from Imervue.gpu_image_view.images.image_loader import open_path
        open_path(main_gui=self._ui.viewer, path=path)
        self.accept()


def open_similar_search(ui: ImervueMainWindow) -> None:
    viewer = ui.viewer
    images = viewer.model.images
    query: str | None = None
    if viewer.deep_zoom and 0 <= viewer.current_index < len(images):
        query = images[viewer.current_index]
    elif viewer.selected_tiles:
        query = next(iter(viewer.selected_tiles))
    elif images:
        query = images[0]
    if not query:
        return
    SimilarSearchDialog(ui, query).exec()
