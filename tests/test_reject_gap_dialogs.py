"""Regression guard: dialogs that had a closeEvent but no reject/accept teardown.

These ran a background QThread and cleaned it up only in ``closeEvent``. Esc (or
a Cancel button wired to reject) calls ``reject()``, which delivers no
``closeEvent`` and left the thread running; export even waited on a bounded
``wait(5000)`` that could drop a live thread on timeout. The QThread-subclass
dialogs now inherit :class:`WorkerHostMixin` (reject + close both join the
worker); the moveToThread-based auto-tag dialog got a targeted reject override
and its Close button rewired off accept().
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


def test_auto_tag_has_a_reject_override_and_no_accept_close():
    """The moveToThread auto-tag dialog can't use the QThread-subclass mixin, so
    it gets a bespoke reject() (Esc) plus closeEvent, both tearing the thread
    down; the Close button must no longer map to accept() (which skips them)."""
    import inspect

    from Imervue.gui.auto_tag_dialog import AutoTagDialog

    assert "reject" in AutoTagDialog.__dict__
    assert "closeEvent" in AutoTagDialog.__dict__
    reject_src = inspect.getsource(AutoTagDialog.reject)
    assert "_teardown_thread" in reject_src
    build_src = inspect.getsource(AutoTagDialog)
    assert "close_btn.clicked.connect(self.close)" in build_src
    assert "close_btn.clicked.connect(self.accept)" not in build_src
