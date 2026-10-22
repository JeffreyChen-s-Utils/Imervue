"""Measure concurrent real viewer decodes with supplied files in an isolated profile."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import platform
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from performance_support import isolated_profile, measure, write_json  # noqa: E402


def _track_admissions(budget) -> list[int]:
    """Record the accounted bytes after every admission; returns the list they land in.

    Observed under the budget's own admission lock, without substituting the policy.
    """
    peaks: list[int] = []
    reserve = budget.reserve

    def tracked_reserve(ticket, size):
        with budget._lock:
            admitted = reserve(ticket, size)
            peaks.append(budget.used_bytes)
            return admitted

    budget.reserve = tracked_reserve
    return peaks


class _Landing:
    """Takes each finished decode on its worker thread: keeps the pixels, settles the budget."""

    def __init__(self, budget) -> None:
        self.budget = budget
        self.results: list[dict] = []
        self.retained: list = []
        self.errors: list[str] = []
        self._gate = threading.Lock()

    def landed(self, worker, result, message) -> None:
        from Imervue.gpu_image_view.ram_budget import image_bytes
        with self._gate:
            if message:
                self.errors.append(f"{worker.path}: {message}")
            size = image_bytes(result)
            if result is not None:
                self._retain(worker, result, size)
            self.results.append({"path": worker.path, "decoded": result is not None,
                                 "actual_bytes": size})
            if self.budget is not None:
                self.budget.release(worker)

    def _retain(self, worker, result, size: int) -> None:
        self.retained.append(result)
        key = (worker.path, id(worker))
        if self.budget is not None and not self.budget.store(key, size, ticket=worker):
            self.errors.append(f"{worker.path}: result admission failed")


def measure_decodes(paths: list[str], *, limit: int | None, repeats: int = 3) -> dict:
    """Run two decoder threads; retain pixels/RSS and record quota refusals separately."""
    from PySide6.QtCore import Qt
    from Imervue.gpu_image_view.images.image_loader import LoadDeepZoomWorker
    from Imervue.gpu_image_view.ram_budget import RamBudget, decode_reservation, image_bytes
    runs = []

    def operation():
        budget = RamBudget(limit) if limit is not None else None
        peaks = _track_admissions(budget) if budget is not None else []
        landing = _Landing(budget)
        workers = [LoadDeepZoomWorker(path, memory_budget=budget) for path in paths]
        for worker in workers:
            worker.signals.completed.connect(landing.landed, Qt.ConnectionType.DirectConnection)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for future in [pool.submit(worker.run) for worker in workers]:
                future.result()
        if landing.errors:
            raise RuntimeError("; ".join(landing.errors))
        runs.append({"results": landing.results, "peak_accounted_bytes": max(peaks, default=0),
                     "accounted_bytes_after": budget.used_bytes if budget is not None else None,
                     "retained_array_bytes": sum(image_bytes(r) for r in landing.retained)})

    metrics = measure(operation, repeats=repeats)
    source_paths = ["Imervue/gpu_image_view/ram_budget.py",
                    "Imervue/gpu_image_view/images/image_loader.py",
                    "Imervue/gpu_image_view/prefetch_scheduler.py",
                    "Imervue/gpu_image_view/prefetch_memory.py", "scripts/performance_ram.py"]
    root = Path(__file__).resolve().parents[1]
    sources = {p: hashlib.sha256((root / p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
               for p in source_paths}
    return {"limit_bytes": limit, "metrics": metrics, "runs": runs,
            "reservations": {p: decode_reservation(p) for p in paths},
            "fixtures": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
            "source_sha256": sources, "platform": platform.platform(),
            "python": platform.python_version(),
            "measurement": "fresh invocation/profile; native WorkingSet samples every 5ms; "
                           "two decode threads; DirectConnection collector; retained pyramids"}


def main() -> None:
    """Use one fresh process per case; input files are read, never modified or downloaded."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", help="supplied RAW/raster files")
    parser.add_argument("--limit-mib", type=int, default=0, help="0: no speculative admission")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.limit_mib < 0 or args.repeats < 1:
        parser.error("limit must be nonnegative and repeats positive")
    if any(not Path(path).is_file() for path in args.images):
        parser.error("every image must be an existing file")
    with tempfile.TemporaryDirectory(prefix="imervue-ram-") as temporary, \
            isolated_profile(Path(temporary) / "profile"):
        from PySide6.QtWidgets import QApplication
        app = QApplication([])
        report = measure_decodes(args.images, limit=args.limit_mib * 1024**2 or None,
                                 repeats=args.repeats)
        write_json(args.output, report)
        app.quit()


if __name__ == "__main__":
    main()
