"""Central image load issue panel."""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class ImageIssuePanel(QWidget):
    """List of failed/offline images with recovery actions."""

    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        self._issues: dict[str, str] = {}
        lang = language_wrapper.language_word_dict

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QLabel(lang.get(
            "image_issues_title",
            "Image load issues",
        )))

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self._list, stretch=1)

        row = QHBoxLayout()
        actions = (
            ("image_issues_retry", "Retry", self.retry_selected),
            ("image_issues_reveal", "Reveal", self.reveal_selected),
            ("image_issues_remove", "Remove", self.remove_selected),
            ("missing_relocate", "Relocate Missing File...", self.relocate_selected),
        )
        for key, fallback, slot in actions:
            btn = QPushButton(lang.get(key, fallback))
            btn.clicked.connect(slot)
            row.addWidget(btn)
        layout.addLayout(row)

    def add_issue(self, path: str, message: str) -> None:
        if not path:
            return
        self._issues[path] = message or "Load failed"
        self._refresh()
        dock = getattr(self._ui, "_image_issue_dock", None)
        if dock is not None:
            dock.show()

    def clear_issue(self, path: str) -> None:
        if path in self._issues:
            self._issues.pop(path, None)
            self._refresh()

    def issue_count(self) -> int:
        return len(self._issues)

    def selected_paths(self) -> list[str]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self._list.selectedItems()]

    def retry_selected(self) -> None:
        viewer = self._ui.viewer
        for path in self.selected_paths():
            if path in getattr(viewer, "tile_errors", {}):
                from Imervue.gpu_image_view.tile_loader import _retry_thumbnail
                viewer.tile_errors.pop(path, None)
                _retry_thumbnail(viewer, path, viewer._load_generation)
            elif path in getattr(getattr(viewer, "model", None), "images", []):
                viewer._deep_zoom_error = None
                viewer.load_deep_zoom_image(path)

    def reveal_selected(self) -> None:
        paths = self.selected_paths()
        if not paths:
            return
        _reveal_path(paths[0])

    def remove_selected(self) -> None:
        paths = set(self.selected_paths())
        if not paths:
            return
        viewer = self._ui.viewer
        base = [
            p for p in getattr(viewer, "_unfiltered_images", viewer.model.images)
            if p not in paths
        ]
        viewer._unfiltered_images = base
        viewer.model.set_images([p for p in viewer.model.images if p not in paths])
        for path in paths:
            self._issues.pop(path, None)
            getattr(viewer, "tile_errors", {}).pop(path, None)
            getattr(viewer, "offline_paths", set()).discard(path)
        self._ui._apply_image_filter()
        self._refresh()

    def relocate_selected(self) -> None:
        paths = self.selected_paths()
        if not paths:
            return
        old_path = paths[0]
        lang = language_wrapper.language_word_dict
        new_path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("missing_relocate", "Relocate Missing File..."),
            str(Path(old_path).parent),
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.gif *.svg "
            "*.cr2 *.nef *.arw *.dng *.raf *.orf)",
        )
        if not new_path:
            return
        if hasattr(self._ui, "_apply_missing_replacements"):
            self._ui._apply_missing_replacements({old_path: new_path})
        self.clear_issue(old_path)

    def _refresh(self) -> None:
        self._list.clear()
        for path, message in sorted(
            self._issues.items(),
            key=lambda item: Path(item[0]).name.lower(),
        ):
            item = QListWidgetItem(f"{Path(path).name} - {message}")
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._list.addItem(item)


def _reveal_path(path: str) -> None:
    with contextlib.suppress(Exception):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", str(Path(path).parent)])
