"""Image-list Qt view and compatibility exports."""

from __future__ import annotations
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import (
    QModelIndex,
    Qt,
    QSize,
    Signal,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QStyledItemDelegate,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.file_manager import reveal_or_warn

from Imervue.gui.image_list_model import ImageListModel
from Imervue.gui.image_list_edit import ImageListEditMixin
from Imervue.gui.image_list_keyboard import ImageListKeyboardMixin
from Imervue.gui.image_list_context import ImageListContextMixin
from Imervue.gui.image_list_rows import _RowMeta
from Imervue.gui.image_list_worker import _ThumbWorker, _ThumbWorkerSignals
from Imervue.gui.image_list_values import (
    _THUMB_SIZE,
    LIST_MARK_ACTIONS,
    _MAX_THUMB_RETRIES,
    _STAR_FILLED,
    _STAR_EMPTY,
    _RATING_MAX,
    _rating_for,
    _format_rating,
    star_at,
    _fmt_size,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


__all__ = [
    "ImageListModel",
    "ImageListView",
    "star_at",
    "LIST_MARK_ACTIONS",
    "_RowMeta",
    "_ThumbWorker",
    "_ThumbWorkerSignals",
    "_MAX_THUMB_RETRIES",
    "_STAR_EMPTY",
    "_rating_for",
    "_format_rating",
    "_fmt_size",
    "Image",
]


class _RowDelegate(QStyledItemDelegate):
    """Fixed 48-px row height for consistent thumbnail rendering."""

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), max(s.height(), _THUMB_SIZE + 4))


class ImageListView(ImageListKeyboardMixin, ImageListEditMixin, ImageListContextMixin, QTableView):
    """QTableView configured for image browsing.

    Renders an "empty state" hint overlay when the model carries no
    rows so users opening a fresh / image-less folder don't stare at
    a blank table — they get a one-line cue confirming the folder is
    empty (rather than e.g. broken).
    """

    image_activated = Signal(str)  # emitted on double-click / Enter

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__()
        self._main_window = main_window

        self._model = ImageListModel()
        self.setModel(self._model)

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        # No column sorted until the user clicks one: the rows keep the viewer's order.
        self.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setHighlightSections(False)
        self.setItemDelegate(_RowDelegate(self))

        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        self.setColumnWidth(ImageListModel.COL_THUMB, 64)
        self.setColumnWidth(ImageListModel.COL_LABEL, 70)
        self.setColumnWidth(ImageListModel.COL_RATING, 86)
        self.setColumnWidth(ImageListModel.COL_NAME, 320)
        self.setColumnWidth(ImageListModel.COL_RES, 110)
        self.setColumnWidth(ImageListModel.COL_SIZE, 100)
        self.setColumnWidth(ImageListModel.COL_TYPE, 70)

        self.doubleClicked.connect(self._on_activate)

    # --- Public API ---
    def set_paths(self, paths: list[str], metadata_index=None) -> None:
        """Show *paths*, sorted again by the column the user chose, if any.

        The list is rebuilt after a delete, a folder refresh or a new folder;
        the header kept its sort arrow while the rows came back in the
        viewer's order.
        """
        self._model.set_paths(paths, metadata_index=metadata_index)
        header = self.horizontalHeader()
        self._model.sort(header.sortIndicatorSection(), header.sortIndicatorOrder())

    def refetch(self, paths) -> None:
        """Read *paths* again: they changed on disk (see :meth:`ImageListModel.refetch`)."""
        self._model.refetch(paths)

    def selected_paths(self) -> list[str]:
        return [
            self._model.path_at(idx.row())
            for idx in self.selectionModel().selectedRows()
            if self._model.path_at(idx.row())
        ]

    # --- Events ---
    def _on_activate(self, index: QModelIndex) -> None:
        path = self._model.path_at(index.row())
        if path:
            self.image_activated.emit(path)

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        """A left click in the Rating column rates that row by the star it lands on.

        The same star again clears it, as the rating keys do. The click still
        selects the row.
        """
        index = self.indexAt(event.position().toPoint())
        if (
            event.button() == Qt.MouseButton.LeftButton
            and index.isValid()
            and index.column() == ImageListModel.COL_RATING
            and self._main_window is not None
        ):
            rect = self.visualRect(index)
            strip = self.fontMetrics().horizontalAdvance(_STAR_FILLED * _RATING_MAX)
            star = star_at(event.position().x(), rect.center().x(), strip)
            path = self._model.path_at(index.row())
            if path:
                self._main_window.mark_list_selection(f"rate_{star}", [path])
        super().mousePressEvent(event)

    @staticmethod
    def _reveal_path(path: str) -> None:
        """Open the OS file manager with ``path`` selected, as Show in Explorer does."""
        reveal_or_warn(path)

    def paintEvent(self, event):  # noqa: N802 - Qt override
        """Draw an empty-state hint when the model has no rows.

        Paint after the base class so the hint sits on top of the
        empty viewport. The same widget paints a populated table
        normally — the hint only shows when ``rowCount`` is 0.
        """
        super().paintEvent(event)
        if self._model.rowCount() > 0:
            return
        from PySide6.QtGui import QPainter, QFont

        lang = language_wrapper.language_word_dict
        msg = lang.get(
            "image_list_empty_hint",
            "No images in this folder",
        )
        painter = QPainter(self.viewport())
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QColor(120, 120, 120))
            font = QFont(painter.font())
            font.setPointSize(font.pointSize() + 2)
            painter.setFont(font)
            painter.drawText(
                self.viewport().rect(),
                Qt.AlignmentFlag.AlignCenter,
                msg,
            )
        finally:
            painter.end()
