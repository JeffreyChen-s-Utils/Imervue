"""Bounded re-run of a layout step while the window is still settling.

A ``QTimer.singleShot(0, …)`` chain only drains Qt's *queued layout*: every hop
lands on the next event-loop turn, so the whole retry budget elapses within
microseconds. Anything slower finishes long after such a chain has given up —
a window landing on another monitor (the OS re-maximises it and the compositor
animates the move), a host frame realising a stacked page's geometry, a
splitter settling after its panes are rebuilt. A one-shot layout computed
before then is locked in wrong, and the chain that was supposed to correct it
already stopped because the size "looked stable".

:func:`poll_settle` spans that settle instead by polling on a REAL interval,
and deliberately keeps going while the measurement looks unchanged — the
change is still in flight, which is exactly what it is waiting for.

Callers supply their own supersession test so a newer trigger retires an
in-flight watch rather than letting several chains fight over the same widget.
"""

from __future__ import annotations

from collections.abc import Callable

# Long enough that a pass costs nothing, short enough that the correction is
# not perceived as a second layout jump.
DEFAULT_INTERVAL_MS = 60


def poll_settle(
    step: Callable[[], None],
    still_current: Callable[[], bool],
    retries: int,
    interval_ms: int = DEFAULT_INTERVAL_MS,
) -> None:
    """Run *step* every *interval_ms* while *still_current*, at most *retries* times.

    Each pass re-arms the next one, so the total watch spans
    ``retries * interval_ms``. A non-positive *retries* schedules nothing, and
    the first pass where *still_current* returns ``False`` ends the chain
    without running *step* — that is how a superseded or torn-down target
    drops out instead of writing a layout nobody asked for.
    """
    from PySide6.QtCore import QTimer
    if retries <= 0:
        return

    def _run() -> None:
        if not still_current():
            return
        step()
        poll_settle(step, still_current, retries - 1, interval_ms)

    QTimer.singleShot(interval_ms, _run)
