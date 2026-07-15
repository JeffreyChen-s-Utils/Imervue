"""The single-image effect dialogs' workers must always report a result.

Their transforms do an unguarded ``import cv2`` (opencv isn't a default
dependency), so a stock install raises ImportError — which the old narrow
``except`` missed, leaving the dialog hung with Apply disabled. The workers now
catch broadly and always emit their completion signal.

Workers are driven via ``run()`` directly (synchronous) — no real QThread.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.gui import ai_upscale_dialog, noise_sharpen_dialog


def _make_image(path):
    Image.fromarray(np.zeros((4, 4, 4), dtype=np.uint8), mode="RGBA").save(str(path))
    return str(path)


def test_noise_sharpen_worker_reports_failure_on_missing_cv2(tmp_path, qapp, monkeypatch):
    src = _make_image(tmp_path / "in.png")

    def _needs_cv2(*_a, **_k):
        raise ImportError("No module named 'cv2'")

    monkeypatch.setattr(noise_sharpen_dialog, "reduce_noise", _needs_cv2)
    results: list = []
    worker = noise_sharpen_dialog._Worker(
        src, str(tmp_path / "out.png"),
        nr_strength=0.5, luma_only=False, sharp_amount=0.0, sharp_radius=1.0,
    )
    worker.done.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert len(results) == 1
    assert results[0][0] is False
    assert "cv2" in results[0][1]


def test_noise_sharpen_worker_reports_success_without_effects(tmp_path, qapp):
    src = _make_image(tmp_path / "in.png")
    out = tmp_path / "out.png"
    results: list = []
    worker = noise_sharpen_dialog._Worker(
        src, str(out), nr_strength=0.0, luma_only=False,
        sharp_amount=0.0, sharp_radius=1.0,
    )
    worker.done.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert results == [(True, str(out))]
    assert out.exists()


def test_upscale_worker_reports_all_failed_when_model_setup_raises(tmp_path, qapp, monkeypatch):
    # The model download / onnxruntime setup runs outside the per-image loop;
    # a failure there must resolve to result_ready(0, total), not a dead thread.
    def _boom(*_a, **_k):
        raise ConnectionError("HF unreachable")

    monkeypatch.setattr(ai_upscale_dialog, "_download_model", _boom)
    ai_key = next(
        k for k in ai_upscale_dialog.UPSCALE_MODELS
        if not k.startswith(ai_upscale_dialog._TRAD_PREFIX)
    )
    paths = [_make_image(tmp_path / "a.png"), _make_image(tmp_path / "b.png")]
    results: list = []
    worker = ai_upscale_dialog._UpscaleWorker(
        paths, str(tmp_path), ai_key, overwrite=False,
    )
    worker.result_ready.connect(lambda ok, bad: results.append((ok, bad)))
    worker.run()
    assert results == [(0, 2)]  # UI resets to "0 upscaled, 2 failed"
