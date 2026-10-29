"""Folder / file navigation and drag-and-drop of the main window.

Opening a folder or file from the file tree, breadcrumb, startup session or a
drop onto the window, and keeping the tree, path label, folder watch and
recent menu in step. ``ImervueMainWindow`` mixes these methods in.
"""
from __future__ import annotations

import logging
from pathlib import Path

from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.image.formats import VIEWER_EXTENSIONS
from Imervue.menu.recent_menu import rebuild_recent_menu
from Imervue.multi_language.language_wrapper import language_wrapper


class MainWindowNavigationMixin:
    """Folder / file navigation and drag-and-drop of the main window."""

    def on_file_clicked(self, index):
        self.navigate_to_path(self.model.filePath(index))

    def navigate_to_path(self, path: str) -> None:
        """Open a folder (tile grid) or a file (deep zoom) and sync the chrome.

        The single entry point the file tree AND the breadcrumb both call, so
        navigation is identical from either: same root, viewer reset, path bar,
        folder watch and recent menu. (The breadcrumb used to duplicate this and
        drifted — it stopped updating the path bar.)
        """
        if Path(path).is_dir():
            # 點擊資料夾 → 導航進入並載入圖片
            self._save_current_folder_session()
            self.tree.set_root_path(path)
            self.viewer.clear_tile_grid()
            open_path(main_gui=self.viewer, path=path)
            self._image_metadata_index.prime(
                getattr(self.viewer, "_unfiltered_images", self.viewer.model.images),
                limit=512,
            )
            self._refresh_tag_filter_options()
            self._restore_folder_session(path)
            self.filename_label.setText(
                language_wrapper.language_word_dict.get(
                    "main_window_current_folder_format"
                ).format(path=path)
            )
            self.breadcrumb.set_path(path)
            self.watch_folder(path)
        elif Path(path).is_file():
            self._save_current_folder_session()
            self.viewer.clear_tile_grid()
            open_path(main_gui=self.viewer, path=path)
            self.breadcrumb.set_path(str(Path(path).parent))

        rebuild_recent_menu(self)

    def _on_directory_loaded(self, directory: str):
        """QFileSystemModel 目錄載入完成回調，確保樹狀圖正確顯示"""
        idx = self.model.index(directory)
        if idx.isValid():
            self.tree.update(idx)

    def _open_startup_folder(self, folder: str):
        self.tree.set_root_path(folder)
        open_path(main_gui=self.viewer, path=folder)
        self._image_metadata_index.prime(
            getattr(self.viewer, "_unfiltered_images", self.viewer.model.images),
            limit=512,
        )
        self._refresh_tag_filter_options()
        self._restore_folder_session(folder)
        # Startup-only: reopen the last deep-zoom image if the session recorded
        # one, so relaunching returns to where the user left off.
        self._restore_deep_zoom_if_saved(self._folder_view_sessions.get(folder) or {})
        self.filename_label.setText(
            language_wrapper.language_word_dict.get(
                "main_window_current_folder_format"
            ).format(path=folder)
        )
        if hasattr(self, "breadcrumb"):
            self.breadcrumb.set_path(folder)
        self.watch_folder(folder)

    @classmethod
    def _is_supported_drop(cls, path: str) -> bool:
        """Return True iff the dropped path is a folder or an image with
        a recognised extension."""
        p = Path(path)
        if p.is_dir():
            return True
        return p.suffix.lower() in VIEWER_EXTENSIONS

    def dragEnterEvent(self, event):  # noqa: N802 — Qt naming
        urls = event.mimeData().urls() if event.mimeData() else []
        if any(self._is_supported_drop(u.toLocalFile()) for u in urls if u.isLocalFile()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802 — Qt naming
        urls = event.mimeData().urls() if event.mimeData() else []
        for url in urls:
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if self._is_supported_drop(path):
                self._open_dropped_path(path)
                event.acceptProposedAction()
                return
        event.ignore()

    def _open_dropped_path(self, path: str) -> None:
        """Open a dropped file or folder via the viewer's existing
        load path. Folders re-root the file tree; image files load
        into the deep-zoom viewer."""
        target = Path(path)
        if target.is_dir():
            self._open_startup_folder(str(target))
            return
        if target.is_file():
            try:
                open_path(main_gui=self.viewer, path=str(target))
            except Exception:   # load surface raises a wide variety
                logger = logging.getLogger("Imervue")
                logger.exception("drop-load failed: %s", target)
                if hasattr(self, "toast"):
                    lang = language_wrapper.language_word_dict
                    self.toast.error(
                        lang.get("drop_load_failed", "Couldn't open {name}").format(
                            name=target.name,
                        ),
                    )
