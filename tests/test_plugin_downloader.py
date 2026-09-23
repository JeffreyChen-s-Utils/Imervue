"""Plugin list parsing and fetching for the plugin downloader.

The list comes from one recursive git-tree call. Only the ``plugins`` and
``languages`` categories count, only files directly inside a plugin
directory are offered, and hidden or dunder directories are skipped.
"""
from __future__ import annotations

import pytest

from Imervue.plugin import plugin_downloader as pd


def _blob(path: str) -> dict:
    return {"path": path, "type": "blob"}


def _tree_entry(path: str) -> dict:
    return {"path": path, "type": "tree"}


def _listing(*entries: dict, truncated: bool = False) -> dict:
    return {"sha": "abc", "tree": list(entries), "truncated": truncated}


def _names(results) -> list[tuple[str, str]]:
    return [(category, name) for category, name, _files in results]


# ---------------------------------------------------------------------------
# parse_plugin_tree
# ---------------------------------------------------------------------------


def test_categories_are_plugins_and_languages_only():
    assert pd.PLUGIN_CATEGORIES == ("plugins", "languages")


def test_parse_groups_flat_files_per_plugin():
    results = pd.parse_plugin_tree(_listing(
        _tree_entry("plugins"),
        _tree_entry("plugins/demo"),
        _blob("plugins/demo/demo_plugin.py"),
        _blob("plugins/demo/__init__.py"),
    ))
    assert _names(results) == [("plugins", "demo")]
    files = results[0][2]
    assert [f["name"] for f in files] == ["__init__.py", "demo_plugin.py"]
    assert files[0] == {
        "name": "__init__.py",
        "path": "plugins/demo/__init__.py",
        "download_url": f"{pd.RAW_BASE_URL}/plugins/demo/__init__.py",
    }


def test_parse_ignores_other_top_level_directories_and_root_files():
    results = pd.parse_plugin_tree(_listing(
        _blob("README.md"),
        _tree_entry("docs"),
        _tree_entry("docs/updates"),
        _blob("docs/updates/2026-09.md"),
        _tree_entry(".github"),
        _tree_entry(".github/workflows"),
        _blob(".github/workflows/ci.yml"),
        _tree_entry("plugins/demo"),
        _blob("plugins/demo/__init__.py"),
    ))
    assert _names(results) == [("plugins", "demo")]


def test_parse_skips_nested_directories_and_files_at_category_level():
    results = pd.parse_plugin_tree(_listing(
        _blob("languages/__init__.py"),
        _tree_entry("plugins/demo"),
        _blob("plugins/demo/__init__.py"),
        _tree_entry("plugins/demo/models"),
        _blob("plugins/demo/models/net.onnx"),
    ))
    assert [f["name"] for f in results[0][2]] == ["__init__.py"]
    assert _names(results) == [("plugins", "demo")]


def test_parse_skips_hidden_and_dunder_plugin_directories():
    results = pd.parse_plugin_tree(_listing(
        _tree_entry("plugins/.cache"),
        _blob("plugins/.cache/x.py"),
        _tree_entry("plugins/__pycache__"),
        _blob("plugins/__pycache__/x.pyc"),
        _tree_entry("plugins/demo"),
    ))
    assert _names(results) == [("plugins", "demo")]


def test_parse_keeps_empty_plugin_directory():
    results = pd.parse_plugin_tree(_listing(_tree_entry("plugins/empty")))
    assert results == [("plugins", "empty", [])]


def test_parse_orders_by_category_then_name():
    results = pd.parse_plugin_tree(_listing(
        _tree_entry("languages/spanish"),
        _tree_entry("plugins/zeta"),
        _tree_entry("plugins/alpha"),
    ))
    assert _names(results) == [
        ("plugins", "alpha"), ("plugins", "zeta"), ("languages", "spanish"),
    ]


def test_parse_quotes_the_download_url():
    results = pd.parse_plugin_tree(_listing(_blob("plugins/demo/my file.py")))
    assert results[0][2][0]["download_url"] == f"{pd.RAW_BASE_URL}/plugins/demo/my%20file.py"


def test_parse_empty_and_missing_tree():
    assert pd.parse_plugin_tree(_listing()) == []
    assert pd.parse_plugin_tree({}) == []


def test_parse_tolerates_entries_without_path_or_type():
    results = pd.parse_plugin_tree(_listing({}, {"path": "plugins/demo/a.py"}))
    assert results == []


def test_parse_rejects_truncated_listing():
    with pytest.raises(ValueError, match="truncated"):
        pd.parse_plugin_tree(_listing(_tree_entry("plugins/demo"), truncated=True))


def test_urls_point_at_the_same_branch():
    assert pd.REPO_TREE_URL.startswith("https://api.github.com/")
    assert f"/git/trees/{pd.REPO_BRANCH}?recursive=1" in pd.REPO_TREE_URL
    assert pd.RAW_BASE_URL.endswith(f"/{pd.REPO_BRANCH}")


# ---------------------------------------------------------------------------
# FetchPluginListWorker
# ---------------------------------------------------------------------------


def _run_fetch(monkeypatch, response):
    requested: list[str] = []

    def fake_get(url):
        requested.append(url)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(pd, "_github_get", fake_get)
    worker = pd.FetchPluginListWorker()
    results: list = []
    errors: list = []
    worker.result_ready.connect(results.append)
    worker.error.connect(errors.append)
    worker.run()
    return requested, results, errors


def test_fetch_makes_a_single_request(qapp, monkeypatch):
    requested, results, errors = _run_fetch(monkeypatch, _listing(
        _tree_entry("plugins/demo"), _blob("plugins/demo/__init__.py"),
    ))
    assert requested == [pd.REPO_TREE_URL]
    assert errors == []
    assert _names(results[0]) == [("plugins", "demo")]


def test_fetch_reports_network_errors(qapp, monkeypatch):
    _requested, results, errors = _run_fetch(monkeypatch, OSError("rate limit exceeded"))
    assert results == []
    assert errors == ["rate limit exceeded"]


def test_fetch_reports_unexpected_payload(qapp, monkeypatch):
    _requested, results, errors = _run_fetch(monkeypatch, [{"path": "plugins"}])
    assert results == []
    assert errors == ["Unexpected plugin repository listing"]


def test_fetch_reports_truncated_listing(qapp, monkeypatch):
    _requested, results, errors = _run_fetch(monkeypatch, _listing(truncated=True))
    assert results == []
    assert len(errors) == 1
    assert "truncated" in errors[0]


@pytest.mark.parametrize("exc", [
    OSError("offline"), ValueError("bad json"), KeyError("tree"), TypeError("odd shape"),
])
def test_fetch_expected_errors_log_no_traceback(qapp, monkeypatch, caplog, exc):
    with caplog.at_level("DEBUG", logger="Imervue"):
        _requested, results, errors = _run_fetch(monkeypatch, exc)
    assert (results, errors) == ([], [str(exc)])
    assert [r for r in caplog.records if r.exc_info] == []


def test_fetch_unexpected_error_is_reported_and_logged(qapp, monkeypatch, caplog):
    with caplog.at_level("DEBUG", logger="Imervue"):
        _requested, results, errors = _run_fetch(monkeypatch, RuntimeError("bug"))
    assert (results, errors) == ([], ["bug"])
    (record,) = [r for r in caplog.records if r.exc_info]
    assert record.exc_info[0] is RuntimeError

# ---------------------------------------------------------------------------
# Path safety: names from the listing become local file and directory names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["demo.py", "plugin_x", "my file.py", ".hidden", "a.b.c"])
def test_safe_path_components(name):
    assert pd.is_safe_path_component(name)


@pytest.mark.parametrize("name", [
    "", ".", "..", "..\\evil.py", "a\\b.py", "a/b", "C:x.py", "x.", "x ", "a*b", "a?b",
    'a"b', "a<b", "a>b", "a|b", "tab\tname", "nul\x00name",
])
def test_unsafe_path_components(name):
    assert not pd.is_safe_path_component(name)


def test_parse_skips_plugins_and_files_with_unsafe_names():
    results = pd.parse_plugin_tree(_listing(
        _tree_entry("plugins/good"),
        _blob("plugins/good/__init__.py"),
        _blob("plugins/good/..\\..\\evil.py"),
        _tree_entry("plugins/..\\escape"),
        _blob("plugins/..\\escape/__init__.py"),
    ))
    assert _names(results) == [("plugins", "good")]
    assert [f["name"] for f in results[0][2]] == ["__init__.py"]
