"""Sub-frame signal-coalescing helper for thread-callback bursts.

When a folder open kicks off N thumbnail-load workers, each finished
callback runs on the GUI thread and (a) updates the progress bar,
(b) updates the status label, (c) requests a repaint. ``QWidget.update``
already merges paint requests internally, but ``set_status`` and
``show_progress`` go directly to the status bar and re-layout the
``QStatusBar`` every call. On a folder with 2000 thumbnails that's
2000 layout passes in a second — visible in profilers as the dominant
GUI-thread cost during folder load.

The coalescer pattern:

1. Worker callback calls :meth:`schedule`.
2. The first schedule arms a ``QTimer.singleShot(interval_ms, _flush)``.
3. Subsequent schedules within the window are silent — the pending
   timer will flush once.
4. :meth:`_flush` emits :attr:`flush_requested` on the GUI thread;
   subscribers do the (expensive) update once.

At 16 ms intervals this caps the GUI-side work at 60 Hz — same cadence
as the paint thread, so no visible lag from the user's perspective.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

DEFAULT_INTERVAL_MS: int = 16
"""One frame at 60 Hz. Updates land in time for the next paint, the
GUI thread stays under one bursty update per frame, and per-worker
cost drops to a trivial flag check."""


class SignalCoalescer(QObject):
    """Sub-frame coalescer. Wire :attr:`flush_requested` to the
    expensive update, call :meth:`schedule` from anywhere — the
    first call within each ``interval_ms`` window arms a delayed
    flush, the rest are no-ops.

    The coalescer is QObject-typed because the GUI-thread callback
    needs Qt event-loop dispatch (QTimer.singleShot fires on the
    receiver's thread); subscribers connect via the standard
    signal API.
    """

    flush_requested = Signal()

    def __init__(
        self,
        interval_ms: int = DEFAULT_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._interval_ms = max(1, int(interval_ms))
        self._pending: bool = False

    def schedule(self) -> None:
        """Request a flush. Idempotent within one window — N
        calls between two timer fires produce one emit."""
        if self._pending:
            return
        self._pending = True
        QTimer.singleShot(self._interval_ms, self._flush)

    def is_pending(self) -> bool:
        """``True`` when a flush is scheduled but hasn't fired
        yet. Useful for tests and for the rare caller that wants
        to early-out on already-pending state."""
        return self._pending

    def force_flush(self) -> None:
        """Bypass the timer — flush right now if anything is
        scheduled, otherwise no-op. Used at the end of a known
        burst (e.g. last thumbnail loaded) so the user sees the
        final state immediately instead of after the 16 ms
        window elapses."""
        if not self._pending:
            return
        self._pending = False
        self.flush_requested.emit()

    def _flush(self) -> None:
        # The timer might fire after ``force_flush`` cleared the
        # pending flag; in that case the flush has already
        # happened and we skip a duplicate emit.
        if not self._pending:
            return
        self._pending = False
        self.flush_requested.emit()
