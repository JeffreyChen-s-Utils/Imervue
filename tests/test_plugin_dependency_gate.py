"""Plugins that always need a heavy package must offer to install it first.

npr_filters (OpenCV) and portrait_mode (rembg + onnxruntime) used to open
their dialog straight away and only failed at Apply time with an ImportError
the user had no way to fix. Opening the dialog now goes through the host's
``ensure_dependencies``, which installs what is missing before the callback.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

GATED = [
    ("npr_filters.npr_filters_plugin", "NPRFiltersPlugin", "NPRFiltersDialog",
     [("cv2", "opencv-python")]),
    ("portrait_mode.portrait_mode", "PortraitModePlugin", "PortraitModeDialog",
     [("rembg", "rembg"), ("onnxruntime", "onnxruntime")]),
]


def _plugin(module, class_name, images, current_index=0):
    main_window = MagicMock()
    main_window.viewer = SimpleNamespace(
        model=SimpleNamespace(images=images), current_index=current_index,
    )
    return getattr(module, class_name)(main_window)


@pytest.fixture
def gate(monkeypatch):
    calls: list = []
    dialogs: list = []

    def install(module, dialog_name):
        monkeypatch.setattr(
            module, "ensure_dependencies",
            lambda parent, packages, on_ready: calls.append((parent, packages, on_ready)),
        )

        class _FakeDialog:
            def __init__(self, viewer, path):
                self.args = (viewer, path)
                self.executed = False
                dialogs.append(self)

            def exec(self):
                self.executed = True

        monkeypatch.setattr(module, dialog_name, _FakeDialog)

    return calls, dialogs, install


@pytest.mark.parametrize(("module_name", "class_name", "dialog_name", "packages"), GATED)
def test_open_dialog_checks_dependencies_first(gate, module_name, class_name, dialog_name,
                                               packages):
    calls, dialogs, install = gate
    module = importlib.import_module(module_name)
    install(module, dialog_name)
    plugin = _plugin(module, class_name, ["a.png", "b.png"], current_index=1)
    plugin._open_dialog()
    assert packages == module.REQUIRED_PACKAGES
    assert len(calls) == 1
    parent, requested, on_ready = calls[0]
    assert parent is plugin.main_window
    assert requested == packages
    assert dialogs == []                     # nothing opens before the check passes
    on_ready()
    assert len(dialogs) == 1
    assert dialogs[0].args == (plugin.viewer, "b.png")
    assert dialogs[0].executed


@pytest.mark.parametrize(("module_name", "class_name", "dialog_name", "packages"), GATED)
@pytest.mark.parametrize(("images", "index"), [([], 0), (["a.png"], 1), (["a.png"], -1)])
def test_open_dialog_without_current_image_does_nothing(gate, module_name, class_name,
                                                        dialog_name, packages, images, index):
    del packages
    calls, dialogs, install = gate
    module = importlib.import_module(module_name)
    install(module, dialog_name)
    _plugin(module, class_name, images, current_index=index)._open_dialog()
    assert calls == []
    assert dialogs == []
