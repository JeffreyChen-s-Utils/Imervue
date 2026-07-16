"""Rapid rating/favorite toasts must restore the REAL caption, not a stale one.

_show_status re-captured filename_label.text() each call, so a second rating
within 1.5s captured the first rating's transient text as the "original" and
restored to it -- losing the folder caption until the next folder change.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.actions.keyboard_actions import (
    _restore_caption,
    _show_status,
)


def _gui():
    label_text = ["Folder: /photos"]
    active = [False]
    label = SimpleNamespace(
        text=lambda: label_text[0],
        setText=lambda t: label_text.__setitem__(0, t),
    )
    timer = SimpleNamespace(
        isActive=lambda: active[0],
        start=lambda _ms: active.__setitem__(0, True),
    )
    win = SimpleNamespace(filename_label=label, _status_restore_timer=timer)
    return SimpleNamespace(main_window=win), win, label_text


def test_rapid_ratings_keep_the_real_caption():
    gui, win, label_text = _gui()

    _show_status(gui, "★★★")
    assert win._status_original_caption == "Folder: /photos"
    assert label_text[0] == "★★★"

    # Second rating while the timer is active must NOT capture the transient.
    _show_status(gui, "★★★★")
    assert win._status_original_caption == "Folder: /photos"
    assert label_text[0] == "★★★★"

    # Restore lands on the real caption, not the stale "★★★".
    _restore_caption(win)
    assert label_text[0] == "Folder: /photos"


def test_show_status_noop_without_filename_label():
    gui = SimpleNamespace(main_window=SimpleNamespace())
    _show_status(gui, "hi")   # must not raise
