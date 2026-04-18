"""
麵包屑路徑列
Breadcrumb bar — clickable path segments above the viewer.

Each segment is a flat button; clicking navigates the main window
to that folder. The bar is hidden when no folder is active.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QSizePolicy,
    QScrollArea,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


_SEGMENT_STYLE = (
    "QPushButton {"
    " border: none; padding: 2px 6px; color: #c8c8c8;"
    " background: transparent; text-align: left;"
    "}"
    "QPushButton:hover { color: #ffffff; background: rgba(255,255,255,0.08);"
    " border-radius: 3px; }"
)
_SEP_STYLE = "color: #666; padding: 0 2px;"


class BreadcrumbBar(QScrollArea):
    """Horizontal clickable breadcrumb — scrolls when path is very long."""

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__()
        self._main_window = main_window

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._container = QWidget()
        self._layout = QHBoxLayout(self._container)
        self._layout.setContentsMargins(4, 0, 4, 0)
        self._layout.setSpacing(2)
        self._layout.addStretch(1)
        self.setWidget(self._container)

        self.set_path("")

    # -------- Public API --------
    def set_path(self, path: str) -> None:
        """Replace the segments with buttons derived from ``path``.

        An empty string hides the bar; passing a folder (or a file inside a
        folder) renders one button per ancestor.
        """
        self._clear_segments()
        if not path:
            self.setVisible(False)
            return

        p = Path(path)
        if p.is_file():
            p = p.parent

        parts = list(p.parts)
        if not parts:
            self.setVisible(False)
            return

        # Build segments
        for i, part in enumerate(parts):
            seg_path = str(Path(*parts[: i + 1]))
            btn = QPushButton(part or seg_path)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_SEGMENT_STYLE)
            btn.clicked.connect(lambda _=False, sp=seg_path: self._navigate(sp))
            # Insert before the trailing stretch
            self._layout.insertWidget(self._layout.count() - 1, btn)

            if i < len(parts) - 1:
                sep = QLabel("\u203A")  # ›
                sep.setStyleSheet(_SEP_STYLE)
                self._layout.insertWidget(self._layout.count() - 1, sep)

        self.setVisible(True)

    # -------- Internal --------
    def _clear_segments(self) -> None:
        # Remove all widgets except the trailing stretch
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()

    def _navigate(self, folder: str) -> None:
        from Imervue.gpu_image_view.images.image_loader import open_path

        mw = self._main_window
        if not Path(folder).is_dir():
            return
        try:
            mw.model.setRootPath(folder)
            mw.tree.setRootIndex(mw.model.index(folder))
            mw.viewer.clear_tile_grid()
            open_path(main_gui=mw.viewer, path=folder)
            from Imervue.multi_language.language_wrapper import language_wrapper
            mw.filename_label.setText(
                language_wrapper.language_word_dict.get(
                    "main_window_current_folder_format"
                ).format(path=folder)
            )
            mw.watch_folder(folder)
            from Imervue.user_settings.user_setting_dict import user_setting_dict
            user_setting_dict["user_last_folder"] = folder
        except Exception:
            import logging
            logging.getLogger("Imervue").exception(
                "breadcrumb navigate to %s failed", folder
            )
