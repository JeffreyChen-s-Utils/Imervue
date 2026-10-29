"""Worker cancellation and failures reap the real child processes they started."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import Qt

from Imervue.gui import gif_video_dialog as video
from Imervue.plugin.subprocess_util import terminate_process
from ai_background_remover import ai_background_remover as remover


@pytest.mark.parametrize("during_launch", [False, True])
def test_cancel_video_reaps_encoder_even_during_launch(qapp, tmp_path, monkeypatch, during_launch):
    real_popen = subprocess.Popen
    started = Event()
    children = []
    worker = video._CreateWorker([], str(tmp_path / "out.mp4"), "MP4", 24, 0, 0, False)
    results = []
    worker.result_ready.connect(lambda *result: results.append(result),
                                Qt.ConnectionType.DirectConnection)
    monkeypatch.setattr(video, "find_ffmpeg", lambda: "test-encoder")

    def launch(_cmd, **kwargs):
        proc = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(proc)
        if during_launch:
            worker.abort()
        started.set()
        return proc

    monkeypatch.setattr(subprocess, "Popen", launch)
    worker.start()
    try:
        assert started.wait(5), "encoder was not launched"
        if not during_launch:
            worker.abort()
        assert worker.wait(2000), "cancelled worker is still waiting for its encoder"
        assert children[0].poll() is not None, "encoder remains alive after worker cancellation"
        assert results == [(False, "cancelled")]
    finally:
        for proc in children:
            terminate_process(proc)
        worker.wait(5000)
        worker.deleteLater()


class _UnreadableStdout:
    def __iter__(self):
        raise OSError("stdout read failed")


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired("encoder", 300),
                                    OSError("encoder pipe failed")])
def test_video_failure_reaps_encoder(qapp, tmp_path, monkeypatch, failure):
    real_popen = subprocess.Popen
    children = []
    worker = video._CreateWorker([], str(tmp_path / "out.mp4"), "MP4", 24, 0, 0, False)
    results = []
    worker.result_ready.connect(lambda *result: results.append(result))
    monkeypatch.setattr(video, "find_ffmpeg", lambda: "test-encoder")

    def communicate(*_args, **_kwargs):
        raise failure

    def launch(_cmd, **kwargs):
        proc = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(proc)
        monkeypatch.setattr(proc, "communicate", communicate)
        return proc

    monkeypatch.setattr(subprocess, "Popen", launch)
    try:
        worker.run()
        assert children[0].poll() is not None
        assert results == [(False, str(failure))]
    finally:
        for proc in children:
            terminate_process(proc)
            proc.stdout.close()
            proc.stderr.close()
        worker.deleteLater()


@pytest.mark.parametrize("batch", [False, True])
def test_removal_stdout_failure_reaps_live_child(qapp, tmp_path, monkeypatch, batch):
    real_popen = subprocess.Popen
    children = []
    streams = []
    list_paths = []

    def launch(cmd, **kwargs):
        proc = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(proc)
        streams.append(proc.stdout)
        proc.stdout = _UnreadableStdout()
        if batch:
            list_paths.append(cmd[4])
        return proc

    monkeypatch.setattr(subprocess, "Popen", launch)
    if batch:
        worker = remover._SubprocessBatchWorker(
            sys.executable, "", ["a.png"], str(tmp_path), "u2net", False)
    else:
        worker = remover._SubprocessRemoveWorker(
            sys.executable, "", "a.png", str(tmp_path / "out.png"), "u2net", False)
    results = []
    worker.result_ready.connect(lambda *result: results.append(result))
    try:
        worker.run()
        assert children[0].poll() is not None, "failed worker left its child alive"
        assert results == ([(0, 1)] if batch else [(False, "stdout read failed")])
        assert all(not Path(path).exists() for path in list_paths)
    finally:
        for proc in children:
            terminate_process(proc)
        for stream in streams:
            stream.close()
        worker.deleteLater()


def test_malformed_batch_progress_reaps_encoder(qapp, tmp_path, monkeypatch):
    real_popen = subprocess.Popen
    children = []

    def launch(_cmd, **kwargs):
        proc = real_popen([sys.executable, "-c",
                          "import time; print('BATCH_PROGRESS:bad:1:file', flush=True); time.sleep(60)"],
                         **kwargs)
        children.append(proc)
        return proc

    monkeypatch.setattr(subprocess, "Popen", launch)
    worker = remover._SubprocessBatchWorker(
        sys.executable, "", ["a.png"], str(tmp_path), "u2net", False)
    results = []
    worker.result_ready.connect(lambda *result: results.append(result))
    try:
        worker.run()
        assert children[0].poll() is not None
        assert results == [(0, 1)]
    finally:
        for proc in children:
            terminate_process(proc)
            proc.stdout.close()
        worker.deleteLater()
