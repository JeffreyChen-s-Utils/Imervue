"""File menu wiring — import / export entries for the Paint workspace.

Each verb in the engine layer (brush_preset_io, color_palette_io,
paint_project_export, export_presets) gets a one-click entry here.
The file dialogs are routed through Qt's ``QFileDialog`` so the
user picks paths via the OS native browser; the engine modules do
the actual reading / writing.

The bridge's verbs live in sibling mixins: comic projects and page exports in
``file_menu_projects``, File ▸ Recent in ``file_menu_recent``, PSD interop in
``file_menu_psd`` and the brush / palette imports with Export image… in
``file_menu_transfer``. This module builds the menu and keeps the shared
pickers and feedback.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.document_files import DocumentFiles
from Imervue.paint.file_menu_projects import FileMenuProjectsMixin, _project_filter
from Imervue.paint.file_menu_psd import FileMenuPsdMixin, commit_open_psd, commit_save_psd
from Imervue.paint.file_menu_recent import FileMenuRecentMixin
from Imervue.paint.file_menu_transfer import (
    EXPORT_IMAGE_FILTER,
    FileMenuTransferMixin,
    export_format_for,
    write_export_image,
)
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace

# Names other modules and the tests import from here; the verbs moved to the
# file_menu_* mixin modules.
__all__ = [
    "EXPORT_IMAGE_FILTER",
    "_FileMenuBridge",
    "_project_filter",
    "commit_open_psd",
    "commit_save_psd",
    "export_format_for",
    "populate_file_menu",
    "write_export_image",
]

logger = logging.getLogger("Imervue.paint.file_menu")


def populate_file_menu(workspace: PaintWorkspace) -> None:
    """Attach the documented File-menu actions to ``workspace``.

    The workspace is responsible for keeping references to the
    helper bridge instances; we hang the bridge on the workspace as
    ``_file_menu_bridge`` so callers can hit the same verbs via
    keyboard shortcut without re-instantiating the helpers.
    """
    bridge = _FileMenuBridge(workspace)
    workspace._file_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "file")
    lang = language_wrapper.language_word_dict
    from PySide6.QtGui import QKeySequence
    for key, fallback, slot, shortcut in (
        ("paint_file_new_tab", "New Tab",
         bridge.new_tab, "Ctrl+N"),
        ("paint_file_new_canvas", "New Canvas…",
         bridge.new_canvas, ""),
        ("paint_file_new_project", "New Comic Project…",
         bridge.new_comic_project, "Ctrl+Alt+N"),
        ("paint_file_open_project", "Open Comic Project…",
         bridge.open_comic_project, ""),
        ("paint_file_save_project", "Save Comic Project…",
         bridge.save_comic_project, ""),
        ("paint_file_close_tab", "Close Tab",
         bridge.close_active_tab, "Ctrl+W"),
        (None, None, None, None),
        ("paint_file_open_document", "Open Document…", bridge.open_document, ""),
        ("paint_file_save_document", "Save Document…", bridge.save_document, ""),
        ("paint_file_save_document_as", "Save Document As…", bridge.save_document_as, ""),
        ("paint_file_save_all", "Save All Documents", bridge.save_all_documents, ""),
        ("paint_file_open_psd", "Open PSD…",
         bridge.open_psd, "Ctrl+O"),
        ("paint_file_save_psd", "Save as PSD…",
         bridge.save_psd, "Ctrl+S"),
        (None, None, None, None),
        ("paint_file_import_brush_preset", "Import brush preset…",
         bridge.import_brush_preset, ""),
        ("paint_file_import_palette", "Import palette…",
         bridge.import_palette, ""),
        ("paint_file_restore_autosave", "Restore Autosave",
         bridge.restore_autosave, ""),
        (None, None, None, None),
        ("paint_file_export_image", "Export image…",
         bridge.export_active_image, ""),
        ("paint_file_export_pages_cbz", "Export pages → CBZ…",
         bridge.export_pages_cbz, ""),
        ("paint_file_export_pages_pdf", "Export pages → PDF…",
         bridge.export_pages_pdf, ""),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)

    # File ▸ Recent submenu — rebuilt every time it's shown so the
    # latest opens land at the top without having to re-tear-down
    # the whole menu. Cleared / Open Recent paths route through
    # the bridge so the same engine call services both new opens
    # and recent reopens (preserves the "added to recent" path).
    recent_menu = menu.addMenu(
        lang.get("paint_file_recent", "Recent"),
    )
    bridge._recent_menu = recent_menu   # noqa: SLF001
    recent_menu.aboutToShow.connect(bridge.refresh_recent_menu)
    bridge.refresh_recent_menu()


# ---------------------------------------------------------------------------
# Bridge — file dialogs + engine calls
# ---------------------------------------------------------------------------


class _FileMenuBridge(
    FileMenuProjectsMixin, FileMenuRecentMixin, FileMenuPsdMixin, FileMenuTransferMixin,
):
    """Stateless-ish glue between the menu actions and engine verbs.

    Kept as a class instead of free functions so the workspace can
    hold a single reference (preventing the bound-method instances
    from getting GC'd between menu builds).
    """

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace
        self._documents = DocumentFiles(self)

    def open_document(self) -> bool:
        """Open an editable native bundle in a fresh tab."""
        return self._documents.open()

    def open_document_at(self, path: str) -> bool:
        """Open a native bundle selected by recent-files or drag and drop."""
        return self._documents.open(path)

    def save_document(self, canvas=None) -> bool:
        """Save the specified tab, including a non-active tab being closed."""
        return self._documents.save(None if isinstance(canvas, bool) else canvas)

    def save_document_as(self) -> bool:
        """Pick a new native save destination for the active document."""
        return self._documents.save(save_as=True)

    def save_all_documents(self) -> bool:
        """Save every modified tab without switching the active document."""
        return self._documents.save_all()

    # ---- multi-document tabs --------------------------------------------

    def new_tab(self) -> None:
        self._workspace.new_tab()

    def new_canvas(self) -> None:  # pragma: no cover - Qt dialog
        """File > New Canvas…: a new tab of the size and background the dialog asks for."""
        from Imervue.paint.new_canvas_dialog import NewCanvasDialog
        from PySide6.QtWidgets import QDialog
        dialog = NewCanvasDialog(parent=self._workspace)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            width, height, fill = dialog.values()
            self._workspace.new_tab(width=width, height=height, fill=fill)

    def close_active_tab(self) -> None:
        # ``_tabs`` is the workspace-private QTabWidget — bridge talks
        # to the public ``close_tab(index)`` so we don't have to duplicate
        # the "refuse to close the last tab" rule here.
        index = self._workspace._tabs.currentIndex()  # noqa: SLF001
        self._workspace.close_tab(index)

    def restore_autosave(self) -> bool:
        """Recover every document's latest valid snapshot in separate tabs."""
        workspace = self._workspace
        count = workspace.restore_all_autosaves()
        lang = language_wrapper.language_word_dict
        toast = getattr(workspace, "toast", None)
        if toast is not None:
            if count:
                toast.info(lang.get("paint_autosave_restored_documents",
                                    "Restored {n} autosaved document(s)").format(n=count))
            else:
                toast.info(lang.get("paint_autosave_none", "No autosave to restore"))
        return bool(count)

    # ---- helpers (testable) ---------------------------------------------

    def _pick_file(  # pragma: no cover - QFileDialog
        self, *, title_key: str, title_fallback: str, filters: list[str],
    ) -> str | None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self._workspace,
            lang.get(title_key, title_fallback),
            "",
            ";;".join(filters),
        )
        return path or None

    def _pick_save_file(  # pragma: no cover - QFileDialog
        self, *, title_key: str, title_fallback: str, name_filter: str,
    ) -> str | None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self._workspace,
            lang.get(title_key, title_fallback),
            "",
            name_filter,
        )
        return path or None

    def _notify_success(
        self, key: str, fallback: str, path: str, *, saved: bool = False,
    ) -> None:
        """Pop a non-blocking success toast for a file write that
        completed cleanly.

        With ``saved`` (a PSD, which keeps the layers) the active tab is
        marked clean: no "modified" asterisk, no close prompt. An export
        (a flattened picture, a comic's pages) leaves it modified, so
        closing still asks before the layers are lost. Falls back to the
        status bar's transient message when the workspace has no toast
        manager (very early bootstrap or a unit-test stub) so the success
        signal is never silent.
        """
        from pathlib import Path
        lang = language_wrapper.language_word_dict
        verb = lang.get(key, fallback)
        msg = f"{verb}: {Path(path).name}"
        mark_clean = getattr(self._workspace, "mark_active_tab_clean", None)
        if saved and callable(mark_clean):
            mark_clean()
        toast = getattr(self._workspace, "toast", None)
        if toast is not None:
            toast.success(msg)
            return
        status = getattr(self._workspace, "_status", None)
        if status is not None:
            status.showMessage(msg, 3000)

    def _warn(self, title_key: str, exc: Exception | str) -> None:
        """Surface a file-operation error (an exception, or the reason as text).

        Prefers a non-blocking toast notification when the workspace
        has one (every paint workspace built since the toast wiring
        landed) so failed exports / imports don't interrupt the
        artist's flow with a modal that has to be dismissed. Falls
        back to ``QMessageBox.warning`` for older callers that
        construct the bridge without a fully-wired workspace
        (legacy tests, embedded contexts).
        """
        lang = language_wrapper.language_word_dict
        title = lang.get(title_key, "Error")
        toast = getattr(self._workspace, "toast", None)
        if toast is not None:
            toast.error(f"{title}: {exc}")
            return
        QMessageBox.warning(self._workspace, title, str(exc))
