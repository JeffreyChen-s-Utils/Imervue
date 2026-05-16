"""Tests for the :class:`PetWindow` overlay construction.

The overlay's GL canvas can't really render in headless CI, but
the window-flag plumbing is testable: the right flag combination
must be set before show, click-through toggle has to round-trip
without losing the other flags, and the auxiliary state (drag
offset, snap threshold) needs sane defaults.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.desktop_pet.edge_snap import DEFAULT_SNAP_THRESHOLD
from Imervue.desktop_pet.pet_window import PetWindow


def _has_flag(flags: Qt.WindowType, target: Qt.WindowType) -> bool:
    return bool(int(flags) & int(target))


def test_window_flags_include_frameless_topmost_tool(qapp):
    """A frameless, always-on-top, tool-window combo is the
    table-stakes desktop-pet flag set — every commercial widget
    uses these three together."""
    window = PetWindow()
    try:
        flags = window.windowFlags()
        assert _has_flag(flags, Qt.WindowType.FramelessWindowHint)
        assert _has_flag(flags, Qt.WindowType.WindowStaysOnTopHint)
        assert _has_flag(flags, Qt.WindowType.Tool)
    finally:
        window.deleteLater()


def test_window_starts_without_click_through(qapp):
    """Default state must be "interactive" — a click-through-by-
    default pet would be undraggable on first show, which is
    confusing UX."""
    window = PetWindow()
    try:
        assert window.click_through_enabled() is False
        flags = window.windowFlags()
        assert not _has_flag(flags, Qt.WindowType.WindowTransparentForInput)
    finally:
        window.deleteLater()


def test_click_through_toggle_round_trip(qapp):
    """Enabling then disabling click-through must preserve the
    other window flags — the toggle rebuilds the flag bitmask
    and a buggy rebuild would silently drop FramelessWindowHint."""
    window = PetWindow()
    try:
        window.set_click_through(True)
        assert window.click_through_enabled() is True
        flags = window.windowFlags()
        assert _has_flag(flags, Qt.WindowType.WindowTransparentForInput)
        assert _has_flag(flags, Qt.WindowType.FramelessWindowHint)
        assert _has_flag(flags, Qt.WindowType.WindowStaysOnTopHint)

        window.set_click_through(False)
        assert window.click_through_enabled() is False
        flags = window.windowFlags()
        assert not _has_flag(flags, Qt.WindowType.WindowTransparentForInput)
        assert _has_flag(flags, Qt.WindowType.FramelessWindowHint)
        assert _has_flag(flags, Qt.WindowType.WindowStaysOnTopHint)
    finally:
        window.deleteLater()


def test_idempotent_click_through_set(qapp):
    """Calling ``set_click_through(False)`` on an already-False
    instance must be a no-op — Qt re-creates the native window on
    flag changes, so silent re-applications would cause flicker."""
    window = PetWindow()
    try:
        window.set_click_through(False)  # already False
        assert window.click_through_enabled() is False
        window.set_click_through(True)
        window.set_click_through(True)   # already True
        assert window.click_through_enabled() is True
    finally:
        window.deleteLater()


def test_translucent_background_attribute_set(qapp):
    """The translucent-background attribute is what makes the
    desktop visible through the canvas's transparent clear. Lose
    it and the pet's edges render against an opaque widget
    background (usually black)."""
    window = PetWindow()
    try:
        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    finally:
        window.deleteLater()


def test_default_snap_threshold_matches_helper(qapp):
    window = PetWindow()
    try:
        assert window._snap_threshold == DEFAULT_SNAP_THRESHOLD   # noqa: SLF001
    finally:
        window.deleteLater()


def test_canvas_is_in_pet_mode(qapp):
    """The embedded canvas must be constructed in pet mode so
    its ``initializeGL`` clears to fully-transparent instead of
    the editor checker backdrop."""
    window = PetWindow()
    try:
        canvas = window.canvas()
        assert canvas._pet_mode is True   # noqa: SLF001
    finally:
        window.deleteLater()


def test_load_puppet_file_returns_false_on_missing(qapp, tmp_path):
    """A non-existent ``.puppet`` archive must produce a False
    return rather than raising — the workspace's status label is
    the user-facing reporting channel."""
    window = PetWindow()
    try:
        result = window.load_puppet_file(tmp_path / "does-not-exist.puppet")
        assert result is False
        assert window.document() is None
    finally:
        window.deleteLater()
