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

from Imervue.plugin.tool_dialog import ToolDialogMixin
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
    ("object_splitter.object_splitter", "ObjectSplitterDialog"),
    ("ai_object_remove.ai_object_remove_plugin", "ObjectRemoveDialog"),
    ("ai_portrait_relight.ai_portrait_relight_plugin", "AIPortraitRelightDialog"),
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



_TOOL_DIALOGS = [
    ("ai_denoise.ai_denoise_plugin", "AIDenoiseDialog"),
    ("ai_colorize.ai_colorize_plugin", "AIColorizeDialog"),
    ("ai_motion_deblur.ai_motion_deblur_plugin", "AIMotionDeblurDialog"),
    ("ai_style_transfer.ai_style_transfer_plugin", "StyleTransferDialog"),
    ("ai_smart_resize.ai_smart_resize_plugin", "AISmartResizeDialog"),
    ("portrait_mode.portrait_mode", "PortraitModeDialog"),
    ("npr_filters.npr_filters_plugin", "NPRFiltersDialog"),
    ("ai_portrait_relight.ai_portrait_relight_plugin", "AIPortraitRelightDialog"),
    ("ai_outpaint.ai_outpaint_plugin", "OutpaintDialog"),
]


@pytest.mark.parametrize("module_name, cls_name", _TOOL_DIALOGS)
def test_tool_dialogs_share_one_done_slot(module_name, cls_name):
    """The wait-then-drop ``_on_done`` lives once, in ``ToolDialogMixin`` (``test_tool_dialog.py``).

    Dropping the only reference to a QThread still returning from run() aborts
    the process; a private copy of the slot in a dialog could drift from that.
    """
    cls = getattr(importlib.import_module(module_name), cls_name)
    assert issubclass(cls, ToolDialogMixin)
    for name in ("_on_done", "_start_worker", "_build_button_box"):
        assert name not in cls.__dict__, name


_OTHER_DONE_SLOTS = [
    ("ai_object_remove.ai_object_remove_plugin", "ObjectRemoveDialog", "_on_sam_done", "_sam_worker"),
    ("ai_object_remove.ai_object_remove_plugin", "ObjectRemoveDialog", "_on_done", "_worker"),
    ("cloud_share.cloud_share_plugin", "CloudShareDialog", "_on_done", "_worker"),
]


@pytest.mark.parametrize("module_name, cls_name, slot, attr", _OTHER_DONE_SLOTS)
def test_other_done_slots_wait_before_dropping(module_name, cls_name, slot, attr):
    """The same wait-then-drop in the slots that are not the shared tool-dialog one."""
    from unittest.mock import MagicMock
    cls = getattr(importlib.import_module(module_name), cls_name)
    host = MagicMock()
    seen = []
    worker = MagicMock()
    worker.wait.side_effect = lambda *_a: seen.append(getattr(host, attr) is worker)
    setattr(host, attr, worker)
    getattr(cls, slot)(host, False, "boom")
    assert seen == [True]
    assert getattr(host, attr) is None
