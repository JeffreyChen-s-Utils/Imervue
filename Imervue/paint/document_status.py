"""Per-canvas file provenance and recovery state, independent of pixel history."""
from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class DocumentStatus:
    """File locations belong to one document, never to a reusable tab widget."""

    document: object
    source: str = ""
    saved_path: str = ""
    saved_format: str = ""
    exported_path: str = ""
    autosave: str = "none"
    autosave_error: str = ""
    autosave_at: float | None = None


def document_status(canvas) -> DocumentStatus:
    """Return current file state, resetting it when the canvas replaces its document."""
    document = canvas.document()
    state = getattr(canvas, "_file_status", None)
    if state is None or state.document is not document:
        state = canvas._file_status = DocumentStatus(document)
    return state


def status_lines(state: DocumentStatus, dirty: bool, lang: dict) -> list[str]:
    """Compose the same explicit provenance/recovery labels for tabs and status tooltips."""
    source = state.source or lang.get("paint_document_new", "New document")
    saved = state.saved_path or lang.get("paint_document_not_saved", "Not saved")
    modified = lang.get("paint_tab_tooltip_modified", "Modified — unsaved") if dirty else lang.get(
        "paint_document_clean", "No unsaved changes",
    )
    auto = lang.get(f"paint_document_autosave_{state.autosave}", state.autosave)
    if state.autosave_error:
        auto = f"{auto}: {state.autosave_error}"
    lines = [lang.get("paint_document_source", "Source: {path}").format(path=source), modified,
             lang.get("paint_document_saved", "Document: {path}").format(path=saved),
             lang.get("paint_document_autosave", "Recovery autosave: {state}").format(state=auto)]
    if state.autosave_at is not None:
        elapsed = max(0, int(time.monotonic() - state.autosave_at))
        lines.append(lang.get("paint_document_autosave_last", "Last recovery: {n}s ago").format(
            n=elapsed,
        ))
    if state.exported_path:
        lines.append(lang.get("paint_document_export", "Flat export: {path}").format(
            path=state.exported_path,
        ))
    return lines


def refresh_document_status(workspace, canvas) -> None:
    """Refresh an affected tab and the active status bar without changing selection."""
    refresh = getattr(workspace, "_refresh_tab_title", None)
    if callable(refresh):
        refresh(canvas)
    if canvas is getattr(workspace, "_canvas", None):
        refresh = getattr(workspace, "_refresh_status_line", None)
        if callable(refresh):
            refresh()
