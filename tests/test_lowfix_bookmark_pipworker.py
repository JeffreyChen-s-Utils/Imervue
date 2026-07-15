"""Two low-severity robustness fixes: bookmark cache identity and the
find-Python worker always reporting.
"""
from __future__ import annotations

from Imervue.user_settings import bookmark
from Imervue.user_settings.user_setting_dict import user_setting_dict


def test_bookmark_cache_retains_the_list_object():
    # The cache holds the backing list object (not its id()), so a freed list's
    # address can't be reused for a new one and compare equal (a stale set).
    lst = ["a.png"]
    user_setting_dict["bookmarks"] = lst
    assert bookmark.is_bookmarked("a.png") is True
    assert bookmark._cached_list is lst          # noqa: SLF001 - the fix's mechanism


def test_bookmark_cache_resyncs_when_list_replaced_wholesale():
    user_setting_dict["bookmarks"] = ["a.png"]
    assert bookmark.is_bookmarked("a.png") is True
    user_setting_dict["bookmarks"] = ["b.png"]   # profile switch / disk reload
    assert bookmark.is_bookmarked("a.png") is False
    assert bookmark.is_bookmarked("b.png") is True


def test_find_python_worker_reports_none_on_failure(qapp, monkeypatch):
    from Imervue.plugin import pip_installer

    def _boom():
        raise PermissionError("registry / dir locked")

    monkeypatch.setattr(pip_installer, "_find_python", _boom)
    results: list = []
    worker = pip_installer._FindPythonWorker()
    worker.result_ready.connect(results.append)
    worker.run()
    assert results == [None]                     # reported, not hung
