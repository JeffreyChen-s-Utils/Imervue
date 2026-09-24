"""Image plugins name their result with Imervue's never-overwrite helper, and still load without it.

A second run of AI Colorize, AI Denoise ... saved over the first run's
``photo_colorized.png``. The plugins now take ``output_path`` from
``Imervue.gui._apply_save``; on an install older than 1.0.75, which has no such
helper, they fall back to the plain name instead of failing to load
(``architecture.md`` §6: a newly downloaded plugin still runs on older installs).
"""
from __future__ import annotations

import builtins
import importlib
from pathlib import Path

import pytest

from Imervue.gui._apply_save import output_path

_PLUGIN_MODULES = [
    "ai_colorize.ai_colorize_plugin", "ai_denoise.ai_denoise_plugin",
    "ai_motion_deblur.ai_motion_deblur_plugin", "ai_portrait_relight.ai_portrait_relight_plugin",
    "ai_smart_resize.ai_smart_resize_plugin", "ai_style_transfer.ai_style_transfer_plugin",
    "npr_filters.npr_filters_plugin", "portrait_mode.portrait_mode",
    "ai_object_remove.ai_object_remove_plugin", "ai_outpaint.ai_outpaint_plugin",
]


@pytest.mark.parametrize("name", _PLUGIN_MODULES)
def test_each_plugin_uses_the_never_overwrite_helper(name):
    module = importlib.import_module(name)
    assert module._output_path is output_path  # noqa: SLF001


def test_an_older_imervue_without_the_helper_still_loads_the_plugin(monkeypatch):
    """The fallback keeps the plain name the plugins wrote before."""
    real_import = builtins.__import__

    def no_output_path(name, globals_=None, locals_=None, fromlist=(), level=0):
        if name == "Imervue.gui._apply_save" and fromlist and "output_path" in fromlist:
            raise ImportError("cannot import name 'output_path'")
        return real_import(name, globals_, locals_, fromlist, level)

    module = importlib.import_module("ai_colorize.ai_colorize_plugin")
    monkeypatch.setattr(builtins, "__import__", no_output_path)
    try:
        importlib.reload(module)
        assert module._output_path is not output_path  # noqa: SLF001
        assert Path(module._output_path("/photos/a.jpg", "colorized")).name == "a_colorized.png"  # noqa: SLF001
    finally:
        monkeypatch.setattr(builtins, "__import__", real_import)
        importlib.reload(module)
    assert module._output_path is output_path  # noqa: SLF001
