"""Tests for the autosave status-line segment."""
from __future__ import annotations

import time

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


def test_segment_absent_before_first_autosave(workspace):
    """Fresh workspace has never autosaved → no segment so the
    status line doesn't pretend a snapshot exists."""
    line = workspace._compose_status_line(None)  # noqa: SLF001
    assert "Saved" not in line
    assert workspace._format_autosave_segment(  # noqa: SLF001
        workspace._compose_status_line.__doc__ and {} or {},
    ) is None


def test_segment_just_now_immediately_after_save(workspace):
    workspace._last_autosave_at = time.monotonic()  # noqa: SLF001
    seg = workspace._format_autosave_segment(  # noqa: SLF001
        workspace._compose_status_line.__doc__ and {} or {},
    )
    assert seg is not None
    assert "just now" in seg.lower() or "剛剛" in seg


def test_segment_seconds_unit_under_a_minute(workspace):
    workspace._last_autosave_at = time.monotonic() - 30   # noqa: SLF001
    seg = workspace._format_autosave_segment({})  # noqa: SLF001
    assert seg is not None
    assert "30" in seg
    assert "s" in seg.lower()


def test_segment_minutes_unit_after_a_minute(workspace):
    workspace._last_autosave_at = time.monotonic() - 90   # noqa: SLF001
    seg = workspace._format_autosave_segment({})  # noqa: SLF001
    assert seg is not None
    assert "1" in seg
    assert "m" in seg.lower()


def test_segment_hours_unit_after_an_hour(workspace):
    workspace._last_autosave_at = time.monotonic() - 7200  # noqa: SLF001
    seg = workspace._format_autosave_segment({})  # noqa: SLF001
    assert seg is not None
    assert "2" in seg
    assert "h" in seg.lower()


def test_take_autosave_snapshot_now_records_timestamp(workspace, tmp_path):
    """The successful-snapshot path stamps ``_last_autosave_at`` so
    the status line picks up the segment on the next refresh."""
    layer = workspace.canvas().document().active_layer()
    layer.image[..., :3] = (10, 20, 30)
    workspace._autosave_target_dir = tmp_path  # noqa: SLF001
    assert workspace._last_autosave_at is None  # noqa: SLF001
    workspace.take_autosave_snapshot_now()
    assert workspace._last_autosave_at is not None  # noqa: SLF001


def test_status_line_includes_autosave_segment_after_save(workspace, tmp_path):
    layer = workspace.canvas().document().active_layer()
    layer.image[..., :3] = (10, 20, 30)
    workspace._autosave_target_dir = tmp_path  # noqa: SLF001
    workspace.take_autosave_snapshot_now()
    line = workspace._compose_status_line(None)  # noqa: SLF001
    assert "Saved" in line or "saved" in line.lower()


def test_skipped_snapshot_does_not_record_timestamp(workspace):
    """An empty document yields ``None`` from ``write_snapshot``;
    the workspace must NOT stamp the timestamp in that case — the
    "Saved" line would otherwise lie about a never-written file."""
    document = workspace.canvas().document()
    document._layers.clear()  # noqa: SLF001
    document._composite_cache = None  # noqa: SLF001
    workspace.take_autosave_snapshot_now()
    assert workspace._last_autosave_at is None  # noqa: SLF001
