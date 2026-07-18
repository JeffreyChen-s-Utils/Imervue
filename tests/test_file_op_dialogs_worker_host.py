"""Regression guard: file-operation / scan dialogs use WorkerHostMixin.

Duplicate detection, EXIF strip, image organizer and image sanitize each run a
background QThread. They tore the worker down only in ``closeEvent`` on a bounded
``wait(timeout)`` — a slow-to-abort worker was dropped while still running
(0xC0000409) — and pressing Esc calls ``reject()``, which delivers no
``closeEvent`` and bypassed the teardown entirely. They now inherit
:class:`WorkerHostMixin`, whose reject and closeEvent both join the worker with
an unbounded wait.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from Imervue.plugin.worker_host import WorkerHostMixin

_DIALOGS = [
    ("Imervue.gui.duplicate_detection_dialog", "DuplicateDetectionDialog"),
    ("Imervue.gui.exif_strip_dialog", "ExifStripDialog"),
    ("Imervue.gui.image_organizer_dialog", "ImageOrganizerDialog"),
    ("Imervue.gui.image_sanitize_dialog", "ImageSanitizeDialog"),
    ("Imervue.gui.bookmark_dialog", "BookmarkDialog"),
]


@pytest.mark.parametrize("module_name, cls_name", _DIALOGS)
def test_dialog_inherits_worker_host_mixin(module_name, cls_name):
    cls = getattr(importlib.import_module(module_name), cls_name)
    assert issubclass(cls, WorkerHostMixin)


@pytest.mark.parametrize("module_name, cls_name", _DIALOGS)
def test_dialog_defers_teardown_to_the_mixin(module_name, cls_name):
    cls = getattr(importlib.import_module(module_name), cls_name)
    assert "closeEvent" not in cls.__dict__


def _worker(events, *, abortable):
    ns = SimpleNamespace(
        isRunning=lambda: True,
        requestInterruption=lambda: None,
        disconnect=lambda: None,
        wait=lambda: events.append("wait"),
    )
    if abortable:
        ns.abort = lambda: events.append("abort")
    return ns


def test_duplicate_detection_declares_both_workers():
    from Imervue.gui.duplicate_detection_dialog import DuplicateDetectionDialog
    assert DuplicateDetectionDialog._worker_attrs == ("_worker", "_delete_worker")


def test_duplicate_detection_aborts_scan_but_only_waits_delete():
    """The trash-delete worker (no abort()) must be waited out, never aborted
    mid-delete; the scan worker is aborted for a prompt cancel."""
    from Imervue.gui.duplicate_detection_dialog import DuplicateDetectionDialog
    scan_events: list[str] = []
    delete_events: list[str] = []
    host = SimpleNamespace(
        _worker_attrs=("_worker", "_delete_worker"),
        _worker=_worker(scan_events, abortable=True),
        _delete_worker=_worker(delete_events, abortable=False),
    )
    DuplicateDetectionDialog._stop_worker(host)
    assert scan_events == ["abort", "wait"]
    assert delete_events == ["wait"]          # waited, never aborted
    assert host._worker is None
    assert host._delete_worker is None
