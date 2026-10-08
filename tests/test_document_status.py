"""Document file state is per-document and never implies a recovery save is a user save."""
from types import SimpleNamespace

from Imervue.paint.document_status import document_status, refresh_document_status, status_lines


def test_replacing_document_resets_every_location_and_recovery_state():
    canvas = SimpleNamespace(document=lambda: first)
    first = object()
    state = document_status(canvas)
    state.source, state.saved_path, state.exported_path = "input.jpg", "work.imervue", "flat.png"
    state.autosave, state.autosave_error, state.autosave_at = "failed", "disk full", 12.0
    assert document_status(canvas) is state
    canvas.document = lambda: object()
    replaced = document_status(canvas)
    assert replaced is not state
    assert not replaced.source and not replaced.saved_path and not replaced.exported_path
    assert replaced.autosave == "none" and replaced.autosave_at is None


def test_labels_distinguish_source_user_save_flat_export_and_failed_recovery():
    canvas = SimpleNamespace(document=lambda: None)
    state = document_status(canvas)
    assert status_lines(state, False, {}) == [
        "Source: New document", "No unsaved changes", "Document: Not saved",
        "Recovery autosave: none",
    ]
    state.source, state.saved_path, state.exported_path = "input.jpg", "edit.imervue", "flat.png"
    state.autosave, state.autosave_error = "failed", "read only"
    labels = "\n".join(status_lines(state, True, {}))
    assert "Modified — unsaved" in labels
    assert "input.jpg" in labels and "edit.imervue" in labels and "Flat export: flat.png" in labels
    assert "failed: read only" in labels


def test_refresh_does_not_switch_tabs_and_only_refreshes_active_status():
    first, second = object(), object()
    tabs, statuses = [], []
    workspace = SimpleNamespace(_canvas=first, _refresh_tab_title=tabs.append,
                                _refresh_status_line=lambda: statuses.append(True))
    refresh_document_status(workspace, second)
    assert tabs == [second] and not statuses and workspace._canvas is first
    refresh_document_status(workspace, first)
    assert statuses == [True]
    refresh_document_status(SimpleNamespace(), None)
