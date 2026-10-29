"""Contracts of the safety_review worker threads.

Pins the parts the other safety_review tests leave open: the argv each
subprocess worker hands ``_runner.py``, how it reads the child's stdout
protocol, how it maps a crash, a non-zero exit or a cancel onto
``result_ready``, the temp path list it cleans up, and the in-process workers'
progress, counts and failure manifest. ``subprocess.Popen`` is replaced by a
fake child, and every worker body runs inline (``worker.run()``) — no thread,
no ML runtime, no real subprocess.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from safety_review import _workers
from safety_review._constants import (
    MODE_ANIME,
    MODE_AUTO,
    SHAPE_ELLIPSE,
    SHAPE_PRECISE,
    SHAPE_RECT,
    STYLE_BLUR,
)

_RUNNER = str(Path(_workers.__file__).resolve().parent / "_runner.py")


class _FakeChild:
    """A finished child process whose stdout yields *lines*."""

    def __init__(self, lines, returncode=0):
        self.stdout = iter(lines)
        self._rc = returncode
        self.returncode = None
        self.calls: list[str] = []

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.calls.append("wait")
        self.returncode = self._rc
        return self._rc

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")


@pytest.fixture
def popen(monkeypatch):
    """Replace ``subprocess.Popen``; ``popen.child`` is the next child handed out."""

    class _Popen:
        child = _FakeChild([])
        argv: list | None = None
        kwargs: dict | None = None
        error: Exception | None = None
        on_spawn = None

        def __call__(self, argv, **kwargs):
            if self.error is not None:
                raise self.error
            self.argv, self.kwargs = argv, kwargs
            if self.on_spawn is not None:
                self.on_spawn(argv)
            return self.child

    fake = _Popen()
    monkeypatch.setattr(subprocess, "Popen", fake)
    return fake


def _single(**kw):
    return _workers._SubprocessSingleWorker(
        "py.exe", "SP", "in.png", "out.png", 12, 3, **kw)


def _batch(paths=("a.png", "b.png", "c.png"), **kw):
    return _workers._SubprocessBatchWorker(
        "py.exe", "SP", list(paths), kw.pop("output_dir", "OUT"), 12, 3,
        kw.pop("overwrite", False), **kw)


def _collect(worker):
    got = {"progress": [], "result": []}
    worker.progress.connect(lambda *a: got["progress"].append(a))
    worker.result_ready.connect(lambda *a: got["result"].append(a))
    return got


# ---------------------------------------------------------------------------
# Public names the dialogs and tests import from ``_workers``
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "_BatchWorker", "_SingleWorker", "_SubprocessBatchWorker",
    "_SubprocessSingleWorker", "_resolve_detector", "_terminate_process",
    "_non_overwrite_destination", "_relative_parent", "_mirrored_destination",
    "_resolve_destination", "_failed_destination", "_copy_failed",
    "_process_with_shape_fallback", "_write_failed_manifest", "_categories_arg",
    "_RUNNER_SCRIPT", "_PLUGIN_DIR", "logger",
])
def test_workers_module_still_exposes(name):
    assert hasattr(_workers, name)


def test_runner_script_is_the_sibling_runner():
    assert str(_workers._RUNNER_SCRIPT) == _RUNNER


# ---------------------------------------------------------------------------
# Subprocess single worker
# ---------------------------------------------------------------------------

def test_single_command_defaults(qapp):
    assert _single()._command() == [
        "py.exe", _RUNNER, "SP", "single", "in.png", "out.png", "12", "3",
        "real", "0.25", "0", "mosaic", "", "rect",
    ]


def test_single_command_carries_every_option(qapp):
    worker = _single(mode=MODE_ANIME, confidence=0.5, expand_pct=7,
                     style=STYLE_BLUR, categories={"b", "a"}, shape=SHAPE_PRECISE)
    assert worker._command()[8:] == ["anime", "0.5", "7", "blur", "a,b", "precise"]


def test_single_spawns_with_piped_stdout_and_no_shell(qapp, popen):
    popen.child = _FakeChild(["OK:x\n"])
    _single().run()
    assert popen.argv == _single()._command()
    assert popen.kwargs["stdout"] is subprocess.PIPE
    assert popen.kwargs["stderr"] is subprocess.STDOUT
    assert "shell" not in popen.kwargs


def test_single_relays_progress_then_ok(qapp, popen):
    popen.child = _FakeChild(["PROGRESS:Loading\n", "\n", "noise\n",
                              "PROGRESS:Detecting\r\n", "OK:done.png\n",
                              "PROGRESS:after\n"])
    worker = _single()
    got = _collect(worker)
    worker.run()
    assert got["progress"] == [("Loading",), ("Detecting",)]
    assert got["result"] == [(True, "done.png", -1)]


def test_single_error_line_reports_failure(qapp, popen):
    popen.child = _FakeChild(["ERROR:no model\n"], returncode=1)
    worker = _single()
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(False, "no model", 0)]


def test_single_clean_exit_without_ok_reports_the_output(qapp, popen):
    popen.child = _FakeChild(["PROGRESS:x\n"], returncode=0)
    worker = _single()
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(True, "out.png", -1)]


def test_single_nonzero_exit_without_terminal_line(qapp, popen):
    popen.child = _FakeChild([], returncode=3)
    worker = _single()
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(False, "Process exited with code 3", 0)]


def test_single_spawn_failure_reports_the_error(qapp, popen, caplog):
    popen.error = OSError("no python")
    worker = _single()
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(False, "no python", 0)]
    assert "Subprocess single worker failed" in caplog.text


def test_single_cancel_terminates_the_child_without_a_result(qapp, popen):
    popen.child = _FakeChild(["PROGRESS:x\n", "OK:y\n"])

    class _Cancelled(_workers._SubprocessSingleWorker):
        def isInterruptionRequested(self):  # noqa: N802 - Qt API
            return True

    worker = _Cancelled("py.exe", "SP", "in.png", "out.png", 12, 3)
    got = _collect(worker)
    worker.run()
    assert got == {"progress": [], "result": []}
    assert popen.child.calls[0] == "terminate"


# ---------------------------------------------------------------------------
# Subprocess batch worker
# ---------------------------------------------------------------------------

def test_batch_command_defaults_turn_none_into_empty(qapp):
    worker = _workers._SubprocessBatchWorker(
        "py.exe", "SP", ["a"], None, 12, 3, False)
    assert worker._command("list.json") == [
        "py.exe", _RUNNER, "SP", "batch", "list.json", "", "12", "3", "False",
        "real", "0.25", "0", "mosaic", "", "", "False", "rect", "", "", "True",
    ]


def test_batch_command_carries_every_option(qapp):
    worker = _batch(output_dir="OUT", overwrite=True, mode=MODE_AUTO,
                    confidence=0.4, expand_pct=5, style=STYLE_BLUR,
                    categories=["z", "y"], source_root="SRC", only_censored=True,
                    shape=SHAPE_ELLIPSE, failed_dir="FAIL", scan_root="SCAN",
                    merge_regions=False)
    assert worker._command("t.json")[4:] == [
        "t.json", "OUT", "12", "3", "True", "auto", "0.4", "5", "blur", "y,z",
        "SRC", "True", "ellipse", "FAIL", "SCAN", "False",
    ]


def test_batch_writes_the_path_list_and_removes_it(qapp, popen):
    seen = {}

    def _spawn(argv):
        seen["path"] = argv[4]
        seen["paths"] = json.loads(Path(argv[4]).read_text(encoding="utf-8"))

    popen.on_spawn = _spawn
    popen.child = _FakeChild(["BATCH_OK:3:0\n"])
    _batch().run()
    assert seen["paths"] == ["a.png", "b.png", "c.png"]
    assert seen["path"].endswith(".json")
    assert not Path(seen["path"]).exists()


def test_batch_relays_progress_keeping_colons_in_the_name(qapp, popen):
    popen.child = _FakeChild([
        "BATCH_PROGRESS:0:3:a.png\n", "BATCH_PROGRESS:1:3:C:/x:y.png\n",
        "BATCH_PROGRESS:bad\n", "BATCH_PROGRESS:x:3:z.png\n", "\n",
        "PROGRESS:Error on b.png: boom\n", "BATCH_OK:2:1\n",
    ])
    worker = _batch()
    got = _collect(worker)
    worker.run()
    assert got["progress"] == [(0, 3, "a.png"), (1, 3, "C:/x:y.png")]
    assert got["result"] == [(2, 1, -1)]


@pytest.mark.parametrize("line", ["BATCH_OK:\n", "BATCH_OK:5\n", "BATCH_OK:a:b\n"])
def test_batch_unreadable_ok_counts_everything_failed(qapp, popen, line):
    popen.child = _FakeChild([line])
    worker = _batch()
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(0, 3, -1)]


def test_batch_error_line_fails_every_path(qapp, popen):
    popen.child = _FakeChild(["ERROR:boom\n", "BATCH_OK:3:0\n"], returncode=1)
    worker = _batch()
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(0, 3, 0)]


@pytest.mark.parametrize("returncode", [0, 2])
def test_batch_without_a_terminal_line_fails_every_path(qapp, popen, returncode):
    popen.child = _FakeChild(["BATCH_PROGRESS:0:3:a.png\n"], returncode=returncode)
    worker = _batch()
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(0, 3, 0)]


def test_batch_spawn_failure_reports_and_cleans_up(qapp, popen, caplog, monkeypatch):
    popen.error = FileNotFoundError("no python")
    created = []
    real_unlink = os.unlink
    monkeypatch.setattr(os, "unlink",
                        lambda p: (created.append(p), real_unlink(p)))
    worker = _batch()
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(0, 3, 0)]
    assert "Subprocess batch worker failed" in caplog.text
    assert len(created) == 1
    assert not Path(created[0]).exists()


def test_batch_cancel_terminates_the_child_without_a_result(qapp, popen):
    popen.child = _FakeChild(["BATCH_PROGRESS:0:3:a.png\n", "BATCH_OK:3:0\n"])

    class _Cancelled(_workers._SubprocessBatchWorker):
        def isInterruptionRequested(self):  # noqa: N802 - Qt API
            return True

    worker = _Cancelled("py.exe", "SP", ["a"], None, 12, 3, False)
    got = _collect(worker)
    worker.run()
    assert got == {"progress": [], "result": []}
    assert popen.child.calls[0] == "terminate"


# ---------------------------------------------------------------------------
# In-process workers
# ---------------------------------------------------------------------------

def test_single_worker_reports_steps_and_count(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(_workers, "_resolve_detector", lambda mode: ("det", mode))
    monkeypatch.setattr(_workers, "_process_single_image",
                        lambda det, src, dst, **kw: calls.append((det, src, dst, kw)) or 4)
    worker = _workers._SingleWorker("in.png", "out.png", 9, 2, mode=MODE_ANIME,
                                    categories={"x"}, shape=SHAPE_ELLIPSE)
    got = _collect(worker)
    worker.run()
    assert [p[0] for p in got["progress"]] == [0, 1, 2, 3]
    assert got["result"] == [(True, "out.png", 4)]
    det, src, dst, kw = calls[0]
    assert (det, src, dst) == (("det", MODE_ANIME), "in.png", "out.png")
    assert kw == {"block_size": 9, "padding": 2, "confidence": 0.25,
                  "expand_pct": 0, "mode": MODE_ANIME, "style": "mosaic",
                  "categories": {"x"}, "shape": SHAPE_ELLIPSE}


def test_single_worker_reports_a_failure(qapp, monkeypatch, caplog):
    def _boom(mode):
        raise RuntimeError("no model")

    monkeypatch.setattr(_workers, "_resolve_detector", _boom)
    worker = _workers._SingleWorker("in.png", "out.png", 9, 2)
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(False, "no model", 0)]
    assert "Single safety review failed" in caplog.text


def test_batch_worker_counts_regions_failures_and_writes_the_manifest(
        qapp, monkeypatch, tmp_path):
    root = tmp_path / "scan"
    (root / "sub").mkdir(parents=True)
    good, bad = root / "good.png", root / "sub" / "bad.png"
    good.write_bytes(b"g")
    bad.write_bytes(b"b")
    out, failed = tmp_path / "out", tmp_path / "failed"
    out.mkdir()
    seen = []

    def _process(det, src, dst, **kw):
        seen.append((src, dst, kw["shape"], kw["only_censored"], kw["merge_regions"]))
        if src == str(bad):
            raise ValueError("corrupt")
        return 2

    monkeypatch.setattr(_workers, "_resolve_detector", lambda mode: object())
    monkeypatch.setattr(_workers, "_process_single_image", _process)
    worker = _workers._BatchWorker(
        [str(good), str(bad)], str(out), 8, 0, False, source_root=str(root),
        only_censored=True, shape=SHAPE_RECT, failed_dir=str(failed),
        scan_root=str(root), merge_regions=False)
    got = _collect(worker)
    worker.run()

    assert got["result"] == [(1, 1, 2)]
    assert [(p[0], p[1], p[2]) for p in got["progress"]] == [
        (0, 2, "good.png"), (1, 2, "bad.png")]
    # rect, rect (retry), ellipse (downgrade) — all to one destination.
    bad_tries = [s for s in seen if s[0] == str(bad)]
    assert [s[2] for s in bad_tries] == [SHAPE_RECT, SHAPE_RECT, SHAPE_ELLIPSE]
    assert {s[1] for s in bad_tries} == {str(out / "sub" / "bad_censored.png")}
    assert seen[0][3:] == (True, False)
    assert (failed / "sub" / "bad.png").read_bytes() == b"b"
    assert (failed / "censor_failed.log").read_text(encoding="utf-8") == "bad.png: corrupt\n"


def test_batch_worker_without_failures_writes_no_manifest(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(_workers, "_resolve_detector", lambda mode: object())
    monkeypatch.setattr(_workers, "_process_single_image", lambda *a, **k: 0)
    failed = tmp_path / "failed"
    worker = _workers._BatchWorker([str(tmp_path / "a.png")], None, 8, 0, True,
                                   failed_dir=str(failed))
    got = _collect(worker)
    worker.run()
    assert got["result"] == [(1, 0, 0)]
    assert not failed.exists()


def test_moved_names_are_the_owning_modules_objects():
    from safety_review import _workers_paths, _workers_subprocess
    for name in ("_SubprocessSingleWorker", "_SubprocessBatchWorker",
                 "_categories_arg", "_terminate_process", "_RUNNER_SCRIPT"):
        assert getattr(_workers, name) is getattr(_workers_subprocess, name)
    for name in ("_resolve_destination", "_copy_failed", "_write_failed_manifest",
                 "_failed_destination", "_relative_parent"):
        assert getattr(_workers, name) is getattr(_workers_paths, name)
