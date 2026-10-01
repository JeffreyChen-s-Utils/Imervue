"""The shared plugin tool dialog: OK → dependency check → worker → toast.

Nine plugin dialogs used to carry their own copy of this flow; the mixin is now
the one place it lives, so each step is covered here on a small dialog.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from Imervue.gui._apply_save import EffectWorker
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin import tool_dialog
from Imervue.plugin.tool_dialog import ToolDialogMixin
from Imervue.plugin.worker_host import WorkerHostMixin
from tests._toast_spy import ToastSpy


class _Tool(ToolDialogMixin, QDialog):
    output_suffix = "inverted"
    failed_key = "test_tool_failed"
    failed_text = "Invert failed"
    done_key = "test_tool_done"
    done_text = "Inverted into {path}"

    def __init__(self, path: str, packages=()):
        super().__init__(None)
        self._toast = ToastSpy()
        self._viewer = SimpleNamespace(main_window=SimpleNamespace(toast=self._toast))
        self._path = path
        self._packages = list(packages)

    def _required_packages(self):
        return self._packages

    def _transform(self):
        return lambda rgba: 255 - rgba


@pytest.fixture
def source(tmp_path) -> str:
    path = tmp_path / "photo.png"
    Image.fromarray(np.full((4, 4, 4), 10, np.uint8), mode="RGBA").save(path)
    return str(path)


@pytest.fixture
def no_thread(monkeypatch):
    """Stop ``_start_worker`` from also starting the thread the tests run inline."""
    monkeypatch.setattr(EffectWorker, "start", lambda _self: None)


def test_the_mixin_brings_the_worker_teardown():
    assert issubclass(ToolDialogMixin, WorkerHostMixin)


def test_ok_runs_the_transform_saves_beside_the_source_and_closes(qapp, source, no_thread):
    dialog = _Tool(source)
    try:
        dialog._commit()
        worker = dialog._worker
        assert isinstance(worker, EffectWorker)
        worker.run()                                   # inline: emits done(True, path)
        saved = Path(source).with_name("photo_inverted.png")
        assert np.asarray(Image.open(saved))[0, 0, 0] == 245
        assert dialog._worker is None
        assert dialog._toast.calls == [("info", "Inverted into photo_inverted.png")]
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()


def test_a_second_run_keeps_the_first_result(qapp, source, no_thread):
    Path(source).with_name("photo_inverted.png").write_bytes(b"first")
    dialog = _Tool(source)
    try:
        dialog._commit()
        dialog._worker.run()
        assert Path(source).with_name("photo_inverted.png").read_bytes() == b"first"
        assert Path(source).with_name("photo_inverted_1.png").exists()
    finally:
        dialog.deleteLater()


def test_a_failure_toasts_the_reason_and_keeps_the_dialog_open(qapp, tmp_path, no_thread):
    dialog = _Tool(str(tmp_path / "missing.png"))
    try:
        dialog._commit()
        dialog._worker.run()
        (kind, text), = dialog._toast.calls
        assert kind == "error"
        assert text.startswith("Invert failed: ")
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert dialog._worker is None
    finally:
        dialog.deleteLater()


def test_toast_texts_follow_the_ui_language(qapp, source, no_thread, monkeypatch):
    monkeypatch.setitem(language_wrapper.language_word_dict, "test_tool_done", "已存成 {path}")
    dialog = _Tool(source)
    try:
        dialog._commit()
        dialog._worker.run()
        assert dialog._toast.calls == [("info", "已存成 photo_inverted.png")]
    finally:
        dialog.deleteLater()


def test_commit_is_ignored_while_a_worker_runs(qapp, source):
    dialog = _Tool(source)
    busy = object()
    dialog._worker = busy
    try:
        dialog._commit()
        assert dialog._worker is busy
    finally:
        dialog._worker = None
        dialog.deleteLater()


def test_a_needed_package_is_offered_before_the_worker_starts(qapp, source, monkeypatch):
    calls = []
    monkeypatch.setattr(tool_dialog, "ensure_dependencies",
                        lambda parent, packages, on_ready: calls.append((parent, packages, on_ready)))
    onnx = [("onnxruntime", "onnxruntime")]
    dialog = _Tool(source, packages=onnx)
    try:
        dialog._commit()
        assert calls == [(dialog, onnx, dialog._start_worker_if_open)]
        assert dialog._worker is None
    finally:
        dialog.deleteLater()


def test_no_needed_package_starts_at_once(qapp, source, monkeypatch, no_thread):
    monkeypatch.setattr(tool_dialog, "ensure_dependencies", MagicMock())
    dialog = _Tool(source)
    try:
        dialog._commit()
        tool_dialog.ensure_dependencies.assert_not_called()
        assert isinstance(dialog._worker, EffectWorker)
    finally:
        dialog._worker = None
        dialog.deleteLater()


@pytest.mark.parametrize(("visible", "started"), [(False, False), (True, True)])
def test_the_install_answer_starts_the_worker_only_while_the_dialog_is_open(visible, started):
    host = SimpleNamespace(isVisible=lambda: visible, _start_worker=MagicMock())
    ToolDialogMixin._start_worker_if_open(host)
    assert host._start_worker.called is started


def test_done_waits_for_the_thread_before_dropping_it():
    """Dropping the only reference to a QThread still returning from run() aborts the process."""
    events = []

    class _Worker:
        def wait(self):
            events.append("wait" if host._worker is self else "wait after drop")

    host = SimpleNamespace(_viewer=None, failed_key="", failed_text="Failed",
                           done_key="k", done_text="Saved {path}", accept=lambda: events.append("accept"))
    host._worker = _Worker()
    ToolDialogMixin._on_done(host, True, "out.png")
    assert events == ["wait", "accept"]
    assert host._worker is None


def test_notify_failure_prefixes_the_message(qapp, source):
    dialog = _Tool(source)
    try:
        dialog._notify_failure("no model selected")
        assert dialog._toast.calls == [("error", "Invert failed: no model selected")]
    finally:
        dialog.deleteLater()


def test_ok_and_cancel_buttons(qapp, source):
    dialog = _Tool(source)
    commits = []
    dialog._commit = lambda: commits.append(True)
    try:
        box = dialog._build_button_box()
        box.button(QDialogButtonBox.StandardButton.Ok).click()
        assert commits == [True]
        box.button(QDialogButtonBox.StandardButton.Cancel).click()
        assert dialog.result() == QDialog.DialogCode.Rejected
    finally:
        dialog.deleteLater()


def test_the_transform_must_be_supplied(qapp, source):
    with pytest.raises(NotImplementedError):
        ToolDialogMixin._transform(SimpleNamespace())


def test_show_toast_without_a_main_window_does_nothing():
    tool_dialog.show_toast(SimpleNamespace(), "nobody listens")
    tool_dialog.show_toast(None, "nobody listens", error=True)
