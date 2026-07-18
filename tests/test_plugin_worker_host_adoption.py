"""Regression guard: worker-owning plugin dialogs use the shared WorkerHostMixin.

Each of these dialogs starts a background QThread and previously cleaned it up
only in ``closeEvent``; because Cancel calls ``reject()`` (which delivers no
``closeEvent``) the worker kept running and was destroyed with the dialog,
aborting the process (0xC0000409). They now inherit
:class:`WorkerHostMixin`, whose ``reject`` and ``closeEvent`` both stop the
worker. This test fails if a dialog stops inheriting the mixin or re-introduces
a bespoke ``closeEvent`` / ``_wait_worker`` that would shadow it.
"""
from __future__ import annotations

import importlib

import pytest

from Imervue.plugin.worker_host import WorkerHostMixin

_DIALOGS = [
    ("ai_denoise.ai_denoise_plugin", "AIDenoiseDialog"),
    ("ai_colorize.ai_colorize_plugin", "AIColorizeDialog"),
    ("ai_motion_deblur.ai_motion_deblur_plugin", "AIMotionDeblurDialog"),
    ("ai_style_transfer.ai_style_transfer_plugin", "StyleTransferDialog"),
    ("ai_smart_resize.ai_smart_resize_plugin", "AISmartResizeDialog"),
    ("ai_outpaint.ai_outpaint_plugin", "OutpaintDialog"),
    ("portrait_mode.portrait_mode", "PortraitModeDialog"),
    ("npr_filters.npr_filters_plugin", "NPRFiltersDialog"),
]


@pytest.mark.parametrize("module_name, cls_name", _DIALOGS)
def test_dialog_inherits_worker_host_mixin(module_name, cls_name):
    cls = getattr(importlib.import_module(module_name), cls_name)
    assert issubclass(cls, WorkerHostMixin)


@pytest.mark.parametrize("module_name, cls_name", _DIALOGS)
def test_dialog_defers_teardown_to_the_mixin(module_name, cls_name):
    cls = getattr(importlib.import_module(module_name), cls_name)
    # A bespoke override here would shadow the mixin's crash-safe teardown.
    assert "closeEvent" not in cls.__dict__
    assert "_wait_worker" not in cls.__dict__
