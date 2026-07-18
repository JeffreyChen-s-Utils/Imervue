"""Tests for the shared apply-and-save EffectWorker completion contract.

~20 single-image tool dialogs share this worker. It must ALWAYS emit ``done`` —
including when the transform raises something the old narrow ``except`` missed
(an ImportError for optional opencv, cv2.error, MemoryError) — or the calling
dialog hangs with its Apply button disabled forever.

``run()`` is called directly (synchronously) so no real QThread is started.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.gui import _apply_save
from Imervue.gui._apply_save import EffectWorker


def _make_image(path):
    Image.fromarray(np.zeros((4, 4, 4), dtype=np.uint8), mode="RGBA").save(str(path))
    return str(path)


def test_reports_success_and_writes_output(tmp_path, qapp):
    src = _make_image(tmp_path / "in.png")
    out = tmp_path / "out.png"
    results: list = []
    worker = EffectWorker(src, lambda arr: arr, str(out))
    worker.done.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert results == [(True, str(out))]
    assert out.exists()


def test_reports_failure_on_importerror_from_missing_backend(tmp_path, qapp):
    # opencv isn't a default dependency, so a cv2-backed transform raises
    # ImportError — which the old except (OSError, ValueError) let escape.
    src = _make_image(tmp_path / "in.png")
    results: list = []

    def _needs_cv2(_arr):
        raise ImportError("No module named 'cv2'")

    worker = EffectWorker(src, _needs_cv2, str(tmp_path / "out.png"))
    worker.done.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert len(results) == 1
    assert results[0][0] is False
    assert "cv2" in results[0][1]


def test_reports_failure_on_arbitrary_exception(tmp_path, qapp):
    src = _make_image(tmp_path / "in.png")
    results: list = []

    def _boom(_arr):
        raise MemoryError("out of memory")

    worker = EffectWorker(src, _boom, str(tmp_path / "out.png"))
    worker.done.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert len(results) == 1
    assert results[0][0] is False


# ---------------------------------------------------------------------------
# finalize_worker — crash-safe QThread teardown for done slots
# ---------------------------------------------------------------------------


class _FakeDialog:
    pass


def test_finalize_worker_waits_then_clears_reference():
    waited: list[bool] = []

    class _FakeWorker:
        def wait(self):
            waited.append(True)

    dlg = _FakeDialog()
    dlg._worker = _FakeWorker()

    _apply_save.finalize_worker(dlg)

    assert waited == [True]        # waited for the thread before releasing
    assert dlg._worker is None     # reference dropped only after the wait


def test_finalize_worker_tolerates_missing_worker():
    dlg = _FakeDialog()
    dlg._worker = None
    _apply_save.finalize_worker(dlg)   # must not raise on a None worker
    assert dlg._worker is None


def test_finalize_worker_waits_for_a_real_thread_before_clearing(qapp):
    from PySide6.QtCore import QObject, QThread, Signal

    class _Worker(QThread):
        done = Signal()

        def run(self):
            self.done.emit()   # emitted as the last act, like the real workers

    # A QObject dialog (like the real QDialog subclasses) so the cross-thread
    # done -> on_done delivery is queued to this thread, not run inline on the
    # worker thread — that queued delivery is what makes the wait() safe.
    class _Dialog(QObject):
        def __init__(self):
            super().__init__()
            self._worker = _Worker()

        def on_done(self):
            _apply_save.finalize_worker(self)

    dlg = _Dialog()
    worker = dlg._worker
    dlg._worker.done.connect(dlg.on_done)
    dlg._worker.start()

    for _ in range(50):
        qapp.processEvents()
        if dlg._worker is None:
            break

    assert dlg._worker is None          # reference cleared via finalize_worker
    assert worker.isFinished()          # and only after the thread truly stopped
