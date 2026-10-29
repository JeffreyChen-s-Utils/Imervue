"""Tag & Album manager dialog — manage custom tags and virtual albums.

:class:`TagAlbumDialog` keeps the window, the name check shared by both tabs
and **Clean Up…**; the Tags tab lives in :mod:`tag_album_tags`, the Albums tab
in :mod:`tag_album_albums`, the pure helpers in :mod:`tag_album_logic` and the
right-click submenus in :mod:`tag_album_menus`, whose ``build_*`` functions
are re-exported here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QInputDialog, QTabWidget, QMessageBox,
)

from Imervue.gui.dialog_rows import confirm
from Imervue.gui.tag_album_albums import AlbumTabMixin
from Imervue.gui.tag_album_logic import cleanup_summary, existing_member_paths
from Imervue.gui.tag_album_menus import (
    build_album_submenu, build_batch_tag_album_submenu, build_tag_submenu,
)
from Imervue.gui.tag_album_tags import TagTabMixin
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.tags import get_all_tags, get_all_albums
from Imervue.user_settings.tag_validator import clean_collection, name_problem, plan_cleanup

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# The right-click menus import the submenu builders from here, and tests reach
# Qt, QInputDialog, QMessageBox and confirm through this module.
__all__ = [
    "QInputDialog",
    "QMessageBox",
    "Qt",
    "TagAlbumDialog",
    "build_album_submenu",
    "build_batch_tag_album_submenu",
    "build_tag_submenu",
    "confirm",
    "open_tag_album_dialog",
]


def open_tag_album_dialog(main_gui: GPUImageView):
    dlg = TagAlbumDialog(main_gui)
    dlg.exec()


class TagAlbumDialog(TagTabMixin, AlbumTabMixin, QDialog):
    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui.main_window)
        self.main_gui = main_gui
        self._lang = language_wrapper.language_word_dict

        self.setWindowTitle(self._lang.get("tag_album_title", "Tags & Albums"))
        self.setMinimumSize(600, 480)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Tab 1: Tags
        self._tag_widget = self._build_tag_tab()
        self._tabs.addTab(self._tag_widget, self._lang.get("tag_tab_tags", "Tags"))

        # Tab 2: Albums
        self._album_widget = self._build_album_tab()
        self._tabs.addTab(self._album_widget, self._lang.get("tag_tab_albums", "Albums"))

        bottom = QHBoxLayout()
        cleanup_btn = QPushButton(self._lang.get("tag_cleanup", "Clean Up…"))
        cleanup_btn.setToolTip(self._lang.get(
            "tag_cleanup_tooltip",
            "Forget files that no longer exist and merge names that differ only in case"))
        cleanup_btn.clicked.connect(self._clean_up)
        bottom.addWidget(cleanup_btn)
        bottom.addStretch(1)
        close_btn = QPushButton(self._lang.get("tag_close", "Close"))
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _usable_name(self, name: str, existing: dict, current: str | None = None) -> bool:
        """True when *name* may be created (or *current* renamed to it); else say why not."""
        problem = name_problem(name, existing, current=current)
        if problem is None:
            return True
        if problem == "duplicate":
            text = self._lang.get("tag_name_taken",
                                  "“{name}” differs from an existing name only in case or spaces.")
        else:
            text = self._lang.get("tag_name_invalid",
                                  "“{name}” can't be used: no tabs or line breaks.")
        QMessageBox.warning(self, self._lang.get("tag_album_title", "Tags & Albums"),
                            text.format(name=name))
        return False

    def _clean_up(self) -> None:
        """Offer to drop entries of missing files and merge case-duplicate names, then do it."""
        from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict
        tags, albums = get_all_tags(), get_all_albums()
        existing = existing_member_paths(tags, albums)
        plans = (plan_cleanup(tags, existing), plan_cleanup(albums, existing))
        title = self._lang.get("tag_cleanup_title", "Clean Up Tags & Albums")
        if not any(plan.changes for plan in plans):
            QMessageBox.information(self, title, self._lang.get(
                "tag_cleanup_nothing",
                "Nothing to clean up: every file still exists and no two names differ "
                "only in case."))
            return
        orphans, merges = cleanup_summary(plans)
        question = self._lang.get(
            "tag_cleanup_confirm",
            "Forget {orphans} entries of files that no longer exist and merge {count} "
            "name(s) that differ only in case?\n{merges}",
        ).format(orphans=orphans, count=len(merges), merges="\n".join(merges))
        if not confirm(self, title, question):
            return
        user_setting_dict["image_tags"] = clean_collection(tags, existing)
        user_setting_dict["albums"] = clean_collection(albums, existing)
        schedule_save()
        self._refresh_tags()
        self._refresh_albums()
