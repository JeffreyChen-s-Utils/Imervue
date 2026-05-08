"""Tests for the clickable zoom indicator in the status bar."""
from __future__ import annotations

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


def test_indicator_present_after_construction(workspace):
    assert hasattr(workspace, "_zoom_btn")
    assert workspace._zoom_btn is not None  # noqa: SLF001


def test_indicator_text_reflects_zoom(workspace):
    workspace._refresh_zoom_indicator(0.75)  # noqa: SLF001
    assert workspace._zoom_btn.text() == "75%"  # noqa: SLF001
    workspace._refresh_zoom_indicator(2.5)  # noqa: SLF001
    assert workspace._zoom_btn.text() == "250%"  # noqa: SLF001


def test_indicator_updates_via_zoom_changed_signal(workspace):
    """The canvas signal must drive the chip — otherwise zoom by
    wheel / View menu wouldn't keep the chip in sync."""
    workspace._on_zoom_changed_refresh_cursor(1.5)  # noqa: SLF001
    assert workspace._zoom_btn.text() == "150%"  # noqa: SLF001


def test_click_when_at_100_resets_to_fit(workspace):
    """Clicking while close to 100 % runs reset_view → "fit to
    window" so the chip is a one-tap toggle."""
    workspace.canvas().set_zoom(1.0)
    called = []
    workspace.canvas().reset_view = lambda: called.append("reset")
    workspace._on_zoom_indicator_clicked()  # noqa: SLF001
    assert called == ["reset"]


def test_click_when_not_100_jumps_to_100(workspace):
    workspace.canvas().set_zoom(2.0)
    snapped = []
    workspace.canvas().set_zoom = lambda factor: snapped.append(factor)
    workspace._on_zoom_indicator_clicked()  # noqa: SLF001
    assert snapped == [1.0]
