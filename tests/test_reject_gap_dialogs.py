"""Regression guard: dialogs that had a closeEvent but no reject/accept teardown.

These ran a background QThread and cleaned it up only in ``closeEvent``. Esc (or
a Cancel button wired to reject) calls ``reject()``, which delivers no
``closeEvent`` and left the thread running; export even waited on a bounded
``wait(5000)`` that could drop a live thread on timeout. The QThread-subclass
dialogs inherit :class:`WorkerHostMixin` for cancellation and retirement.
Auto-tag Esc and Close-button behavior is exercised with a real worker in
``test_full_review_ui_failures.py``.
"""
from __future__ import annotations

import importlib

import pytest

from Imervue.plugin.worker_host import WorkerHostMixin

# (module, class, expected _worker_attrs)
_MIXIN_DIALOGS = [
    ("ai_upscale_dialog", "AIUpscaleDialog", ("_worker",)),
    ("batch_convert_dialog", "BatchConvertDialog", ("_worker",)),
    ("deflicker_dialog", "DeflickerDialog", ("_worker",)),
    ("optimize_dialog", "OptimizeDialog", ("_worker",)),
    ("export_dialog", "ExportDialog", ("_size_worker",)),
    ("library_search_dialog", "LibrarySearchDialog", ("_thread",)),
]


def _cls(module_name, cls_name):
    return getattr(importlib.import_module(f"Imervue.gui.{module_name}"), cls_name)


@pytest.mark.parametrize("module_name, cls_name, attrs", _MIXIN_DIALOGS)
def test_dialog_inherits_mixin_with_expected_worker_attrs(module_name, cls_name, attrs):
    cls = _cls(module_name, cls_name)
    assert issubclass(cls, WorkerHostMixin)
    assert "closeEvent" not in cls.__dict__
    assert cls._worker_attrs == attrs
