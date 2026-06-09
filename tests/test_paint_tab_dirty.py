"""Tests for the per-tab modified indicator + close protection."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


# ---------------------------------------------------------------------------
# Dirty flag lifecycle
# ---------------------------------------------------------------------------


def test_fresh_tab_starts_clean(workspace):
    """A newly-built workspace has a single seed tab with no dirty
    flag set — the title carries no asterisk."""
    canvas = workspace.canvas()
    assert workspace._tab_dirty.get(canvas, False) is False  # noqa: SLF001
    assert "*" not in workspace._tabs.tabText(0)  # noqa: SLF001


def test_dispatcher_commit_marks_active_tab_dirty(workspace):
    """Any committed stroke must flip the active tab to "modified"
    so the UI surfaces the unsaved-edits state."""
    workspace._on_dispatcher_commit()  # noqa: SLF001
    canvas = workspace.canvas()
    assert workspace._tab_dirty.get(canvas) is True  # noqa: SLF001
    assert workspace._tabs.tabText(0).endswith(" *")  # noqa: SLF001


def test_image_loaded_resets_dirty(workspace):
    """Opening a fresh image into the active canvas drops the dirty
    flag — the user just loaded something they haven't edited yet."""
    workspace._on_dispatcher_commit()  # noqa: SLF001
    workspace._on_image_loaded(800, 600)  # noqa: SLF001
    canvas = workspace.canvas()
    assert workspace._tab_dirty.get(canvas) is False  # noqa: SLF001


def test_mark_active_tab_clean_clears_asterisk(workspace):
    workspace._on_dispatcher_commit()  # noqa: SLF001
    assert workspace._tabs.tabText(0).endswith(" *")  # noqa: SLF001
    workspace.mark_active_tab_clean()
    assert "*" not in workspace._tabs.tabText(0)  # noqa: SLF001


def test_setting_dirty_to_same_value_is_idempotent(workspace):
    """Repeated dispatcher commits on a tab that is already dirty
    don't keep appending asterisks — one is enough."""
    workspace._on_dispatcher_commit()  # noqa: SLF001
    workspace._on_dispatcher_commit()  # noqa: SLF001
    title = workspace._tabs.tabText(0)  # noqa: SLF001
    # Exactly one asterisk suffix.
    assert title.endswith(" *")
    assert title.count("*") == 1


# ---------------------------------------------------------------------------
# Close protection
# ---------------------------------------------------------------------------


def test_close_clean_tab_does_not_prompt(workspace, monkeypatch):
    """A clean tab closes silently — the modal prompt is reserved
    for actually-modified tabs."""
    workspace.new_tab()   # second tab so close_tab can succeed
    prompted = []
    monkeypatch.setattr(
        workspace, "_confirm_discard_unsaved",
        lambda widget: prompted.append(widget) or True,
    )
    assert workspace.close_tab(1) is True
    assert prompted == []


def test_close_dirty_tab_invokes_confirm(workspace, monkeypatch):
    workspace.new_tab()
    new_canvas = workspace.canvas()
    workspace._set_tab_dirty(new_canvas, True)  # noqa: SLF001
    seen = []
    monkeypatch.setattr(
        workspace, "_confirm_discard_unsaved",
        lambda widget: seen.append(widget) or True,
    )
    assert workspace.close_tab(1) is True
    assert seen == [new_canvas]


def test_close_dirty_tab_cancelled_keeps_tab(workspace, monkeypatch):
    """If the user cancels the discard prompt the tab stays open."""
    workspace.new_tab()
    new_canvas = workspace.canvas()
    workspace._set_tab_dirty(new_canvas, True)  # noqa: SLF001
    monkeypatch.setattr(
        workspace, "_confirm_discard_unsaved", lambda widget: False,
    )
    before = workspace._tabs.count()  # noqa: SLF001
    assert workspace.close_tab(1) is False
    assert workspace._tabs.count() == before  # noqa: SLF001


def test_close_dirty_tab_force_skips_prompt(workspace, monkeypatch):
    """``force=True`` is the no-questions-asked path — used after
    the user already confirmed elsewhere (Save → cleaned → close)."""
    workspace.new_tab()
    new_canvas = workspace.canvas()
    workspace._set_tab_dirty(new_canvas, True)  # noqa: SLF001
    prompted = []
    monkeypatch.setattr(
        workspace, "_confirm_discard_unsaved",
        lambda widget: prompted.append(widget),
    )
    assert workspace.close_tab(1, force=True) is True
    assert prompted == []


def test_close_drops_dirty_entry(workspace, monkeypatch):
    """Closing a tab pops its dirty-map entry so subsequent
    iterations of ``_tab_dirty`` (e.g. the close confirm sweep)
    don't reference deleted widgets."""
    workspace.new_tab()
    new_canvas = workspace.canvas()
    workspace._set_tab_dirty(new_canvas, True)  # noqa: SLF001
    monkeypatch.setattr(
        workspace, "_confirm_discard_unsaved", lambda widget: True,
    )
    workspace.close_tab(1)
    assert new_canvas not in workspace._tab_dirty   # noqa: SLF001


# ---------------------------------------------------------------------------
# File-menu success integration
# ---------------------------------------------------------------------------


def test_file_menu_notify_success_marks_active_tab_clean(qapp):
    from Imervue.paint.file_menu import _FileMenuBridge

    cleared = []

    class _StubToast:
        def success(self, text, duration_ms=2500):
            """No-op — the test only checks that the bridge tries to
            mark the active tab clean, not that a toast renders."""

    class _StubWorkspace:
        toast = _StubToast()

        def mark_active_tab_clean(self):
            cleared.append(True)

    bridge = _FileMenuBridge(_StubWorkspace())
    fake = "/scratch/out.png"   # noqa: S108  # label only, no file write
    bridge._notify_success(  # noqa: SLF001
        "paint_file_export_image_done", "Exported", fake,
    )
    assert cleared == [True]
