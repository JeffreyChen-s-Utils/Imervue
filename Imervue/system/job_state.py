"""Thread-safe task results shared by workers and the application job panel."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import chain, islice
from threading import RLock

TERMINAL = frozenset({"succeeded", "partial", "failed", "cancelled"})


@dataclass(frozen=True, slots=True)
class JobItem:
    """One source and its durable output or failure reason."""

    source: str
    status: str = "pending"
    output: str = ""
    error: str = ""


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    """Immutable UI view; completed work is retained across retries."""

    status: str
    current: int
    total: int
    items: tuple[JobItem, ...]


class JobState:
    """Workers publish durable item results; Qt never reads their mutable containers."""

    def __init__(self, paths: list[str] | tuple[str, ...] = ()) -> None:
        self._lock = RLock()
        self._items: dict[str, JobItem | None] = dict.fromkeys(paths)
        self._status = "running"
        self._cancel = False
        self._current = 0
        self._total = len(self._items)
        self._external_progress = False
        self._pending = len(self._items)
        self._failures = self._successes = self._outputs = 0
        self._terminal_error = ""

    def set_items(self, paths: list[str]) -> None:
        """Set a discovered workload before any item result is published."""
        with self._lock:
            if self._successes or self._failures:
                raise RuntimeError("Cannot replace a job that has completed items")
            self._items = dict.fromkeys(paths)
            self._total = len(self._items)
            self._pending = self._total

    def request_cancel(self) -> None:
        """Record cooperative cancellation without blocking on a worker."""
        with self._lock:
            if self._status not in TERMINAL:
                self._cancel = True
                self._status = "cancelling"

    @property
    def cancelled(self) -> bool:
        """Whether cancellation was requested, including after completion."""
        with self._lock:
            return self._cancel

    def record(self, source: str, *, output: str = "", error: str = "",
               skipped: bool = False) -> None:
        """Publish an item after its output/transaction commits, never before."""
        with self._lock:
            if (
                source not in self._items
                or self._items[source] is not None
                or self._status in TERMINAL
            ):
                return
            outcome = "failed" if error else "succeeded"
            status = "skipped" if skipped else outcome
            self._items[source] = JobItem(source, status, output, error)
            self._pending -= 1
            if error and not skipped:
                self._failures += 1
            else:
                self._successes += 1
                self._outputs += bool(output)
            if not self._external_progress:
                self._current += 1

    def progress(self, current: int, total: int) -> None:
        """Report atomic-install substeps without claiming each file is a committed plugin."""
        if not 0 <= current <= total:
            raise ValueError("Progress must satisfy 0 <= current <= total")
        with self._lock:
            if self._status not in TERMINAL:
                self._current, self._total = current, total
                self._external_progress = True

    def finish(self, *, error: str = "") -> None:
        """Finish in O(1); pending item statuses resolve only when details are requested."""
        with self._lock:
            if self._status in TERMINAL:
                return
            self._terminal_error = error or "Worker did not complete this item"
            failed = self._failures + self._pending
            if self._cancel:
                self._status = "cancelled"
            elif failed and self._successes:
                self._status = "partial"
            else:
                self._status = "failed" if failed or error else "succeeded"

    def snapshot(self, *, include_items: bool = True) -> JobSnapshot:
        """Copy results only on demand; periodic progress polling is O(1)."""
        with self._lock:
            items = (
                tuple(self._resolve(path, item) for path, item in self._items.items())
                if include_items
                else ()
            )
            return JobSnapshot(self._status, self._current, self._total, items)

    def failed_paths(self) -> tuple[str, ...]:
        """Only actual failures can retry; completed and cancelled items are excluded."""
        with self._lock:
            if not self._failures and not (self._pending and self._status in {"failed", "partial"}):
                return ()
            return tuple(path for path, item in self._items.items() if self._is_failed(item))

    def _is_failed(self, item: JobItem | None) -> bool:
        return (item is not None and item.status == "failed") or (
            item is None and self._status in {"failed", "partial"}
        )

    def _resolve(self, path: str, item: JobItem | None) -> JobItem:
        if item is not None:
            return item
        if self._status not in TERMINAL:
            return JobItem(path)
        return JobItem(path, "cancelled" if self._cancel else "failed", error=self._terminal_error)

    def visible_results(self, limit: int) -> tuple[tuple[JobItem, ...], int]:
        """Bound detail materialization, put failures first, omit non-output index successes."""
        if limit < 0:
            raise ValueError("Result limit cannot be negative")
        with self._lock:
            failed = self._failures + (
                self._pending if self._status in {"failed", "partial"} else 0
            )
            total = failed + self._outputs
            if not total or not limit:
                return (), total
            failures = (
                (
                    self._resolve(path, item)
                    for path, item in self._items.items()
                    if self._is_failed(item)
                )
                if failed
                else ()
            )
            outputs = (
                (
                    item
                    for item in self._items.values()
                    if item is not None and item.status == "succeeded" and item.output
                )
                if self._outputs
                else ()
            )
            return tuple(islice(chain(failures, outputs), limit)), total
