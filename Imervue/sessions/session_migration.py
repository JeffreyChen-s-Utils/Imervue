"""Validate, version-migrate and merge ``.imervue-session.json`` snapshots.

``session_manager._sanitize_loaded`` silently cleans a session as it loads;
these helpers complement it: :func:`validate_session` *reports* what's wrong
(for a "this session looks corrupt" warning), :func:`migrate_session` brings a
partial / older snapshot up to the current schema (every key present, version
stamped) so it loads cleanly, and :func:`merge_sessions` unions several
snapshots for workspace recovery. Pure dict work — no Qt.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from Imervue.sessions.session_manager import SESSION_VERSION

_DEFAULTS: dict[str, Any] = {
    "version": SESSION_VERSION,
    "tabs": [],
    "active_tab": 0,
    "current_image": "",
    "selection": [],
    "tile_grid_mode": False,
    "folder": "",
}


def validate_session(data: Any) -> list[str]:
    """Return a list of problems with *data* (empty list = a valid session)."""
    if not isinstance(data, dict):
        return ["session must be a JSON object"]
    errors: list[str] = []
    _validate_version(data, errors)
    tabs = data.get("tabs")
    _validate_tabs(tabs, errors)
    _validate_active_tab(data.get("active_tab", 0), tabs, errors)
    if data.get("selection") is not None and not isinstance(data.get("selection"), list):
        errors.append("'selection' must be a list")
    return errors


def _validate_version(data: dict, errors: list[str]) -> None:
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        errors.append("missing or non-integer 'version'")
    elif version > SESSION_VERSION:
        errors.append(
            f"session version {version} is newer than supported {SESSION_VERSION}",
        )


def _validate_tabs(tabs: Any, errors: list[str]) -> None:
    if tabs is None:
        return
    if not isinstance(tabs, list):
        errors.append("'tabs' must be a list")
        return
    for i, tab in enumerate(tabs):
        if not isinstance(tab, dict) or not isinstance(tab.get("path", ""), str):
            errors.append(f"tab {i} is malformed")


def _validate_active_tab(active: Any, tabs: Any, errors: list[str]) -> None:
    if not isinstance(active, int) or isinstance(active, bool):
        errors.append("'active_tab' must be an integer")
    elif isinstance(tabs, list) and tabs and not 0 <= active < len(tabs):
        errors.append(f"active_tab {active} out of range for {len(tabs)} tab(s)")


def migrate_session(data: Any) -> dict[str, Any]:
    """Return a current-schema dict: every key present, version stamped.

    A partial or older snapshot has missing keys filled with typed defaults and
    its version raised to the current one; an already-current snapshot is
    unchanged; a future-version snapshot keeps its version (validate first).
    """
    if not isinstance(data, dict):
        return _fresh_defaults()
    out = dict(data)
    for key, default in _DEFAULTS.items():
        out.setdefault(key, default.copy() if isinstance(default, list) else default)
    if not isinstance(out.get("version"), int) or out["version"] < SESSION_VERSION:
        out["version"] = SESSION_VERSION
    return out


def merge_sessions(sessions: Iterable[dict]) -> dict[str, Any]:
    """Union several snapshots: tabs (deduped by path) and selection (deduped),
    taking the first snapshot's ``active_tab`` / ``current_image`` / ``folder``."""
    merged = _fresh_defaults()
    seen_paths: set[str] = set()
    seen_selection: set[str] = set()
    items = [s for s in sessions if isinstance(s, dict)]
    for snapshot in items:
        _collect_tabs(snapshot.get("tabs") or [], seen_paths, merged["tabs"])
        _collect_selection(
            snapshot.get("selection") or [], seen_selection, merged["selection"])
    if items:
        _carry_first(items[0], merged)
    return merged


def _collect_tabs(raw_tabs: Any, seen: set[str], out: list[dict]) -> None:
    for tab in raw_tabs:
        if not isinstance(tab, dict):
            continue
        path = tab.get("path", "")
        if isinstance(path, str) and path and path not in seen:
            seen.add(path)
            out.append({"path": path, "title": str(tab.get("title", ""))})


def _collect_selection(raw: Any, seen: set[str], out: list[str]) -> None:
    for path in raw:
        if isinstance(path, str) and path and path not in seen:
            seen.add(path)
            out.append(path)


def _carry_first(first: dict, merged: dict) -> None:
    for key in ("active_tab", "current_image", "folder", "tile_grid_mode"):
        value = first.get(key)
        if isinstance(value, type(_DEFAULTS[key])) and not (
            isinstance(value, bool) and not isinstance(_DEFAULTS[key], bool)
        ):
            merged[key] = value


def _fresh_defaults() -> dict[str, Any]:
    return {
        key: default.copy() if isinstance(default, list) else default
        for key, default in _DEFAULTS.items()
    }
