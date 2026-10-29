"""File ▸ Recent submenu of the Paint File menu: rebuild, clear and reopen.

A mixin of :class:`Imervue.paint.file_menu._FileMenuBridge`; reopening routes
through the bridge's document, PSD and dropped-path verbs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


class FileMenuRecentMixin:
    """The persisted recent-files list as a submenu, and format-aware reopening."""

    _workspace: PaintWorkspace

    def refresh_recent_menu(self) -> None:
        """Rebuild the File ▸ Recent submenu from the persisted list.

        Keeps the truncation simple: when no recents exist a single
        disabled placeholder entry shows so the submenu doesn't look
        broken; when entries exist, the bottom row offers Clear.
        """
        from Imervue.paint import recent_files

        recent_menu = getattr(self, "_recent_menu", None)
        if recent_menu is None:
            return
        recent_menu.clear()
        lang = language_wrapper.language_word_dict
        entries = recent_files.paths()
        if not entries:
            placeholder = recent_menu.addAction(
                lang.get("paint_file_recent_empty", "(no recent files)"),
            )
            placeholder.setEnabled(False)
            return
        for path in entries:
            label = self._format_recent_label(path)
            action = recent_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, p=path: self.open_recent_at(p),
            )
        recent_menu.addSeparator()
        clear_action = recent_menu.addAction(
            lang.get("paint_file_recent_clear", "Clear recent files"),
        )
        clear_action.triggered.connect(self._on_clear_recent)

    def _on_clear_recent(self) -> None:
        from Imervue.paint import recent_files
        recent_files.clear()
        self.refresh_recent_menu()

    @staticmethod
    def _format_recent_label(path: str) -> str:
        """Turn an absolute path into a short menu label.

        Show the file name plus the parent directory so the user can
        disambiguate two files with the same name in different
        folders without showing the full absolute path.
        """
        import os
        head, tail = os.path.split(path)
        if not tail:
            return path
        parent = os.path.basename(head)
        if parent:
            return f"{tail}    [{parent}]"
        return tail

    def open_recent_at(self, path: str) -> None:
        """Dispatch recent files by their real format instead of treating all as PSD."""
        if path.lower().endswith(".imervue"):
            self.open_document_at(path)
        elif path.lower().endswith(".psd"):
            self.open_psd_at(path)
        else:
            self._workspace._open_dropped_path(path)
