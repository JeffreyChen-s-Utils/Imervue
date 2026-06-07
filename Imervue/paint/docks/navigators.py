"""Navigator, history and page-navigator docks."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    pass

from Imervue.paint.docks._helpers import (
    _HINT_LABEL_STYLE,
    _slider,
)


class NavigatorDock(QDockWidget):
    """Mini-map preview of the current canvas with a zoom slider."""

    zoom_changed = Signal(float)
    fit_requested = Signal()

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_navigator", "Navigator"), parent)

        body = QWidget()
        layout = QVBoxLayout(body)

        self._preview = QLabel(lang.get("paint_navigator_no_image", "(no canvas)"))
        self._preview.setMinimumSize(180, 140)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("background:#222;color:#888;border:1px solid #333;")
        layout.addWidget(self._preview)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel(lang.get("paint_navigator_zoom", "Zoom:")))
        self._zoom_slider = _slider(5, 800, 100)
        self._zoom_slider.valueChanged.connect(
            lambda v: self.zoom_changed.emit(v / 100.0),
        )
        self._zoom_slider.setToolTip(lang.get(
            "paint_navigator_zoom_tooltip",
            "Drag to zoom the canvas (5–800%) — same as Ctrl+wheel "
            "but with a numeric scrub",
        ))
        zoom_row.addWidget(self._zoom_slider, stretch=1)

        fit_btn = QPushButton(lang.get("paint_navigator_fit", "Fit"))
        fit_btn.clicked.connect(self.fit_requested.emit)
        # Pull the live binding from the registry so the tooltip stays
        # in sync if the user remaps Fit View.
        from Imervue.paint.shortcut_registry import load_shortcuts
        try:
            fit_key = load_shortcuts().get("paint.view.fit")
        except KeyError:
            fit_key = ""
        base_tip = lang.get(
            "paint_navigator_fit_tooltip",
            "Reset the canvas to fit the viewport",
        )
        fit_btn.setToolTip(f"{base_tip} ({fit_key})" if fit_key else base_tip)
        zoom_row.addWidget(fit_btn)

        layout.addLayout(zoom_row)
        layout.addStretch(1)
        self.setWidget(body)

    def set_zoom(self, factor: float) -> None:
        """Update the slider without emitting ``zoom_changed`` again."""
        self._zoom_slider.blockSignals(True)
        try:
            self._zoom_slider.setValue(int(round(factor * 100)))
        finally:
            self._zoom_slider.blockSignals(False)

    def set_preview_image(self, pixmap: QPixmap | None) -> None:
        if pixmap is None or pixmap.isNull():
            self._preview.setPixmap(QPixmap())
            self._preview.setText(language_wrapper.language_word_dict.get(
                "paint_navigator_no_image", "(no canvas)",
            ))
            return
        scaled = pixmap.scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setText("")
        self._preview.setPixmap(scaled)


# ---------------------------------------------------------------------------
# History dock — undo/redo log
# ---------------------------------------------------------------------------


class HistoryDock(QDockWidget):
    """Undo / redo log with click-to-jump-to-state."""

    state_selected = Signal(int)

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_history", "History"), parent)

        body = QWidget()
        layout = QVBoxLayout(body)
        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, stretch=1)
        self._hint = QLabel(lang.get(
            "paint_history_empty", "(no undo states yet)",
        ))
        self._hint.setStyleSheet(_HINT_LABEL_STYLE)
        layout.addWidget(self._hint)
        self.setWidget(body)

    def set_states(self, labels: list[str], current_index: int) -> None:
        self._list.clear()
        for label in labels:
            self._list.addItem(QListWidgetItem(label))
        if 0 <= current_index < self._list.count():
            self._list.setCurrentRow(current_index)
        self._hint.setVisible(not labels)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:  # pragma: no cover - Qt UI
        self.state_selected.emit(self._list.row(item))


# ---------------------------------------------------------------------------
# Page navigator dock — multi-page projects
# ---------------------------------------------------------------------------


class PageNavigatorDock(QDockWidget):
    """Page-strip view for a :class:`PaintProject`.

    Shows one row per page (thumbnail + name) plus add / remove /
    move-up / move-down buttons. Clicking a row emits
    :attr:`page_activated` with the page index so the workspace can
    bind that page's document into the canvas.
    """

    page_activated = Signal(int)
    add_requested = Signal()
    remove_requested = Signal(int)
    move_requested = Signal(int, int)   # (src, dst)

    def __init__(self, project=None, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_pages", "Pages"), parent)
        self._project = project

        body = QWidget()
        layout = QVBoxLayout(body)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list, stretch=1)

        row = QHBoxLayout()
        for key, fallback, slot, tooltip_key, tooltip_fallback in (
            ("paint_pages_add", "+", self._on_add,
             "paint_pages_add_tooltip", "Add page"),
            ("paint_pages_remove", "−", self._on_remove,
             "paint_pages_remove_tooltip", "Delete page"),
            ("paint_pages_up", "↑", lambda: self._on_move(up=True),
             "paint_pages_up_tooltip", "Move page up"),
            ("paint_pages_down", "↓", lambda: self._on_move(up=False),
             "paint_pages_down_tooltip", "Move page down"),
        ):
            btn = QToolButton()
            btn.setText(lang.get(key, fallback))
            btn.setToolTip(lang.get(tooltip_key, tooltip_fallback))
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        layout.addLayout(row)
        self.setWidget(body)

        self.refresh()

    # ---- public ----------------------------------------------------------

    def set_project(self, project) -> None:
        self._project = project
        self.refresh()

    def project(self):
        return self._project

    def refresh(self) -> None:
        self._list.blockSignals(True)
        try:
            self._list.clear()
            if self._project is None:
                return
            for idx, page in enumerate(self._project.pages):
                self._list.addItem(QListWidgetItem(f"{idx + 1}. {page.name}"))
            active = self._project.active_page_index
            if 0 <= active < self._list.count():
                self._list.setCurrentRow(active)
        finally:
            self._list.blockSignals(False)

    # ---- internals -------------------------------------------------------

    def _on_row_changed(self, row: int) -> None:
        if self._project is None or row < 0:
            return
        if row != self._project.active_page_index:
            self.page_activated.emit(row)

    def _on_add(self) -> None:
        self.add_requested.emit()

    def _on_remove(self) -> None:
        if self._project is None:
            return
        self.remove_requested.emit(self._project.active_page_index)

    def _on_move(self, *, up: bool) -> None:
        if self._project is None:
            return
        src = self._project.active_page_index
        dst = src - 1 if up else src + 1
        if not 0 <= dst < self._project.page_count:
            return
        self.move_requested.emit(src, dst)


# ---------------------------------------------------------------------------
# Material library dock
# ---------------------------------------------------------------------------


