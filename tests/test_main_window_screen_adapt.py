"""Tests for the drag-to-another-screen adaptation on the main window.

When the window settles on a screen with a different available geometry,
``_adapt_to_current_screen`` rescales the frame proportionally and re-fits
the deep-zoom image. Light fakes are bound to the production (unbound)
methods — same pattern as ``test_main_window_drop`` — so no GL widget or
real second monitor is needed.
"""
from __future__ import annotations

from PySide6.QtCore import QRect

from Imervue.Imervue_main_window import ImervueMainWindow

_PRIMARY = QRect(0, 0, 1920, 1080)
_SMALLER = QRect(1920, 0, 1280, 720)


class _FakeScreen:
    def __init__(self, rect: QRect):
        self._rect = rect

    def availableGeometry(self) -> QRect:  # noqa: N802 — Qt naming
        return self._rect


class _FakeViewer:
    def __init__(self, *, deep: bool = True, grid: bool = False):
        self.deep_zoom = object() if deep else None
        self.tile_grid_mode = grid
        self.fit_calls = 0
        self.update_calls = 0

    def _fit_to_window(self):
        self.fit_calls += 1

    def update(self):
        self.update_calls += 1


class _StubMainWindow:
    """Attribute surface for the screen-adapt methods, bound to the
    production implementations so the real dispatch is exercised."""

    _adapt_to_current_screen = ImervueMainWindow._adapt_to_current_screen
    _rescale_window_between_screens = ImervueMainWindow._rescale_window_between_screens
    _refit_deep_zoom_image = ImervueMainWindow._refit_deep_zoom_image

    def __init__(self, *, screen_rect: QRect | None = None,
                 geometry: QRect | None = None, frame_extra: int = 0,
                 maximized: bool = False):
        self._screen = _FakeScreen(screen_rect or QRect(_PRIMARY))
        self._geometry = geometry or QRect(100, 100, 800, 600)
        # frame_extra simulates window decorations: the frame extends this
        # many pixels left/right/bottom and 4x above (title bar).
        self._frame_extra = frame_extra
        self._maximized = maximized
        self._last_screen_avail = None
        self.viewer = _FakeViewer()
        self.set_geometry_calls: list[tuple[int, int, int, int]] = []

    def screen(self):
        return self._screen

    def isMaximized(self) -> bool:  # noqa: N802 — Qt naming
        return self._maximized

    def isFullScreen(self) -> bool:  # noqa: N802 — Qt naming
        return False

    def geometry(self) -> QRect:
        return QRect(self._geometry)

    def frameGeometry(self) -> QRect:  # noqa: N802 — Qt naming
        extra = self._frame_extra
        return self._geometry.adjusted(-extra, -4 * extra, extra, extra)

    def setGeometry(self, x: int, y: int, w: int, h: int):  # noqa: N802 — Qt naming
        self.set_geometry_calls.append((x, y, w, h))
        self._geometry = QRect(x, y, w, h)


def _settle(win: _StubMainWindow) -> None:
    """First debounce fire after startup — records the baseline screen."""
    win._adapt_to_current_screen()   # noqa: SLF001


def test_first_fire_records_baseline_without_adapting(qapp):
    win = _StubMainWindow()
    _settle(win)
    assert win._last_screen_avail == (0, 0, 1920, 1080)   # noqa: SLF001
    assert win.set_geometry_calls == []
    qapp.processEvents()
    assert win.viewer.fit_calls == 0


def test_same_screen_is_noop(qapp):
    win = _StubMainWindow()
    _settle(win)
    win._adapt_to_current_screen()   # noqa: SLF001
    assert win.set_geometry_calls == []
    qapp.processEvents()
    assert win.viewer.fit_calls == 0


def test_screen_change_rescales_window_and_refits_image(qapp):
    win = _StubMainWindow()
    _settle(win)
    win._screen = _FakeScreen(QRect(_SMALLER))
    win._adapt_to_current_screen()   # noqa: SLF001

    assert len(win.set_geometry_calls) == 1
    x, y, w, h = win.set_geometry_calls[0]
    # Proportional footprint: 800/1920 and 600/1080 of the new screen.
    assert w == round(800 / 1920 * 1280)
    assert h == round(600 / 1080 * 720)
    # Fully inside the (offset) target screen.
    assert x >= 1920 and x + w <= 1920 + 1280
    assert y >= 0 and y + h <= 720

    qapp.processEvents()
    assert win.viewer.fit_calls == 1
    assert win.viewer.update_calls == 1


def test_frame_margins_keep_title_bar_on_screen(qapp):
    # Window client rect at the very top of the old screen; a naive clamp
    # of the client rect would push the (taller) frame's title bar above
    # the new screen. setGeometry must receive client coords inset by the
    # decoration margins.
    win = _StubMainWindow(geometry=QRect(0, 32, 800, 600), frame_extra=8)
    _settle(win)
    win._screen = _FakeScreen(QRect(_SMALLER))
    win._adapt_to_current_screen()   # noqa: SLF001

    assert len(win.set_geometry_calls) == 1
    x, y, _w, _h = win.set_geometry_calls[0]
    # Client origin sits inside the frame: ≥ 8 px from the screen's left
    # edge and ≥ 32 px from its top so the decorations remain visible.
    assert x >= 1920 + 8
    assert y >= 32


def test_maximized_window_keeps_geometry_but_refits(qapp):
    win = _StubMainWindow(maximized=True)
    _settle(win)
    win._screen = _FakeScreen(QRect(_SMALLER))
    win._adapt_to_current_screen()   # noqa: SLF001
    assert win.set_geometry_calls == []
    qapp.processEvents()
    assert win.viewer.fit_calls == 1


def test_no_deep_zoom_skips_refit(qapp):
    win = _StubMainWindow()
    win.viewer = _FakeViewer(deep=False)
    _settle(win)
    win._screen = _FakeScreen(QRect(_SMALLER))
    win._adapt_to_current_screen()   # noqa: SLF001
    qapp.processEvents()
    assert win.viewer.fit_calls == 0
    # The window itself still adapts — only the image fit is skipped.
    assert len(win.set_geometry_calls) == 1


def test_tile_grid_mode_skips_refit(qapp):
    win = _StubMainWindow()
    win.viewer = _FakeViewer(grid=True)
    _settle(win)
    win._screen = _FakeScreen(QRect(_SMALLER))
    win._adapt_to_current_screen()   # noqa: SLF001
    qapp.processEvents()
    assert win.viewer.fit_calls == 0


def test_deep_zoom_cleared_before_deferred_fit_is_safe(qapp):
    # The image can be closed between scheduling and the 0 ms timer firing;
    # the deferred fit must notice and do nothing.
    win = _StubMainWindow()
    _settle(win)
    win._screen = _FakeScreen(QRect(_SMALLER))
    win._adapt_to_current_screen()   # noqa: SLF001
    win.viewer.deep_zoom = None
    qapp.processEvents()
    assert win.viewer.fit_calls == 0


class _NoScreenWindow(_StubMainWindow):
    """Window whose ``screen()`` reports None (mid-teardown / unplugged)."""

    def screen(self):
        return None


def test_missing_screen_is_safe(qapp):
    win = _NoScreenWindow()
    win._adapt_to_current_screen()   # noqa: SLF001
    assert win._last_screen_avail is None   # noqa: SLF001
    assert win.set_geometry_calls == []
