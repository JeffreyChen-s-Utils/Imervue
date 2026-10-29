"""Per-image browse actions of the viewer.

Mixed into :class:`GPUImageView`: the current path, status-bar sync,
bookmark toggle, clipboard paste, browsing history, colour labels / cull
states, view-state memory, shortcut dispatch and localized toasts. Each is
a thin delegation to its helper module or collaborator.
"""
from __future__ import annotations


class ViewBrowseActionsMixin:
    """Per-image browse actions for :class:`GPUImageView`."""

    def _current_path(self) -> str | None:
        imgs = self.model.images
        if imgs and 0 <= self.current_index < len(imgs):
            return imgs[self.current_index]
        return None

    def _update_status_info(self):
        """Sync the main-window status bar — called by viewer collaborators
        and external GUI panels. External contract, keep stable."""
        from Imervue.gpu_image_view.status_info import update_status_info
        update_status_info(self)

    def _toggle_bookmark(self):
        """切換當前圖片的書籤狀態"""
        images = self.model.images
        if not images or self.current_index >= len(images):
            return
        path = images[self.current_index]
        from Imervue.user_settings.bookmark import is_bookmarked, add_bookmark, remove_bookmark
        lang = self.main_window.language_wrapper.language_word_dict
        if is_bookmarked(path):
            remove_bookmark(path)
            msg = lang.get("bookmark_removed", "Bookmark removed")
        else:
            add_bookmark(path)
            msg = lang.get("bookmark_added", "\u2605 Bookmarked")
        if hasattr(self.main_window, 'toast'):
            self.main_window.toast.info(msg)
        self.update()

    def _paste_image_from_clipboard(self):
        """Paste a clipboard image — called by the key-action dispatcher.
        External contract, keep the name/signature stable."""
        from Imervue.gpu_image_view.clipboard_paste import paste_image_from_clipboard
        paste_image_from_clipboard(self)

    def run_shortcut_action(self, action: str) -> None:
        """Run a Shortcut Settings action (``"undo"``, ``"delete"``…) as if its key was pressed."""
        self._key_dispatch.dispatch(action)

    # ---------------------------
    # 瀏覽歷史 (Alt+←/→) — delegated to HistoryController
    # ---------------------------
    def _push_history(self, path: str) -> None:
        """Record ``path`` in the browsing history (no-op while navigating)."""
        self._history.push(path)

    def history_back(self) -> bool:
        """Jump to the previous image. External contract (key dispatcher)."""
        return self._history.back()

    def history_forward(self) -> bool:
        """Jump to the next image. External contract (key dispatcher)."""
        return self._history.forward()

    # ---------------------------
    # 顏色標籤 (F1-F5)
    # ---------------------------
    def _apply_color_label(self, color: str) -> None:
        """Toggle ``color`` on the currently-active target(s)."""
        from Imervue.gpu_image_view.cull_actions import apply_color_label
        apply_color_label(self, color)

    def _apply_cull_state(self, state: str) -> None:
        """Apply a cull state — called by the key-action dispatcher.
        External contract, keep the name/signature stable."""
        from Imervue.gpu_image_view.cull_actions import apply_cull_state
        apply_cull_state(self, state)

    def jump_to_random_image(self) -> None:
        """Jump to a random image — external contract (key dispatcher)."""
        from Imervue.gpu_image_view.view_state import jump_to_random
        jump_to_random(self)

    def _save_view_state(self):
        from Imervue.gpu_image_view.view_state import save_view_state
        save_view_state(self)

    def _restore_view_state(self, path: str):
        from Imervue.gpu_image_view.view_state import restore_view_state
        restore_view_state(self, path)

    def _toast(self, key: str, fallback: str) -> None:
        """Show a localized toast via the main window, if available."""
        if hasattr(self.main_window, 'toast'):
            lang = self.main_window.language_wrapper.language_word_dict
            self.main_window.toast.info(lang.get(key, fallback))
