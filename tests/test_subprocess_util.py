"""Tests for the shared ``terminate_process`` subprocess helper.

Uses a fake Popen that records the terminate/kill/wait calls it receives, so
the assertions read call history (which a static analyser can't constant-fold)
rather than mutated booleans.
"""
from __future__ import annotations

import subprocess

import pytest

from Imervue.plugin.subprocess_util import terminate_process


class _FakeProc:
    def __init__(self, poll_val=None, wait_timeout=False):
        self._poll = poll_val
        self._wait_timeout = wait_timeout
        self.calls: list[str] = []

    def poll(self):
        return self._poll

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")

    def wait(self, timeout=None):
        self.calls.append("wait")
        if self._wait_timeout and timeout is not None:
            raise subprocess.TimeoutExpired("cmd", timeout)


def test_none_is_noop():
    terminate_process(None)          # must not raise


def test_already_exited_is_untouched():
    proc = _FakeProc(poll_val=0)     # poll() not None -> already exited
    terminate_process(proc)
    assert proc.calls == []


def test_running_process_is_terminated():
    proc = _FakeProc(poll_val=None)
    terminate_process(proc)
    assert "terminate" in proc.calls
    assert "kill" not in proc.calls


def test_escalates_to_kill_on_terminate_timeout():
    proc = _FakeProc(poll_val=None, wait_timeout=True)
    terminate_process(proc)
    assert proc.calls == ["terminate", "wait", "kill", "wait"]


def test_suppresses_errors_from_a_racing_child():
    class _Raising(_FakeProc):
        def terminate(self):
            raise OSError("already reaped")

    proc = _Raising(poll_val=None)
    terminate_process(proc)          # error suppressed -> no raise


@pytest.mark.parametrize("poll_val", [0, 1, -1])
def test_any_exited_return_code_is_a_noop(poll_val):
    proc = _FakeProc(poll_val=poll_val)
    terminate_process(proc)
    assert proc.calls == []
