"""Tests for logging configuration."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from Imervue.system import log_setup
import contextlib


@pytest.fixture
def clean_logger():
    """Snapshot + restore the Imervue root logger state."""
    root = logging.getLogger("Imervue")
    original_handlers = root.handlers[:]
    original_level = root.level
    yield root
    for h in root.handlers[:]:
        root.removeHandler(h)
        with contextlib.suppress(OSError):
            h.close()
    for h in original_handlers:
        root.addHandler(h)
    root.setLevel(original_level)


class TestSetupLogging:
    def test_attaches_file_handler(self, tmp_path, monkeypatch, clean_logger):
        from Imervue.system import app_paths
        monkeypatch.setattr(app_paths, "app_dir", lambda: tmp_path)
        log_setup.setup_logging()

        file_handlers = [h for h in clean_logger.handlers
                         if isinstance(h, logging.FileHandler)]
        assert file_handlers
        assert (tmp_path / "imervue.log").exists()

    def test_sets_debug_level(self, tmp_path, monkeypatch, clean_logger):
        from Imervue.system import app_paths
        monkeypatch.setattr(app_paths, "app_dir", lambda: tmp_path)
        log_setup.setup_logging()
        assert clean_logger.level == logging.DEBUG

    def test_adds_stream_handler_in_dev(self, tmp_path, monkeypatch, clean_logger):
        from Imervue.system import app_paths
        monkeypatch.setattr(app_paths, "app_dir", lambda: tmp_path)
        monkeypatch.setattr(app_paths, "is_frozen", lambda: False)
        log_setup.setup_logging()
        stream_handlers = [
            h for h in clean_logger.handlers
            if type(h).__name__ == "StreamHandler"
            and not isinstance(h, logging.FileHandler)
        ]
        assert stream_handlers

    def test_skips_stream_handler_when_frozen(
        self, tmp_path, monkeypatch, clean_logger,
    ):
        from Imervue.system import app_paths
        monkeypatch.setattr(app_paths, "app_dir", lambda: tmp_path)
        monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
        log_setup.setup_logging()
        # One FileHandler, no additional StreamHandler.
        stream_only = [
            h for h in clean_logger.handlers
            if type(h).__name__ == "StreamHandler"
            and not isinstance(h, logging.FileHandler)
        ]
        assert stream_only == []

    def test_initial_message_is_logged(self, tmp_path, monkeypatch, clean_logger):
        from Imervue.system import app_paths
        monkeypatch.setattr(app_paths, "app_dir", lambda: tmp_path)
        log_setup.setup_logging()
        content = (tmp_path / "imervue.log").read_text(encoding="utf-8")
        assert "Logging initialized" in content

    def test_is_idempotent(self, tmp_path, monkeypatch, clean_logger):
        from Imervue.system import app_paths
        monkeypatch.setattr(app_paths, "app_dir", lambda: tmp_path)
        log_setup.setup_logging()
        first = clean_logger.handlers[:]
        log_setup.setup_logging()
        assert clean_logger.handlers == first

    def test_falls_back_when_the_app_dir_is_not_writable(
        self, tmp_path, monkeypatch, clean_logger,
    ):
        # An EXE installed under Program Files cannot write next to itself.
        from Imervue.system import app_paths
        blocked = tmp_path / "app"
        fallback = tmp_path / "user"
        monkeypatch.setattr(app_paths, "app_dir", lambda: blocked)
        monkeypatch.setattr(log_setup, "_user_log_dir", lambda: fallback)
        real = log_setup._file_handler

        def fail_on_blocked(directory):
            if directory == blocked:
                raise OSError("read-only")
            return real(directory)

        monkeypatch.setattr(log_setup, "_file_handler", fail_on_blocked)
        log_setup.setup_logging()
        assert (fallback / "imervue.log").exists()
        assert not blocked.exists()

    def test_creates_a_missing_log_directory(self, tmp_path, clean_logger):
        target = tmp_path / "nested" / "dir"
        handler = log_setup._file_handler(target)
        handler.close()
        assert (target / "imervue.log").exists()

    def test_user_log_dir_is_under_localappdata_on_windows(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert log_setup._user_log_dir() == tmp_path / "Imervue"

    def test_user_log_dir_falls_back_to_home_without_localappdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        assert log_setup._user_log_dir() == tmp_path / "Imervue"


class TestInstallExceptionLogging:
    @pytest.fixture(autouse=True)
    def _restore_hook(self):
        original = sys.excepthook
        yield
        sys.excepthook = original

    def test_logs_and_chains_to_the_previous_hook(
        self, tmp_path, monkeypatch, clean_logger,
    ):
        from Imervue.system import app_paths
        monkeypatch.setattr(app_paths, "app_dir", lambda: tmp_path)
        log_setup.setup_logging()
        seen = []
        sys.excepthook = lambda *exc: seen.append(exc[0])
        log_setup.install_exception_logging()

        try:
            raise ValueError("boom")
        except ValueError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)

        assert seen == [ValueError]
        content = (tmp_path / "imervue.log").read_text(encoding="utf-8")
        assert "Unhandled exception" in content
        assert "boom" in content
