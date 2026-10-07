"""Measure dialog response while a real QThread/cancellation hook remains blocked."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from threading import Event
from time import perf_counter, sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from performance_support import isolated_profile, summarize, write_json  # noqa: E402


def measure_retirement(*, repeats: int = 3, blocked_ms: int = 250) -> dict:
    """Use controlled uninterruptible boundaries, not claims about codec/model throughput."""
    from PySide6.QtCore import QThread, QTimer
    from PySide6.QtWidgets import QApplication, QDialog
    from Imervue.plugin.worker_host import WorkerHostMixin
    from Imervue.plugin.worker_retirement import _RETIRING

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
            worker = dialog._worker = Worker(slow_stop=slow_stop)
            finished = []
            dialog.finished.connect(finished.append)
            timer = QTimer()
            timer.setInterval(10)
            last = [perf_counter()]

            def tick(beats=beats, last=last):
                now = perf_counter()
                beats.append((now - last[0]) * 1000)
                last[0] = now

            timer.timeout.connect(tick)
            worker.start()
            try:
                if not worker.entered.wait(10):
                    raise TimeoutError("worker did not start")
                last[0] = begin = perf_counter()
                timer.start()
                dialog.reject()
                requests.append((perf_counter() - begin) * 1000)
                while not finished or _RETIRING:
                    if perf_counter() - begin > 30:
                        raise TimeoutError("worker did not retire")
                    app.processEvents()
                    sleep(0.001)
                completed.append((perf_counter() - begin) * 1000)
                if finished != [0]:
                    raise RuntimeError("dialog lost original rejection")
            finally:
                timer.stop()
                worker.cancelled.set()
                if not worker.wait(30000):
                    raise TimeoutError("worker join failed")
                dialog.deleteLater()
                app.processEvents()
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
