"""Material library dock."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    pass

from Imervue.paint.docks._helpers import (
    _HINT_LABEL_STYLE,
)


class _MaterialThumbnailButton(QToolButton):
    """QToolButton that doubles as a drag source for its material path.

    The dock keeps the click-to-emit ``material_chosen`` signal for
    casual one-click apply; a slow press-and-drag instead starts a
    QDrag carrying the material's path under the imervue MIME type so
    the canvas drop handler can spawn a fresh layer at the drop point.
    """

    def __init__(self, path: str, preview):
        super().__init__()
        self._path = str(path)
        self._preview = preview
        self._press_pos = None

    def mousePressEvent(self, event):  # pragma: no cover - Qt UI
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # pragma: no cover - Qt UI
        from PySide6.QtCore import QByteArray, QMimeData
        from PySide6.QtGui import QDrag

        from Imervue.paint.material_drop import MATERIAL_MIME_TYPE

        if (
            self._press_pos is None
            or not (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            super().mouseMoveEvent(event)
            return
        moved = (event.position().toPoint() - self._press_pos).manhattanLength()
        if moved < 8:
            return
        mime = QMimeData()
        mime.setData(
            MATERIAL_MIME_TYPE,
            QByteArray(self._path.encode("utf-8")),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        if self._preview is not None and not self._preview.isNull():
            drag.setPixmap(self._preview)
        drag.exec(Qt.DropAction.CopyAction)
        self._press_pos = None


class MaterialDock(QDockWidget):
    """Searchable thumbnail grid backed by a :class:`MaterialIndex`.

    The dock owns the visible category tabs and a search box. Clicking
    a thumbnail emits :attr:`material_chosen` with the entry's path
    so a host workspace can route it to the right consumer (pattern
    fill / brush-tip swap / image-paste).
    """

    material_chosen = Signal(str)   # absolute path of the chosen material

    def __init__(self, index=None, parent=None):
        from Imervue.paint.material_library import (
            MATERIAL_CATEGORIES,
            MaterialIndex,
        )

        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_material", "Materials"), parent)
        self._index = index if index is not None else MaterialIndex()
        self._all_categories = MATERIAL_CATEGORIES
        self._active_category: str | None = None

        body = QWidget()
        layout = QVBoxLayout(body)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            lang.get("paint_material_search", "Search materials…"),
        )
        self._search.setClearButtonEnabled(True)
        self._search.setToolTip(
            lang.get(
                "paint_material_search_tooltip",
                "Filter materials by name — Esc clears the field",
            ),
        )
        self._search.textChanged.connect(self._refresh_grid)
        layout.addWidget(self._search)

        self._tab_row = QHBoxLayout()
        self._tab_buttons: dict[str | None, QToolButton] = {}
        self._build_tab_buttons()
        layout.addLayout(self._tab_row)

        self._grid_host = QWidget()
        self._grid_layout = QGridLayout(self._grid_host)
        self._grid_layout.setSpacing(4)
        layout.addWidget(self._grid_host, stretch=1)

        self._empty_hint = QLabel(
            lang.get("paint_material_empty", "(no materials yet)"),
        )
        self._empty_hint.setStyleSheet(_HINT_LABEL_STYLE)
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_hint)

        self.setWidget(body)
        self._refresh_grid()

    # ---- public ----------------------------------------------------------

    def set_index(self, index) -> None:
        """Replace the index and refresh the grid."""
        self._index = index
        self._build_tab_buttons()
        self._refresh_grid()

    def index(self):
        return self._index

    # ---- internals -------------------------------------------------------

    def _build_tab_buttons(self) -> None:
        """Rebuild the category tab strip from the current index."""
        # Clear existing buttons first.
        while self._tab_row.count():
            child = self._tab_row.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        self._tab_buttons.clear()

        lang = language_wrapper.language_word_dict
        all_btn = QToolButton()
        all_btn.setText(lang.get("paint_material_all", "All"))
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.clicked.connect(lambda: self._on_tab_clicked(None))
        self._tab_row.addWidget(all_btn)
        self._tab_buttons[None] = all_btn
        for category in self._index.categories():
            btn = QToolButton()
            btn.setText(lang.get(
                f"paint_material_cat_{category}", category.replace("_", " ").title(),
            ))
            btn.setCheckable(True)
            btn.clicked.connect(lambda *_, c=category: self._on_tab_clicked(c))
            self._tab_row.addWidget(btn)
            self._tab_buttons[category] = btn
        self._tab_row.addStretch(1)
        self._active_category = None

    def _on_tab_clicked(self, category: str | None) -> None:
        self._active_category = category
        for cat, btn in self._tab_buttons.items():
            btn.setChecked(cat == category)
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        # Clear existing thumbnails.
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        results = self._index.filter(
            category=self._active_category,
            query=self._search.text(),
        )
        self._empty_hint.setVisible(not results)
        cols = 3
        for idx, entry in enumerate(results):
            row, col = divmod(idx, cols)
            btn = self._make_thumbnail(entry)
            self._grid_layout.addWidget(btn, row, col)

    def _make_thumbnail(self, entry) -> QToolButton:
        pix = self._render_thumbnail(entry)
        btn = _MaterialThumbnailButton(str(entry.path), pix)
        btn.setIconSize(QPixmap(64, 64).size())
        btn.setIcon(pix)
        btn.setText(entry.name)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.clicked.connect(
            lambda *_, p=str(entry.path): self.material_chosen.emit(p),
        )
        return btn

    @staticmethod
    def _render_thumbnail(entry) -> QPixmap:
        """Build a 64×64 thumbnail QPixmap from any kind of entry.

        Procedural entries call their provider and convert the numpy
        tile into a QImage. Path-backed entries load via QPixmap
        which handles every Qt-supported image format. Both fall back
        to a neutral placeholder swatch on failure so a broken entry
        never propagates a None into the grid.
        """
        if getattr(entry, "is_procedural", lambda: False)():
            try:
                tile = entry.render()
            except (ValueError, RuntimeError):
                tile = None
            if tile is not None:
                arr = np.ascontiguousarray(tile)
                h, w = arr.shape[:2]
                qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
                pix = QPixmap.fromImage(qimg.copy())
                return pix.scaled(
                    64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        pix = QPixmap(str(entry.path))
        if not pix.isNull():
            return pix.scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        placeholder = QPixmap(64, 64)
        placeholder.fill(QColor("#444"))
        return placeholder


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


