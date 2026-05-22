"""Worker-pool sizing policy for the image viewer.

The viewer historically shared one ``QThreadPool.globalInstance()``
sized at ``min(cpus * 2, 16)`` for every workload. The catch:
thumbnail-loading bursts (folder open → N parallel JPEG decodes)
end up competing with the current image's deep-zoom worker AND
with the ±N prefetch workers, so the user-visible deep-zoom can
queue behind 30 thumbnails on a 4-core laptop.

The fix is per-workload pools sized so each kind has its own
guaranteed budget:

* **thumbnail** — many cheap CPU-light decodes. Scales with cores
  (capped to keep memory pressure bounded on big folders).
* **deepzoom**  — one or two at a time; user-visible.
* **prefetch**  — background; must not starve the foreground.

This module is the pure-Python sizing policy. The actual
``QThreadPool`` objects live on the viewer.
"""
from __future__ import annotations

MIN_THUMBNAIL_WORKERS: int = 2
"""Floor for the thumbnail pool. A single-thread machine still
needs to make progress on a folder of thumbnails; 2 lets disk
read and JPEG decode overlap."""

MAX_THUMBNAIL_WORKERS: int = 8
"""Ceiling for the thumbnail pool. Past 8 the extra parallelism
doesn't help on typical SSD throughput and memory pressure
ramps up — each in-flight thumbnail decode holds a copy of the
decoded buffer plus its source bytes."""

MIN_DEEPZOOM_WORKERS: int = 1
"""Floor for the deep-zoom pool. We only ever cancel + restart
the *current* image's worker, so one is the meaningful minimum;
two lets a fresh switch start decoding before the previous abort
returns."""

MAX_DEEPZOOM_WORKERS: int = 4
"""Ceiling. Each deep-zoom decode allocates the full RGBA buffer
+ pyramid; piling many in parallel risks OOM on the largest
RAWs."""

MIN_PREFETCH_WORKERS: int = 1
MAX_PREFETCH_WORKERS: int = 2
"""Prefetch is "spare cycles" by definition — never more than 2
even on a many-core box, so it can't starve the foreground."""


def worker_pool_sizes(cpu_count: int) -> dict[str, int]:
    """Decide per-workload pool sizes for ``cpu_count`` cores.

    Returns ``{"thumbnail": int, "deepzoom": int, "prefetch": int}``
    where each value sits inside the module's documented
    ``MIN_*`` / ``MAX_*`` floors and ceilings.

    The policy is intentionally conservative: a 32-core workstation
    doesn't get 32 thumbnail workers because the I/O backend isn't
    that fast and the extra parallelism mostly buys L3 thrashing.

    Robust to garbage input (``cpu_count <= 0`` → treat as 1) so the
    caller can pass ``os.cpu_count() or 1`` without a guard.
    """
    cores = max(1, int(cpu_count))
    return {
        "thumbnail": _clamp(cores, MIN_THUMBNAIL_WORKERS, MAX_THUMBNAIL_WORKERS),
        "deepzoom": _clamp(
            max(1, cores // 2), MIN_DEEPZOOM_WORKERS, MAX_DEEPZOOM_WORKERS,
        ),
        "prefetch": _clamp(
            max(1, cores // 4), MIN_PREFETCH_WORKERS, MAX_PREFETCH_WORKERS,
        ),
    }


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


# ---------------------------------------------------------------
# Per-runnable priority — used by QThreadPool.start(runnable, priority)
# ---------------------------------------------------------------

MAX_PRIORITY: int = 10
"""Reserved for the current image / user-visible items. Higher
than any neighbour distance can reach."""

MIN_PRIORITY: int = -10
"""Floor for very far-away items. Stops the priority from going
unboundedly negative on a 10 000-image folder."""


def priority_for_distance(distance: int) -> int:
    """Convert "how many images away from the current view" to a
    QThreadPool priority hint.

    Distance 0 (the current image itself) gets :data:`MAX_PRIORITY`;
    each step further drops priority by 1, clamped to
    :data:`MIN_PRIORITY` so the planner never runs negative
    overflow risk.

    Negative distances (looking back) and positive distances
    (looking ahead) yield the same priority — direction is the
    prefetch policy's job (see :mod:`prefetch`); priority here
    only cares about how *soon* the user might need the image."""
    abs_distance = abs(int(distance))
    if abs_distance == 0:
        return MAX_PRIORITY
    return max(MIN_PRIORITY, MAX_PRIORITY - abs_distance)
