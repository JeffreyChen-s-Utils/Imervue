"""Tests for the right-click canvas quick-actions menu."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


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


def test_select_all_writes_full_mask(workspace):
    workspace._select_all_canvas()  # noqa: SLF001
    sel = workspace.canvas().document().selection()
    assert sel is not None
    assert bool(sel.all())


def test_deselect_clears_selection(workspace):
    h, w = workspace.canvas().document().shape
    workspace.canvas().document().set_selection(
        np.ones((h, w), dtype=bool),
    )
    assert workspace._has_active_selection() is True  # noqa: SLF001
    workspace._deselect_canvas()  # noqa: SLF001
    assert workspace._has_active_selection() is False  # noqa: SLF001


def test_has_active_selection_false_initially(workspace):
    """Default workspace has no selection so the deselect entry
    must render disabled."""
    assert workspace._has_active_selection() is False  # noqa: SLF001


def test_canvas_uses_custom_context_menu_policy(workspace):
    """The signal-based policy is what gets the customContextMenuRequested
    signal to fire — without it the workspace never gets a chance
    to populate the menu."""
    from PySide6.QtCore import Qt
    assert workspace.canvas().contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_build_context_menu_lists_documented_actions(workspace):
    """Verify the menu carries the documented quick actions —
    avoids ``QMenu.exec`` (which would deadlock the headless
    runner) by exercising the construction step directly."""
    menu = workspace._build_canvas_context_menu()  # noqa: SLF001
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    # Six visible actions: undo, redo, select all, deselect, fit, 100%.
    assert len(labels) == 6


def test_build_context_menu_disables_undo_when_stack_empty(workspace):
    """``can_undo`` is False on a fresh workspace → the Undo entry
    must render greyed-out so the user gets the right affordance."""
    menu = workspace._build_canvas_context_menu()  # noqa: SLF001
    actions = [a for a in menu.actions() if not a.isSeparator()]
    undo = actions[0]
    assert undo.isEnabled() is False


def test_build_context_menu_enables_undo_after_commit(workspace):
    workspace._on_dispatcher_commit()  # noqa: SLF001
    menu = workspace._build_canvas_context_menu()  # noqa: SLF001
    actions = [a for a in menu.actions() if not a.isSeparator()]
    undo = actions[0]
    assert undo.isEnabled() is True
