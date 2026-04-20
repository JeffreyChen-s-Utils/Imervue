"""Tests for logging configuration."""
from __future__ import annotations

import logging
import sys

import pytest

from Imervue.system import log_setup


@pytest.fixture
def clean_logger():
    """Snapshot + restore the Imervue root logger state."""
    root = logging.getLogger("Imervue")
    original_handlers = root.handlers[:]
    original_level = root.level
    yield root
    for h in root.handlers[:]:
        root.removeHandler(h)
        try:
            h.close()
        except OSError:
            pass
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
        monkeypatch.setattr(sys, "frozen", False, raising=False)
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
        monkeypatch.setattr(sys, "frozen", True, raising=False)
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
