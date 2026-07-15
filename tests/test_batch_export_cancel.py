"""The batch-export dialog must honour Cancel and never destroy a live worker.

Cancel was wired straight to ``reject``, so ``_ExportWorker`` kept running and
wrote every output file after the user cancelled; and with no ``closeEvent``,
quitting the app mid-export destroyed the running QThread ("QThread: Destroyed
while thread is still running" -> abort). The worker now has an abort flag the
run loop checks, Cancel signals it, and the dialog aborts+waits on close.

Worker tests run ``run()`` directly under ``qapp``; dialog tests drive the
methods unbound on fakes -- no widget constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.batch_export_dialog import BatchExportDialog, _ExportWorker


def test_export_worker_abort_stops_before_processing(qapp):
    results: list = []
    worker = _ExportWorker(["a.png", "b.png"], "/out", "PNG", 90, False, 0, 0)
    worker.result_ready.connect(lambda s, f: results.append((s, f)))
    worker.abort()
    worker.run()   # aborted before the first image -> nothing written
    assert results == [(0, 0)]


def test_on_cancel_aborts_running_worker_then_rejects():
    calls: list = []
    worker = SimpleNamespace(isRunning=lambda: True,
                             abort=lambda: calls.append("abort"))
    fake = SimpleNamespace(_worker=worker, reject=lambda: calls.append("reject"))
    BatchExportDialog._on_cancel(fake)
    assert calls == ["abort", "reject"]


def test_on_cancel_without_running_worker_just_rejects():
    calls: list = []
    fake = SimpleNamespace(_worker=None, reject=lambda: calls.append("reject"))
    BatchExportDialog._on_cancel(fake)
    assert calls == ["reject"]


def test_wait_worker_aborts_and_waits_a_running_worker():
    calls: list = []
    worker = SimpleNamespace(isRunning=lambda: True,
                             abort=lambda: calls.append("abort"),
                             wait=lambda: calls.append("wait"))
    BatchExportDialog._wait_worker(SimpleNamespace(_worker=worker))
    assert calls == ["abort", "wait"]


def test_wait_worker_is_a_noop_when_not_running():
    calls: list = []
    worker = SimpleNamespace(isRunning=lambda: False,
                             abort=lambda: calls.append("abort"),
                             wait=lambda: calls.append("wait"))
    BatchExportDialog._wait_worker(SimpleNamespace(_worker=worker))
    assert calls == []


def test_wait_worker_handles_no_worker():
    BatchExportDialog._wait_worker(SimpleNamespace(_worker=None))  # must not raise
