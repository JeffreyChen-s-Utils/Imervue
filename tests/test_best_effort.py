"""Tests for ``best_effort``: swallow and log a step's failure, never hide the traceback."""
from __future__ import annotations

import logging

import pytest

from Imervue.system.best_effort import best_effort


def test_success_logs_nothing(caplog):
    ran = []
    with caplog.at_level("DEBUG", logger="Imervue"), best_effort("step"):
        ran.append(True)
    assert ran == [True]
    assert caplog.records == []


def test_failure_is_swallowed_logged_and_stops_only_the_block(caplog):
    after = []
    with caplog.at_level("DEBUG", logger="Imervue"):
        with best_effort("close the widget"):
            raise RuntimeError("already deleted")
        after.append("next step ran")
    assert after == ["next step ran"]
    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert "close the widget" in record.getMessage()
    assert record.exc_info[0] is RuntimeError


def test_custom_logger(caplog):
    log = logging.getLogger("Imervue.custom_test")
    with caplog.at_level("DEBUG", logger="Imervue"), best_effort("x", log):
        raise ValueError("bad")
    assert caplog.records[0].name == "Imervue.custom_test"


@pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit])
def test_base_exceptions_propagate(exc):
    with pytest.raises(exc), best_effort("step"):
        raise exc
