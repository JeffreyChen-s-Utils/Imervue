"""Measure periodic autosave enqueue, worker phases and UI heartbeat with committed pixels."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject, QThreadPool, QTimer

from Imervue.paint import autosave_jobs
from Imervue.paint.workspace_autosave import AutosaveMixin
from scripts.performance_support import measure, summarize


class _Canvas:
    def __init__(self, document):
        self._document = document

    def document(self):
        return self._document


class _Host(QObject, AutosaveMixin):
    def __init__(self, document, stack, directory):
        QObject.__init__(self)
        self._canvas = _Canvas(document)
        self._tab_dirty = {self._canvas: True}
        self._undo_stacks = {self._canvas: stack}
        self._autosave_target_dir = directory
        self.completed = 0
        self.warnings = []

    def _refresh_status_line(self):
        self.completed += 1

    def _report_autosave_error(self, message):
        self.warnings.append(message)


def background_autosave(app, document, stack, directory: Path, repeats: int) -> dict:
    """Time the real mixin/pool pipeline, retaining synchronous writes as a separate metric."""
    host = _Host(document, stack, directory)
    enqueues, installed, materializations, writes, heartbeats = [], [], [], [], []
    heartbeat = QTimer()
    heartbeat.setInterval(10)
    previous = [time.perf_counter()]

    def beat():
        now = time.perf_counter()
        heartbeats.append((now - previous[0]) * 1000)
        previous[0] = now

    heartbeat.timeout.connect(beat)
    materialize = type(stack.committed_snapshot()).materialize
    write = autosave_jobs.write_snapshot

    def timed_materialize(content):
        start = time.perf_counter()
        result = materialize(content)
        materializations.append((time.perf_counter() - start) * 1000)
        return result

    def timed_write(*args, **kwargs):
        start = time.perf_counter()
        result = write(*args, **kwargs)
        writes.append((time.perf_counter() - start) * 1000)
        return result

    def operate():
        for _ in range(repeats):
            target = host.completed + 1
            start = time.perf_counter()
            host._on_autosave_tick()
            enqueues.append((time.perf_counter() - start) * 1000)
            deadline = time.monotonic() + 30
            while host.completed < target:
                app.processEvents()
                if host.warnings or time.monotonic() > deadline:
                    raise RuntimeError("background autosave did not complete: "
                                       + "; ".join(host.warnings))
                time.sleep(.001)
            installed.append((time.perf_counter() - start) * 1000)

    try:
        heartbeat.start()
        with patch.object(type(stack.committed_snapshot()), "materialize", timed_materialize), \
                patch.object(autosave_jobs, "write_snapshot", timed_write):
            memory = measure(operate, repeats=1)
        return {"ui_enqueue": summarize(enqueues), "request_to_recorded": summarize(installed),
                "worker_materialize": summarize(materializations), "worker_compress_write":
                summarize(writes), "ui_heartbeat":
                summarize(heartbeats) if heartbeats else None, "memory": memory,
                "boundary": "real QObject/mixin/pool; immutable committed version; "
                            "no GL drawing; UI fallback copy when history is disabled is excluded"}
    finally:
        heartbeat.stop()
        jobs = getattr(host, "_autosave_jobs", None)
        if jobs is not None:
            jobs.close()
        QThreadPool.globalInstance().waitForDone(10000)
        host.deleteLater()
