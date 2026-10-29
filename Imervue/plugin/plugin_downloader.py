"""Plugin downloader: the public import location for the distribution-repo contract.

Holds the repository URL and branch, the one-call recursive tree listing and its
walk (``parse_plugin_tree``), path-component validation and the ``_https_urlopen``
guard. The workers live in :mod:`plugin_downloader_workers` and the dialog in
:mod:`plugin_downloader_dialog`; both read ``_https_urlopen``, ``_github_get`` and
``_get_plugin_dir`` from this module at call time, so patching them here reaches
every request and file write.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse

from Imervue.system.app_paths import plugins_dir as _plugins_dir
from Imervue.plugin.plugin_downloader_workers import (
    _EXPECTED_FETCH_ERRORS,
    DownloadPluginWorker,
    FetchPluginListWorker,
    _retry_download,
    needs_newer_text,
)
from Imervue.plugin.plugin_downloader_dialog import PluginDownloaderDialog

__all__ = [
    "_EXPECTED_FETCH_ERRORS", "PLUGIN_CATEGORIES", "RAW_BASE_URL", "REPO_BRANCH", "REPO_TREE_URL",
    "DownloadPluginWorker", "FetchPluginListWorker", "PluginDownloaderDialog", "PluginListing",
    "_get_plugin_dir", "_github_get", "_https_urlopen", "_is_hidden", "_retry_download",
    "is_safe_path_component", "needs_newer_text", "parse_plugin_tree",
]


def _https_urlopen(req: urllib.request.Request, timeout: int):
    """urlopen that refuses non-https schemes.

    Guards against compromised GitHub API responses that might supply a
    non-https download URL. Bandit B310 is satisfied once the scheme is
    verified before the request is issued.
    """
    scheme = urlparse(req.full_url).scheme
    if scheme != "https":
        raise ValueError(f"Refusing non-https URL scheme: {scheme!r}")
    return urllib.request.urlopen(req, timeout=timeout)  # nosec B310  # scheme validated above


REPO_BRANCH = "main"
# One recursive tree listing replaces a Contents API call per directory, which
# spent ~20 of the 60 requests per hour GitHub allows an unauthenticated client
# every time the dialog opened. File downloads go through raw.githubusercontent,
# which is not charged against that API limit.
REPO_TREE_URL = (
    "https://api.github.com/repos/Jeffrey-Plugin-Repos/Imervue_Plugins"
    f"/git/trees/{REPO_BRANCH}?recursive=1"
)
RAW_BASE_URL = (
    f"https://raw.githubusercontent.com/Jeffrey-Plugin-Repos/Imervue_Plugins/{REPO_BRANCH}"
)
# Only these top-level directories of the distribution repository hold plugins;
# anything else there (docs, CI config) is not offered for download.
PLUGIN_CATEGORIES: tuple[str, ...] = ("plugins", "languages")

PluginListing = tuple[str, str, list[dict]]


def _get_plugin_dir() -> Path:
    return _plugins_dir()


def _github_get(url: str) -> list | dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    with _https_urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _is_hidden(name: str) -> bool:
    return name.startswith((".", "__"))


# Characters Windows refuses or treats as a separator in a file name. A git tree
# path is split on "/" only, so a name pushed from Linux can still carry a
# backslash (``..\evil.py``) and step outside the plugin directory on Windows.
_UNSAFE_NAME_CHARS = frozenset('\\/:*?"<>|')


def is_safe_path_component(name: str) -> bool:
    """True if *name* can be one plain file or directory name on every platform.

    Rejects empty names, ``.`` and ``..``, separators and characters Windows
    forbids, control characters, and a trailing dot or space (Windows drops
    them, so the name would resolve to a different file).
    """
    if not name or name in (".", "..") or name[-1] in ". ":
        return False
    return not any(ch in _UNSAFE_NAME_CHARS or ord(ch) < 32 for ch in name)


def parse_plugin_tree(tree: dict) -> list[PluginListing]:
    """Group a recursive git tree listing into ``(category, plugin, files)``.

    A plugin is a directory directly inside one of :data:`PLUGIN_CATEGORIES`;
    only the files directly inside it are listed, because nested directories
    (``models/``, ``assets/``) are never downloaded. Hidden and dunder
    directories (``.git``, ``__pycache__``) are skipped. Plugins come back in
    category order, then by name; each file carries ``name``, ``path`` and a
    raw ``download_url``. Raises ``ValueError`` if GitHub truncated the listing.
    """
    if tree.get("truncated"):
        raise ValueError("The plugin repository listing was truncated by GitHub")
    grouped: dict[tuple[str, str], list[dict]] = {}
    for entry in tree.get("tree", []):
        path = entry.get("path", "")
        parts = path.split("/")
        if len(parts) not in (2, 3) or parts[0] not in PLUGIN_CATEGORIES:
            continue
        if _is_hidden(parts[1]) or not all(is_safe_path_component(p) for p in parts[1:]):
            continue
        key = (parts[0], parts[1])
        if len(parts) == 2 and entry.get("type") == "tree":
            grouped.setdefault(key, [])
        elif len(parts) == 3 and entry.get("type") == "blob":
            grouped.setdefault(key, []).append({
                "name": parts[2],
                "path": path,
                "download_url": f"{RAW_BASE_URL}/{quote(path)}",
            })
    ordered = sorted(grouped, key=lambda k: (PLUGIN_CATEGORIES.index(k[0]), k[1]))
    return [
        (category, name, sorted(grouped[(category, name)], key=lambda f: f["name"]))
        for category, name in ordered
    ]
