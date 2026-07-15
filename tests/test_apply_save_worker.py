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
