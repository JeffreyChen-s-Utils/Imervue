"""The deflicker worker must always emit finished_with_count.

mkdir and the luminance/gain computation ran outside the narrow inner except, so
a read-only output folder or a compute failure escaped run(), the completion
signal never fired, and the dialog hung. run() now wraps everything.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.gui import deflicker_dialog
from Imervue.gui.deflicker_dialog import DeflickerWorker
from Imervue.image.deflicker import DeflickerOptions


def _frames(tmp_path, n=2):
    paths = []
    for i in range(n):
        p = tmp_path / f"f{i}.png"
        Image.fromarray(np.zeros((4, 4, 4), dtype=np.uint8), mode="RGBA").save(str(p))
        paths.append(str(p))
    return paths


def _opts():
    return DeflickerOptions(rolling_window=9, target_mode="rolling")


def test_worker_emits_finished_even_when_processing_raises(tmp_path, qapp, monkeypatch):
    paths = _frames(tmp_path)

    def _boom(_frames):
        raise MemoryError("out of memory")

    monkeypatch.setattr(deflicker_dialog, "frame_luminance_means", _boom)
    results: list = []
    worker = DeflickerWorker(paths, _opts())
    worker.finished_with_count.connect(results.append)
    worker.run()
    assert results == [0]           # reported despite the failure, not hung


def test_worker_writes_and_reports_on_success(tmp_path, qapp):
    paths = _frames(tmp_path)
    results: list = []
    worker = DeflickerWorker(paths, _opts())
    worker.finished_with_count.connect(results.append)
    worker.run()
    assert results == [2]
    assert (tmp_path / "deflickered").is_dir()
