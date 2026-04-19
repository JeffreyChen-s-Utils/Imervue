"""
Staging Tray dialog — a cross-folder basket for batch move/copy/export.

The tray is persisted in ``user_setting_dict["staging_tray"]`` (see
``library.staging_tray``) so it survives restarts. This dialog exposes add
from selection / remove / clear / move-all / copy-all operations.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QFileDialog, QMessageBox,
)

from Imervue.library import staging_tray
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class StagingTrayDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("staging_tray_title", "Staging Tray"))
        self.resize(620, 500)

        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel(
            lang.get("staging_tray_explain",
                     "Cross-folder basket. Drop items from any folder then "
                     "move/copy them all at once.")
        ))
        header_row.addStretch()
        self._count_label = QLabel()
        header_row.addWidget(self._count_label)
        layout.addLayout(header_row)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self._list, stretch=1)

        # Add / remove / clear
        row1 = QHBoxLayout()
        add_sel_btn = QPushButton(lang.get("staging_tray_add_selected", "Add selected tiles"))
        add_sel_btn.clicked.connect(self._add_selected)
        add_cur_btn = QPushButton(lang.get("staging_tray_add_current", "Add current image"))
        add_cur_btn.clicked.connect(self._add_current)
        remove_btn = QPushButton(lang.get("staging_tray_remove", "Remove"))
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton(lang.get("staging_tray_clear", "Clear"))
        clear_btn.clicked.connect(self._clear)
        for b in (add_sel_btn, add_cur_btn, remove_btn, clear_btn):
            row1.addWidget(b)
        layout.addLayout(row1)

        # Move / copy / show-as-album
        row2 = QHBoxLayout()
        move_btn = QPushButton(lang.get("staging_tray_move", "Move all to…"))
        move_btn.clicked.connect(lambda: self._bulk_op(move=True))
        copy_btn = QPushButton(lang.get("staging_tray_copy", "Copy all to…"))
        copy_btn.clicked.connect(lambda: self._bulk_op(move=False))
        view_btn = QPushButton(lang.get("staging_tray_view_as_album", "Show as album"))
        view_btn.clicked.connect(self._view_as_album)
        for b in (move_btn, copy_btn, view_btn):
            row2.addWidget(b)
        layout.addLayout(row2)

        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._refresh()

    # ---------- Data ----------

    def _refresh(self) -> None:
        self._list.clear()
        entries = staging_tray.get_all()
        for p in entries:
            self._list.addItem(p)
        lang = language_wrapper.language_word_dict
        self._count_label.setText(
            lang.get("staging_tray_count", "{n} item(s)").format(n=len(entries))
        )

    def _collect_from_viewer(self) -> list[str]:
        viewer = self._ui.viewer
        paths = list(viewer.selected_tiles)
        if paths:
            return paths
        if viewer.deep_zoom and viewer.model.images:
            return [viewer.model.images[viewer.current_index]]
        return []

    # ---------- Actions ----------

    def _add_selected(self) -> None:
        paths = [p for p in self._ui.viewer.selected_tiles]
        if not paths:
            return
        staging_tray.add_many(paths)
        self._refresh()

    def _add_current(self) -> None:
        viewer = self._ui.viewer
        if viewer.deep_zoom and viewer.model.images:
            staging_tray.add(viewer.model.images[viewer.current_index])
            self._refresh()

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            staging_tray.remove(item.text())
        self._refresh()

    def _clear(self) -> None:
        if staging_tray.count() == 0:
            return
        confirm = QMessageBox.question(
            self, "",
            language_wrapper.language_word_dict.get(
                "staging_tray_confirm_clear", "Clear the staging tray?"
            ),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        staging_tray.clear()
        self._refresh()

    def _bulk_op(self, *, move: bool) -> None:
        if staging_tray.count() == 0:
            return
        dest = QFileDialog.getExistingDirectory(
            self,
            language_wrapper.language_word_dict.get(
                "staging_tray_choose_dest", "Choose destination folder"
            ),
            str(Path.home()),
        )
        if not dest:
            return
        try:
            if move:
                ok, failed = staging_tray.move_all(dest)
            else:
                ok, failed = staging_tray.copy_all(dest)
        except NotADirectoryError:
            QMessageBox.warning(self, "", "Destination is not a directory")
            return
        if hasattr(self._ui, "toast"):
            lang = language_wrapper.language_word_dict
            key = "staging_tray_moved" if move else "staging_tray_copied"
            fallback = "Moved {ok} (failed {f})" if move else "Copied {ok} (failed {f})"
            self._ui.toast.success(lang.get(key, fallback).format(ok=ok, f=failed))
        self._refresh()

    def _view_as_album(self) -> None:
        paths = staging_tray.get_all()
        if not paths:
            return
        viewer = self._ui.viewer
        viewer._unfiltered_images = list(viewer.model.images)
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(paths)
        self.accept()


def open_staging_tray(ui: ImervueMainWindow) -> None:
    StagingTrayDialog(ui).exec()
