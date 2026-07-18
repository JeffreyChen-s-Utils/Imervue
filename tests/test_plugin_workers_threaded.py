"""The 7 heavy AI/NPR plugins must run their compute on a background QThread.

Each dialog used to call ONNX / rembg / seam-carve / OpenCV inference directly
in _commit on the GUI thread, freezing the UI until it finished. They now hand
the work to a _XxxWorker(QThread) that emits done(ok, message), and each dialog
waits its worker on close so the thread is never destroyed mid-run.

The worker.run() bodies are exercised by calling run() directly (no start()), so
the emit is captured synchronously; the heavy function and image load are
monkeypatched so the tests stay fast and dependency-free.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from ai_colorize import ai_colorize_plugin as cz
from ai_denoise import ai_denoise_plugin as dn
from ai_motion_deblur import ai_motion_deblur_plugin as db
from ai_object_remove import ai_object_remove_plugin as orm
from ai_outpaint import ai_outpaint_plugin as op
from ai_smart_resize import ai_smart_resize_plugin as sr
from ai_style_transfer import ai_style_transfer_plugin as st
from npr_filters import npr_filters_plugin as npr
from portrait_mode import portrait_mode as pm

_ARR = np.zeros((3, 3, 4), dtype=np.uint8)


def _capture(worker):
    captured: list[tuple[bool, str]] = []
    worker.done.connect(lambda ok, msg: captured.append((ok, msg)))
    worker.run()
    assert captured, "worker.run() must always emit done"
    return captured[-1]


def _boom(*_a, **_k):
    raise ValueError("kaboom")


class _HardError(Exception):
    """An exception outside the workers' old narrow catch tuple — stands in
    for onnxruntime.InvalidArgument / cv2.error / PIL.DecompressionBombError,
    all of which subclass Exception directly."""


def _boom_hard(*_a, **_k):
    raise _HardError("unexpected backend failure")


# --- per-plugin worker success + failure -----------------------------------

def test_portrait_worker(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "_load_rgba", lambda _p: _ARR.copy())
    monkeypatch.setattr(pm, "_extract_subject_mask", lambda _a: np.zeros((3, 3), np.uint8))
    monkeypatch.setattr(pm, "apply_portrait_blur", lambda _a, _m, _o: _ARR.copy())
    out = tmp_path / "p.png"
    ok, msg = _capture(pm._PortraitWorker("in.png", object(), str(out)))
    assert ok and msg == str(out) and out.exists()

    monkeypatch.setattr(pm, "_extract_subject_mask", _boom)
    ok, msg = _capture(pm._PortraitWorker("in.png", object(), str(tmp_path / "x.png")))
    assert not ok and "kaboom" in msg


def test_style_transfer_worker(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_load_rgba", lambda _p: _ARR.copy())
    monkeypatch.setattr(st, "stylise", lambda _a, _o: _ARR.copy())
    out = tmp_path / "s.png"
    ok, msg = _capture(st._StyleTransferWorker("in.png", object(), str(out)))
    assert ok and msg == str(out) and out.exists()

    monkeypatch.setattr(st, "stylise", _boom)
    ok, msg = _capture(st._StyleTransferWorker("in.png", object(), str(tmp_path / "x.png")))
    assert not ok and "kaboom" in msg


def test_denoise_worker(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(dn, "_load_rgba", lambda _p: _ARR.copy())
    monkeypatch.setattr(dn, "bilateral_denoise", lambda _a, _o: _ARR.copy())
    monkeypatch.setattr(dn, "onnx_denoise", lambda _a, _m, blend=0.0: _ARR.copy())
    out = tmp_path / "d.png"
    ok, msg = _capture(dn._DenoiseWorker("in.png", "bilateral", 0.5, object(), str(out)))
    assert ok and out.exists()
    # ONNX branch routes through onnx_denoise.
    out2 = tmp_path / "d2.png"
    ok, _ = _capture(dn._DenoiseWorker("in.png", "some_model", 0.5, None, str(out2)))
    assert ok and out2.exists()

    monkeypatch.setattr(dn, "onnx_denoise", _boom)
    ok, msg = _capture(dn._DenoiseWorker("in.png", "some_model", 0.5, None, str(tmp_path / "x.png")))
    assert not ok and "kaboom" in msg


def test_colorize_worker(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(cz, "_load_rgba", lambda _p: _ARR.copy())
    monkeypatch.setattr(cz, "_colorize_dispatch", lambda _a, _m, _i: _ARR.copy())
    out = tmp_path / "c.png"
    ok, msg = _capture(cz._ColorizeWorker("in.png", "heuristic:sepia", 0.5, str(out)))
    assert ok and out.exists()

    monkeypatch.setattr(cz, "_colorize_dispatch", _boom)
    ok, msg = _capture(cz._ColorizeWorker("in.png", "heuristic:sepia", 0.5, str(tmp_path / "x.png")))
    assert not ok and "kaboom" in msg


def test_deblur_worker(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_load_rgba", lambda _p: _ARR.copy())
    monkeypatch.setattr(db, "wiener_deblur", lambda _a, _o: _ARR.copy())
    monkeypatch.setattr(db, "onnx_deblur", lambda _a, _m, blend=0.0: _ARR.copy())
    out = tmp_path / "b.png"
    ok, _ = _capture(db._DeblurWorker("in.png", ("wiener", "gaussian"), 0.5, object(), str(out)))
    assert ok and out.exists()
    out2 = tmp_path / "b2.png"
    ok, _ = _capture(db._DeblurWorker("in.png", ("onnx", "model.onnx"), 0.5, None, str(out2)))
    assert ok and out2.exists()

    monkeypatch.setattr(db, "wiener_deblur", _boom)
    ok, msg = _capture(db._DeblurWorker("in.png", ("wiener", "gaussian"), 0.5, None, str(tmp_path / "x.png")))
    assert not ok and "kaboom" in msg


def test_smart_resize_worker(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "_load_rgba", lambda _p: _ARR.copy())
    monkeypatch.setattr(sr, "smart_resize", lambda _a, _o: _ARR.copy())
    out = tmp_path / "r.png"
    ok, msg = _capture(sr._SmartResizeWorker("in.png", object(), str(out)))
    assert ok and out.exists()

    monkeypatch.setattr(sr, "smart_resize", _boom)
    ok, msg = _capture(sr._SmartResizeWorker("in.png", object(), str(tmp_path / "x.png")))
    assert not ok and "kaboom" in msg


def test_npr_worker(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(npr, "_load_rgba", lambda _p: _ARR.copy())
    monkeypatch.setattr(npr, "apply_npr_filter", lambda _a, _o: _ARR.copy())
    out = tmp_path / "n.png"
    ok, msg = _capture(npr._NPRFilterWorker("in.png", object(), str(out)))
    assert ok and out.exists()

    monkeypatch.setattr(npr, "apply_npr_filter", _boom)
    ok, msg = _capture(npr._NPRFilterWorker("in.png", object(), str(tmp_path / "x.png")))
    assert not ok and "kaboom" in msg


# --- unexpected backend errors still report (not just the narrow tuple) -----

# (module, patch_load_rgba, compute_attr, worker_factory(module, out_path))
_HARD_FAIL_CASES = [
    (cz, True, "_colorize_dispatch",
     lambda m, out: m._ColorizeWorker("in.png", "heuristic:sepia", 0.5, out)),
    (dn, True, "onnx_denoise",
     lambda m, out: m._DenoiseWorker("in.png", "some_model", 0.5, None, out)),
    (db, True, "wiener_deblur",
     lambda m, out: m._DeblurWorker("in.png", ("wiener", "gaussian"), 0.5, object(), out)),
    (sr, True, "smart_resize",
     lambda m, out: m._SmartResizeWorker("in.png", object(), out)),
    (st, True, "stylise",
     lambda m, out: m._StyleTransferWorker("in.png", object(), out)),
    (npr, True, "apply_npr_filter",
     lambda m, out: m._NPRFilterWorker("in.png", object(), out)),
    (pm, True, "_extract_subject_mask",
     lambda m, out: m._PortraitWorker("in.png", object(), out)),
    (orm, False, "remove_object",
     lambda m, out: m._RemoveWorker(_ARR.copy(), np.zeros((3, 3), np.uint8), out)),
    (orm, False, "sam_mask",
     lambda m, _out: m._SamMaskWorker(_ARR.copy(), (1, 1), "enc", "dec")),
    (op, True, "outpaint",
     lambda m, out: m._OutpaintWorker("in.png", 10, out)),
]


@pytest.mark.parametrize("module, patch_load, compute_attr, factory", _HARD_FAIL_CASES)
def test_worker_reports_unexpected_error(
    module, patch_load, compute_attr, factory, qapp, tmp_path, monkeypatch,
):
    """Regression: each worker caught only (ImportError, OSError, ValueError
    [, RuntimeError]); an ORT/cv2/PIL exception outside that tuple escaped
    run(), killing the thread with done() never emitted — the dialog then hung
    with a permanently dead OK button. run() must report every failure."""
    if patch_load:
        monkeypatch.setattr(module, "_load_rgba", lambda _p: _ARR.copy())
    monkeypatch.setattr(module, compute_attr, _boom_hard)
    ok, msg = _capture(factory(module, str(tmp_path / "x.png")))
    assert ok is False
    assert "unexpected backend failure" in str(msg)


def test_cloud_share_worker_reports_unexpected_error(qapp, monkeypatch):
    """cloud_share's single-path catch missed http.client exceptions and its
    batch path was unwrapped entirely — a provider error left the spinner
    hung. Any uploader failure must now report."""
    from cloud_share import cloud_share_plugin as cs
    monkeypatch.setattr(
        cs._UploadWorker, "_uploader", lambda _self: _boom_hard,
    )
    worker = cs._UploadWorker("imgur", ["a.png"], {"client_id": "x"})
    ok, msg = _capture(worker)
    assert ok is False
    assert "unexpected backend failure" in str(msg)


def test_cloud_share_worker_reports_batch_error(qapp, monkeypatch):
    from cloud_share import cloud_share_plugin as cs
    monkeypatch.setattr(cs, "upload_batch", _boom_hard)
    monkeypatch.setattr(
        cs._UploadWorker, "_uploader", lambda _self: (lambda _p: "link"),
    )
    worker = cs._UploadWorker("imgur", ["a.png", "b.png"], {"client_id": "x"})
    ok, msg = _capture(worker)
    assert ok is False
    assert "unexpected backend failure" in str(msg)


# --- every dialog waits its worker on close --------------------------------

_DIALOGS = [
    pm.PortraitModeDialog,
    st.StyleTransferDialog,
    dn.AIDenoiseDialog,
    cz.AIColorizeDialog,
    db.AIMotionDeblurDialog,
    sr.AISmartResizeDialog,
    npr.NPRFiltersDialog,
]


@pytest.mark.parametrize("dialog_cls", _DIALOGS)
def test_wait_worker_joins_running_thread(dialog_cls):
    waited: list[str] = []
    fake = SimpleNamespace(
        _worker=SimpleNamespace(isRunning=lambda: True, wait=lambda: waited.append("w")),
    )
    dialog_cls._wait_worker(fake)
    assert waited == ["w"]


@pytest.mark.parametrize("dialog_cls", _DIALOGS)
def test_wait_worker_safe_without_a_worker(dialog_cls):
    dialog_cls._wait_worker(SimpleNamespace(_worker=None))   # must not raise
