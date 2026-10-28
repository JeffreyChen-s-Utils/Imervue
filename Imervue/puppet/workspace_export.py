"""Batch motion export dialogs and progress feedback."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.batch_export import SUPPORTED_EXTENSIONS

class PuppetExportMixin:
    def _batch_export_via_dialog(self) -> None:
        doc = self._canvas.document()
        if doc is None or not doc.motions:
            self._announce(
                "puppet_batch_no_motions",
                "Document has no motions to export.",
            )
            return
        lang = language_wrapper.language_word_dict
        directory = QFileDialog.getExistingDirectory(
            self,
            lang.get("puppet_batch_dir_title", "Export motions to…"),
            "",
        )
        if not directory:
            return
        # Format pick — use a simple input dialog rather than a custom
        # dialog so the workspace stays small. Defaults to MP4.
        ext_choices = list(SUPPORTED_EXTENSIONS)
        ext, ok = QInputDialog.getItem(
            self,
            lang.get("puppet_batch_format_title", "Output format"),
            lang.get("puppet_batch_format_prompt", "Container:"),
            ext_choices, 0, False,
        )
        if not ok:
            return
        self._batch_exporter.start(directory, extension=ext)

    def _on_batch_progress(self, index: int, total: int, name: str) -> None:
        self._announce(
            "puppet_batch_progress",
            "Exporting motion {index}/{total}: {name}",
            index=index + 1, total=total, name=name,
        )

    def _on_batch_finished(self, paths: list) -> None:
        self._announce(
            "puppet_batch_done",
            "Exported {count} motions.",
            count=len(paths),
        )

    def _on_batch_failed(self, reason: str) -> None:
        self._announce(
            "puppet_batch_failed", "Batch export failed: {error}",
            error=reason,
        )
