"""Regression guard: the GUI tool dialogs that run a background QThread use the
shared WorkerHostMixin for teardown.

Each of these dialogs (HDR merge, panorama, focus/exposure stacking, healing /
clone brushes, lens correction, sky replace, crop-straighten, noise/sharpen,
print layout) starts a compute worker and is shown as a throwaway
``open_x(viewer).exec()`` temporary. They had no closeEvent or reject teardown,
so cancelling or closing mid-run destroyed the live thread and could abort the
process. They now inherit :class:`WorkerHostMixin`, whose reject and closeEvent
both join the worker. This fails if a dialog stops inheriting the mixin or
re-introduces a shadowing ``closeEvent``.
"""
from __future__ import annotations

import importlib

import pytest

from Imervue.plugin.worker_host import WorkerHostMixin

_DIALOGS = [
    ("Imervue.gui.hdr_merge_dialog", "HdrMergeDialog"),
    ("Imervue.gui.panorama_dialog", "PanoramaDialog"),
    ("Imervue.gui.focus_stack_dialog", "FocusStackDialog"),
    ("Imervue.gui.stack_blend_dialog", "StackBlendDialog"),
    ("Imervue.gui.healing_brush_dialog", "HealingBrushDialog"),
    ("Imervue.gui.clone_stamp_dialog", "CloneStampDialog"),
    ("Imervue.gui.lens_correction_dialog", "LensCorrectionDialog"),
    ("Imervue.gui.sky_replace_dialog", "SkyReplaceDialog"),
    ("Imervue.gui.crop_straighten_dialog", "CropStraightenDialog"),
    ("Imervue.gui.noise_sharpen_dialog", "NoiseSharpenDialog"),
    ("Imervue.gui.print_layout_dialog", "PrintLayoutDialog"),
]


@pytest.mark.parametrize("module_name, cls_name", _DIALOGS)
def test_dialog_inherits_worker_host_mixin(module_name, cls_name):
    cls = getattr(importlib.import_module(module_name), cls_name)
    assert issubclass(cls, WorkerHostMixin)


@pytest.mark.parametrize("module_name, cls_name", _DIALOGS)
def test_dialog_defers_teardown_to_the_mixin(module_name, cls_name):
    cls = getattr(importlib.import_module(module_name), cls_name)
    assert "closeEvent" not in cls.__dict__
