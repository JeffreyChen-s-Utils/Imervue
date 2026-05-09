"""UX-layer tests: dock clusters, layout persistence, tool→dock raise.

These exercise the workspace's UX wiring rather than business
logic — the goal is to lock down the user-visible defaults so a
refactor that drops a cluster or breaks the persistence contract
fails loudly in CI.
"""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop(PaintWorkspace.DOCK_STATE_SETTING_KEY, None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop(PaintWorkspace.DOCK_STATE_SETTING_KEY, None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Dock clusters
# ---------------------------------------------------------------------------


def test_workspace_exposes_three_dock_clusters(qapp):
    ws = PaintWorkspace()
    try:
        clusters = ws._dock_clusters   # noqa: SLF001
        assert set(clusters.keys()) == {"drawing", "canvas", "library"}
        # Cluster sizes match the documented split.
        assert len(clusters["drawing"]) == 4    # color/brush/fill/swatches
        assert len(clusters["canvas"]) == 6     # layer/nav/history/pages/anim/hist
        assert len(clusters["library"]) == 4    # material/stamps/pose/reference
    finally:
        ws.deleteLater()


def test_drawing_cluster_groups_color_brush_bucket_swatches(qapp):
    ws = PaintWorkspace()
    try:
        cluster = ws._dock_clusters["drawing"]   # noqa: SLF001
        assert ws._color_dock in cluster   # noqa: SLF001
        assert ws._brush_dock in cluster   # noqa: SLF001
        assert ws._fill_dock in cluster    # noqa: SLF001
        assert ws._swatch_dock in cluster  # noqa: SLF001
        # All four titles non-empty so the tab labels render.
        assert all(d.windowTitle() for d in cluster)
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Dock layout persistence
# ---------------------------------------------------------------------------


def test_save_dock_state_writes_base64_blob_to_settings(qapp):
    ws = PaintWorkspace()
    try:
        ws._save_dock_state()  # noqa: SLF001
        blob = user_setting_dict.get(PaintWorkspace.DOCK_STATE_SETTING_KEY)
        assert isinstance(blob, str)
        assert len(blob) > 0
    finally:
        ws.deleteLater()


def test_restore_dock_state_no_op_when_missing(qapp):
    """First-run case — no saved blob; restore must succeed silently
    rather than crash the constructor."""
    user_setting_dict.pop(PaintWorkspace.DOCK_STATE_SETTING_KEY, None)
    ws = PaintWorkspace()
    try:
        # Just constructed — restore was already called and we're alive.
        ws._restore_dock_state()  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_restore_dock_state_ignores_corrupt_blob(qapp):
    user_setting_dict[PaintWorkspace.DOCK_STATE_SETTING_KEY] = "not_base64_!!"
    ws = PaintWorkspace()  # constructor calls _restore_dock_state
    try:
        # Workspace is alive — corrupt blob did not raise.
        assert ws._dock_clusters is not None  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_save_then_restore_round_trip_keeps_workspace_alive(qapp):
    """Build a workspace, save state, build another, restore the
    previous state — both workspaces survive the round-trip."""
    ws1 = PaintWorkspace()
    try:
        ws1._save_dock_state()                              # noqa: SLF001
    finally:
        ws1.deleteLater()
    blob = user_setting_dict.get(PaintWorkspace.DOCK_STATE_SETTING_KEY)
    assert blob

    ws2 = PaintWorkspace()
    try:
        # Constructor restores; we still have working clusters.
        assert ws2._dock_clusters["drawing"]                # noqa: SLF001
    finally:
        ws2.deleteLater()


# ---------------------------------------------------------------------------
# Auto-raise dock on tool change
# ---------------------------------------------------------------------------


def test_brush_tool_raises_brush_dock(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_tool("brush")  # noqa: SLF001
        # We can't easily assert tab activation in a headless test
        # without showing the window, but the raise call must run
        # without raising — verify the wiring fires by spying.
        captured: list[str] = []
        original = ws._brush_dock.raise_   # noqa: SLF001

        def spy():
            captured.append("brush_dock")
            original()
        ws._brush_dock.raise_ = spy   # noqa: SLF001
        ws._raise_dock_for_tool()     # noqa: SLF001
        assert captured == ["brush_dock"]
    finally:
        ws.deleteLater()


def test_fill_tool_raises_fill_dock(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_tool("fill")  # noqa: SLF001
        captured: list[str] = []
        original = ws._fill_dock.raise_   # noqa: SLF001

        def spy():
            captured.append("fill_dock")
            original()
        ws._fill_dock.raise_ = spy   # noqa: SLF001
        ws._raise_dock_for_tool()    # noqa: SLF001
        assert captured == ["fill_dock"]
    finally:
        ws.deleteLater()


def test_unmapped_tool_does_not_raise_anything(qapp):
    ws = PaintWorkspace()
    try:
        # "hand" / "zoom" are tools without a settings dock.
        ws._state.set_tool("hand")    # noqa: SLF001
        ws._raise_dock_for_tool()     # noqa: SLF001  — succeeds silently
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Pose canvas size policy
# ---------------------------------------------------------------------------


def test_pose_canvas_uses_expanding_size_policy(qapp):
    from PySide6.QtWidgets import QSizePolicy
    from Imervue.paint.pose_dock import PoseCanvas
    canvas = PoseCanvas()
    try:
        policy = canvas.sizePolicy()
        assert policy.horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert policy.verticalPolicy() == QSizePolicy.Policy.Expanding
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# New comic project dialog
# ---------------------------------------------------------------------------


def test_new_project_dialog_default_values(qapp):
    from Imervue.paint.new_project_dialog import (
        DEFAULT_PAGE_COUNT,
        NewProjectDialog,
    )
    dialog = NewProjectDialog()
    try:
        choice = dialog.values()
        assert choice.page_count == DEFAULT_PAGE_COUNT
        assert choice.project_name == "Untitled Project"
        assert choice.template_name  # non-empty
    finally:
        dialog.deleteLater()


def test_new_project_dialog_picks_user_template(qapp):
    from Imervue.paint.new_project_dialog import NewProjectDialog
    dialog = NewProjectDialog()
    try:
        # Switch to a panel-grid template and bump page count.
        idx = dialog._template.findData("manga_b5_2x3_grid")  # noqa: SLF001
        assert idx >= 0
        dialog._template.setCurrentIndex(idx)                 # noqa: SLF001
        dialog._page_count.setValue(7)                        # noqa: SLF001
        choice = dialog.values()
        assert choice.template_name == "manga_b5_2x3_grid"
        assert choice.page_count == 7
    finally:
        dialog.deleteLater()
