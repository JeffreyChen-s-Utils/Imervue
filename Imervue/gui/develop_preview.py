"""Bounded Modify preview jobs: latest generation wins, reduced then full quality."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Event

from PIL import Image
from PySide6.QtCore import QCoreApplication, QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QImage

from Imervue.image.develop_preview import (
    PreviewCache, PreviewCancelledError, PreviewPixels,
    PreviewRequest, render_preview,
)
from Imervue.image.recipe import Recipe
from Imervue.system.qimage_convert import pil_to_qimage

logger = logging.getLogger("Imervue.develop_preview")


@dataclass(frozen=True)
class PreviewResult:
    """Owned, already-converted QImage plus the immutable request and pixel owners."""

    request: PreviewRequest
    pixels: PreviewPixels
    qimage: QImage
    render_ms: float


class _Signals(QObject):
    finished = Signal(object, object, object)


class _Job(QRunnable):
    def __init__(self, request: PreviewRequest, cache: PreviewCache, *, full: bool):
        super().__init__()
        self.request = request
        self.cache = cache
        self.full = full
        # The application retains the sender until a queued UI-thread delete,
        # including when its panel/controller disappears during computation.
        self.signals = _Signals(QCoreApplication.instance())

    def run(self) -> None:
        result = None
        error = None
        try:
            started = time.perf_counter()
            pixels = render_preview(self.request, self.cache, full=self.full)
            qimage = pil_to_qimage(pixels.image)
            if not self.request.cancelled.is_set():
                result = PreviewResult(self.request, pixels, qimage,
                                       (time.perf_counter() - started) * 1000)
        except PreviewCancelledError:
            # Expected cooperative stop; completion still drains the scheduler.
            result = None
        except Exception as exc:
            logger.exception("Modify preview failed for %s", self.request.path)
            error = str(exc)
        self.signals.finished.emit(self, result, error)


class PreviewScheduler(QObject):
    """At most one active reduced job and one active full job per panel.

    Pending requests replace each other; full rendering starts only after a
    reduced result for that generation. Jobs own sources/signals and the global
    pool owns running QRunnables even if the panel is destroyed.
    """

    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache = PreviewCache()
        self.version = 0
        self._latest: PreviewRequest | None = None
        self._low: _Job | None = None
        self._full: _Job | None = None
        self._pending: PreviewRequest | None = None
        self._final_version = -1
        self._reduced_version = -1
        self._complete_version = -1
        self._full_started_version = -1

    @property
    def is_idle(self) -> bool:
        """Whether all active and coalesced work has drained."""
        return self._low is None and self._full is None and self._pending is None

    def request(self, path: str, source: Image.Image, recipe: Recipe, *, final: bool) -> int:
        """Enqueue the latest immutable recipe; never copy full source pixels on the UI."""
        if (self._latest is not None and self._latest.path == path
                and self._latest.source is source and self._latest.recipe == recipe):
            if final:
                self._final_version = self.version
                self._start_full()
            return self.version
        previous_source = self._latest.source if self._latest else None
        self.cancel()
        if previous_source is not source:
            self.cache.clear()
        self._latest = PreviewRequest(self.version, path, source,
                                      Recipe.from_dict(recipe.to_dict()), Event())
        self._pending = self._latest
        self._final_version = self.version if final else -1
        self._start_low()
        return self.version

    def cancel(self) -> None:
        """Invalidate results and pending work without waiting on CPU or Qt threads."""
        self.version += 1
        for job in (self._low, self._full):
            if job is not None:
                job.request.cancelled.set()
        self._pending = None
        self._latest = None
        self._final_version = -1

    def _start_low(self) -> None:
        if self._low is not None or self._pending is None:
            return
        request = self._pending
        self._pending = None
        self._low = _Job(request, self.cache, full=False)
        self._launch(self._low, priority=100)

    def _start_full(self) -> None:
        request = self._latest
        if (request is None or self._full is not None or self._final_version != request.version
                or self._reduced_version != request.version
                or request.version in (self._complete_version, self._full_started_version)):
            return
        # Separate cancellation flags: discarding a full job must not poison the
        # reduced request's lifecycle, and vice versa.
        request = PreviewRequest(request.version, request.path, request.source,
                                 request.recipe, Event())
        self._full = _Job(request, self.cache, full=True)
        self._full_started_version = request.version
        self._launch(self._full, priority=0)

    def _launch(self, job: _Job, *, priority: int) -> None:
        job.signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        job.signals.finished.connect(job.signals.deleteLater, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(job, priority)

    def _finished(self, job: _Job, result: PreviewResult | None, error: str | None) -> None:
        if self._low is job:
            self._low = None
        if self._full is job:
            self._full = None
        current = self._latest is not None and job.request.version == self.version
        if current and error is not None:
            self.failed.emit(error)
        if current and result is not None:
            self._reduced_version = self.version
            if result.pixels.full_quality:
                self._complete_version = self.version
            self.result_ready.emit(result)
        elif current and not job.full and error is not None:
            # A reduced approximation may fail on unsupported extras; still try
            # the canonical pipeline once when full quality was requested.
            self._reduced_version = self.version
        self._start_low()
        self._start_full()
