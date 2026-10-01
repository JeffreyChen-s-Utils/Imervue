"""The heavy AI/NPR plugins run their compute off the GUI thread.

Nine tool dialogs hand their work to the shared ``ToolDialogMixin``
(``Imervue/plugin/tool_dialog.py``), whose ``EffectWorker`` always reports
``done(ok, message)``; that flow is covered once in ``test_tool_dialog.py`` and
the worker's always-report contract in ``test_apply_save_worker.py``. Here each
dialog's own part is checked: the transform it hands over runs the plugin's
compute with the dialog's settings. Dialogs are stand-ins (``SimpleNamespace``)
so no model discovery or image load runs. object_remove and cloud_share keep
their own workers, run inline by calling ``run()``.
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
from ai_portrait_relight import ai_portrait_relight_plugin as rl
from ai_smart_resize import ai_smart_resize_plugin as sr
from ai_style_transfer import ai_style_transfer_plugin as st
from npr_filters import npr_filters_plugin as npr
from portrait_mode import portrait_mode as pm

_ARR = np.zeros((3, 3, 4), dtype=np.uint8)
_OUT = np.full((3, 3, 4), 7, dtype=np.uint8)


def _w(value):
    """A widget stand-in answering ``value()``, ``currentData()`` and ``isChecked()``."""
    return SimpleNamespace(value=lambda: value, currentData=lambda: value, isChecked=lambda: value)


@pytest.fixture
def record(monkeypatch):
    """Replace ``module.name`` by a recorder that returns ``_OUT``."""
    calls: list = []

    def patch(module, name):
        def fake(*args, **kwargs):
            calls.append((args, kwargs))
            return _OUT
        monkeypatch.setattr(module, name, fake)
    return calls, patch


def _run(dialog_cls, me) -> np.ndarray:
    return dialog_cls._transform(me)(_ARR)


def test_colorize_hands_over_the_method_and_intensity(record):
    calls, patch = record
    patch(cz, "_colorize_dispatch")
    me = SimpleNamespace(_method=_w("heuristic:sepia"), _intensity=_w(40))
    assert _run(cz.AIColorizeDialog, me) is _OUT
    assert calls == [((_ARR, "heuristic:sepia", 40 / cz._PERCENT_STEPS), {})]


def test_denoise_bilateral_builds_its_options(record):
    calls, patch = record
    patch(dn, "bilateral_denoise")
    me = SimpleNamespace(_method=_w("bilateral"), _blend=_w(50), _radius=_w(4), _sigma=_w(30))
    assert _run(dn.AIDenoiseDialog, me) is _OUT
    ((arr, options), _), = calls
    assert arr is _ARR
    assert options == dn.BilateralOptions(spatial_radius=4, intensity_sigma=30.0,
                                          blend=50 / dn._PERCENT_STEPS)


def test_denoise_onnx_passes_the_model_and_blend(record):
    calls, patch = record
    patch(dn, "onnx_denoise")
    me = SimpleNamespace(_method=_w("/m/d.onnx"), _blend=_w(80))
    assert _run(dn.AIDenoiseDialog, me) is _OUT
    assert calls == [((_ARR, "/m/d.onnx"), {"blend": 80 / dn._PERCENT_STEPS})]


def test_deblur_wiener_builds_its_options(record):
    calls, patch = record
    patch(db, "wiener_deblur")
    me = SimpleNamespace(_method=_w(("wiener", "motion")), _blend=_w(100), _gauss_radius=_w(3),
                         _motion_length=_w(15), _motion_angle=_w(30), _snr=_w(25))
    assert _run(db.AIMotionDeblurDialog, me) is _OUT
    ((_arr, options), _), = calls
    assert options == db.WienerOptions(psf_kind="motion", gaussian_radius=3, motion_length=15,
                                       motion_angle=30, snr_db=25, blend=100 / db._PERCENT_STEPS)


def test_deblur_onnx_passes_the_model_and_blend(record):
    calls, patch = record
    patch(db, "onnx_deblur")
    me = SimpleNamespace(_method=_w(("onnx", "/m/b.onnx")), _blend=_w(60))
    assert _run(db.AIMotionDeblurDialog, me) is _OUT
    assert calls == [((_ARR, "/m/b.onnx"), {"blend": 60 / db._PERCENT_STEPS})]


def test_relight_builds_its_options(record):
    calls, patch = record
    patch(rl, "heuristic_relight")
    me = SimpleNamespace(_method=_w(("heuristic", None)), _azimuth=_w(45), _elevation=_w(30),
                         _intensity=_w(60), _temperature=_w(-10), _blend=_w(100))
    assert _run(rl.AIPortraitRelightDialog, me) is _OUT
    ((_arr, options), _), = calls
    assert options == rl.RelightOptions(azimuth=45.0, elevation=30.0,
                                        intensity=60 / rl._INTENSITY_STEPS, temperature=-10,
                                        blend=100 / rl._PERCENT_STEPS)


def test_smart_resize_builds_its_options(record):
    calls, patch = record
    patch(sr, "smart_resize")
    me = SimpleNamespace(_width=_w(800), _height=_w(600), _boost=_w(150), _protect_alpha=_w(False))
    assert _run(sr.AISmartResizeDialog, me) is _OUT
    ((_arr, options), _), = calls
    assert options == sr.SmartResizeOptions(out_width=800, out_height=600,
                                            energy_boost=150 / sr._BOOST_SLIDER_STEPS,
                                            protect_alpha=False)


def test_style_transfer_passes_the_model_and_intensity(record):
    calls, patch = record
    patch(st, "stylise")
    me = SimpleNamespace(_model=_w("/m/s.onnx"), _intensity=_w(70))
    assert _run(st.StyleTransferDialog, me) is _OUT
    ((_arr, options), _), = calls
    assert options == st.StyleTransferOptions(model_path="/m/s.onnx",
                                              intensity=70 / st._PERCENT_STEPS)


def test_npr_clamps_the_intensity_and_builds_its_options(record):
    calls, patch = record
    patch(npr, "apply_npr_filter")
    me = SimpleNamespace(_style=_w("pencil"), _intensity=_w(10_000), _sigma_s=_w(60),
                         _sigma_r=_w(40), _oil_levels=_w(8), _line_threshold=_w(90))
    assert _run(npr.NPRFiltersDialog, me) is _OUT
    ((_arr, options), _), = calls
    assert options == npr.NPRFilterOptions(style="pencil", intensity=npr.INTENSITY_MAX,
                                           sigma_s=60, sigma_r=40, oil_levels=8, line_threshold=90)


def test_portrait_blurs_around_the_subject_mask(record, monkeypatch):
    calls, patch = record
    mask = np.ones((3, 3), np.uint8)
    monkeypatch.setattr(pm, "_extract_subject_mask", lambda _a: mask)
    patch(pm, "apply_portrait_blur")
    me = SimpleNamespace(_blur=_w(16), _feather=_w(4))
    assert _run(pm.PortraitModeDialog, me) is _OUT
    ((arr, got_mask, options), _), = calls
    assert arr is _ARR and got_mask is mask
    assert options == pm.PortraitBlurOptions(blur_radius=16, feather_radius=4)


def test_outpaint_passes_the_border_width(record):
    calls, patch = record
    patch(op, "outpaint")
    assert _run(op.OutpaintDialog, SimpleNamespace(_padding=_w(96))) is _OUT
    assert calls == [((_ARR, 96), {})]


@pytest.mark.parametrize(("dialog_cls", "suffix"), [
    (cz.AIColorizeDialog, "colorized"), (dn.AIDenoiseDialog, "denoised"),
    (db.AIMotionDeblurDialog, "deblur"), (rl.AIPortraitRelightDialog, "relit"),
    (sr.AISmartResizeDialog, "smart"), (st.StyleTransferDialog, "styled"),
    (npr.NPRFiltersDialog, "npr"), (pm.PortraitModeDialog, "portrait"),
    (op.OutpaintDialog, "outpaint"),
])
def test_each_tool_keeps_its_output_name(dialog_cls, suffix):
    assert dialog_cls.output_suffix == suffix


# --- the workers object_remove and cloud_share still own ---------------------

def _capture(worker):
    captured: list[tuple[bool, str]] = []
    worker.done.connect(lambda ok, msg: captured.append((ok, msg)))
    worker.run()
    assert captured, "worker.run() must always emit done"
    return captured[-1]


class _HardError(Exception):
    """Outside any narrow catch tuple — stands in for onnxruntime / cv2 / PIL errors."""


def _boom_hard(*_a, **_k):
    raise _HardError("unexpected backend failure")


@pytest.mark.parametrize(("compute_attr", "factory"), [
    ("remove_object", lambda m, out: m._RemoveWorker(_ARR.copy(), np.zeros((3, 3), np.uint8), out)),
    ("sam_mask", lambda m, _out: m._SamMaskWorker(_ARR.copy(), (1, 1), "enc", "dec")),
])
def test_object_remove_workers_report_unexpected_errors(compute_attr, factory, qapp, tmp_path,
                                                        monkeypatch):
    monkeypatch.setattr(orm, compute_attr, _boom_hard)
    ok, msg = _capture(factory(orm, str(tmp_path / "x.png")))
    assert ok is False
    assert "unexpected backend failure" in str(msg)


def test_cloud_share_worker_reports_unexpected_error(qapp, monkeypatch):
    """A provider error must report, or the spinner hangs."""
    from cloud_share import cloud_share_plugin as cs
    monkeypatch.setattr(cs._UploadWorker, "_uploader", lambda _self: _boom_hard)
    ok, msg = _capture(cs._UploadWorker("imgur", ["a.png"], {"client_id": "x"}))
    assert ok is False
    assert "unexpected backend failure" in str(msg)


def test_cloud_share_worker_reports_batch_error(qapp, monkeypatch):
    from cloud_share import cloud_share_plugin as cs
    monkeypatch.setattr(cs, "upload_batch", _boom_hard)
    monkeypatch.setattr(cs._UploadWorker, "_uploader", lambda _self: (lambda _p: "link"))
    ok, msg = _capture(cs._UploadWorker("imgur", ["a.png", "b.png"], {"client_id": "x"}))
    assert ok is False
    assert "unexpected backend failure" in str(msg)
