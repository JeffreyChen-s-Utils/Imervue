"""CLI worker sizing and cancellation before joining active encoders."""
from __future__ import annotations

import os
from threading import Event


def _resolve_workers(jobs: int, count: int) -> int:
    """Worker count: 1 = inline; 0 = auto; clamp to the number of files."""
    if jobs == 1 or count <= 1:
        return 1
    workers = (os.cpu_count() or 1) if jobs <= 0 else jobs
    return max(1, min(workers, count))


def _run_outputs(pairs, work, workers: int, cancelled: Event) -> bool:
    """Set cancellation before joining active encoders after Ctrl+C."""
    from concurrent.futures import ThreadPoolExecutor
    if workers == 1:
        try:
            for pair in pairs:
                work(pair)
        except KeyboardInterrupt:
            cancelled.set()
            return True
        return False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, pair) for pair in pairs]
        try:
            for future in futures:
                future.result()
        except KeyboardInterrupt:
            cancelled.set()
            for future in futures:
                future.cancel()
            return True
    return False
