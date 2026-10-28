"""Puppet document open/save dialogs, failure reporting and recent paths."""
from __future__ import annotations
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QFileDialog,
)
from Imervue.gui.file_filters import translated_filter
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict
from Imervue.puppet.document_io import PuppetFormatError, load_puppet, save_puppet
from Imervue.puppet.workspace_menus import RECENT_KEY

logger = logging.getLogger("Imervue.plugin.puppet.workspace")

class PuppetFilesMixin:
    def _open_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_open_dialog_title", "Open Puppet"),
            "",
            translated_filter("file_filter_puppet", "Puppet files", ("puppet",)),
        )
        if not path:
            return
        self.open_puppet(path)

    def open_puppet(self, path: str | Path) -> bool:
        """Load ``path`` into the canvas. Returns ``True`` on success."""
        path_str = str(path)
        try:
            doc = load_puppet(path_str)
        except (FileNotFoundError, PuppetFormatError) as exc:
            logger.warning("failed to open puppet %s: %s", path_str, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_open_failed", "Failed to open puppet: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_loaded",
                "Loaded {name} ({w}×{h}, {n} drawables)",
            ).format(
                name=Path(path_str).name,
                w=doc.size[0], h=doc.size[1],
                n=len(doc.drawables),
            ),
        )
        _push_recent(path_str)
        return True

    def _save_via_dialog(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("puppet_save_dialog_title", "Save Puppet As"),
            "",
            translated_filter("file_filter_puppet", "Puppet files", ("puppet",)),
        )
        if not path:
            return
        if not path.lower().endswith(".puppet"):
            path = f"{path}.puppet"
        self.save_puppet(path)

    def save_puppet(self, path: str | Path) -> bool:
        doc = self._canvas.document()
        if doc is None:
            return False
        try:
            save_puppet(doc, path)
        except OSError as exc:
            logger.warning("puppet save failed: %s", exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_save_failed", "Save failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_save_done", "Saved to {name}",
            ).format(name=Path(str(path)).name),
        )
        _push_recent(str(path))
        return True


_RECENT_LIMIT = 10


def _push_recent(path: str) -> None:
    """Move ``path`` to the front of the recent-files list, dedupe,
    truncate to ``_RECENT_LIMIT``."""
    existing = [p for p in user_setting_dict.get(RECENT_KEY, []) if p != path]
    existing.insert(0, path)
    user_setting_dict[RECENT_KEY] = existing[:_RECENT_LIMIT]
