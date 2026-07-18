"""Unit tests for object_splitter subprocess helpers.

The subprocess worker used to abort on a malformed STEP line (unguarded int())
and never reap the rembg child, orphaning the process. These cover the parsing
guard and the always-terminate helper directly, without spawning a real process.
"""
from __future__ import annotations

import subprocess

from object_splitter.object_splitter import _parse_step_line, _terminate_process


class TestParseStepLine:
    def test_valid_line(self):
        assert _parse_step_line("3:10:working") == (3, 10, "working")

    def test_message_may_contain_colons(self):
        assert _parse_step_line("1:2:a:b:c") == (1, 2, "a:b:c")

    def test_too_few_parts_returns_none(self):
        assert _parse_step_line("3:10") is None

    def test_non_numeric_current_returns_none(self):
        assert _parse_step_line("x:10:msg") is None

    def test_non_numeric_total_returns_none(self):
        assert _parse_step_line("3:y:msg") is None


class _FakeProc:
    def __init__(self, poll_val=None, wait_timeout=False):
        self._poll = poll_val          # None -> running, int -> already exited
        self._wait_timeout = wait_timeout
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self):
        return self._poll

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self._wait_timeout and timeout is not None:
            raise subprocess.TimeoutExpired("cmd", timeout)


class TestTerminateProcess:
    def test_none_is_noop(self):
        _terminate_process(None)   # must not raise

    def test_already_exited_is_not_terminated(self):
        proc = _FakeProc(poll_val=0)
        _terminate_process(proc)
        assert proc.terminated is False
        assert proc.killed is False

    def test_running_process_is_terminated(self):
        proc = _FakeProc(poll_val=None)
        _terminate_process(proc)
        assert proc.terminated is True
        assert proc.killed is False
        assert proc.wait_calls == 1

    def test_escalates_to_kill_when_terminate_times_out(self):
        proc = _FakeProc(poll_val=None, wait_timeout=True)
        _terminate_process(proc)
        assert proc.terminated is True
        assert proc.killed is True          # escalated after the timeout
        assert proc.wait_calls == 2         # timed-out wait, then post-kill wait
