"""
Timeline view — images grouped by year / month / day, Google-Photos style.

Implemented as a QListView over a custom model that interleaves separator
rows between date groups. Double-click opens deep zoom; date source is EXIF
DateTimeOriginal when present, else file mtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import (
    QAbstractListModel, QModelIndex, Qt, QSize, QThreadPool, QRunnable,
    QObject, Signal,
)
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPixmap
from PySide6.QtWidgets import QListView

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

_THUMB_SIZE = 96


@dataclass
class _TimelineEntry:
    path: str | None   # None for separator rows
    label: str
    when: datetime
    icon: QIcon | None = None
    fetched: bool = False


class _WorkerSignals(QObject):
    done = Signal(str, QPixmap)


class _TimelineThumbWorker(QRunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            with Image.open(self.path) as src:
                src.thumbnail((_THUMB_SIZE, _THUMB_SIZE), Image.Resampling.LANCZOS)
                im = src.convert("RGBA")
                data = im.tobytes("raw", "RGBA")
                qimg = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
                pm = QPixmap.fromImage(qimg.copy())
        except Exception:  # noqa: BLE001
            pm = QPixmap(_THUMB_SIZE, _THUMB_SIZE)
            pm.fill(QColor(40, 40, 40))
        self.signals.done.emit(self.path, pm)


def _extract_date(path: str) -> datetime:
    """Prefer EXIF DateTimeOriginal; fall back to file mtime."""
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if exif:
                raw = exif.get(36867) or exif.get(306)  # DateTimeOriginal or DateTime
                if raw:
                    try:
                        return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass
    except Exception:  # noqa: BLE001
        pass
    try:
        mtime = Path(path).stat().st_mtime
        return datetime.fromtimestamp(mtime)
    except OSError:
        return datetime.fromtimestamp(0)


def _group_entries(paths: list[str], granularity: str = "month") -> list[_TimelineEntry]:
    dated = sorted(((p, _extract_date(p)) for p in paths), key=lambda x: x[1], reverse=True)
    entries: list[_TimelineEntry] = []
    last_key: str | None = None
    for path, when in dated:
        key = _group_key(when, granularity)
        if key != last_key:
            entries.append(_TimelineEntry(path=None, label=key, when=when))
            last_key = key
        entries.append(_TimelineEntry(path=path, label=Path(path).name, when=when))
    return entries


def _group_key(when: datetime, granularity: str) -> str:
    if granularity == "day":
        return when.strftime("%Y-%m-%d")
    if granularity == "year":
        return when.strftime("%Y")
    return when.strftime("%Y-%m")


class TimelineModel(QAbstractListModel):
    def __init__(self, paths: list[str], granularity: str = "month"):
        super().__init__()
        self._entries = _group_entries(paths, granularity)
        self._pool = QThreadPool.globalInstance()
        self._in_flight: set[str] = set()

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = QModelIndex()
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return entry.path
        if entry.path is None:
            return self._separator_data(entry, role)
        if role == Qt.ItemDataRole.DisplayRole:
            return entry.label
        if role == Qt.ItemDataRole.DecorationRole:
            self._ensure_fetched(entry)
            return entry.icon
        if role == Qt.ItemDataRole.ToolTipRole:
            return entry.path
        return None

    def _separator_data(self, entry: _TimelineEntry, role: int):
        if role == Qt.ItemDataRole.DisplayRole:
            return entry.label
        if role == Qt.ItemDataRole.FontRole:
            f = QFont()
            f.setBold(True)
            f.setPointSize(f.pointSize() + 2)
            return f
        if role == Qt.ItemDataRole.BackgroundRole:
            return QColor(30, 30, 30)
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(200, 200, 200)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        entry = self._entries[index.row()]
        if entry.path is None:
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def _ensure_fetched(self, entry: _TimelineEntry) -> None:
        if entry.fetched or entry.path is None or entry.path in self._in_flight:
            return
        self._in_flight.add(entry.path)
        worker = _TimelineThumbWorker(entry.path)
        worker.signals.done.connect(self._on_thumb)
        self._pool.start(worker)

    def _on_thumb(self, path: str, pm: QPixmap) -> None:
        self._in_flight.discard(path)
        for i, entry in enumerate(self._entries):
            if entry.path == path:
                entry.icon = QIcon(pm)
                entry.fetched = True
                idx = self.index(i)
                self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DecorationRole])
                break

    def path_at(self, row: int) -> str | None:
        if 0 <= row < len(self._entries):
            return self._entries[row].path
        return None


class TimelineView(QListView):
    def __init__(self, main_window: ImervueMainWindow):
        super().__init__(main_window)
        self._main_window = main_window
        self._model: TimelineModel | None = None
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setUniformItemSizes(False)
        self.setSpacing(6)
        self.setIconSize(QSize(_THUMB_SIZE, _THUMB_SIZE))
        self.setGridSize(QSize(_THUMB_SIZE + 24, _THUMB_SIZE + 36))
        self.doubleClicked.connect(self._on_double_click)

    def set_paths(self, paths: list[str], granularity: str = "month") -> None:
        self._model = TimelineModel(paths, granularity)
        self.setModel(self._model)

    def _on_double_click(self, index: QModelIndex) -> None:
        if self._model is None:
            return
        path = self._model.path_at(index.row())
        if not path:
            return
        from Imervue.gpu_image_view.images.image_loader import open_path
        open_path(main_gui=self._main_window.viewer, path=path)


def open_timeline(ui: ImervueMainWindow, granularity: str = "month") -> None:
    """Swap the central view stack to the timeline for the current image list."""
    viewer = ui.viewer
    paths = list(viewer.model.images)
    if not paths:
        if hasattr(ui, "toast"):
            ui.toast.info(
                language_wrapper.language_word_dict.get(
                    "timeline_no_images", "No images to timeline"
                )
            )
        return
    controller = _ensure_timeline_controller(ui)
    controller.show(paths, granularity)


def _ensure_timeline_controller(ui: ImervueMainWindow):
    existing = getattr(ui, "_timeline_controller", None)
    if existing is not None:
        return existing
    controller = _TimelineController(ui)
    ui._timeline_controller = controller
    return controller


class _TimelineController:
    """Owns the TimelineView widget and manages its lifecycle in the view stack."""

    def __init__(self, ui: ImervueMainWindow):
        self._ui = ui
        self._view = TimelineView(ui)
        # Insert into the main view stack (index 3).
        self._stack_index = ui._view_stack.addWidget(self._view)

    def show(self, paths: list[str], granularity: str) -> None:
        self._view.set_paths(paths, granularity)
        self._ui._view_stack.setCurrentIndex(self._stack_index)
