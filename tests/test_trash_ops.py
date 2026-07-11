"""Tests for background trash operations (``trash_batch`` + worker).

``trash_batch`` is exercised with the shell call monkeypatched, so no test
ever touches the real OS recycle bin. The worker test calls ``run()``
directly — the thread body — to stay deterministic.
"""
from __future__ import annotations

import pytest

from Imervue.system import trash_ops
from Imervue.system.trash_ops import FileDeleteWorker, trash_batch


@pytest.fixture
def batch_spy(monkeypatch):
    """Capture the path groups handed to the (stubbed) shell call."""
    calls: list[list[str]] = []
    monkeypatch.setattr(trash_ops, "_trash_many",
                        lambda paths: calls.append(list(paths)))
    return calls


def _files(tmp_path, count):
    out = []
    for i in range(count):
        target = tmp_path / f"f{i}.png"
        target.write_bytes(b"x")
        out.append(str(target))
    return out


class TestTrashBatch:
    def test_one_shell_call_per_chunk(self, tmp_path, batch_spy):
        paths = _files(tmp_path, 5)
        trashed, failed = trash_batch(paths, chunk_size=2)
        assert trashed == paths
        assert failed == []
        assert [len(group) for group in batch_spy] == [2, 2, 1]

    def test_progress_reports_after_each_chunk(self, tmp_path, batch_spy):
        paths = _files(tmp_path, 5)
        seen: list[tuple[int, int]] = []
        trash_batch(paths, on_progress=lambda done, total: seen.append((done, total)),
                    chunk_size=2)
        assert seen == [(2, 5), (4, 5), (5, 5)]

    def test_missing_paths_are_skipped_silently(self, tmp_path, batch_spy):
        real = _files(tmp_path, 1)
        gone = str(tmp_path / "gone.png")
        trashed, failed = trash_batch([gone, real[0]])
        assert trashed == real
        assert failed == []
        assert batch_spy == [real]

    def test_empty_input_is_a_noop(self, batch_spy):
        assert trash_batch([]) == ([], [])
        assert batch_spy == []

    def test_single_path(self, tmp_path, batch_spy):
        paths = _files(tmp_path, 1)
        assert trash_batch(paths) == (paths, [])

    def test_chunk_failure_is_isolated_per_file(self, tmp_path, monkeypatch):
        # The whole-chunk shell call blows up (e.g. one locked file) → the
        # fallback retries per file so only the genuinely bad path fails.
        paths = _files(tmp_path, 3)

        def _boom(_paths):
            raise OSError("locked")

        monkeypatch.setattr(trash_ops, "_trash_many", _boom)
        from Imervue.gpu_image_view.actions import keyboard_actions
        monkeypatch.setattr(keyboard_actions, "_send_to_trash",
                            lambda p: p != paths[1])

        trashed, failed = trash_batch(paths)
        assert trashed == [paths[0], paths[2]]
        assert failed == [paths[1]]


class TestFileDeleteWorker:
    def test_run_emits_progress_then_result(self, qapp, tmp_path, batch_spy):
        paths = _files(tmp_path, 3)
        worker = FileDeleteWorker(paths)
        progressed: list[tuple[int, int]] = []
        results: list[tuple[list, list]] = []
        worker.progress.connect(lambda done, total: progressed.append((done, total)))
        worker.finished_with.connect(lambda ok, bad: results.append((ok, bad)))
        worker.run()  # the thread body, called synchronously for determinism
        assert results == [(paths, [])]
        assert progressed[-1] == (3, 3)

    def test_run_reports_failures(self, qapp, tmp_path, monkeypatch):
        paths = _files(tmp_path, 1)
        monkeypatch.setattr(
            trash_ops, "_trash_many",
            lambda _paths: (_ for _ in ()).throw(OSError("locked")))
        from Imervue.gpu_image_view.actions import keyboard_actions
        monkeypatch.setattr(keyboard_actions, "_send_to_trash", lambda p: False)
        worker = FileDeleteWorker(paths)
        results: list[tuple[list, list]] = []
        worker.finished_with.connect(lambda ok, bad: results.append((ok, bad)))
        worker.run()
        assert results == [([], paths)]
