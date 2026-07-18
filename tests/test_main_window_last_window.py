"""File -> New Window must not let closing one window kill the whole process.

closeEvent runs an app-global plugin unload + ``os._exit``; a secondary window
shares it, so those must run only when the LAST main window closes. The
last-window decision is a pure helper, unit-tested here with plain objects
(``os._exit`` itself is untestable -- it would terminate pytest, and the window
is a Qt/GL widget we don't construct).
"""
from __future__ import annotations

from Imervue.Imervue_main_window import _other_live_windows_remain


def test_other_window_open_is_not_the_last_window():
    a, b = object(), object()
    assert _other_live_windows_remain([a, b], a) is True


def test_empty_registry_is_the_last_window():
    assert _other_live_windows_remain([], object()) is False


def test_only_self_left_is_the_last_window():
    # Defensive: self doesn't count as "another" window even if not discarded.
    a = object()
    assert _other_live_windows_remain([a], a) is False


def test_sibling_remaining_after_self_discarded_is_not_last():
    sibling = object()
    assert _other_live_windows_remain([sibling], object()) is True
