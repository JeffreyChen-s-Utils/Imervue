"""
多標籤過濾對話框
Multi-tag filter dialog — pick tags/albums with AND / OR logic.

A lightweight dialog that lets the user combine multiple tags or albums
using boolean AND (intersect) or OR (union) and then pushes the result
back to the viewer's tile grid.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QRadioButton, QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def combine_sets(groups: list[set[str]], mode: str) -> set[str]:
    """AND → intersection, OR → union. Empty ``groups`` → empty set."""
    if not groups:
        return set()
    if mode == "and":
        result = set(groups[0])
        for g in groups[1:]:
            result &= g
        return result
    # default OR
    result: set[str] = set()
    for g in groups:
        result |= g
    return result


class TagFilterDialog(QDialog):
    """Dialog that collects (tags + albums + mode) → applied to the grid."""

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__(main_window)
        self._main_window = main_window
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("tag_filter_title", "Filter by Tags / Albums"))
        self.resize(460, 560)

        root = QVBoxLayout(self)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(lang.get("tag_filter_mode", "Match:")))
        self._radio_or = QRadioButton(lang.get("tag_filter_or", "Any (OR)"))
        self._radio_and = QRadioButton(lang.get("tag_filter_and", "All (AND)"))
        self._radio_or.setChecked(True)
        mode_group = QButtonGroup(self)
        mode_group.addButton(self._radio_or)
        mode_group.addButton(self._radio_and)
        mode_row.addWidget(self._radio_or)
        mode_row.addWidget(self._radio_and)
        mode_row.addStretch(1)
        root.addLayout(mode_row)

        # Tags section
        root.addWidget(QLabel(lang.get("tag_filter_tags", "Tags")))
        self._tag_list = self._build_checkable_list(self._load_tags())
        root.addWidget(self._tag_list, stretch=1)

        # Albums section
        root.addWidget(QLabel(lang.get("tag_filter_albums", "Albums")))
        self._album_list = self._build_checkable_list(self._load_albums())
        root.addWidget(self._album_list, stretch=1)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # -------- Data --------
    @staticmethod
    def _load_tags() -> dict[str, list[str]]:
        try:
            from Imervue.user_settings.tags import get_all_tags
            return get_all_tags() or {}
        except Exception:
            return {}

    @staticmethod
    def _load_albums() -> dict[str, list[str]]:
        try:
            from Imervue.user_settings.tags import get_all_albums
            return get_all_albums() or {}
        except Exception:
            return {}

    @staticmethod
    def _build_checkable_list(groups: dict[str, list[str]]) -> QListWidget:
        lw = QListWidget()
        for name in sorted(groups.keys()):
            count = len(groups[name])
            item = QListWidgetItem(f"{name}  ({count})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, name)
            lw.addItem(item)
        if lw.count() == 0:
            empty = QListWidgetItem("—")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            lw.addItem(empty)
        return lw

    # -------- Accept --------
    def _on_accept(self) -> None:
        selected_tags = self._checked_items(self._tag_list)
        selected_albums = self._checked_items(self._album_list)
        if not (selected_tags or selected_albums):
            self.reject()
            return

        groups: list[set[str]] = []
        tag_map = self._load_tags()
        album_map = self._load_albums()
        for name in selected_tags:
            groups.append({p for p in tag_map.get(name, []) if Path(p).is_file()})
        for name in selected_albums:
            groups.append({p for p in album_map.get(name, []) if Path(p).is_file()})

        mode = "and" if self._radio_and.isChecked() else "or"
        result = sorted(combine_sets(groups, mode))

        lang = language_wrapper.language_word_dict
        if not result:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.warning(
                    lang.get("tag_filter_no_match", "No images match the selected tags.")
                )
            self.reject()
            return

        viewer = self._main_window.viewer
        if not getattr(viewer, "_unfiltered_images", None):
            viewer._unfiltered_images = list(viewer.model.images)
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(result)
        if hasattr(self._main_window, "toast"):
            self._main_window.toast.info(
                lang.get("tag_filter_applied", "Tag filter: {n} images")
                    .format(n=len(result))
            )
        self.accept()

    @staticmethod
    def _checked_items(lw: QListWidget) -> list[str]:
        out = []
        for i in range(lw.count()):
            it = lw.item(i)
            if it.flags() & Qt.ItemFlag.ItemIsUserCheckable \
                    and it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out


def open_tag_filter_dialog(main_window: ImervueMainWindow) -> None:
    TagFilterDialog(main_window).exec()
