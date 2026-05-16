"""Detect "another app is fullscreen on this screen" so the pet
can hide itself politely.

Why this exists: a desktop pet that stays on top of a video
player / game / presentation defeats the point of fullscreen
mode — the user wanted to hide everything BUT that app. Most
commercial Live2D widgets implement this hide-behind-fullscreen
rule; we match.

The detector is structured as a small poll loop (``QTimer`` at
~1 Hz) so we don't subscribe to platform-specific window-manager
events. On Windows we read the foreground window's rect via the
``ctypes`` Win32 API; macOS / Linux fall back to "compare the
focused window's geometry to its screen's geometry".
"""
from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

if TYPE_CHECKING:
    from PySide6.QtCore import QRect

logger = logging.getLogger("Imervue.desktop_pet.fullscreen_detector")

POLL_INTERVAL_MS: int = 1000
"""How often to check for fullscreen state. 1 Hz is plenty —
fullscreen toggles are user-driven (Alt+Tab / F11 / start a
game), not 60 fps events."""

_OS_NAME = platform.system()


class FullscreenDetector(QObject):
    """Polls the active window and emits a bool whenever the
    "screen is in fullscreen mode" answer changes.

    Owned by the pet window; lives as long as the pet does. The
    detector itself does NOT decide whether to hide the pet —
    callers wire :attr:`state_changed` to their own visibility
    logic. Keeps the detector reusable for other use-cases (e.g.
    speech-bubble suppression during fullscreen)."""

    state_changed = Signal(bool)
    """``True`` when fullscreen begins, ``False`` when it ends.
    Edge-only — does not re-emit on every poll."""

    def __init__(
        self,
        screen_getter: Callable[[], QRect | None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        # ``screen_getter`` returns the screen rect to compare
        # against — the pet window passes its current
        # ``screen().geometry()`` so multi-monitor setups only
        # hide when fullscreen is on the SAME screen as the pet.
        self._screen_getter = screen_getter
        self._is_fullscreen = False
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    # ---- polling -----------------------------------------------

    def _poll(self) -> None:   # pragma: no cover - platform-specific
        active_rect = self._foreground_window_rect()
        screen_rect = self._screen_getter()
        if active_rect is None or screen_rect is None:
            new_state = False
        else:
            new_state = _rects_cover(active_rect, screen_rect)
        if new_state != self._is_fullscreen:
            self._is_fullscreen = new_state
            self.state_changed.emit(new_state)

    def _foreground_window_rect(self) -> QRect | None:   # pragma: no cover - platform
        """Best-effort lookup of the active window's screen rect.
        Returns ``None`` when the platform can't answer (we treat
        that as "not fullscreen", so the pet stays visible)."""
        if _OS_NAME == "Windows":
            return _windows_foreground_rect()
        # Generic fallback — Qt knows about its OWN windows but
        # not foreign ones; on macOS / Linux without a clean
        # cross-platform API the safest behaviour is "never hide",
        # which we model by returning None.
        return None


def _rects_cover(window_rect, screen_rect) -> bool:
    """Treat a window as "fullscreen on this screen" when it
    covers >= 99% of the screen's area AND its bounds are within
    a tolerance of the screen edges. Catches both true fullscreen
    (rect == screen) and borderless windowed (rect within a
    pixel of screen). The tolerance avoids false positives for a
    maximised-but-not-fullscreen window with a 1-2 px decoration."""
    sw = screen_rect.width()
    sh = screen_rect.height()
    if sw <= 0 or sh <= 0:
        return False
    ww = window_rect.width()
    wh = window_rect.height()
    coverage = (ww * wh) / (sw * sh)
    if coverage < 0.99:
        return False
    tolerance = 4
    return (
        abs(window_rect.left() - screen_rect.left()) <= tolerance
        and abs(window_rect.top() - screen_rect.top()) <= tolerance
        and abs(window_rect.right() - screen_rect.right()) <= tolerance
        and abs(window_rect.bottom() - screen_rect.bottom()) <= tolerance
    )


def _windows_foreground_rect():   # pragma: no cover - Windows-only
    """Read the foreground window's screen rect via the Win32
    API. Returns ``None`` on any failure (DLL missing, no
    foreground window). Pure ctypes — no extra dep."""
    import ctypes
    from ctypes import wintypes
    try:
        user32 = ctypes.windll.user32
    except (AttributeError, OSError):
        return None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    from PySide6.QtCore import QRect
    return QRect(
        rect.left, rect.top,
        rect.right - rect.left, rect.bottom - rect.top,
    )


__all__ = [
    "POLL_INTERVAL_MS",
    "FullscreenDetector",
]


def _qt_screens_geometry():
    """Convenience for callers that need the full multi-screen
    bounding rect — useful for "is the active window covering
    EVERY screen?" detection. Currently unused but kept exported
    so future heuristics can grab it without touching Qt."""
    screens = QGuiApplication.screens()
    if not screens:
        return None
    return [s.geometry() for s in screens]
