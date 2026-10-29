"""Build list context actions and relocate missing images."""

from __future__ import annotations
from pathlib import Path
from Imervue.gui.file_filters import viewer_filter
from Imervue.multi_language.language_wrapper import language_wrapper


class ImageListContextMixin:
    """Build list context actions and relocate missing images."""

    def contextMenuEvent(self, event):  # noqa: N802 - Qt override
        """Right-click → quick actions: Open / Reveal / Copy path.

        The menu mirrors what users expect from a file browser
        (Finder / Explorer / Nautilus) so we don't make them leave
        the app to perform housekeeping verbs."""
        from PySide6.QtWidgets import QApplication, QMenu

        paths = self.selected_paths()
        if not paths:
            return
        lang = language_wrapper.language_word_dict
        menu = QMenu(self)
        open_action = menu.addAction(
            lang.get("image_list_action_open", "Open"),
        )
        missing = [p for p in paths if not Path(p).exists()]
        relocate_action = None
        if missing:
            relocate_action = menu.addAction(
                lang.get("missing_relocate", "Relocate Missing File..."),
            )
        copy_action = menu.addAction(
            lang.get("image_list_action_copy_path", "Copy path"),
        )
        reveal_action = menu.addAction(
            lang.get("image_list_action_reveal", "Reveal in folder"),
        )
        chosen = menu.exec(event.globalPos())
        if chosen is open_action:
            self.image_activated.emit(paths[0])
        elif relocate_action is not None and chosen is relocate_action:
            self._relocate_missing(missing[0])
        elif chosen is copy_action:
            QApplication.clipboard().setText("\n".join(paths))
        elif chosen is reveal_action:
            self._reveal_path(paths[0])

    def _relocate_missing(self, old_path: str) -> None:
        from PySide6.QtWidgets import QFileDialog

        lang = language_wrapper.language_word_dict
        new_path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("missing_relocate", "Relocate Missing File..."),
            str(Path(old_path).parent),
            viewer_filter(),
        )
        if not new_path:
            return
        if hasattr(self._main_window, "_apply_missing_replacements"):
            self._main_window._apply_missing_replacements({old_path: new_path})
