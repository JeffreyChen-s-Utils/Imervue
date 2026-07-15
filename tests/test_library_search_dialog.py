"""Tests for the library-search scan lifecycle (no double-scan, clean finish).

Each scan overwrote the (unparented) thread reference, so a double-click dropped
the first thread's only ref → "QThread destroyed while running" + two scanners
writing the same SQLite index. _start_scan now guards on the running thread and
_finish_scan re-enables the button and clears the handle. Driven unbound on
fakes — no real dialog / thread.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.library_search_dialog import LibrarySearchDialog


def test_start_scan_is_a_noop_while_a_scan_is_running():
    fake = SimpleNamespace(_thread=SimpleNamespace(isRunning=lambda: True))
    # Returns before touching the index / building a second thread.
    LibrarySearchDialog._start_scan(fake)
    assert fake._thread.isRunning() is True


def test_finish_scan_reenables_button_and_clears_the_thread():
    enabled: list = []
    fake = SimpleNamespace(
        _progress=SimpleNamespace(setVisible=lambda _v: None),
        _scan_btn=SimpleNamespace(setEnabled=enabled.append),
        _thread=SimpleNamespace(wait=lambda: None),
    )
    LibrarySearchDialog._finish_scan(fake)
    assert enabled == [True]
    assert fake._thread is None
