"""Tests for the deep-zoom "adapt the view when the canvas changes" path.

The bug these cover: after switching to another main tab, or after the window
landed on a different monitor, the image could still open at a size that
doesn't suit the canvas. Two causes:

* a single ``singleShot(0)`` fit can land while Qt is still relaying out (a
  stacked page only gets its real geometry after the queued layout request),
  so the fit anchored to an intermediate size;
* a screen change that arrived while the viewer sat behind another tab was
  computed against the hidden page's stale pre-hide geometry.

``GPUImageView`` is a ``QOpenGLWidget``; these tests never construct one —
the methods are called unbound on light duck-typed fakes, so no GL surface is
created and the file runs on headless CI.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.gpu_image_view import (
    _LAYOUT_SETTLE_RETRIES, GPUImageView,
)

_START_SIZE = (800, 600)
_SETTLED_SIZE = (1280, 720)


class _FakeView:
    """Minimal attribute surface the canvas-adapt methods touch."""

    _adapt_view_to_canvas = GPUImageView._adapt_view_to_canvas
    _schedule_canvas_adapt = GPUImageView._schedule_canvas_adapt
    _on_view_shown = GPUImageView._on_view_shown
    request_screen_refit = GPUImageView.request_screen_refit

    def __init__(self, *, deep: bool = True, grid: bool = False,
                 locked: bool = False, visible: bool = True):
        self.deep_zoom = object() if deep else None
        self.tile_grid_mode = grid
        self._user_locked_view = locked
        self._visible = visible
        self._last_resize_size = _START_SIZE
        self.fit_calls = 0
        self.clamp_calls = 0
        self.update_calls = 0
        self._browse = SimpleNamespace(clamp_pan=self._clamp_pan)

    def isVisible(self) -> bool:  # noqa: N802 — Qt naming
        return self._visible

    def _clamp_pan(self) -> None:
        self.clamp_calls += 1

    def _fit_to_window(self) -> None:
        self.fit_calls += 1

    def update(self) -> None:
        self.update_calls += 1


class _SettlingView(_FakeView):
    """Canvas that reaches its final size one event-loop turn after the fit."""

    def _fit_to_window(self) -> None:
        super()._fit_to_window()
        self._last_resize_size = _SETTLED_SIZE


class _NeverSettlingView(_FakeView):
    """Pathological canvas whose size changes on every single turn."""

    def _fit_to_window(self) -> None:
        super()._fit_to_window()
        width, height = self._last_resize_size
        self._last_resize_size = (width + 1, height + 1)


# --- _adapt_view_to_canvas: fit vs clamp vs nothing --------------------


def test_adapt_fits_an_unlocked_whole_image_view():
    view = _FakeView()
    view._adapt_view_to_canvas()
    assert (view.fit_calls, view.clamp_calls) == (1, 0)


def test_adapt_clamps_instead_of_destroying_a_user_zoom():
    # The deliberate zoom-in survives, but its pan is re-clamped so the
    # smaller viewport can't leave the image stranded off-canvas.
    view = _FakeView(locked=True)
    view._adapt_view_to_canvas()
    assert (view.fit_calls, view.clamp_calls) == (0, 1)
    assert view._user_locked_view is True


def test_adapt_without_deep_zoom_is_a_noop():
    view = _FakeView(deep=False)
    view._adapt_view_to_canvas()
    assert (view.fit_calls, view.clamp_calls) == (0, 0)


def test_adapt_in_tile_grid_mode_is_a_noop():
    view = _FakeView(grid=True)
    view._adapt_view_to_canvas()
    assert (view.fit_calls, view.clamp_calls) == (0, 0)


# --- _schedule_canvas_adapt: deferral + bounded settle retry -----------


def test_scheduled_adapt_runs_after_the_event_loop_turns(qapp):
    view = _FakeView()
    view._schedule_canvas_adapt()
    assert view.fit_calls == 0            # deferred, not immediate
    qapp.processEvents()
    assert (view.fit_calls, view.update_calls) == (1, 1)


def test_scheduled_adapt_refits_while_the_canvas_is_still_moving(qapp):
    # The first fit used the intermediate size; because the canvas then
    # changed, a second pass runs against the settled size. That second fit
    # is the one that lands the image at the right size.
    view = _SettlingView()
    view._schedule_canvas_adapt()
    for _ in range(_LAYOUT_SETTLE_RETRIES + 2):
        qapp.processEvents()
    assert view.fit_calls == 2
    assert view._last_resize_size == _SETTLED_SIZE


def test_scheduled_adapt_does_not_rearm_on_a_stable_canvas(qapp):
    view = _FakeView()
    view._schedule_canvas_adapt()
    for _ in range(_LAYOUT_SETTLE_RETRIES + 2):
        qapp.processEvents()
    assert view.fit_calls == 1


def test_scheduled_adapt_retries_are_bounded(qapp):
    # A canvas that never stops moving must not re-arm the timer forever.
    view = _NeverSettlingView()
    view._schedule_canvas_adapt()
    for _ in range(_LAYOUT_SETTLE_RETRIES + 5):
        qapp.processEvents()
    assert view.fit_calls == _LAYOUT_SETTLE_RETRIES + 1


def test_scheduled_adapt_after_the_image_closed_is_safe(qapp):
    view = _FakeView()
    view._schedule_canvas_adapt()
    view.deep_zoom = None                 # image closed before the timer fires
    qapp.processEvents()
    assert view.fit_calls == 0


# --- request_screen_refit: visible now vs parked until shown ----------


def test_screen_refit_on_a_visible_viewer_overrides_the_user_zoom(qapp):
    view = _FakeView(locked=True)
    view.request_screen_refit()
    assert view._user_locked_view is False
    qapp.processEvents()
    assert view.fit_calls == 1


def test_screen_refit_on_a_hidden_viewer_is_skipped_not_mis_computed(qapp):
    # A hidden stacked page keeps its pre-hide geometry, so fitting now would
    # use the OLD screen's size. Coming back into view re-fits anyway.
    view = _FakeView(visible=False)
    view.request_screen_refit()
    qapp.processEvents()
    assert view.fit_calls == 0


def test_screen_refit_without_deep_zoom_is_a_noop(qapp):
    view = _FakeView(deep=False)
    view.request_screen_refit()
    qapp.processEvents()
    assert view.fit_calls == 0


def test_screen_refit_in_tile_grid_mode_is_a_noop(qapp):
    view = _FakeView(grid=True)
    view.request_screen_refit()
    qapp.processEvents()
    assert view.fit_calls == 0


# --- _on_view_shown: the tab-switch-back path -------------------------


def test_show_always_returns_to_the_whole_image(qapp):
    # Coming back from another tab / view mode: the canvas may be any size
    # now, so a zoom that suited the canvas it was left on is dropped.
    view = _FakeView(locked=True)
    view._on_view_shown()
    assert view._user_locked_view is False
    qapp.processEvents()
    assert (view.fit_calls, view.clamp_calls) == (1, 0)


def test_show_refits_an_unlocked_view(qapp):
    view = _FakeView()
    view._on_view_shown()
    qapp.processEvents()
    assert view.fit_calls == 1


def test_show_unlocks_immediately_so_a_loading_image_can_relock(qapp):
    # The unlock is synchronous but the fit is deferred: an image that lands
    # in between restores its own remembered zoom-in and re-locks, and the
    # deferred pass must then clamp it instead of fitting it away.
    view = _FakeView(locked=True)
    view._on_view_shown()
    view._user_locked_view = True          # image load restored a zoom-in
    qapp.processEvents()
    assert (view.fit_calls, view.clamp_calls) == (0, 1)


def test_show_without_a_deep_zoom_image_schedules_nothing(qapp):
    view = _FakeView(deep=False, locked=True)
    view._on_view_shown()
    qapp.processEvents()
    assert view.fit_calls == 0
    assert view._user_locked_view is True   # untouched; no image to fit
