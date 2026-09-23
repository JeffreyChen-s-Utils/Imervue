"""The subprocess batch worker always removes its temporary path-list file.

The list of images reaches the child process through a temp JSON file. It used
to be removed only on the protocol's success and error lines, so a child that
could not be started (``Popen`` raising) left the file behind. The worker body
runs inline with ``Popen`` patched, so no child process starts.
"""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from ai_background_remover import ai_background_remover as mod


class _FakeProc:
    def __init__(self, lines):
        self._lines = lines
        self.returncode = 0

    @property
    def stdout(self):
        return iter(self._lines)

    def wait(self, timeout=None):
        return self.returncode


@pytest.fixture
def worker_run(qapp, monkeypatch):
    """Run the batch worker over two paths; return (results, list-file paths seen)."""

    def _run(popen):
        seen: list[str] = []

        def fake_popen(cmd, **_kwargs):
            seen.append(cmd[4])   # the path-list argument
            return popen(cmd, seen)

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        worker = mod._SubprocessBatchWorker("python", "", ["a.png", "b.png"], "out", "u2net", False)
        results: list = []
        worker.result_ready.connect(lambda ok, bad: results.append((ok, bad)))
        worker.run()   # the thread body, inline
        return results, seen

    return _run


def test_list_file_carries_the_paths_and_is_removed_after_success(worker_run):
    contents: list = []

    def popen(cmd, _seen):
        with open(cmd[4], encoding="utf-8") as fh:
            contents.append(json.load(fh))
        return _FakeProc(["BATCH_OK:2:0\n"])

    results, seen = worker_run(popen)
    assert results == [(2, 0)]
    assert contents == [["a.png", "b.png"]]
    assert not any(os.path.exists(p) for p in seen)


def test_list_file_is_removed_when_the_child_cannot_start(worker_run):
    def popen(_cmd, _seen):
        raise FileNotFoundError("python not found")

    results, seen = worker_run(popen)
    assert results == [(0, 2)]
    assert len(seen) == 1
    assert not os.path.exists(seen[0])
