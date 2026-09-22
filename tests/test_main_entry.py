"""``Imervue/__main__.py`` must configure logging before it touches Qt.

A windowed frozen build has no console, so an exception during startup is
only visible if the log file and the excepthook are already in place.
"""
from __future__ import annotations

import sys

import pytest

from Imervue import __main__ as entry


class _StopError(Exception):
    """Aborts main() right after the logging setup under test."""


def test_importing_the_entry_point_does_not_import_qt():
    # Qt imports live inside main(), so logging is configured before the
    # first PySide6 import — an import-time failure still reaches the log.
    source = entry.__file__
    with open(source, encoding="utf-8") as handle:
        module_level = [
            line for line in handle
            if line.startswith(("import ", "from ")) and "PySide6" in line
        ]
    assert module_level == []


def test_main_sets_up_logging_before_parsing_arguments(monkeypatch):
    calls: list[str] = []
    from Imervue.system import log_setup

    monkeypatch.setattr(log_setup, "setup_logging", lambda: calls.append("log"))
    monkeypatch.setattr(
        log_setup, "install_exception_logging", lambda: calls.append("hook"))

    def _parse_args():
        calls.append("args")
        raise _StopError

    monkeypatch.setattr(entry, "parse_args", _parse_args)
    with pytest.raises(_StopError):
        entry.main()
    assert calls == ["log", "hook", "args"]


def test_set_windows_app_user_model_id_is_a_noop_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    entry._set_windows_app_user_model_id()  # must not raise


def test_parse_args_defaults(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["Imervue"])
    args = entry.parse_args()
    assert (args.debug, args.software_opengl, args.file) == (False, False, None)


def test_parse_args_reads_flags_and_file(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["Imervue", "--debug", "--software_opengl", "a.png"])
    args = entry.parse_args()
    assert (args.debug, args.software_opengl, args.file) == (True, True, "a.png")
