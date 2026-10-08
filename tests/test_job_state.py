"""Durable results and cooperative cancellation are independent of Qt lifetimes."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from Imervue.system.job_state import JobState


@pytest.mark.parametrize(
    ("paths", "error", "status"),
    [
        ([], "", "succeeded"),
        ([], "offline", "failed"),
        (["one"], "offline", "failed"),
        (["one", "two"], "", "failed"),
    ],
)
def test_unfinished_and_empty_work(paths, error, status):
    state = JobState(paths)
    state.finish(error=error)
    assert state.snapshot().status == status
    assert state.failed_paths() == tuple(paths)


def test_partial_retry_set_is_unique_and_does_not_include_success():
    state = JobState(["ok", "bad", "bad", "remaining"])
    state.record("ok", output="/result.png")
    state.record("bad", error="disk full")
    old = state.snapshot()
    state.request_cancel()
    state.finish()
    assert state.failed_paths() == ("bad",)
    snap = state.snapshot()
    assert snap.status == "cancelled" and snap.total == 3
    assert snap.items[0].output == "/result.png" and snap.items[-1].status == "cancelled"
    assert old.status == "running" and old.items[-1].status == "pending"
    state.record("remaining", output="late")
    state.finish(error="late")
    assert state.snapshot() == snap


def test_finish_with_mixed_results_and_repeat_packets():
    state = JobState(["ok", "bad"])
    state.record("missing")
    state.record("ok", output="output")
    state.record("ok", error="stale duplicate")
    state.record("bad", error="permission")
    state.finish()
    state.request_cancel()
    assert state.snapshot().status == "partial"
    assert not state.cancelled and state.snapshot().current == 2


def test_discovery_and_parallel_publication():
    state = JobState()
    paths = [str(i) for i in range(1000)]
    state.set_items(paths)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(state.record, paths))
    with pytest.raises(RuntimeError):
        state.set_items([])
    state.finish()
    snap = state.snapshot(include_items=False)
    assert snap.items == () and snap.current == snap.total == 1000
    assert snap.status == "succeeded"


@pytest.mark.parametrize(("current", "total"), [(-1, 0), (1, 0), (0, -1)])
def test_invalid_substep_progress(current, total):
    with pytest.raises(ValueError):
        JobState().progress(current, total)


def test_atomic_install_progress_does_not_claim_individual_commits():
    state = JobState(["plugin"])
    state.progress(1, 2)
    assert state.snapshot().items[0].status == "pending"
    state.progress(2, 2)
    state.record("plugin", output="installed")
    state.finish()
    state.progress(0, 0)
    snap = state.snapshot()
    assert snap.status == "succeeded" and snap.current == snap.total == 2


@pytest.mark.parametrize("limit", [0, 1, 2, 10])
def test_visible_results_resolve_pending_failures_without_losing_completed_outputs(limit):
    state = JobState(["indexed", "output", "failed", "unattempted"])
    state.record("indexed")
    state.record("output", output="result.png")
    state.record("failed", error="disk full")
    state.finish(error="aborted")
    visible, total = state.visible_results(limit)
    assert total == 3
    assert tuple(item.source for item in visible) == ("failed", "unattempted", "output")[:limit]
    assert state.failed_paths() == ("failed", "unattempted")
    assert state.snapshot().items[-1].error == "aborted"


def test_cancelled_work_is_not_materialized_as_failed_or_retried():
    state = JobState([str(i) for i in range(10000)])
    state.record("0")
    state.request_cancel()
    state.finish()
    assert state.visible_results(500) == ((), 0)
    assert state.failed_paths() == ()
    assert state.snapshot().items[-1].status == "cancelled"
    with pytest.raises(ValueError):
        state.visible_results(-1)
