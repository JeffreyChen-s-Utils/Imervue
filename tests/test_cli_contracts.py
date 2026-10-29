"""CLI validation, cancellation and publication ordering contracts."""
import concurrent.futures
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from Imervue import cli


@pytest.mark.parametrize("raw", [None, ""])
def test_optional_output_directory_is_unset(raw):
    assert cli._validated_out_dir(raw) is None


@pytest.mark.parametrize("raw", ["a/../b", "../b", "a/.."])
def test_path_validation_keeps_context_diagnostics(raw):
    with pytest.raises(ValueError, match="--out must not contain"):
        cli._validated_out_dir(raw)
    with pytest.raises(ValueError, match="path must not contain"):
        cli._checked_path(raw)


@pytest.mark.parametrize("raw", [".", "a/.../b", "a/b", ""])
def test_checked_paths_are_not_resolved_or_normalized(raw):
    assert cli._checked_path(raw) == Path(raw)


def test_pipeline_validation_keeps_all_errors_in_order():
    errors = cli.validate_pipeline([None, {"op": "absent"}] + [{"op": "invert"}] * 49)
    assert errors[0] == "too many steps (51 > 50)"
    assert errors[1] == "step 0: each step must be an object with an 'op' name"
    assert errors[2].startswith("step 1: unknown op 'absent'; known:")
    assert len(errors) == 3


def test_inline_cancellation_keeps_completed_prefix():
    cancel, visited = Event(), []

    def work(value):
        visited.append(value)
        if value == 2:
            raise KeyboardInterrupt

    assert cli._run_outputs([1, 2, 3], work, 1, cancel) is True
    assert cancel.is_set() and visited == [1, 2]


def test_threaded_cancel_is_set_before_waiting_for_encoder(monkeypatch):
    real_executor = concurrent.futures.ThreadPoolExecutor
    started, release, finished, cancelled = Event(), Event(), Event(), Event()
    events = []

    class InterruptFuture:
        def __init__(self, future):
            self.future = future

        def result(self):
            assert started.wait(5)
            raise KeyboardInterrupt

        def cancel(self):
            assert cancelled.is_set()
            events.append("cancel")
            return self.future.cancel()

    class Pool:
        def __init__(self, **kwargs):
            self.pool = real_executor(**kwargs)

        def __enter__(self):
            self.pool.__enter__()
            return self

        def submit(self, work, item):
            return InterruptFuture(self.pool.submit(work, item))

        def __exit__(self, *args):
            try:
                assert cancelled.is_set()
                assert not finished.is_set()
                events.append("join")
            finally:
                release.set()
                self.pool.__exit__(*args)

    def encode(_item):
        started.set()
        assert release.wait(5)
        finished.set()

    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", Pool)
    assert cli._run_outputs([1], encode, 2, cancelled) is True
    assert finished.is_set() and events == ["cancel", "join"]


@pytest.mark.parametrize("workers", [1, 2])
def test_unexpected_worker_error_propagates(workers):
    def fail(_item):
        raise RuntimeError("encoder failure")

    cancel = Event()
    with pytest.raises(RuntimeError, match="encoder failure"):
        cli._run_outputs([1], fail, workers, cancel)
    assert not cancel.is_set()


def test_report_failure_precedes_interrupted_exit(monkeypatch, tmp_path, capsys):
    args = SimpleNamespace(out=None, result_report=str(tmp_path / "result.json"), jobs=1)
    owner = cli._write.__globals__
    monkeypatch.setitem(owner, "_run_outputs", lambda *_args: True)

    def fail_report(_path, _items):
        raise OSError("report unavailable")

    monkeypatch.setitem(owner, "write_report", fail_report)
    assert cli._write(args, [tmp_path / "image.png"], None, "_out", lambda _a: None) == 1
    captured = capsys.readouterr()
    assert "cancelled:" in captured.out
    assert captured.err.endswith("error: result report: report unavailable\n")


def test_pipeline_validation_precedes_input_selection(tmp_path, capsys):
    pipeline = tmp_path / "invalid.json"
    pipeline.write_text('[{"op": "absent"}]', encoding="utf-8")
    assert cli.main(["pipeline", str(pipeline), str(tmp_path / "missing.png")]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("pipeline error:")
    assert "no input images found" not in captured.err


def test_report_conflict_is_checked_before_operation(monkeypatch, tmp_path, capsys):
    src = tmp_path / "image.png"
    args = SimpleNamespace(out=None, result_report=str(src), jobs=1)
    calls = []
    monkeypatch.setitem(cli._write.__globals__, "_run_outputs", lambda *_args: calls.append(1))
    assert cli._write(args, [src], None, "_out", lambda _a: None) == 2
    assert calls == []
    assert capsys.readouterr().err == "error: Result report must differ from every source and output\n"
