"""InstallDependenciesDialog must wait its workers on close.

The dialog is WA_DeleteOnClose and had no closeEvent, so closing it (or app-exit)
while a find/download/install/import QThread ran destroyed the thread mid-run.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.plugin.pip_installer import InstallDependenciesDialog


def _worker(name, running, waited):
    return SimpleNamespace(
        isRunning=lambda: running, wait=lambda: waited.append(name))


def test_wait_workers_waits_only_the_running_ones():
    waited: list = []
    fake = SimpleNamespace(
        _worker=_worker("install", True, waited),
        _dl_worker=_worker("dl", False, waited),      # not running -> skipped
        _find_worker=_worker("find", True, waited),
        # _import_worker attribute absent -> getattr None -> skipped
    )
    InstallDependenciesDialog._wait_workers(fake)
    assert waited == ["install", "find"]


def test_wait_workers_is_safe_with_no_workers():
    InstallDependenciesDialog._wait_workers(SimpleNamespace())   # must not raise
