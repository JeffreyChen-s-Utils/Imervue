"""PSD interop of the Paint File menu: Open PSD… / Save as PSD… and their commits.

The commit helpers are pure logic, callable from tests without a dialog; the
mixin is part of :class:`Imervue.paint.file_menu._FileMenuBridge`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.document_status import document_status, refresh_document_status

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


class FileMenuPsdMixin:
    """Open a PSD into a fresh tab (feeding File ▸ Recent) or save the active one."""

    _workspace: PaintWorkspace

    def open_psd(self) -> None:  # pragma: no cover - QFileDialog
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self._workspace,
            language_wrapper.language_word_dict.get(
                "paint_file_open_psd", "Open PSD",
            ),
            "",
            "Photoshop (*.psd)",
        )
        if not path:
            return
        self.open_psd_at(path)

    def open_psd_at(self, path: str) -> None:
        """Open ``path`` and add it to the recent-files list.

        Centralised entry point for both the file-dialog open and the
        File ▸ Recent submenu reopen, so every successful open feeds
        the recent list through one code path.
        """
        from Imervue.paint import recent_files
        if not commit_open_psd(self._workspace, path):
            self._warn("paint_file_open_psd", path)
            return
        document_status(self._workspace.canvas()).source = str(path)
        refresh_document_status(self._workspace, self._workspace.canvas())
        recent_files.add(str(path))
        self.refresh_recent_menu()

    def save_psd(self) -> None:  # pragma: no cover - QFileDialog
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self._workspace,
            language_wrapper.language_word_dict.get(
                "paint_file_save_psd", "Save as PSD",
            ),
            "",
            "Photoshop (*.psd)",
        )
        if not path:
            return
        try:
            from Imervue.paint.psd_io import save_psd
            document = self._workspace.canvas().document()
            if document.shape is None:
                return
            save_psd(document, path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_save_psd", exc)
            return
        self._notify_success("paint_file_save_psd_done", "Saved PSD", path, saved=True)
        state = document_status(self._workspace.canvas())
        state.saved_path, state.saved_format = path, "psd"
        refresh_document_status(self._workspace, self._workspace.canvas())


# ---------------------------------------------------------------------------
# PSD commit helpers — pure logic, callable from tests without a dialog
# ---------------------------------------------------------------------------


def commit_open_psd(workspace, path: str) -> bool:
    """Load ``path`` as a PSD and replace the active document.

    Returns ``True`` on success, ``False`` for any decode failure
    (caller can show a non-modal error). Loaded PSDs land in a fresh
    tab when the workspace supports tabs so the open document isn't
    silently destroyed by the import.
    """
    from Imervue.paint.psd_io import load_psd
    try:
        new_doc = load_psd(path)
    except (OSError, ValueError):
        return False
    if new_doc.shape is None:
        return False
    composite = new_doc.composite()
    if composite is None:
        return False
    if hasattr(workspace, "new_tab"):
        canvas = workspace.new_tab()
        canvas.set_document(new_doc)
        workspace._ensure_undo_stack()
        workspace._layer_dock.set_document(new_doc)
    else:
        workspace.load_image(composite)
    return True


def commit_save_psd(workspace, path: str) -> bool:
    """Write the active document to ``path``. Returns ``True`` on
    success, ``False`` when there's no document or save fails."""
    from Imervue.paint.psd_io import save_psd
    document = workspace.canvas().document()
    if document.shape is None:
        return False
    try:
        save_psd(document, path)
    except (OSError, ValueError):
        return False
    return True
