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
from ai_smart_resize import ai_smart_resize_plugin as sr
from ai_style_transfer import ai_style_transfer_plugin as st
from npr_filters import npr_filters_plugin as npr
from portrait_mode import portrait_mode as pm

_ARR = np.zeros((3, 3, 4), dtype=np.uint8)


def _capture(worker):
    captured: list[tuple[bool, str]] = []
    worker.done.connect(lambda ok, msg: captured.append((ok, msg)))
    worker.run()
    return captured[-1]


def _boom(*_a, **_k):
    raise ValueError("kaboom")


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
