"""The ONNX paths of the AI plugins must offer to install onnxruntime first.

Picking an ONNX model used to fail with an ImportError toast when
onnxruntime was missing, with no way to install it. Each dialog names the
packages its current settings need (``_required_packages``); the shared
``ToolDialogMixin._commit`` offers to install them before starting the worker,
and skips the worker when the install answer arrives after the dialog closed
(``test_tool_dialog.py``). The per-dialog choice is tested on a stand-in
``self`` so no dialog (and no model discovery or image load) has to be built.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from Imervue.plugin import tool_dialog

ONNX = [("onnxruntime", "onnxruntime")]

# module, dialog class, combo userData for the ONNX branch, for the plain branch
COMMIT_GATED = [
    ("ai_colorize.ai_colorize_plugin", "AIColorizeDialog", "onnx:/m/c.onnx", "heuristic:warm"),
    ("ai_denoise.ai_denoise_plugin", "AIDenoiseDialog", "/m/d.onnx", "bilateral"),
    ("ai_motion_deblur.ai_motion_deblur_plugin", "AIMotionDeblurDialog",
     ("onnx", "/m/b.onnx"), ("wiener", "gaussian")),
    ("ai_portrait_relight.ai_portrait_relight_plugin", "AIPortraitRelightDialog",
     ("onnx", "/m/r.onnx"), ("heuristic", None)),
]


@pytest.fixture
def ensure(monkeypatch):
    calls: list = []

    def patch(module):
        monkeypatch.setattr(
            module, "ensure_dependencies",
            lambda parent, packages, on_ready: calls.append((parent, packages, on_ready)),
        )

    return calls, patch


def _dialog_class(module_name: str, class_name: str):
    module = importlib.import_module(module_name)
    return module, getattr(module, class_name)


def _stand_in(method_data, **extra):
    return SimpleNamespace(
        _worker=None,
        _method=SimpleNamespace(currentData=lambda: method_data),
        _start_worker=MagicMock(),
        **extra,
    )


@pytest.mark.parametrize(("module_name", "class_name", "onnx_data", "plain_data"), COMMIT_GATED)
def test_only_the_onnx_branch_needs_onnxruntime(module_name, class_name, onnx_data, plain_data):
    module, dialog = _dialog_class(module_name, class_name)
    assert module.ONNX_PACKAGES == ONNX
    onnx = SimpleNamespace(_method=SimpleNamespace(currentData=lambda: onnx_data))
    plain = SimpleNamespace(_method=SimpleNamespace(currentData=lambda: plain_data))
    assert dialog._required_packages(onnx) == ONNX
    assert dialog._required_packages(plain) == []


# ---------------------------------------------------------------------------
# ai_style_transfer: ONNX only
# ---------------------------------------------------------------------------

def test_style_transfer_always_needs_onnxruntime():
    _module, dialog = _dialog_class("ai_style_transfer.ai_style_transfer_plugin",
                                    "StyleTransferDialog")
    assert dialog._required_packages(SimpleNamespace()) == ONNX


def test_style_transfer_with_a_model_offers_onnxruntime(qapp, tmp_path, ensure):
    calls, patch = ensure
    patch(tool_dialog)
    _module, dialog_cls = _dialog_class("ai_style_transfer.ai_style_transfer_plugin",
                                        "StyleTransferDialog")
    dialog = dialog_cls(object(), str(tmp_path / "a.png"))
    try:
        dialog._model.addItem("model", userData="/m/s.onnx")
        dialog._model.setCurrentIndex(dialog._model.count() - 1)
        dialog._commit()
        assert calls == [(dialog, ONNX, dialog._start_worker_if_open)]
    finally:
        dialog.deleteLater()


def test_style_transfer_without_model_reports_and_skips_check(ensure):
    calls, patch = ensure
    patch(tool_dialog)
    _module, dialog = _dialog_class("ai_style_transfer.ai_style_transfer_plugin",
                                    "StyleTransferDialog")
    me = SimpleNamespace(_worker=None, _model=SimpleNamespace(currentData=lambda: None),
                         _notify_failure=MagicMock())
    dialog._commit(me)
    assert calls == []
    me._notify_failure.assert_called_once_with("no model selected")


# ---------------------------------------------------------------------------
# ai_object_remove: SAM click and ONNX inpaint
# ---------------------------------------------------------------------------

_OBJECT_REMOVE = ("ai_object_remove.ai_object_remove_plugin", "ObjectRemoveDialog")


class _Mask:
    def __init__(self, selected: bool):
        self._selected = selected

    def any(self) -> bool:
        return self._selected


def test_object_remove_sam_click_waits_for_the_dependency_check(ensure):
    calls, patch = ensure
    module, dialog = _dialog_class(*_OBJECT_REMOVE)
    patch(module)
    me = SimpleNamespace(_sam_worker=None, _start_sam=MagicMock())
    dialog._run_sam(me, (3, 4))
    assert [(p, pk) for p, pk, _cb in calls] == [(me, ONNX)]
    me._start_sam.assert_not_called()
    calls[0][2]()
    me._start_sam.assert_called_once_with((3, 4))


def test_object_remove_sam_click_ignored_while_busy(ensure):
    calls, patch = ensure
    module, dialog = _dialog_class(*_OBJECT_REMOVE)
    patch(module)
    dialog._run_sam(SimpleNamespace(_sam_worker=object()), (1, 1))
    assert calls == []


@pytest.mark.parametrize(("method_data", "gated"), [("/m/lama.onnx", True), (None, False)])
def test_object_remove_commit_gates_only_the_onnx_inpaint(ensure, method_data, gated):
    calls, patch = ensure
    module, dialog = _dialog_class(*_OBJECT_REMOVE)
    patch(module)
    me = _stand_in(method_data, _mask=_Mask(selected=True))
    dialog._commit(me)
    assert bool(calls) is gated
    assert me._start_worker.called is not gated


def test_object_remove_commit_without_selection_notifies(ensure):
    calls, patch = ensure
    module, dialog = _dialog_class(*_OBJECT_REMOVE)
    patch(module)
    me = _stand_in("/m/lama.onnx", _mask=_Mask(selected=False), _notify=MagicMock())
    dialog._commit(me)
    assert calls == []
    me._notify.assert_called_once()
    me._start_worker.assert_not_called()


def test_object_remove_starts_skipped_once_dialog_is_closed():
    _module, dialog = _dialog_class(*_OBJECT_REMOVE)
    me = SimpleNamespace(_worker=None, _sam_worker=None, _mask=_Mask(True),
                         isVisible=lambda: False)
    dialog._start_worker(me)
    dialog._start_sam(me, (0, 0))
    assert me._worker is None
    assert me._sam_worker is None
