"""Tests for the memory-pressure status-bar indicator.

Pure helpers (state thresholds + label formatting) are testable
without Qt. The widget itself uses a callable source so the Qt
tests can feed it canned numbers without spawning a GPUImageView.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.memory_pressure import (
    RED_THRESHOLD,
    YELLOW_THRESHOLD,
    MemoryPressureIndicator,
    MemoryPressureState,
    format_tooltip,
    format_usage_label,
    state_from_usage,
)


# ---------------------------------------------------------------
# state_from_usage
# ---------------------------------------------------------------


def test_state_green_when_well_under_yellow():
    """Half-full cache → green. The user has plenty of headroom and
    the dot should stay calm."""
    used = int(100 * 1024 * 1024)
    limit = int(1024 * 1024 * 1024)
    assert state_from_usage(used, limit) is MemoryPressureState.GREEN


def test_state_yellow_at_threshold():
    """Exactly at the yellow threshold → yellow. Off-by-one would
    have the dot stay green for one tick longer than documented."""
    limit = 1000
    used = int(limit * YELLOW_THRESHOLD)
    assert state_from_usage(used, limit) is MemoryPressureState.YELLOW


def test_state_yellow_in_band():
    """Between yellow and red thresholds → yellow."""
    limit = 1000
    used = int(limit * (YELLOW_THRESHOLD + RED_THRESHOLD) / 2)
    assert state_from_usage(used, limit) is MemoryPressureState.YELLOW


def test_state_red_at_threshold():
    limit = 1000
    used = int(limit * RED_THRESHOLD)
    assert state_from_usage(used, limit) is MemoryPressureState.RED


def test_state_red_when_over_limit():
    """Slightly over (LRU was about to evict but hadn't yet) → red.
    The dot should never report 'green' when usage > limit."""
    limit = 1000
    used = 1500
    assert state_from_usage(used, limit) is MemoryPressureState.RED


def test_state_green_when_limit_is_zero():
    """Boundary: before the viewer probes VRAM the limit is 0;
    showing red would scare new users on first launch."""
    assert state_from_usage(0, 0) is MemoryPressureState.GREEN
    assert state_from_usage(100, 0) is MemoryPressureState.GREEN


def test_state_green_when_limit_is_negative():
    """A misconfigured limit (negative) → green fallback. The
    helper must never raise on integer math."""
    assert state_from_usage(100, -50) is MemoryPressureState.GREEN


def test_state_negative_used_treated_as_zero():
    """A caller passing negative used bytes (briefly during cache
    shrink) → green, not crash."""
    assert state_from_usage(-10, 1000) is MemoryPressureState.GREEN


@pytest.mark.parametrize("yellow,red", [(0.5, 0.8), (0.7, 0.95)])
def test_state_custom_thresholds(yellow, red):
    """Future tuning UI use-case: per-user thresholds."""
    limit = 1000
    assert state_from_usage(
        int(limit * yellow),
        limit,
        yellow_threshold=yellow,
        red_threshold=red,
    ) is MemoryPressureState.YELLOW
    assert state_from_usage(
        int(limit * red),
        limit,
        yellow_threshold=yellow,
        red_threshold=red,
    ) is MemoryPressureState.RED


# ---------------------------------------------------------------
# format_usage_label
# ---------------------------------------------------------------


def test_label_shows_percentage():
    assert format_usage_label(500, 1000) == "50%"


def test_label_rounds_to_integer():
    """Sub-percent precision is noise — the dot doesn't move fast
    enough to make 50.3 % vs 50.7 % readable."""
    assert format_usage_label(503, 1000) == "50%"


def test_label_handles_zero_limit():
    """First-launch placeholder — must not divide by zero."""
    assert format_usage_label(0, 0) == "--"
    assert format_usage_label(100, 0) == "--"
    assert format_usage_label(100, -1) == "--"


def test_label_can_exceed_100_percent():
    """Mid-eviction the cache can briefly exceed budget — the
    indicator should show the truth (e.g. 105 %) rather than clamp,
    so the user sees how bad it actually got."""
    assert format_usage_label(1050, 1000) == "105%"


# ---------------------------------------------------------------
# format_tooltip
# ---------------------------------------------------------------


def test_tooltip_includes_byte_totals():
    out = format_tooltip(100 * 1024 * 1024, 1024 * 1024 * 1024)
    assert "100.0 MB" in out
    assert "1024.0 MB" in out


def test_tooltip_omits_optional_counts():
    """When the source can't supply tile / prefetch counts the
    tooltip must still be useful — show what we have."""
    out = format_tooltip(100, 1000)
    assert "Loaded tiles" not in out
    assert "Prefetched images" not in out


def test_tooltip_shows_optional_counts_when_supplied():
    out = format_tooltip(100, 1000, tile_count=42, prefetch_count=3)
    assert "Loaded tiles: 42" in out
    assert "Prefetched images: 3" in out


def test_tooltip_handles_zero_limit():
    """Tooltip on a not-yet-probed cache should still render —
    just with zero MB on the limit line."""
    out = format_tooltip(0, 0)
    assert "0.0 MB" in out


# ---------------------------------------------------------------
# MemoryPressureIndicator — Qt smoke
# ---------------------------------------------------------------


def test_indicator_starts_green_before_first_poll(qapp):
    """Constructed widget primes itself with one refresh; with a
    zero-limit source that's GREEN. Verifies the first-frame
    placeholder behaviour."""
    indicator = MemoryPressureIndicator(source=lambda: {})
    try:
        assert indicator.state() is MemoryPressureState.GREEN
    finally:
        indicator.shutdown()
        indicator.deleteLater()


def test_indicator_updates_on_refresh(qapp):
    """Push numbers into the source, call refresh, observe the new
    state. Skips the QTimer so the test is deterministic."""
    state = {"used_bytes": 900, "limit_bytes": 1000}

    def source():
        return state

    indicator = MemoryPressureIndicator(source=source)
    try:
        assert indicator.state() is MemoryPressureState.RED
        state["used_bytes"] = 100
        indicator.refresh()
        assert indicator.state() is MemoryPressureState.GREEN
    finally:
        indicator.shutdown()
        indicator.deleteLater()


def test_indicator_source_exception_does_not_crash(qapp):
    """A stale viewer reference might raise on shutdown — the
    indicator must swallow it rather than propagate to the GUI
    event loop."""
    def boom():
        raise RuntimeError("viewer torn down")

    indicator = MemoryPressureIndicator(source=boom)
    try:
        indicator.refresh()   # must not raise
    finally:
        indicator.shutdown()
        indicator.deleteLater()


def test_indicator_clear_cache_callback_invoked(qapp):
    """The constructor's ``clear_cache`` callback fires on
    left-click + the indicator immediately refreshes (so the dot
    drops to green if the source now reports zero)."""
    fired: list[int] = []

    def source():
        # First call: pressure red. After clear: green.
        return {
            "used_bytes": 0 if fired else 950,
            "limit_bytes": 1000,
        }

    def clear():
        fired.append(1)

    indicator = MemoryPressureIndicator(source=source, clear_cache=clear)
    try:
        assert indicator.state() is MemoryPressureState.RED
        # Synthesise a left-click via the override directly to avoid
        # spawning a QMouseEvent — the production handler is small
        # enough to call its callback by hand here.
        from PySide6.QtCore import Qt, QPointF, QEvent
        from PySide6.QtGui import QMouseEvent
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(0.0, 0.0),
            QPointF(0.0, 0.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        indicator.mousePressEvent(event)
        assert fired == [1]
        assert indicator.state() is MemoryPressureState.GREEN
    finally:
        indicator.shutdown()
        indicator.deleteLater()


def test_indicator_tooltip_updates_after_refresh(qapp):
    """``setToolTip`` is called as part of refresh; verify the
    visible tooltip reflects the latest data."""
    state = {
        "used_bytes": 100 * 1024 * 1024,
        "limit_bytes": 1024 * 1024 * 1024,
        "tile_count": 7,
    }
    indicator = MemoryPressureIndicator(source=lambda: state)
    try:
        tip = indicator.toolTip()
        assert "100.0 MB" in tip
        assert "Loaded tiles: 7" in tip
    finally:
        indicator.shutdown()
        indicator.deleteLater()
