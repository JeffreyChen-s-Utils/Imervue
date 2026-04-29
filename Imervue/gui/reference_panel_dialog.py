"""Reference Panel — dockable mood-board / comparison surface.

Modeless QDialog (the staging-tray pattern) that pins reference images
for side-by-side comparison while editing. Drag-drop from any folder
adds entries; the list is persisted across restarts via
:mod:`Imervue.library.reference_pins`.

UX:
* Thumbnails on the left, full preview on the right.
* Single-click selects + previews; double-click opens in the main viewer.
* Up/Down buttons reorder; Remove and Clear are explicit.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
)

from Imervue.library import reference_pins
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

_THUMB_SIZE = 96
_PREVIEW_HINT = (640, 480)
_SUPPORTED_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp",
}


class ReferencePanelDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("reference_panel_title", "Reference Panel"))
        self.resize(820, 540)
        self.setAcceptDrops(True)
        # Modeless so the user can keep editing in the main window.
        self.setModal(False)

        self._list = self._build_list()
        self._preview = self._build_preview(lang)
        self._count_label = QLabel()

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_header(lang))
        layout.addWidget(self._build_splitter(), stretch=1)
        layout.addLayout(self._build_button_row(lang))

        self._refresh()

    # ---- builders ---------------------------------------------------------

    def _build_header(self, lang: dict) -> QLabel:
        msg = lang.get(
            "reference_panel_explain",
            "Pin reference images for visual comparison. "
            "Drag-drop from any folder. The list persists across restarts.",
        )
        label = QLabel(msg)
        label.setWordWrap(True)
        label.setStyleSheet("color: #888;")
        return label

    @staticmethod
    def _build_list() -> QListWidget:
        widget = QListWidget()
        widget.setIconSize(QSize(_THUMB_SIZE, _THUMB_SIZE))
        widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        widget.setMinimumWidth(220)
        return widget

    @staticmethod
    def _build_preview(lang: dict) -> QLabel:
        preview = QLabel(lang.get("reference_panel_no_preview", "No reference selected."))
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumSize(*_PREVIEW_HINT)
        preview.setStyleSheet("background:#1f1f1f;color:#999;")
        return preview

    def _build_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._list)
        splitter.addWidget(self._preview)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._on_item_activated)
        return splitter

    def _build_button_row(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        add_btn = QPushButton(lang.get("reference_panel_add", "Add Files…"))
        add_btn.clicked.connect(self._on_add_clicked)
        add_cur = QPushButton(lang.get("reference_panel_add_current", "Add Current Image"))
        add_cur.clicked.connect(self._on_add_current)
        up_btn = QPushButton(lang.get("reference_panel_up", "Up"))
        up_btn.clicked.connect(lambda: self._on_move(up=True))
        down_btn = QPushButton(lang.get("reference_panel_down", "Down"))
        down_btn.clicked.connect(lambda: self._on_move(up=False))
        remove_btn = QPushButton(lang.get("reference_panel_remove", "Remove"))
        remove_btn.clicked.connect(self._on_remove)
        clear_btn = QPushButton(lang.get("reference_panel_clear", "Clear"))
        clear_btn.clicked.connect(self._on_clear)
        close_btn = QPushButton(lang.get("close", "Close"))
        close_btn.clicked.connect(self.accept)

        for btn in (add_btn, add_cur, up_btn, down_btn, remove_btn, clear_btn):
            row.addWidget(btn)
        row.addWidget(self._count_label)
        row.addStretch(1)
        row.addWidget(close_btn)
        return row

    # ---- drag & drop ------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # pragma: no cover - Qt UI
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # pragma: no cover - Qt UI
        paths: list[str] = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local and Path(local).suffix.lower() in _SUPPORTED_EXTS:
                paths.append(local)
        if paths:
            reference_pins.add_many(paths)
            self._refresh()

    # ---- handlers ---------------------------------------------------------

    def _on_add_clicked(self) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        filter_str = lang.get(
            "reference_panel_filter",
            "Images (*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp)",
        )
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            lang.get("reference_panel_pick_files", "Select reference images"),
            "",
            filter_str,
        )
        if paths:
            reference_pins.add_many(paths)
            self._refresh()

    def _on_add_current(self) -> None:  # pragma: no cover - Qt UI
        viewer = getattr(self._ui, "viewer", None)
        if viewer is None:
            return
        images = list(getattr(viewer.model, "images", []))
        idx = getattr(viewer, "current_index", -1)
        if 0 <= idx < len(images) and reference_pins.add(str(images[idx])):
            self._refresh()

    def _on_remove(self) -> None:
        for item in self._list.selectedItems():
            reference_pins.remove(item.data(Qt.ItemDataRole.UserRole))
        self._refresh()

    def _on_clear(self) -> None:
        reference_pins.clear()
        self._refresh()

    def _on_move(self, *, up: bool) -> None:
        items = self._list.selectedItems()
        if not items:
            return
        path = items[0].data(Qt.ItemDataRole.UserRole)
        if reference_pins.move(path, up=up):
            self._refresh()
            self._reselect(path)

    def _on_selection_changed(self) -> None:
        items = self._list.selectedItems()
        if not items:
            self._preview.setText(language_wrapper.language_word_dict.get(
                "reference_panel_no_preview", "No reference selected.",
            ))
            self._preview.setPixmap(QPixmap())
            return
        path = items[0].data(Qt.ItemDataRole.UserRole)
        pix = _load_preview_pixmap(path, self._preview.size())
        if pix is None:
            self._preview.setText(language_wrapper.language_word_dict.get(
                "reference_panel_load_failed", "Failed to load preview.",
            ))
            self._preview.setPixmap(QPixmap())
            return
        self._preview.setText("")
        self._preview.setPixmap(pix)

    def _on_item_activated(self, item: QListWidgetItem) -> None:  # pragma: no cover - Qt UI
        path = item.data(Qt.ItemDataRole.UserRole)
        opener = getattr(self._ui, "open_file", None) or getattr(self._ui, "open_path", None)
        if callable(opener) and path:
            opener(path)

    # ---- list refresh -----------------------------------------------------

    def _refresh(self) -> None:
        self._list.clear()
        for path in reference_pins.get_all():
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            icon = _load_thumb_icon(path)
            if icon is not None:
                item.setIcon(icon)
            self._list.addItem(item)
        self._count_label.setText(
            language_wrapper.language_word_dict.get(
                "reference_panel_count", "Pinned: {n}",
            ).format(n=reference_pins.count()),
        )
        self._on_selection_changed()

    def _reselect(self, path: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self._list.setCurrentItem(item)
                return


# ---------------------------------------------------------------------------
# Image helpers — kept module-level so they can be exercised by tests.
# ---------------------------------------------------------------------------


def _load_thumb_icon(path: str):
    """Best-effort thumbnail QIcon. Returns ``None`` on read failure."""
    from PySide6.QtGui import QIcon
    pix = _load_preview_pixmap(path, QSize(_THUMB_SIZE, _THUMB_SIZE))
    if pix is None:
        return None
    return QIcon(pix)


def _load_preview_pixmap(path: str, target: QSize) -> QPixmap | None:
    try:
        with Image.open(path) as src:
            rgba = src.convert("RGBA")
            rgba.thumbnail(
                (max(8, target.width()), max(8, target.height())),
                Image.Resampling.LANCZOS,
            )
            data = rgba.tobytes("raw", "RGBA")
            width, height = rgba.size
        from PySide6.QtGui import QImage
        qimg = QImage(data, width, height, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg.copy())
    except (OSError, ValueError):
        return None


def open_reference_panel(ui: ImervueMainWindow) -> None:
    """Show (or raise to front) the singleton reference panel."""
    existing = getattr(ui, "_reference_panel", None)
    if existing is not None and existing.isVisible():
        existing.raise_()
        existing.activateWindow()
        return
    panel = ReferencePanelDialog(ui)
    ui._reference_panel = panel  # noqa: SLF001  # ad-hoc cache, mirrors other panels
    panel.show()
