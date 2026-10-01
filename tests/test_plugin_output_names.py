"""Image plugins name their result with Imervue's never-overwrite helper.

A second run of AI Colorize, AI Denoise ... saved over the first run's
``photo_colorized.png``. The tool dialogs now save through the shared
``ToolDialogMixin``, and AI Object Remove calls the same ``output_path``, so a
second run gets ``photo_colorized_1.png``. Both need plugin API 2, declared in
their ``plugin.json`` (``test_plugin_api.py``).
"""
from __future__ import annotations

import importlib

import pytest

from Imervue.gui._apply_save import output_path
from Imervue.plugin import tool_dialog
from Imervue.plugin.tool_dialog import ToolDialogMixin

_TOOL_DIALOGS = [
    ("ai_colorize.ai_colorize_plugin", "AIColorizeDialog"),
    ("ai_denoise.ai_denoise_plugin", "AIDenoiseDialog"),
    ("ai_motion_deblur.ai_motion_deblur_plugin", "AIMotionDeblurDialog"),
    ("ai_portrait_relight.ai_portrait_relight_plugin", "AIPortraitRelightDialog"),
    ("ai_smart_resize.ai_smart_resize_plugin", "AISmartResizeDialog"),
    ("ai_style_transfer.ai_style_transfer_plugin", "StyleTransferDialog"),
    ("npr_filters.npr_filters_plugin", "NPRFiltersDialog"),
    ("portrait_mode.portrait_mode", "PortraitModeDialog"),
    ("ai_outpaint.ai_outpaint_plugin", "OutpaintDialog"),
]


def test_the_shared_dialog_names_with_the_never_overwrite_helper():
    assert tool_dialog.output_path is output_path


@pytest.mark.parametrize(("module_name", "class_name"), _TOOL_DIALOGS)
def test_each_tool_dialog_saves_through_the_shared_dialog(module_name, class_name):
    cls = getattr(importlib.import_module(module_name), class_name)
    assert issubclass(cls, ToolDialogMixin)
    assert not hasattr(importlib.import_module(module_name), "_output_path")


def test_object_remove_uses_the_never_overwrite_helper():
    module = importlib.import_module("ai_object_remove.ai_object_remove_plugin")
    assert module.output_path is output_path
