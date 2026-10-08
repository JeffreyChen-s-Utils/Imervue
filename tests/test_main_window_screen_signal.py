"""_connect_screen_change_signal must retry until windowHandle() exists.

windowHandle() is None on the first deferred attempt (before the native window
is shown); a one-shot that gave up then left the screenChanged signal
permanently unconnected, so dragging/restoring the window to another monitor
never re-fit the view. Driven on the unbound method with a fake self.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import Imervue.gui.main_window_screens as screens_mod
from Imervue.Imervue_main_window import ImervueMainWindow


class _FakeScheduler:
    """``call_later`` stand-in that records what each test scheduled.

    Instance state, not class attributes: a shared class-level list would have
    to be reset by hand in every test and leaks schedules between them.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[int, object, object]] = []

    def __call__(self, ms, owner, fn) -> None:
        self.calls.append((ms, owner, fn))


@pytest.fixture
def fake_timer(monkeypatch):
    """Swap the window module's ``call_later`` for a fresh per-test recorder."""
    scheduler = _FakeScheduler()
    monkeypatch.setattr(screens_mod, "call_later", scheduler)
    return scheduler


def test_retries_when_window_handle_missing(fake_timer):
    fake = SimpleNamespace(_screen_signal_connected=False, windowHandle=lambda: None)

    ImervueMainWindow._connect_screen_change_signal(fake, _retries=3)

    assert len(fake_timer.calls) == 1     # scheduled a retry
    assert fake_timer.calls[0][0] == 50   # ...on a 50ms timer
    assert fake_timer.calls[0][1] is fake  # ...owned by the window, so it dies with it
    assert fake._screen_signal_connected is False


def test_gives_up_after_retries_exhausted(fake_timer):
    fake = SimpleNamespace(_screen_signal_connected=False, windowHandle=lambda: None)

    ImervueMainWindow._connect_screen_change_signal(fake, _retries=0)

    assert fake_timer.calls == []         # no infinite retry loop
    assert fake._screen_signal_connected is False


def test_connects_when_handle_ready(fake_timer):
    connected: list = []
    handle = SimpleNamespace(
        screenChanged=SimpleNamespace(connect=lambda slot: connected.append(slot)))
    fake = SimpleNamespace(
        _screen_signal_connected=False,
        windowHandle=lambda: handle,
        _on_screen_changed=lambda _s: None,
    )

    ImervueMainWindow._connect_screen_change_signal(fake)

    assert len(connected) == 1            # signal wired
    assert fake._screen_signal_connected is True
    assert fake_timer.calls == []         # connected directly, no retry


def test_noop_when_already_connected(fake_timer):
    fake = SimpleNamespace(_screen_signal_connected=True, windowHandle=lambda: None)

    ImervueMainWindow._connect_screen_change_signal(fake)

    assert fake_timer.calls == []         # already connected, nothing to do


# ---------------------------------------------------------------------------
# _reflow_modify_canvas — window/screen resize must re-fit the Modify canvas
# ---------------------------------------------------------------------------


def _reflow_fake(tab_index, has_canvas):
    updated: list = []
    canvas = (SimpleNamespace(update=lambda: updated.append(True))
              if has_canvas else None)
    fake = SimpleNamespace(
        _main_tabs=SimpleNamespace(currentIndex=lambda: tab_index),
        modify_panel=SimpleNamespace(_canvas=canvas),
    )
    return fake, updated


def test_reflow_on_modify_tab_repaints_the_canvas():
    fake, updated = _reflow_fake(1, has_canvas=True)
    ImervueMainWindow._reflow_modify_canvas(fake)
    assert updated == [True]          # canvas repainted -> re-fits to its new width


def test_reflow_noop_off_the_modify_tab():
    fake, updated = _reflow_fake(0, has_canvas=True)
    ImervueMainWindow._reflow_modify_canvas(fake)
    assert updated == []


def test_reflow_noop_when_no_canvas():
    fake, updated = _reflow_fake(1, has_canvas=False)
    ImervueMainWindow._reflow_modify_canvas(fake)   # no raise


def test_reflow_safe_before_tabs_exist():
    ImervueMainWindow._reflow_modify_canvas(SimpleNamespace(_main_tabs=None))  # no raise
