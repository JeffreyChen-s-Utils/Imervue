"""Tests for ``_InstallWorker``: the pip commands it runs and what it reports.

``run()`` is called directly on the test thread and ``_run_with_live_output``
is replaced, so no subprocess starts.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from Imervue.plugin import pip_installer
from Imervue.plugin.pip_constraints import PIP_CONSTRAINTS


@pytest.fixture
def run_worker(qapp, monkeypatch):
    """Run a worker over *names*; return (commands, constraint texts, results)."""

    def _run(names, *, outcome=lambda _cmd: 0):
        commands: list[list[str]] = []
        texts: list[str] = []
        results: list[tuple[bool, str]] = []

        def fake_run(_self, cmd, timeout=600):
            commands.append(cmd)
            texts.append(Path(cmd[cmd.index("-c") + 1]).read_text(encoding="utf-8"))
            return outcome(cmd)

        monkeypatch.setattr(pip_installer._InstallWorker, "_run_with_live_output", fake_run)
        worker = pip_installer._InstallWorker(names, "python.exe")
        worker.result_ready.connect(lambda ok, msg: results.append((ok, msg)))
        worker.run()
        worker.deleteLater()
        return commands, texts, results

    return _run


def test_every_install_runs_under_the_constraints(run_worker):
    commands, texts, results = run_worker(["nudenet", "onnxruntime"])
    assert [c[-1] for c in commands] == ["nudenet", "onnxruntime"]
    assert all(t.splitlines() == list(PIP_CONSTRAINTS) for t in texts)
    assert results == [(True, "All packages installed successfully!")]


def test_constraints_file_is_removed_afterwards(run_worker):
    commands, _texts, _results = run_worker(["nudenet"])
    constraints = Path(commands[0][commands[0].index("-c") + 1])
    assert not constraints.exists()
    assert not constraints.parent.exists()


def test_stops_at_the_first_failure(run_worker):
    commands, _texts, results = run_worker(
        ["a", "b", "c"], outcome=lambda cmd: 1 if cmd[-1] == "b" else 0)
    assert [c[-1] for c in commands] == ["a", "b"]
    assert results == [(False, "Failed to install b (exit code 1)")]


def test_missing_python_is_reported(run_worker):
    def outcome(_cmd):
        raise FileNotFoundError
    _commands, _texts, results = run_worker(["a"], outcome=outcome)
    assert results == [(False, "Python not found: python.exe")]


def test_other_errors_are_reported(run_worker):
    def outcome(_cmd):
        raise OSError("disk full")
    _commands, _texts, results = run_worker(["a"], outcome=outcome)
    assert results == [(False, "disk full")]


def test_no_packages_still_succeeds(run_worker):
    commands, _texts, results = run_worker([])
    assert commands == []
    assert results == [(True, "All packages installed successfully!")]


def test_temp_dir_failure_is_reported(run_worker, monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("no temp dir")
    monkeypatch.setattr(pip_installer.tempfile, "TemporaryDirectory", boom)
    commands, _texts, results = run_worker(["a"])
    assert commands == []
    assert results == [(False, "no temp dir")]


def test_frozen_build_installs_into_the_target_dir(run_worker, monkeypatch, tmp_path):
    from Imervue.system import app_paths
    target = tmp_path / "site"
    monkeypatch.setattr(pip_installer, "_is_frozen", lambda: True)
    monkeypatch.setattr(app_paths, "frozen_site_packages", lambda: target)
    monkeypatch.setattr(pip_installer.sys, "path", list(pip_installer.sys.path))
    commands, _texts, results = run_worker(["a"])
    assert commands[0][-3:] == ["a", "--target", str(target)]
    assert target.is_dir()
    assert str(target) in pip_installer.sys.path
    assert results[0][0] is True


# ---------------------------------------------------------------------------
# _verify_python — failure modes are specific and logged, and the probe has time
# ---------------------------------------------------------------------------


def _fake_run(outcome):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if isinstance(outcome, BaseException):
            raise outcome
        return subprocess.CompletedProcess(args, outcome, b"", b"")

    return run, calls


@pytest.mark.parametrize(("outcome", "expected"), [
    (0, True),
    (1, False),
    (subprocess.TimeoutExpired(["py"], 30), False),
    (FileNotFoundError("no such file"), False),
    (PermissionError("denied"), False),
    (ValueError("embedded null byte"), False),
])
def test_verify_python_outcomes(monkeypatch, caplog, outcome, expected):
    from Imervue.plugin import pip_installer
    run, calls = _fake_run(outcome)
    monkeypatch.setattr(pip_installer.subprocess, "run", run)
    with caplog.at_level("INFO", logger="Imervue"):
        assert pip_installer._verify_python("C:/py/python.exe") is expected  # noqa: SLF001
    (args, kwargs), = calls
    assert args == ["C:/py/python.exe", "-m", "pip", "--version"]
    assert kwargs["timeout"] == pip_installer._VERIFY_TIMEOUT_S  # noqa: SLF001
    if not expected:
        assert "C:/py/python.exe" in caplog.text


def test_verify_python_allows_a_slow_cold_start():
    from Imervue.plugin import pip_installer
    assert pip_installer._VERIFY_TIMEOUT_S >= 30  # noqa: SLF001


def test_verify_python_does_not_swallow_unexpected_errors(monkeypatch):
    from Imervue.plugin import pip_installer
    run, _calls = _fake_run(RuntimeError("bug"))
    monkeypatch.setattr(pip_installer.subprocess, "run", run)
    with pytest.raises(RuntimeError):
        pip_installer._verify_python("C:/py/python.exe")  # noqa: SLF001
