"""The session-start basetemp pruning must never delete a running session's dir.

pytest writes ``.lock`` into a basetemp while its session runs. Pruning used
to ignore it, so starting a second pytest run deleted the first run's
``tmp_path`` directories and every later test in that run errored in setup.
"""
from __future__ import annotations

import os
import time

from tests.conftest import (
    _BASETEMP_LOCK_TIMEOUT,
    _basetemp_in_use,
    _prune_old_pytest_basetemps,
)


def _session_dirs(base, count: int):
    owner = base / "pytest-of-someone"
    owner.mkdir()
    dirs = []
    for n in range(1, count + 1):
        d = owner / f"pytest-{n}"
        d.mkdir()
        dirs.append(d)
    return dirs


def _lock(path, age_seconds: float = 0.0) -> None:
    lock = path / ".lock"
    lock.write_text("1234", encoding="utf-8")
    stamp = time.time() - age_seconds
    os.utime(lock, (stamp, stamp))


def test_prune_keeps_newest_and_locked_dirs(tmp_path):
    d1, d2, d3, d4, d5 = _session_dirs(tmp_path, 5)
    _lock(d1)                                          # a session still running
    _lock(d2, age_seconds=_BASETEMP_LOCK_TIMEOUT + 60)  # a crashed session's lock
    _prune_old_pytest_basetemps(retain=2, base=tmp_path)
    assert [d.exists() for d in (d1, d2, d3, d4, d5)] == [True, False, False, True, True]


def test_prune_orders_by_numeric_suffix(tmp_path):
    owner = tmp_path / "pytest-of-someone"
    owner.mkdir()
    for name in ("pytest-9", "pytest-10", "pytest-11", "unrelated"):
        (owner / name).mkdir()
    _prune_old_pytest_basetemps(retain=2, base=tmp_path)
    assert sorted(p.name for p in owner.iterdir()) == ["pytest-10", "pytest-11", "unrelated"]


def test_prune_ignores_missing_base_and_foreign_dirs(tmp_path):
    _prune_old_pytest_basetemps(base=tmp_path / "missing")
    (tmp_path / "other").mkdir()
    _prune_old_pytest_basetemps(base=tmp_path)
    assert (tmp_path / "other").is_dir()


def test_basetemp_in_use_boundaries(tmp_path):
    now = time.time()
    assert _basetemp_in_use(tmp_path, now) is False
    _lock(tmp_path, age_seconds=_BASETEMP_LOCK_TIMEOUT - 60)
    assert _basetemp_in_use(tmp_path, now) is True
    _lock(tmp_path, age_seconds=_BASETEMP_LOCK_TIMEOUT + 60)
    assert _basetemp_in_use(tmp_path, now) is False


def test_basetemp_in_use_assumes_live_when_lock_unreadable(tmp_path, monkeypatch):
    _lock(tmp_path)

    def boom(self, *args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(type(tmp_path), "stat", boom)
    assert _basetemp_in_use(tmp_path, time.time()) is True
