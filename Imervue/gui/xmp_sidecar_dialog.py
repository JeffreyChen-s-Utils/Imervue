"""
XMP sidecar dialog \u2014 export / import ``.xmp`` files for the current folder
so ratings, titles, keywords, and colour labels round-trip with Lightroom,
Bridge, Capture One, and other XMP-aware applications.

Design note: operating on ``viewer.model.images`` (the current browsing set)
keeps the dialog simple and matches how the neighbouring metadata-export
and culling dialogs scope their work. The two buttons are intentionally
unambiguous \u2014 we never merge without the user clicking Import explicitly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from Imervue.image import xmp_sidecar
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class XmpSidecarDialog(QDialog):
    """Two-button UI for batch XMP sidecar export / import across a folder."""

    def __init__(self, ui: ImervueMainWindow, paths: list[str]):
        super().__init__(ui)
        self._ui = ui
        self._paths = paths
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("xmp_title", "XMP Sidecars"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("xmp_explain", (
                "Read or write Lightroom-compatible ``.xmp`` sidecar files "
                "alongside each image. Stores rating, title, description, "
                "keywords (tags) and colour label."
            ))
        ))
        layout.addWidget(QLabel(
            lang.get("xmp_count", "{n} image(s) in this view.").format(n=len(paths))
        ))

        btn_row = QHBoxLayout()
        export_btn = QPushButton(lang.get("xmp_export", "Export sidecars"))
        export_btn.clicked.connect(self._export_all)
        import_btn = QPushButton(lang.get("xmp_import", "Import sidecars"))
        import_btn.clicked.connect(self._import_all)
        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(export_btn)
        btn_row.addWidget(import_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _export_all(self) -> None:
        written, skipped, failed = run_export(self._paths)
        self._report("xmp_export_done", "Exported {ok}, skipped {skip}, failed {f}.",
                     ok=written, skip=skipped, f=failed)

    def _import_all(self) -> None:
        imported, missing, failed = run_import(self._paths)
        self._report("xmp_import_done", "Imported {ok}, missing {miss}, failed {f}.",
                     ok=imported, miss=missing, f=failed)

    def _report(self, key: str, fallback: str, **kwargs: int) -> None:
        lang = language_wrapper.language_word_dict
        msg = lang.get(key, fallback).format(**kwargs)
        toast = getattr(self._ui, "toast", None)
        if toast is not None:
            toast.info(msg)


def run_export(paths: list[str]) -> tuple[int, int, int]:
    """Write sidecars for every path. Returns (written, skipped, failed).

    A path is *skipped* when its snapshot is empty (no rating/title/tags/
    label) and no previous sidecar exists \u2014 there is nothing to write.
    """
    written = skipped = failed = 0
    for p in paths:
        try:
            data = xmp_sidecar.snapshot_from_settings(p)
            sidecar_exists = xmp_sidecar.has_sidecar(p)
            if data.is_empty() and not sidecar_exists:
                skipped += 1
                continue
            xmp_sidecar.save(p, data)
            written += 1
        except OSError:
            failed += 1
    return written, skipped, failed


def run_import(paths: list[str]) -> tuple[int, int, int]:
    """Merge sidecars into settings. Returns (imported, missing, failed)."""
    imported = missing = failed = 0
    for p in paths:
        if not xmp_sidecar.has_sidecar(p):
            missing += 1
            continue
        try:
            xmp_sidecar.import_for(p)
            imported += 1
        except (OSError, ValueError):
            failed += 1
    return imported, missing, failed


def open_xmp_sidecar(ui: ImervueMainWindow) -> None:
    paths = list(ui.viewer.model.images)
    if not paths:
        return
    XmpSidecarDialog(ui, paths).exec()
