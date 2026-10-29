"""Contracts of the plugin downloader that the other downloader tests do not pin.

``Imervue.plugin.plugin_downloader`` is the public import location: the
distribution-repo URL and branch, the listing walk, the ``_https_urlopen``
guard and every class stay importable from it, and the network helpers
(``_https_urlopen``, ``_github_get``, ``_get_plugin_dir``) are read from it at
call time so patching them there reaches the workers and the dialog. No test
here touches the network: every request goes to a patched ``_https_urlopen``
and every worker thread's ``start`` is a no-op.
"""
from __future__ import annotations

import json
import sys
import urllib.request

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin import plugin_downloader as pd
from Imervue.plugin.plugin_api import PLUGIN_API_VERSION, IncompatiblePluginError
from Imervue.plugin.status import status_registry


class _FakeResp:
    def __init__(self, data: bytes = b"content"):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _word(key: str, default: str) -> str:
    return language_wrapper.language_word_dict.get(key, default)


# ---------------------------------------------------------------- public surface

@pytest.mark.parametrize("name", [
    "_https_urlopen", "_github_get", "_get_plugin_dir", "_is_hidden", "_retry_download",
    "_EXPECTED_FETCH_ERRORS", "needs_newer_text", "is_safe_path_component",
    "parse_plugin_tree", "FetchPluginListWorker", "DownloadPluginWorker",
    "PluginDownloaderDialog", "REPO_BRANCH", "REPO_TREE_URL", "RAW_BASE_URL",
    "PLUGIN_CATEGORIES", "PluginListing",
])
def test_every_public_name_stays_importable_from_the_downloader(name):
    assert hasattr(pd, name)


def test_the_distribution_repo_contract_is_unchanged():
    assert pd.REPO_BRANCH == "main"
    assert pd.REPO_TREE_URL == (
        "https://api.github.com/repos/Jeffrey-Plugin-Repos/Imervue_Plugins"
        "/git/trees/main?recursive=1"
    )
    assert pd.RAW_BASE_URL == (
        "https://raw.githubusercontent.com/Jeffrey-Plugin-Repos/Imervue_Plugins/main"
    )
    assert pd.PLUGIN_CATEGORIES == ("plugins", "languages")


def test_the_https_guard_lives_in_the_downloader_module():
    assert pd._https_urlopen.__module__ == "Imervue.plugin.plugin_downloader"


def test_expected_fetch_errors_are_the_documented_set():
    assert (OSError, ValueError, TypeError, KeyError) == pd._EXPECTED_FETCH_ERRORS


@pytest.mark.parametrize(("name", "hidden"), [
    (".git", True), ("__pycache__", True), ("_private", False), ("demo", False),
])
def test_is_hidden_skips_dot_and_dunder_names(name, hidden):
    assert pd._is_hidden(name) is hidden


def test_needs_newer_text_names_the_plugin_and_both_api_versions():
    error = IncompatiblePluginError("demo", PLUGIN_API_VERSION + 3)
    text = pd.needs_newer_text(error)
    assert "demo" in text
    assert str(PLUGIN_API_VERSION + 3) in text
    assert str(PLUGIN_API_VERSION) in text


# ---------------------------------------------------------------- network helpers

def test_github_get_goes_through_the_guard_read_at_call_time(monkeypatch):
    seen = []

    def fake_guard(req, timeout):
        seen.append((req, timeout))
        return _FakeResp(json.dumps({"tree": []}).encode())

    monkeypatch.setattr(pd, "_https_urlopen", fake_guard)
    assert pd._github_get(pd.REPO_TREE_URL) == {"tree": []}
    ((req, timeout),) = seen
    assert isinstance(req, urllib.request.Request)
    assert req.full_url == pd.REPO_TREE_URL
    assert req.get_header("Accept") == "application/vnd.github.v3+json"
    assert timeout == 15


def test_github_get_refuses_a_non_https_url_before_any_request(monkeypatch):
    def no_network(*_a, **_k):
        raise AssertionError("urlopen must not run")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    with pytest.raises(ValueError, match="non-https"):
        pd._github_get("http://api.github.com/x")


def test_fetch_worker_parses_the_listing_from_the_tree_url(qapp, monkeypatch):
    requested = []
    tree = {"tree": [
        {"type": "tree", "path": "languages/lang_x"},
        {"type": "blob", "path": "languages/lang_x/__init__.py"},
    ]}
    monkeypatch.setattr(pd, "_github_get", lambda url: requested.append(url) or tree)
    results, errors = [], []
    worker = pd.FetchPluginListWorker()
    worker.result_ready.connect(results.append)
    worker.error.connect(errors.append)
    worker.run()
    assert requested == [pd.REPO_TREE_URL]
    assert errors == []
    assert results == [pd.parse_plugin_tree(tree)]


# ---------------------------------------------------------------- download worker

def test_download_worker_requests_each_file_through_the_guard(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)
    seen = []

    def fake_guard(req, timeout):
        seen.append((req.full_url, timeout))
        return _FakeResp(req.full_url.encode())

    monkeypatch.setattr(pd, "_https_urlopen", fake_guard)
    worker = pd.DownloadPluginWorker("demo", [
        {"name": "__init__.py", "download_url": "https://h/a"},
        {"name": "b.py", "download_url": "https://h/b"},
    ])
    done = []
    worker.result_ready.connect(done.append)
    worker.run()
    assert seen == [("https://h/a", 30), ("https://h/b", 30)]
    assert (tmp_path / "demo" / "b.py").read_bytes() == b"https://h/b"
    assert done == ["demo"]
    snap = worker.job_state.snapshot()
    assert snap.status == "succeeded"
    assert snap.items[0].output == str(tmp_path / "demo")


def test_download_worker_creates_a_missing_plugin_root(qapp, tmp_path, monkeypatch):
    root = tmp_path / "deep" / "plugins"
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: root)
    monkeypatch.setattr(pd, "_https_urlopen", lambda _req, timeout: _FakeResp())
    worker = pd.DownloadPluginWorker("demo", [{"name": "__init__.py", "download_url": "https://h/a"}])
    worker.run()
    assert (root / "demo" / "__init__.py").read_bytes() == b"content"


def test_download_worker_copies_its_file_infos(qapp):
    infos = [{"name": "__init__.py", "download_url": "https://h/a"}]
    worker = pd.DownloadPluginWorker("demo", infos)
    infos[0]["name"] = "changed.py"
    assert worker.file_infos == [{"name": "__init__.py", "download_url": "https://h/a"}]


def test_cancelled_download_requests_nothing_and_publishes_cancelled(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(pd, "_https_urlopen", lambda req, timeout: calls.append(req))
    worker = pd.DownloadPluginWorker("demo", [{"name": "__init__.py", "download_url": "https://h/a"}])
    errors = []
    worker.error.connect(errors.append)
    worker.stop()
    worker.run()
    assert calls == []
    assert errors == []
    assert worker.job_state.snapshot().status == "cancelled"
    assert not (tmp_path / "demo").exists()


def test_download_status_is_published_as_installed(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)
    monkeypatch.setattr(pd, "_https_urlopen", lambda _req, timeout: _FakeResp())
    published = []
    monkeypatch.setattr(status_registry, "publish", lambda *args: published.append(args))
    pd.DownloadPluginWorker("demo", [{"name": "__init__.py", "download_url": "https://h/a"}]).run()
    assert [entry[:3] for entry in published] == [
        ("download:demo", "demo", "downloading"),
        ("download:demo", "demo", "installed"),
    ]


def test_retry_download_builds_a_fresh_worker_for_the_first_path(qapp):
    infos = ({"name": "__init__.py", "download_url": "https://h/a"},)
    worker = pd._retry_download(("demo", "ignored"), file_infos=infos)
    assert isinstance(worker, pd.DownloadPluginWorker)
    assert worker.plugin_name == "demo"
    assert worker.file_infos == [dict(infos[0])]


# ---------------------------------------------------------------- dialog

_LISTING = [
    ("plugins", "alpha", [{"name": "__init__.py", "download_url": "https://h/a"}]),
    ("plugins", "beta", [{"name": "__init__.py", "download_url": "https://h/b"}]),
    ("languages", "gamma", []),
]


@pytest.fixture
def dialog(qapp, tmp_path, monkeypatch):
    """A downloader dialog whose workers never start and whose plugin dir is tmp."""
    monkeypatch.setattr(pd.FetchPluginListWorker, "start", lambda self: None)
    monkeypatch.setattr(pd.DownloadPluginWorker, "start", lambda self: None)
    monkeypatch.setattr(pd, "_get_plugin_dir", lambda: tmp_path)
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "__init__.py").write_text("", encoding="utf-8")
    dlg = pd.PluginDownloaderDialog(None)
    yield dlg
    dlg._workers.clear()
    dlg.deleteLater()


def _plugin_item(dlg, name):
    root = dlg.tree.invisibleRootItem()
    for i in range(root.childCount()):
        cat = root.child(i)
        for j in range(cat.childCount()):
            if cat.child(j).text(0) == name:
                return cat.child(j)
    raise AssertionError(name)


def test_dialog_starts_fetching_on_open(dialog):
    assert not dialog.refresh_btn.isEnabled()
    assert not dialog.download_btn.isEnabled()
    assert not dialog.delete_btn.isEnabled()
    assert dialog.status_label.text() == _word("plugin_dl_status_fetching", "Fetching plugin list...")
    assert len(dialog._workers) == 1
    assert isinstance(dialog._workers[0], pd.FetchPluginListWorker)


def test_list_fetched_groups_plugins_and_marks_installed(dialog):
    dialog._on_list_fetched(list(_LISTING))
    root = dialog.tree.invisibleRootItem()
    assert [root.child(i).text(0) for i in range(root.childCount())] == ["plugins", "languages"]
    cat = root.child(0)
    assert not cat.flags() & Qt.ItemFlag.ItemIsSelectable
    assert cat.isExpanded()
    assert _plugin_item(dialog, "alpha").text(1) == _word("plugin_dl_installed", "Installed")
    assert _plugin_item(dialog, "beta").text(1) == _word("plugin_dl_not_installed", "Not Installed")
    assert _plugin_item(dialog, "gamma").data(0, Qt.ItemDataRole.UserRole) == ("gamma", [])
    assert dialog.status_label.text() == _word(
        "plugin_dl_status_found", "Found {count} plugin(s)").format(count=3)
    assert dialog.refresh_btn.isEnabled()
    assert dialog._plugin_data == _LISTING


def test_list_error_shows_the_message(dialog):
    dialog._on_list_error("rate limited")
    assert dialog.status_label.text() == _word(
        "plugin_dl_status_error", "Error: {error}").format(error="rate limited")
    assert dialog.refresh_btn.isEnabled()


def test_selection_drives_the_download_and_delete_buttons(dialog):
    dialog._on_list_fetched(list(_LISTING))
    _plugin_item(dialog, "beta").setSelected(True)
    assert dialog.download_btn.isEnabled()
    assert not dialog.delete_btn.isEnabled()
    assert dialog.download_btn.text() == _word("plugin_dl_download", "Download")
    dialog.tree.clearSelection()
    _plugin_item(dialog, "alpha").setSelected(True)
    assert dialog.delete_btn.isEnabled()
    assert dialog.download_btn.text() == _word("plugin_dl_reinstall", "Reinstall")
    dialog.tree.clearSelection()
    assert not dialog.download_btn.isEnabled()
    assert not dialog.delete_btn.isEnabled()


def test_delete_removes_the_plugin_after_confirmation(dialog, tmp_path, monkeypatch):
    dialog._on_list_fetched(list(_LISTING))
    _plugin_item(dialog, "alpha").setSelected(True)
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    dialog._delete_selected()
    assert not (tmp_path / "alpha").exists()
    assert dialog.status_label.text() == _word(
        "plugin_dl_status_deleted", "Deleted {name}.").format(name="alpha")
    assert _plugin_item(dialog, "alpha").text(1) == _word("plugin_dl_not_installed", "Not Installed")
    assert not dialog.delete_btn.isEnabled()


def test_delete_keeps_the_plugin_when_declined(dialog, tmp_path, monkeypatch):
    dialog._on_list_fetched(list(_LISTING))
    _plugin_item(dialog, "alpha").setSelected(True)
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.No)
    dialog._delete_selected()
    assert (tmp_path / "alpha" / "__init__.py").exists()


def test_delete_and_download_without_selection_do_nothing(dialog, monkeypatch):
    def never(*_a):
        raise AssertionError("must not ask")

    monkeypatch.setattr(QMessageBox, "question", never)
    dialog._on_list_fetched(list(_LISTING))
    before = list(dialog._workers)
    dialog._delete_selected()
    dialog._download_selected()
    assert dialog._workers == before


def test_download_selected_registers_and_starts_one_job(dialog, monkeypatch):
    added = []

    class _Registry:
        def add(self, worker, title, retry):
            added.append((worker, title, retry))

    owner = sys.modules[pd.PluginDownloaderDialog.__module__]
    monkeypatch.setattr(owner, "job_registry", _Registry)
    dialog._on_list_fetched(list(_LISTING))
    _plugin_item(dialog, "beta").setSelected(True)
    dialog._download_selected()
    ((worker, title, retry),) = added
    assert isinstance(worker, pd.DownloadPluginWorker)
    assert worker.plugin_name == "beta"
    assert title == dialog.windowTitle()
    assert retry(("beta",)).file_infos == _LISTING[1][2]
    assert worker in dialog._workers
    assert dialog.progress_bar.maximum() == 1
    assert not dialog.download_btn.isEnabled()
    assert dialog.status_label.text() == _word(
        "plugin_dl_status_downloading", "Downloading {name}...").format(name="beta")


def test_download_progress_moves_the_bar(dialog):
    dialog._on_download_progress(2, 5)
    assert dialog.progress_bar.maximum() == 5
    assert dialog.progress_bar.value() == 2


def test_download_error_restores_the_controls(dialog):
    dialog._on_list_fetched(list(_LISTING))
    dialog.progress_bar.setVisible(True)
    dialog._on_download_error("offline")
    assert dialog.progress_bar.isHidden()
    assert dialog.refresh_btn.isEnabled()
    assert dialog.status_label.text() == _word(
        "plugin_dl_status_error", "Error: {error}").format(error="offline")


def test_download_finished_informs_and_accepts(dialog, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: shown.append(args[2]))
    dialog._on_list_fetched(list(_LISTING))
    dialog._on_download_finished("beta")
    assert len(shown) == 1 and "beta" in shown[0]
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.status_label.text() == _word(
        "plugin_dl_status_done", "Downloaded {name} successfully!").format(name="beta")


def test_stop_worker_with_only_idle_workers_needs_no_retirement(dialog):
    assert dialog._stop_worker() is False
    assert dialog._workers == []


def test_cleanup_drops_workers_that_are_not_running(dialog):
    dialog._cleanup_finished_workers()
    assert dialog._workers == []
