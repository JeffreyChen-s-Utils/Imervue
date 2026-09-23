"""``best_effort``: run a step whose failure must not stop the caller, and log it.

Shutdown, teardown and cleanup code runs a chain of independent steps where
one failing (a signal already disconnected, a GL context already gone) must
not skip the rest. ``contextlib.suppress(Exception)`` did that silently, so a
real bug in such a step left no trace. ``best_effort`` swallows the same
exceptions but logs each one with its traceback, naming the step.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

_logger = logging.getLogger("Imervue.best_effort")


@contextmanager
def best_effort(step: str, logger: logging.Logger | None = None) -> Iterator[None]:
    """Run the ``with`` block; on any ``Exception`` log a warning with the traceback and go on.

    ``step`` names what was being attempted; ``logger`` defaults to
    ``Imervue.best_effort``. ``BaseException`` (``KeyboardInterrupt``,
    ``SystemExit``) still propagates.
    """
    try:
        yield
    except Exception:  # noqa: BLE001 - best-effort by definition; logged with the traceback
        (logger or _logger).warning("Best-effort step failed: %s", step, exc_info=True)
