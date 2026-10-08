"""A CI run's process exit status is the one pytest reported.

``tests/conftest.py`` leaves a CI process early to dodge a Qt teardown crash:
``pytest_unconfigure`` terminates a passing session and an ``atexit`` handler
``os._exit``s otherwise. The status used to be a module global defaulting to 0.
One test's bare ``import conftest`` built a second copy of the module, whose
handler ran first and exited 0, so the ``Fast`` jobs concluded ``success`` over
failed tests; a usage error exited 0 through the same default.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import conftest

_REPO = Path(__file__).resolve().parent.parent
_TESTS = _REPO / "tests"
_TIMEOUT = 300
_PASSING = "def test_probe():\n    assert sorted([2, 1]) == [1, 2]\n"
_FAILING = "def test_probe():\n    assert sorted([2, 1]) == [2, 1]\n"
# What the bare import in tests/test_conftest_os_trash.py did: tests/ is on
# sys.path, so this runs tests/conftest.py again as a module named ``conftest``.
_SECOND_COPY = "import conftest  # noqa: F401\n\n\n"


def _run_ci_session(tmp_path: Path, source: str, *options: str) -> subprocess.CompletedProcess:
    """Run *source* as a one-file pytest session set up the way the CI test jobs are."""
    probe = tmp_path / "test_probe.py"
    probe.write_text(source, encoding="utf-8")
    command = [
        sys.executable, "-X", "faulthandler", "-u", "-m", "pytest", str(probe),
        "-c", str(_REPO / "pyproject.toml"), "-p", "tests.conftest",
        f"--rootdir={tmp_path}",
        f"--confcutdir={tmp_path}",
        "-p", "no:unraisableexception", "-p", "no:cacheprovider",
        f"--basetemp={tmp_path / 'basetemp'}", "-q", *options,
    ]
    env = {**os.environ, "CI": "true", "QT_QPA_PLATFORM": "offscreen"}
    return subprocess.run(command, cwd=_REPO, env=env, capture_output=True, encoding="utf-8",
                          errors="replace", timeout=_TIMEOUT, check=False)


# --- the process exit status, end to end --------------------------------------

def test_a_failed_test_fails_the_process_even_with_a_second_copy_of_conftest(tmp_path):
    result = _run_ci_session(tmp_path, _SECOND_COPY + _FAILING)
    assert "1 failed" in result.stdout, result.stdout + result.stderr
    assert result.returncode == pytest.ExitCode.TESTS_FAILED


def test_a_passing_session_exits_zero_after_printing_its_summary(tmp_path):
    result = _run_ci_session(tmp_path, _PASSING)
    assert "1 passed" in result.stdout, result.stdout + result.stderr
    assert result.returncode == pytest.ExitCode.OK


def test_probe_does_not_collect_a_vanishing_neighbour(tmp_path, monkeypatch):
    """The subprocess must not stat unrelated directories in the system Temp tree."""
    neighbour = tmp_path.parent / ("vanishing-" + tmp_path.name)
    neighbour.mkdir()
    plugin = tmp_path / "vanishing_probe.py"
    plugin.write_text(
        "from pathlib import Path\n"
        "original = Path.lstat\n"
        f"neighbour = Path({str(neighbour)!r})\n"
        "def lstat(self, *args, **kwargs):\n"
        "    if self == neighbour:\n"
        "        raise FileNotFoundError('unrelated directory vanished')\n"
        "    return original(self, *args, **kwargs)\n"
        "Path.lstat = lstat\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    result = _run_ci_session(tmp_path, _PASSING, "-p", "vanishing_probe", "--tb=long")
    assert "1 passed" in result.stdout, result.stdout + result.stderr
    assert result.returncode == pytest.ExitCode.OK


def test_a_usage_error_keeps_the_exit_code_pytest_gives_it(tmp_path):
    result = _run_ci_session(tmp_path, _PASSING, "--test-layer=nonsense")
    assert "--test-layer" in result.stderr, result.stdout + result.stderr
    assert result.returncode == pytest.ExitCode.USAGE_ERROR


# --- the two exit layers, in process -------------------------------------------

def _config(status: int | None = None) -> SimpleNamespace:
    """A stand-in ``pytest.Config`` whose session reported *status* (``None``: not finished)."""
    config = SimpleNamespace(stash=pytest.Stash())
    if status is not None:
        conftest.pytest_sessionfinish(SimpleNamespace(config=config), status)
    return config


@pytest.fixture
def exits(monkeypatch):
    """The exits the two layers ask for, recorded instead of carried out."""
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(os, "_exit", lambda status: calls.append(("os._exit", status)))
    monkeypatch.setattr(conftest, "_hard_exit_zero", lambda: calls.append(("terminate", 0)))
    return calls


@pytest.mark.parametrize("status", [0, 1, 2, 5])
def test_the_fallback_exits_with_the_reported_status(monkeypatch, exits, status):
    monkeypatch.setenv("CI", "true")
    conftest._force_clean_exit(_config(status))
    assert exits == [("os._exit", status)]


def test_the_fallback_takes_an_exit_code_enum_as_its_number(monkeypatch, exits):
    monkeypatch.setenv("CI", "true")
    conftest._force_clean_exit(_config(pytest.ExitCode.TESTS_FAILED))
    assert exits == [("os._exit", 1)]
    assert type(exits[0][1]) is int


def test_the_fallback_leaves_an_unfinished_session_alone(monkeypatch, exits):
    monkeypatch.setenv("CI", "true")
    conftest._force_clean_exit(_config())
    assert exits == []


@pytest.mark.parametrize("ci", [None, "false", "1"])
def test_the_fallback_does_nothing_off_ci(monkeypatch, exits, ci):
    if ci is None:
        monkeypatch.delenv("CI", raising=False)
    else:
        monkeypatch.setenv("CI", ci)
    conftest._force_clean_exit(_config(1))
    assert exits == []


@pytest.mark.parametrize(("ci", "status", "expected"), [
    ("true", 0, [("terminate", 0)]),
    ("true", 1, []),                # failed tests: normal teardown, then the fallback
    ("true", 5, []),                # no tests collected
    ("true", None, []),             # the session never finished
    (None, 0, []),                  # a local run tears down normally
])
def test_only_a_passing_ci_session_is_terminated_early(monkeypatch, exits, ci, status, expected):
    if ci is None:
        monkeypatch.delenv("CI", raising=False)
    else:
        monkeypatch.setenv("CI", ci)
    conftest.pytest_unconfigure(_config(status))
    assert exits == expected


def test_configure_arms_the_fallback_for_its_own_config(monkeypatch):
    registered = []
    monkeypatch.setattr(conftest.atexit, "register", lambda *args: registered.append(args))
    config = _config()
    conftest.pytest_configure(config)
    assert registered == [(conftest._force_clean_exit, config)]


# --- one copy of the module ----------------------------------------------------

def _bare_conftest_imports(source: str) -> list[int]:
    """Line numbers of ``import conftest`` and ``from conftest import ...`` in *source*."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            bare = any(alias.name == "conftest" for alias in node.names)
        else:
            bare = (isinstance(node, ast.ImportFrom) and node.level == 0
                    and node.module == "conftest")
        if bare:
            lines.append(node.lineno)
    return sorted(lines)


def test_bare_conftest_imports_are_told_from_package_imports():
    assert _bare_conftest_imports(
        "import os, conftest\n\ndef f():\n    from conftest import qapp\n") == [1, 4]
    assert _bare_conftest_imports(
        "from tests import conftest\nfrom tests.conftest import qapp\n"
        "from . import conftest\nfrom .conftest import qapp\nimport tests.conftest\n") == []


def test_tests_conftest_is_the_module_pytest_loaded(pytestconfig):
    assert pytestconfig.pluginmanager.is_registered(conftest)


def test_no_test_module_imports_conftest_by_its_bare_name():
    offenders = {}
    for path in sorted(_TESTS.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        lines = _bare_conftest_imports(source) if "conftest" in source else []
        if lines:
            offenders[path.relative_to(_REPO).as_posix()] = lines
    assert offenders == {}, "import tests.conftest instead: a bare import builds a second copy"
