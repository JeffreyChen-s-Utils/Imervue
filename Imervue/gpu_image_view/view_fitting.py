"""Fitting the deep-zoom view to the canvas.

Fit to window / width / height, the initial view of a freshly loaded image,
and re-fitting while the layout or the screen settles: a resize, a move to a
monitor with a different scale, or a window that is still growing after the
image arrived. The settle loops poll on a real interval (``settle_poll``)
because a ``singleShot(0)`` chain cannot span an OS window change.
``GPUImageView`` mixes these methods in.
"""
from __future__ import annotations

import logging

from Imervue.system.qt_timers import call_later


logger = logging.getLogger("Imervue.gpu_image_view")
# How many extra event-loop turns a deferred fit may wait for the canvas size
# to stop changing (tab relayout, dock settling, a move to another monitor).
_LAYOUT_SETTLE_RETRIES = 3
# Screen-change settle watch: a cross-monitor move takes hundreds of ms (OS
# re-maximise + compositor animation + the new screen's resizeGL), far longer
# than the singleShot(0) layout-drain chain above can span.
_SCREEN_SETTLE_INTERVAL_MS = 60
_SCREEN_SETTLE_RETRIES = 8
# Image-load settle watch: shorter than the screen one — the host frame draining
# a queued layout settles far quicker than an OS-level monitor change — but
# still on a real interval, which the singleShot(0) chain is not.
_LOAD_SETTLE_INTERVAL_MS = 60
_LOAD_SETTLE_RETRIES = 5


class ViewFittingMixin:
    """Fit and settle-refit of the viewer."""

    def _adapt_view_to_canvas(self) -> None:
        """Re-fit or re-clamp the deep-zoom view for the current canvas size.

        Single entry point for every "the drawing area changed" trigger
        (``resizeGL``, the deferred post-show settle, a screen change), so all
        three agree on what happens to a whole-image view versus a deliberate
        zoom-in. See :func:`fit_view.refit_action` for the decision itself.
        """
        from Imervue.gpu_image_view.fit_view import (
            REFIT_CLAMP, REFIT_FIT, canvas_size, refit_action,
        )
        action = refit_action(self)
        logger.debug("adapt-view: action=%s canvas=%s locked=%s zoom=%.4f",
                     action, canvas_size(self), self._user_locked_view, self.zoom)
        if action == REFIT_FIT:
            self._fit_to_window()
        elif action == REFIT_CLAMP:
            self._browse.clamp_pan()

    def _schedule_canvas_adapt(self, retries: int = _LAYOUT_SETTLE_RETRIES) -> None:
        """Adapt the view to the canvas once Qt's layout queue has drained.

        A single ``singleShot(0)`` can still land mid-relayout: a stacked page
        only receives its real geometry after the queued layout request is
        processed. Fitting against that intermediate size is exactly the "opens
        at the wrong size" bug, so re-arm (bounded) while the canvas is still
        moving — the last fit then uses the final size.

        This chain drains Qt's *queued layout*, nothing slower: every hop is a
        ``singleShot(0)``, so the whole retry budget is spent within a few
        event-loop turns. A screen change needs
        :meth:`_schedule_screen_settle_adapt` instead.
        """
        from Imervue.gpu_image_view.fit_view import canvas_size
        before = canvas_size(self)

        def _run() -> None:
            self._adapt_view_to_canvas()
            self.update()
            if retries > 0 and canvas_size(self) != before:
                self._schedule_canvas_adapt(retries - 1)

        call_later(0, self, _run)

    def _schedule_screen_settle_adapt(
        self, retries: int = _SCREEN_SETTLE_RETRIES,
        interval_ms: int = _SCREEN_SETTLE_INTERVAL_MS,
    ) -> None:
        """Keep re-adapting the view for ~half a second after a screen change.

        :meth:`_schedule_canvas_adapt` chains ``singleShot(0)`` hops, so its
        entire retry budget elapses in a few event-loop turns — microseconds.
        Landing on another monitor takes orders of magnitude longer: the OS
        re-maximises the window, the compositor animates the move, and the new
        screen's ``resizeGL`` arrives well after those hops are done. The chain
        therefore always sees an unchanged canvas, stops immediately, and
        leaves the fit anchored to the screen the window just left.

        Polling on a real interval spans the actual settle instead, so the last
        pass runs against the final canvas whichever way the race went. Each
        pass is pure math plus a repaint request, and
        :func:`fit_view.refit_action` still honours a zoom the user takes
        during the window, so the extra passes cost little and can't fight the
        user.

        Two guards keep the watch from writing a fit nobody asked for. A newer
        screen change supersedes this one (dragging across three monitors must
        not leave three chains fitting over each other), and a viewer hidden
        mid-watch stops rather than measuring a background page's stale
        pre-hide geometry — :meth:`_on_view_shown` re-fits on return anyway.
        """
        generation = self._screen_settle_generation
        self._poll_settle(
            self._adapt_and_update,
            lambda: generation == self._screen_settle_generation,
            retries, interval_ms,
        )

    def _schedule_load_settle_refit(
        self, retries: int = _LOAD_SETTLE_RETRIES,
        interval_ms: int = _LOAD_SETTLE_INTERVAL_MS,
    ) -> None:
        """Keep confirming a freshly-displayed image's fit on a real interval.

        :meth:`_schedule_settle_refit` re-arms through ``singleShot(0)``, so its
        whole budget elapses in a few event-loop turns. When the canvas settles
        on a slower timescale — the window still landing on another monitor, a
        dock or splitter animating, the host frame draining a queued layout —
        that chain dies before the final size exists and the image keeps the
        size it was fitted to.

        Paging on does not rescue it: the next image runs its own fit against
        the same unsettled canvas and lands on the same wrong size, so the error
        looks like it is being carried over from image to image when in fact
        each one re-derives it. This watch spans the settle so the last pass
        runs against the final canvas.

        Tagged with the deep-zoom request id like the fast chain, so paging on
        retires it instead of letting it clobber the incoming image.
        """
        request_id = self._deep_zoom_request_id
        self._poll_settle(
            lambda: self._settle_refit(request_id),
            lambda: request_id == self._deep_zoom_request_id,
            retries, interval_ms,
        )

    def _adapt_and_update(self) -> None:
        """One screen-settle pass: re-adapt the view, then request a repaint."""
        self._adapt_view_to_canvas()
        self.update()

    def _poll_settle(self, step, still_current, retries: int,
                     interval_ms: int) -> None:
        """Run *step* every *interval_ms* while *still_current*, bounded by
        *retries*.

        Thin wrapper over :func:`gui.settle_poll.poll_settle` (see there for why
        a real interval is required) that adds the one condition every viewer
        watch shares: a hidden viewer drops out, because measuring a background
        page's stale pre-hide geometry is exactly the mistake these watches
        exist to prevent. *still_current* carries the caller's own supersession
        test — the screen-settle generation or the deep-zoom request id.
        """
        from Imervue.gui.settle_poll import poll_settle
        poll_settle(
            step,
            lambda: still_current() and self.isVisible(),
            retries, interval_ms, owner=self,
        )

    def request_screen_refit(self) -> None:
        """Force a whole-image re-fit after the window changed screen.

        Landing on another monitor means "show me the whole image at THIS
        screen's size", so this deliberately overrides a user zoom-in. A
        hidden viewer is skipped rather than fitted against a stale size: a
        background stacked page keeps its pre-hide geometry, and coming back
        into view re-fits the whole image anyway (see :meth:`_on_view_shown`).

        The cached ``resizeGL`` size is dropped BEFORE the nothing-to-re-fit
        early return below. Opening a folder lands on the tile wall, where
        ``refit_action`` is ``REFIT_NONE``, so the return would otherwise leave
        ``_last_resize_size`` describing the screen the window just left — and
        :func:`fit_view.canvas_size` prefers that cache over live geometry.
        Entering deep zoom before the new screen's ``resizeGL`` has been
        delivered then fits the image to the OLD monitor ("it opens at the
        other screen's size"). Invalidating here makes that fit read live
        geometry instead; the next ``resizeGL`` repopulates the cache.
        """
        from Imervue.gpu_image_view.fit_view import (
            REFIT_NONE, invalidate_canvas_size, refit_action,
        )
        if not self.isVisible():
            return
        invalidate_canvas_size(self)
        if refit_action(self) == REFIT_NONE:
            return
        self._user_locked_view = False
        # Two chains: the first drains Qt's queued layout immediately, the
        # second keeps watching while the window actually settles on the new
        # monitor (see :meth:`_schedule_screen_settle_adapt` for why the first
        # cannot cover that on its own). Bumping the generation retires any
        # watch still running from a previous screen change.
        self._screen_settle_generation += 1
        self._schedule_canvas_adapt()
        self._schedule_screen_settle_adapt()

    def _fit_zoom(self) -> float:
        """Zoom level that fits the whole image in the canvas (capped at 1.0)."""
        from Imervue.gpu_image_view.fit_view import fit_zoom
        return fit_zoom(self)

    def _should_refit_on_load(self) -> bool:
        """Content-fit on display unless the user has a genuine zoom-in saved
        for this image (see :func:`fit_view.should_refit_on_load`)."""
        from Imervue.gpu_image_view.fit_view import should_refit_on_load
        return should_refit_on_load(
            self._loading_was_remembered, self, self._loading_remembered_dims,
            was_locked=self._loading_was_locked,
        )

    def _fit_to_window(self):
        """Centre + fit the image. Called by the input controller and loaders."""
        from Imervue.gpu_image_view.fit_view import fit_to_window
        fit_to_window(self)

    def _apply_initial_view(self) -> None:
        """Set the zoom/offset for a freshly displayed full-res image.

        A low-res progressive preview fits itself into ``view.zoom`` while the
        full image loads, so by the time the full image lands ``view.zoom`` is
        the preview's placeholder fit — not this image's remembered view. Re-
        restore the image's own saved view first, so the fit-or-keep decision
        and the kept zoom use the right values instead of the preview's fit.
        A fresh image restores to defaults and then fits; a whole-image view
        re-fits to the current canvas; a genuine zoom-in is preserved.
        """
        path = self._current_path()
        if path is None:
            return
        self._restore_view_state(path)
        if self._should_refit_on_load():
            self._fit_to_window()
            # Two chains, for the same reason request_screen_refit arms two:
            # the first drains Qt's queued layout immediately, the second spans
            # a canvas that settles on a slower timescale. Without the second,
            # paging on before the correction lands just re-derives the same
            # wrong fit from the same unsettled canvas.
            self._schedule_settle_refit()
            self._schedule_load_settle_refit()
        else:
            # Keeping a genuine remembered zoom-in: clamp its pan to the current
            # (maybe smaller / different-DPI) canvas so it can't open off-screen,
            # and lock the view so the next resize's settle re-fit doesn't snap
            # the deliberate zoom away.
            self._browse.clamp_pan()
            self._user_locked_view = True

    def _schedule_settle_refit(self, retries: int = _LAYOUT_SETTLE_RETRIES) -> None:
        """Queue a confirmation re-fit for the next event-loop turn.

        Tagged with the current deep-zoom request id so a fit queued for one
        image can't fire after a quick keyboard switch to the next — which
        would otherwise clobber the incoming image's remembered zoom-in.

        Re-armed (bounded) while the canvas is still moving, for the same
        reason :meth:`_schedule_canvas_adapt` retries: a single ``singleShot(0)``
        can land mid-relayout — the window still settling on a new monitor, a
        dock or splitter draining its queued layout request — and fitting
        against that intermediate size is exactly the "opens at the wrong size"
        bug. The last fit then uses the final size.
        """
        from Imervue.gpu_image_view.fit_view import canvas_size
        request_id = self._deep_zoom_request_id
        before = canvas_size(self)

        def _run() -> None:
            self._settle_refit(request_id)
            if (retries > 0 and request_id == self._deep_zoom_request_id
                    and canvas_size(self) != before):
                self._schedule_settle_refit(retries - 1)

        call_later(0, self, _run)

    def _settle_refit(self, request_id: int) -> None:
        """Confirm the fit after the event loop settles the deep-zoom layout.

        Entering deep zoom from the tile wall makes the horizontal filmstrip
        band appear and can realise the live canvas size a beat after the
        synchronous fit, so the image could open at the wrong size / overlap
        the strip. Re-fitting once here — only while the view is unlocked and
        no newer image has been requested since — lands it in the correct
        content area. A no-op when the first fit was already correct."""
        if request_id != self._deep_zoom_request_id:
            return  # a newer navigation superseded this fit
        from Imervue.gpu_image_view.fit_view import should_settle_refit
        if should_settle_refit(self):
            self._fit_to_window()

    def _fit_to_width(self):
        """Fit image width — external contract (key dispatcher)."""
        from Imervue.gpu_image_view.fit_view import fit_to_width
        fit_to_width(self)

    def _fit_to_height(self):
        """Fit image height — external contract (key dispatcher)."""
        from Imervue.gpu_image_view.fit_view import fit_to_height
        fit_to_height(self)
