"""Pure helpers for the image-prefetch window around the current view.

When the user is browsing a folder, the viewer warms a small cache of
neighbouring images so the next arrow-key press lands instantly. The
*size* of that cache and which neighbours it picks aren't constants —
they depend on how the user's been navigating.

This module is the policy in one place, kept Qt-free / IO-free so the
heuristic is unit-testable:

* :func:`compute_prefetch_targets` picks indices around ``current_index``
  given separate ahead / behind ranges.
* :func:`infer_recent_direction` looks at the last few index changes
  and decides whether the user is moving forward, backward, or has no
  clear direction.
* :func:`range_for_direction` maps that direction to an asymmetric
  ``(ahead, behind)`` tuple — bias the cache toward where the user is
  actually going.

The Qt :class:`GPUImageView` records each index change and threads the
inferred direction through to the helpers; everything below the GL
fence stays pure.
"""
from __future__ import annotations

from collections import deque

DEFAULT_RANGE: int = 3
"""Symmetric fallback when navigation direction is unknown. Same as
the original constant the viewer shipped with; preserves behaviour
for users who jump around the folder."""

DIRECTIONAL_RANGE_AHEAD: int = 5
"""Window size in the direction of travel. Larger than the symmetric
default — a user pressing → repeatedly will burn through 3 images
before the cache catches up; 5 hides the LRU eviction latency."""

DIRECTIONAL_RANGE_BEHIND: int = 1
"""Window size opposite the direction of travel. One image is enough
to make "oh wait, go back one" snappy without spending budget on
images the user is clearly leaving."""

_DIRECTION_HISTORY_DEPTH: int = 5
"""How many recent navigations to look at when inferring direction.
Long enough to ignore one stray reverse-step; short enough to react
quickly when the user pivots."""

_DIRECTION_THRESHOLD: float = 0.75
"""Fraction of recent steps that must agree to call the direction
'forward' or 'backward'. Below this the navigation looks scattered
and we fall back to the symmetric window."""


def compute_prefetch_targets(
    current_index: int,
    total: int,
    *,
    range_ahead: int = DEFAULT_RANGE,
    range_behind: int = DEFAULT_RANGE,
) -> list[int]:
    """Return the indices to prefetch around ``current_index``.

    ``range_ahead`` and ``range_behind`` are independent so callers can
    bias toward the direction of travel. The current index is *not*
    included — the viewer already has it loaded. Out-of-range indices
    are silently clipped so a small folder doesn't trigger negative or
    past-the-end lookups.

    Returned in order from closest to farthest so the worker pool
    picks up "neighbouring images" before "5 steps out" — a user that
    keeps pressing the same arrow gets the immediate next image
    finished first.
    """
    if total <= 0 or current_index < 0 or current_index >= total:
        return []
    range_ahead = max(0, int(range_ahead))
    range_behind = max(0, int(range_behind))
    out: list[int] = []
    # Interleave ahead / behind by distance so distance-1 candidates
    # land before distance-2 candidates regardless of which side they
    # came from.
    for distance in range(1, max(range_ahead, range_behind) + 1):
        if distance <= range_ahead:
            forward = current_index + distance
            if forward < total:
                out.append(forward)
        if distance <= range_behind:
            backward = current_index - distance
            if backward >= 0:
                out.append(backward)
    return out


def infer_recent_direction(history: list[int]) -> int:
    """Read a list of *index deltas* (``+1`` for next, ``-1`` for
    previous, anything else for jumps) and return:

    * ``+1`` when most recent moves agree on forward,
    * ``-1`` when they agree on backward,
    * ``0`` when scattered (jumps / mixed direction).

    ``history`` is treated as oldest-to-newest; only the last
    :data:`_DIRECTION_HISTORY_DEPTH` entries count, so callers can
    keep a longer log without changing the heuristic.
    """
    if not history:
        return 0
    window = history[-_DIRECTION_HISTORY_DEPTH:]
    if not window:
        return 0
    forward = sum(1 for d in window if d == 1)
    backward = sum(1 for d in window if d == -1)
    counted = forward + backward
    if counted == 0:
        return 0
    if forward / counted >= _DIRECTION_THRESHOLD:
        return 1
    if backward / counted >= _DIRECTION_THRESHOLD:
        return -1
    return 0


def range_for_direction(direction: int) -> tuple[int, int]:
    """Map ``infer_recent_direction``'s output to a
    ``(range_ahead, range_behind)`` tuple.

    Forward → big ahead, small behind. Backward → mirror. Scattered
    → symmetric :data:`DEFAULT_RANGE` on both sides so the user who
    pivots gets the same baseline they had before this heuristic
    existed."""
    if direction == 1:
        return (DIRECTIONAL_RANGE_AHEAD, DIRECTIONAL_RANGE_BEHIND)
    if direction == -1:
        return (DIRECTIONAL_RANGE_BEHIND, DIRECTIONAL_RANGE_AHEAD)
    return (DEFAULT_RANGE, DEFAULT_RANGE)


class NavigationDirectionTracker:
    """Bookkeeping the viewer keeps so it can call
    :func:`infer_recent_direction` cheaply on every navigation.

    Records the *delta* between consecutive ``current_index`` values
    in a bounded deque; the viewer pushes :meth:`record` from its
    index-change hook and reads :meth:`direction` when computing the
    next prefetch window.
    """

    def __init__(self) -> None:
        self._deltas: deque[int] = deque(maxlen=_DIRECTION_HISTORY_DEPTH)
        self._last_index: int | None = None

    def record(self, new_index: int) -> None:
        """Note a new ``current_index``. The first call seeds the
        tracker without producing a direction; subsequent calls
        push the signed delta into the history buffer."""
        if self._last_index is not None:
            delta = new_index - self._last_index
            # Normalise so a multi-step jump (skip ahead 10) doesn't
            # poison the deque with weight-10 signals — only ±1
            # contributes to the direction vote.
            if delta == 1:
                self._deltas.append(1)
            elif delta == -1:
                self._deltas.append(-1)
            else:
                self._deltas.append(0)
        self._last_index = new_index

    def direction(self) -> int:
        """Current best guess. ``0`` until at least one navigation has
        been recorded with a clear direction."""
        return infer_recent_direction(list(self._deltas))

    def reset(self) -> None:
        """Forget history — call when the folder changes so the new
        folder gets a fresh symmetric window."""
        self._deltas.clear()
        self._last_index = None
