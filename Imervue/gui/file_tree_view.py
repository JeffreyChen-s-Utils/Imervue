"""File-tree view for the main window.

The QTreeView subclass with keyboard shortcuts and right-click menu, plus the
duplicate-name helper. Extracted from ``Imervue_main_window``; re-exported
there for backwards compatibility.
"""
import os
import subprocess  # nosec B404  # NOSONAR - static arg lists for trusted OS file managers
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QTreeView, QFileSystemModel, QMenu,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib


def _next_duplicate_name(source: Path) -> Path:
    """Pick a sibling path for ``source`` that does not exist yet, in
    the form ``stem (copy).ext``, ``stem (copy 2).ext``, …"""
    parent = source.parent
    stem = source.stem
    suffix = source.suffix
    candidate = parent / f"{stem} (copy){suffix}"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = parent / f"{stem} (copy {n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


class _FileTreeView(QTreeView):
    """QTreeView with Delete key and right-click context menu."""

    def __init__(self, main_window: "ImervueMainWindow"):
        super().__init__()
        self._main_window = main_window
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ---------- Keyboard shortcuts ----------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Delete:
            self._delete_selected()
            return
        if key == Qt.Key.Key_F5:
            self._refresh_tree()
            return
        if key == Qt.Key.Key_F2:
            self._rename_selected()
            return
        super().keyPressEvent(event)

    def _rename_selected(self) -> None:
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        model: QFileSystemModel = self.model()
        path = model.filePath(indexes[0])
        if path:
            self._rename_path(path)

    def _refresh_tree(self) -> None:
        """Force QFileSystemModel to re-scan the current root.

        Useful when external tools have changed the folder contents and
        Qt's native watcher hasn't picked it up yet.
        """
        model: QFileSystemModel = self.model()
        root = self.rootIndex()
        if not root.isValid():
            return
        path = model.filePath(root)
        if path:
            # setRootPath() re-stats the directory even if the value is the same
            model.setRootPath("")
            model.setRootPath(path)
            self.setRootIndex(model.index(path))

    def _delete_selected(self):
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        model: QFileSystemModel = self.model()
        path = model.filePath(indexes[0])
        if not path or not Path(path).exists():
            return
        self._delete_path(path)

    # ---------- Right-click menu ----------

    def _show_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return
        model: QFileSystemModel = self.model()
        path = model.filePath(index)
        if not path:
            return

        lang = language_wrapper.language_word_dict
        menu = QMenu(self)

        # Show in Explorer
        action_explorer = menu.addAction(
            lang.get("tree_open_in_explorer", "Open in Explorer")
        )
        action_explorer.triggered.connect(lambda: self._open_in_explorer(path))

        # Open containing folder
        if Path(path).is_file():
            action_folder = menu.addAction(
                lang.get("tree_open_folder", "Open Containing Folder")
            )
            action_folder.triggered.connect(
                lambda: self._open_in_explorer(str(Path(path).parent), select=False)
            )

        # Open with system default application — useful when the user
        # wants to bounce a file to its associated editor without
        # leaving the tree.
        if Path(path).is_file():
            action_open_default = menu.addAction(
                lang.get("tree_open_with_default", "Open with Default App"),
            )
            action_open_default.triggered.connect(
                lambda: self._open_with_default_app(path),
            )

        menu.addSeparator()

        # Copy path
        action_copy = menu.addAction(lang.get("right_click_copy_path", "Copy Path"))
        action_copy.triggered.connect(
            lambda: QApplication.clipboard().setText(path)
        )

        menu.addSeparator()

        # New Folder (inside the clicked folder, or the clicked file's parent)
        action_new = menu.addAction(lang.get("tree_new_folder", "New Folder"))
        target_dir = path if Path(path).is_dir() else str(Path(path).parent)
        action_new.triggered.connect(lambda: self._create_new_folder(target_dir))

        # Refresh
        action_refresh = menu.addAction(lang.get("tree_refresh", "Refresh"))
        action_refresh.triggered.connect(self._refresh_tree)

        # Expand / collapse all children
        if Path(path).is_dir():
            action_expand = menu.addAction(lang.get("tree_expand_all", "Expand All"))
            action_expand.triggered.connect(lambda: self.expandRecursively(index))
            action_collapse = menu.addAction(lang.get("tree_collapse_all", "Collapse All"))
            action_collapse.triggered.connect(lambda: self.collapse(index))

        menu.addSeparator()

        # Rename
        action_rename = menu.addAction(lang.get("tree_rename", "Rename"))
        action_rename.setShortcut("F2")
        action_rename.triggered.connect(lambda: self._rename_path(path))

        # Duplicate
        if Path(path).is_file():
            action_dup = menu.addAction(lang.get("tree_duplicate", "Duplicate"))
            action_dup.triggered.connect(lambda: self._duplicate_file(path))

        menu.addSeparator()

        # Delete
        action_del = menu.addAction(lang.get("tree_delete", "Delete"))
        action_del.triggered.connect(lambda: self._delete_path(path))

        menu.exec(self.viewport().mapToGlobal(pos))

    def _create_new_folder(self, parent_dir: str) -> None:
        """Prompt for a folder name and create it under ``parent_dir``."""
        from PySide6.QtWidgets import QInputDialog
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("tree_new_folder", "New Folder"),
            lang.get("tree_new_folder_prompt", "Folder name:"),
        )
        if not ok or not name.strip():
            return
        try:
            target = Path(parent_dir) / name.strip()
            target.mkdir(parents=False, exist_ok=False)
            self._refresh_tree()
        except FileExistsError:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.warning(
                    lang.get("tree_folder_exists", "Folder already exists")
                )
            return
        except OSError as exc:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.error(
                    f"{lang.get('tree_new_folder_failed', 'Create failed')}: {exc}"
                )
            return
        if hasattr(self._main_window, "toast"):
            self._main_window.toast.success(
                lang.get("tree_new_folder_done", "Created folder {name}").format(
                    name=target.name,
                ),
            )

    def _rename_path(self, path: str) -> None:
        """Prompt for a new basename and rename the file or folder."""
        from PySide6.QtWidgets import QInputDialog
        lang = language_wrapper.language_word_dict
        target = Path(path)
        if not target.exists():
            return
        new_name, ok = QInputDialog.getText(
            self,
            lang.get("tree_rename", "Rename"),
            lang.get("tree_rename_prompt", "New name:"),
            text=target.name,
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == target.name:
            return
        new_path = target.with_name(new_name)
        if new_path.exists():
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.warning(
                    lang.get("tree_rename_exists", "A file with that name already exists"),
                )
            return
        try:
            target.rename(new_path)
        except OSError as exc:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.error(
                    f"{lang.get('tree_rename_failed', 'Rename failed')}: {exc}",
                )
            return
        self._refresh_tree()
        if hasattr(self._main_window, "toast"):
            self._main_window.toast.success(
                lang.get("tree_rename_done", "Renamed to {name}").format(
                    name=new_path.name,
                ),
            )

    def _duplicate_file(self, path: str) -> None:
        """Copy ``path`` to a sibling with a "(copy)" suffix."""
        import shutil
        lang = language_wrapper.language_word_dict
        source = Path(path)
        if not source.is_file():
            return
        candidate = _next_duplicate_name(source)
        try:
            shutil.copy2(source, candidate)
        except OSError as exc:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.error(
                    f"{lang.get('tree_duplicate_failed', 'Duplicate failed')}: {exc}",
                )
            return
        self._refresh_tree()
        if hasattr(self._main_window, "toast"):
            self._main_window.toast.success(
                lang.get("tree_duplicate_done", "Duplicated to {name}").format(
                    name=candidate.name,
                ),
            )

    @staticmethod
    def _open_in_explorer(path: str, select: bool = True):
        # Static command + a local filesystem path from the file tree — no
        # untrusted input, shell=False. Bandit B603/B607 and Semgrep flag any
        # subprocess use; suppressed inline (rules are also config-skipped).
        with contextlib.suppress(Exception):
            if sys.platform == "win32":
                if select and Path(path).is_file():
                    subprocess.Popen(  # nosec B603,B607  # nosemgrep
                        ["explorer", "/select,", os.path.normpath(path)],
                    )
                else:
                    subprocess.Popen(  # nosec B603,B607  # nosemgrep
                        ["explorer", os.path.normpath(path)],
                    )
            elif sys.platform == "darwin":
                subprocess.Popen(  # nosec B603,B607  # nosemgrep
                    ["open", "-R" if select else "", path],
                )
            else:
                target = path if Path(path).is_dir() else str(Path(path).parent)
                subprocess.Popen(  # nosec B603,B607  # nosemgrep
                    ["xdg-open", target],
                )

    def _open_with_default_app(self, path: str) -> None:
        """Open ``path`` with the OS's default application via Qt's
        QDesktopServices, which is more portable than rolling per-OS
        subprocess calls. Surfaces a toast on failure so the artist
        knows whether the launch worked."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        url = QUrl.fromLocalFile(path)
        if QDesktopServices.openUrl(url):
            return
        if hasattr(self._main_window, "toast"):
            lang = language_wrapper.language_word_dict
            self._main_window.toast.error(
                lang.get(
                    "tree_open_with_failed",
                    "Couldn't open {name} with the default application",
                ).format(name=Path(path).name),
            )

    def _delete_path(self, path: str):
        if not Path(path).exists():
            return
        viewer = self._main_window.viewer
        images = viewer.model.images
        if Path(path).is_file() and path in images:
            self._delete_from_viewer_list(path, viewer, images)
        else:
            self._delete_external(path)

    def _delete_from_viewer_list(self, path: str, viewer, images: list[str]) -> None:
        idx = images.index(path)
        images.pop(idx)
        viewer.undo_stack.append({
            "mode": "delete",
            "deleted_paths": [path],
            "indices": [idx],
            "restored": False,
        })
        tex = viewer.tile_textures.pop(path, None)
        if tex is not None:
            # The delete fires from a menu-action event handler, not
            # from within ``paintGL``, so the viewer's GL context may
            # not be current. Make it current before freeing the
            # texture and swallow the GLError if the context is gone
            # entirely (window already destroyed during shutdown).
            from OpenGL.GL import glDeleteTextures
            from PySide6.QtGui import QOpenGLContext
            try:
                if hasattr(viewer, "makeCurrent"):
                    viewer.makeCurrent()
                if QOpenGLContext.currentContext() is not None:
                    glDeleteTextures([tex])
            except Exception:   # nosec B110  # noqa: BLE001, S110 — GL context torn down; nothing to log
                pass
            finally:
                if hasattr(viewer, "doneCurrent"):
                    viewer.doneCurrent()
        viewer.tile_cache.pop(path, None)
        self._refresh_viewer_after_delete(viewer, images, idx)
        self._notify_deleted(path)

    @staticmethod
    def _refresh_viewer_after_delete(viewer, images: list[str], idx: int) -> None:
        if viewer.tile_grid_mode:
            viewer.tile_rects.clear()
            viewer.update()
            return
        if not viewer.deep_zoom:
            return
        if images:
            viewer.current_index = min(idx, len(images) - 1)
            viewer.load_deep_zoom_image(images[viewer.current_index])
        else:
            viewer.deep_zoom = None
            viewer.current_index = 0
            viewer.tile_grid_mode = True
            viewer.update()

    def _delete_external(self, path: str) -> None:
        from Imervue.gpu_image_view.actions.keyboard_actions import _send_to_trash
        if _send_to_trash(path):
            self._notify_deleted(path)

    def _notify_deleted(self, path: str) -> None:
        if not hasattr(self._main_window, "toast"):
            return
        lang = language_wrapper.language_word_dict
        self._main_window.toast.info(
            lang.get("tree_deleted", "Moved to trash: {name}").format(
                name=Path(path).name
            )
        )


