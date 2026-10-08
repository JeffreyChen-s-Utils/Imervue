"""Measure dialog response while a real QThread/cancellation hook remains blocked."""
from __future__ import annotations

import argparse
import sys
import tempfile
from functools import partial
from pathlib import Path
from threading import Event
from time import perf_counter, sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from performance_support import isolated_profile, summarize, write_json  # noqa: E402


def _beat(beats: list, last: list) -> None:
    """Record the gap since the previous timer beat, in milliseconds."""
    now = perf_counter()
    beats.append((now - last[0]) * 1000)
    last[0] = now


def _reject_and_retire(app, dialog, beats: list) -> tuple[float, float]:
    """Reject *dialog* while its worker is blocked; milliseconds until ``reject`` returned
    and until the worker had retired. UI heartbeat gaps are appended to *beats*."""
    from PySide6.QtCore import QTimer
    from Imervue.plugin.worker_retirement import _RETIRING
    worker = dialog._worker
    finished = []
    dialog.finished.connect(finished.append)
    timer = QTimer()
    timer.setInterval(10)
    last = [perf_counter()]
    timer.timeout.connect(partial(_beat, beats, last))
    worker.start()
    try:
        if not worker.entered.wait(10):
            raise TimeoutError("worker did not start")
        last[0] = begin = perf_counter()
        timer.start()
        dialog.reject()
        request = (perf_counter() - begin) * 1000
        while not finished or _RETIRING:
            if perf_counter() - begin > 30:
                raise TimeoutError("worker did not retire")
            app.processEvents()
            sleep(0.001)
        retirement = (perf_counter() - begin) * 1000
        if finished != [0]:
            raise RuntimeError("dialog lost original rejection")
        return request, retirement
    finally:
        timer.stop()
        worker.cancelled.set()
        if not worker.wait(30000):
            raise TimeoutError("worker join failed")
        dialog.deleteLater()
        app.processEvents()


def measure_retirement(*, repeats: int = 3, blocked_ms: int = 250) -> dict:
    """Use controlled uninterruptible boundaries, not claims about codec/model throughput."""
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication, QDialog
    from Imervue.plugin.worker_host import WorkerHostMixin

    app = QApplication.instance() or QApplication([])

    class Worker(QThread):
        def __init__(self, *, slow_stop):
            super().__init__()
            self.entered, self.cancelled = Event(), Event()
            self.slow_stop = slow_stop

        def run(self):
            self.entered.set()
            self.cancelled.wait(30)
            self.msleep(blocked_ms)

        def stop(self):
            self.cancelled.set()
            if self.slow_stop:
                self.msleep(blocked_ms)

    class Dialog(WorkerHostMixin, QDialog):
        pass

    cases = {}
    for name, slow_stop in (("decode_inference_io_boundary", False), ("blocking_stop", True)):
        requests, completed, beats = [], [], []
        for _ in range(repeats):
            dialog = Dialog()
            dialog._worker = Worker(slow_stop=slow_stop)
            request, retirement = _reject_and_retire(app, dialog, beats)
            requests.append(request)
            completed.append(retirement)
        cases[name] = {"ui_request": summarize(requests), "actual_retirement": summarize(completed),
                       "ui_heartbeat": summarize(beats)}
    return {"blocked_ms": blocked_ms, "cases": cases,
            "boundary": ("real QDialog/QThread; controlled 250ms boundary or blocking stop; "
                         "no GL/model/codec throughput; final process exit drain excluded")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    from performance_benchmark import environment
    with tempfile.TemporaryDirectory(prefix="imervue-workers-") as scratch, \
            isolated_profile(Path(scratch) / "profile"):
        report = {"environment": environment(),
                  "measurement": measure_retirement(repeats=args.repeats)}
        write_json(args.output, report)


if __name__ == "__main__":
    main()
