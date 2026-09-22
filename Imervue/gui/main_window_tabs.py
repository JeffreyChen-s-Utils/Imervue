"""Folder tabs of the main window.

Opening, closing, moving and cycling the folder tabs, their context menu,
and keeping the active tab, the file tree and the viewer on the same path.
``ImervueMainWindow`` mixes these methods in.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QMenu

from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.multi_language.language_wrapper import language_wrapper


class MainWindowTabsMixin:
    """Folder tabs of the main window."""

    def _sync_current_tab_with_path(self, path: str) -> None:
        """Called whenever the viewer's deep-zoom image changes.

        Updates the currently-active tab's path/title, or creates the
        first tab if none exists yet. Guarded against re-entering while
        a tab switch is already loading a new image.
        """
        if self._tab_switching or not path:
            return
        title = Path(path).name

        idx = self._tab_bar.currentIndex()
        if idx < 0 or idx >= len(self._image_tabs):
            # No tab yet — create the first one automatically so the
            # user sees the image they just opened pinned in the bar.
            self._image_tabs.append({"path": path, "title": title})
            self._tab_switching = True
            try:
                new_idx = self._tab_bar.addTab(title)
                self._tab_bar.setTabToolTip(new_idx, path)
                self._tab_bar.setCurrentIndex(new_idx)
            finally:
                self._tab_switching = False
            return

        tab = self._image_tabs[idx]
        if tab["path"] == path:
            # Same image, nothing to update (avoids flicker on reloads).
            return
        tab["path"] = path
        tab["title"] = title
        self._tab_bar.setTabText(idx, title)
        self._tab_bar.setTabToolTip(idx, path)

    def _on_tab_changed(self, idx: int) -> None:
        """User clicked a tab — load its image into the viewer."""
        if self._tab_switching or idx < 0 or idx >= len(self._image_tabs):
            return
        path = self._image_tabs[idx]["path"]
        if not path or not Path(path).exists():
            return
        # Avoid reloading if the viewer is already on this image.
        if (self.viewer.deep_zoom
                and 0 <= self.viewer.current_index < len(self.viewer.model.images)
                and self.viewer.model.images[self.viewer.current_index] == path):
            return

        self._tab_switching = True
        try:
            # Preserve the outgoing tab image's zoom/pan before the clear nulls
            # the save key, so returning to it restores where you left off.
            self.viewer._save_view_state()
            self.viewer._clear_deep_zoom()
            open_path(main_gui=self.viewer, path=path)
        except Exception:
            import logging
            logging.getLogger("Imervue").exception(
                "tab switch to %s failed", path
            )
        finally:
            self._tab_switching = False

    def _on_tab_close(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._image_tabs):
            return
        self._image_tabs.pop(idx)
        self._tab_switching = True
        try:
            self._tab_bar.removeTab(idx)
        finally:
            self._tab_switching = False
        # Activate whichever tab is now current — Qt auto-picks a neighbor.
        new_idx = self._tab_bar.currentIndex()
        if new_idx >= 0 and new_idx < len(self._image_tabs):
            self._on_tab_changed(new_idx)

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        """Keep our tab state in sync when the user drags a tab to reorder."""
        if 0 <= from_idx < len(self._image_tabs) and 0 <= to_idx < len(self._image_tabs):
            moved = self._image_tabs.pop(from_idx)
            self._image_tabs.insert(to_idx, moved)

    def _new_tab(self) -> None:
        """Ctrl+T — open an empty placeholder tab.

        The placeholder has no path; the user fills it by clicking an
        image in the file tree, which triggers ``_sync_current_tab_with_path``
        via the viewer's filename-changed hook.
        """
        lang = language_wrapper.language_word_dict
        title = lang.get("tab_new", "New Tab")
        self._image_tabs.append({"path": "", "title": title})
        self._tab_switching = True
        try:
            new_idx = self._tab_bar.addTab(title)
            self._tab_bar.setCurrentIndex(new_idx)
        finally:
            self._tab_switching = False

    def _close_current_tab(self) -> None:
        idx = self._tab_bar.currentIndex()
        if idx >= 0:
            self._on_tab_close(idx)

    def _on_tab_context_menu(self, pos) -> None:
        """Right-click on a tab → reveal / copy path / close family."""
        idx = self._tab_bar.tabAt(pos)
        if idx < 0:
            return
        lang = language_wrapper.language_word_dict
        menu = QMenu(self._tab_bar)
        tab_path = self._image_tabs[idx].get("path", "") if 0 <= idx < len(self._image_tabs) else ""

        reveal_act = None
        copy_path_act = None
        if tab_path:
            reveal_act = menu.addAction(
                lang.get("tab_reveal_in_tree", "Reveal in File Tree"),
            )
            copy_path_act = menu.addAction(lang.get("tab_copy_path", "Copy Path"))
            menu.addSeparator()

        close_act = menu.addAction(lang.get("tab_close", "Close"))
        close_others = menu.addAction(lang.get("tab_close_others", "Close Other Tabs"))
        close_right = menu.addAction(
            lang.get("tab_close_to_right", "Close Tabs to the Right"),
        )
        menu.addSeparator()
        close_all = menu.addAction(lang.get("tab_close_all", "Close All Tabs"))
        chosen = menu.exec(self._tab_bar.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is reveal_act:
            self._reveal_path_in_tree(tab_path)
        elif chosen is copy_path_act:
            QApplication.clipboard().setText(tab_path)
        elif chosen is close_act:
            self._on_tab_close(idx)
        elif chosen is close_others:
            self._close_tabs_except(idx)
        elif chosen is close_right:
            self._close_tabs_after(idx)
        elif chosen is close_all:
            self._close_all_tabs()

    def _reveal_path_in_tree(self, path: str) -> None:
        """Scroll the file tree to ``path`` and select that row, so the
        user has a one-click bridge from "this tab's image" back to its
        location on disk. Falls back silently if the path is gone."""
        if not path:
            return
        if not Path(path).exists():
            if hasattr(self, "toast"):
                lang = language_wrapper.language_word_dict
                self.toast.warning(
                    lang.get(
                        "tab_reveal_missing", "{name} is no longer on disk",
                    ).format(name=Path(path).name or path),
                )
            return
        index = self.model.index(path)
        if not index.isValid():
            return
        self.tree.scrollTo(index)
        self.tree.setCurrentIndex(index)
        self.tree.setFocus()

    def _close_tabs_except(self, keep_idx: int) -> None:
        """Close every tab whose index is not ``keep_idx``."""
        if not (0 <= keep_idx < len(self._image_tabs)):
            return
        # Walk highest-to-lowest so popping doesn't shift the kept index.
        for idx in reversed(range(len(self._image_tabs))):
            if idx != keep_idx:
                self._on_tab_close(idx)

    def _close_tabs_after(self, idx: int) -> None:
        """Close every tab whose index is greater than ``idx``."""
        for closing in reversed(range(idx + 1, len(self._image_tabs))):
            self._on_tab_close(closing)

    def _close_all_tabs(self) -> None:
        for idx in reversed(range(len(self._image_tabs))):
            self._on_tab_close(idx)

    def _next_tab(self) -> None:
        count = self._tab_bar.count()
        if count <= 1:
            return
        self._tab_bar.setCurrentIndex(
            (self._tab_bar.currentIndex() + 1) % count
        )

    def _prev_tab(self) -> None:
        count = self._tab_bar.count()
        if count <= 1:
            return
        self._tab_bar.setCurrentIndex(
            (self._tab_bar.currentIndex() - 1) % count
        )
