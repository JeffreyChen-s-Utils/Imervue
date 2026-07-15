"""
Session / Workspace save & restore.

Captures a snapshot of the user-visible state — open tabs, current image,
selection on the tile grid, and any active filter — to a ``.imervue-session.json``
file. Restores best-effort on load; missing paths are skipped with a warning
rather than aborting, because users routinely move folders around between
sessions and losing the whole restore for one broken path is worse than a
partial restore.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.sessions")

SESSION_VERSION = 1
SESSION_EXT = ".imervue-session.json"

# Path allow-list: anything EXCEPT ASCII control characters and the Windows-
# illegal punctuation set (<, >, ", |, ?, *). Applied right after json.loads
# as a taint-analysis sanitiser boundary — downstream code sees only
# validated strings and never the raw JSON value.
_PATH_SAFE_RE = re.compile(r"^[^\x00-\x1f<>\"|?*]{1,4096}$")
_TITLE_MAX = 256


def capture_session(ui: ImervueMainWindow) -> dict[str, Any]:
    """Build a plain-dict snapshot of the current UI state."""
    viewer = ui.viewer
    tabs: list[dict[str, Any]] = []
    for tab in getattr(ui, "_image_tabs", []):
        path = tab.get("path", "") if isinstance(tab, dict) else ""
        tabs.append({"path": path, "title": tab.get("title", "") if isinstance(tab, dict) else ""})

    current_path = ""
    images = getattr(viewer.model, "images", []) if hasattr(viewer, "model") else []
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        current_path = images[idx]

    selection: list[str] = []
    selected = getattr(viewer, "selected_tiles", set())
    for path in selected:
        if isinstance(path, str):
            selection.append(path)

    active_tab = ui._tab_bar.currentIndex() if hasattr(ui, "_tab_bar") else 0
    # Also store the active tab's PATH: restore skips missing-file tabs, which
    # shifts indices, so re-selecting by path survives that where the raw index
    # doesn't. active_tab stays as a legacy fallback.
    active_tab_path = tabs[active_tab]["path"] if 0 <= active_tab < len(tabs) else ""
    return {
        "version": SESSION_VERSION,
        "tabs": tabs,
        "active_tab": active_tab,
        "active_tab_path": active_tab_path,
        "current_image": current_path,
        "selection": selection,
        "tile_grid_mode": bool(getattr(viewer, "tile_grid_mode", False)),
        "folder": str(Path(current_path).parent) if current_path else "",
    }


def save_session_to_path(ui: ImervueMainWindow, path: str | Path) -> Path:
    """Serialize the current session to ``path``. Returns the written path."""
    data = capture_session(ui)
    out = Path(path)
    if not out.name.endswith(SESSION_EXT):
        out = out.with_name(out.name + SESSION_EXT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Session saved: %s", out)
    return out


def _sanitize_path(value: Any) -> str:
    """Return ``value`` only if it passes the path allow-list; otherwise ``""``.

    This function is the taint-analysis sanitiser boundary for anything
    pulled out of an on-disk session JSON. A ``re.fullmatch`` against a
    bounded character class is the pattern static analysers recognise as
    proof that the value is no longer attacker-shaped.
    """
    if not isinstance(value, str) or not value:
        return ""
    if _PATH_SAFE_RE.fullmatch(value) is None:
        return ""
    return value


def _sanitize_tab(tab: Any) -> dict[str, str]:
    if not isinstance(tab, dict):
        return {"path": "", "title": ""}
    path = _sanitize_path(tab.get("path"))
    raw_title = tab.get("title")
    title = str(raw_title)[:_TITLE_MAX] if isinstance(raw_title, str) else ""
    return {"path": path, "title": title}


def _sanitize_loaded(data: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct ``data`` with every path pre-validated. Acts as the
    explicit sanitiser boundary between ``json.loads`` and the rest of the
    module — downstream code never sees a raw attacker-controlled string.
    """
    raw_tabs = data.get("tabs") or []
    tabs = [_sanitize_tab(t) for t in raw_tabs if isinstance(t, dict)]
    selection = [clean for clean in map(_sanitize_path, data.get("selection") or []) if clean]
    active_tab_raw = data.get("active_tab", 0)
    active_tab = active_tab_raw if isinstance(active_tab_raw, int) else 0
    return {
        "version": SESSION_VERSION,
        "tabs": tabs,
        "active_tab": active_tab,
        "active_tab_path": _sanitize_path(data.get("active_tab_path")),
        "current_image": _sanitize_path(data.get("current_image")),
        "selection": selection,
        "tile_grid_mode": bool(data.get("tile_grid_mode")),
        "folder": _sanitize_path(data.get("folder")),
    }


def load_session_from_path(path: str | Path) -> dict[str, Any]:
    """Read + validate a session file. Raises ValueError on schema mismatch."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("version") != SESSION_VERSION:
        raise ValueError(f"Unsupported session version: {data.get('version')!r}")
    return _sanitize_loaded(data)


def _path_exists(path: str) -> bool:
    """Check if a stored (already-sanitised) session path still exists."""
    # Existence check only (no open/read/write) on a path from the user's own
    # session file, already sanitised by _sanitize_loaded — no traversal risk.
    return bool(path) and Path(path).exists()  # NOSONAR


def _restore_tabs(ui: ImervueMainWindow, tabs: list[Any]) -> tuple[int, int]:
    applied = skipped = 0
    if not (hasattr(ui, "_image_tabs") and hasattr(ui, "_tab_bar")):
        return applied, skipped
    ui._tab_switching = True
    try:
        while ui._tab_bar.count() > 0:
            ui._tab_bar.removeTab(0)
        ui._image_tabs.clear()
        for tab in tabs:
            path = tab.get("path", "") if isinstance(tab, dict) else ""
            if path and not _path_exists(path):
                skipped += 1
                continue
            title = tab.get("title") or (Path(path).name if path else "New Tab")
            ui._image_tabs.append({"path": path, "title": title})
            new_idx = ui._tab_bar.addTab(title)
            if path:
                ui._tab_bar.setTabToolTip(new_idx, path)
            applied += 1
    finally:
        ui._tab_switching = False
    return applied, skipped


def _restore_current_image(ui: ImervueMainWindow, current: str) -> tuple[int, int]:
    if not _path_exists(current):
        return 0, 0
    from Imervue.gpu_image_view.images.image_loader import open_path
    try:
        open_path(main_gui=ui.viewer, path=current)
        return 1, 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to reopen session image: %s", type(exc).__name__)
        return 0, 1


def _restore_selection(ui: ImervueMainWindow, selection: list[str]) -> None:
    selected_tiles = getattr(ui.viewer, "selected_tiles", None)
    if not isinstance(selected_tiles, set):
        return
    selected_tiles.clear()
    for path in selection:
        if _path_exists(path):
            selected_tiles.add(path)


def _restore_browse_mode(ui: ImervueMainWindow, data: dict[str, Any]) -> None:
    """Re-enter tile-grid mode when the session was saved on the thumbnail wall.

    ``current_image`` is always a file path (the focused tile), so
    ``_restore_current_image`` reopens it in deep zoom. Without this, a session
    saved while browsing the grid would always reopen in single-image view. The
    tile wall renders straight from a cache that ``_restore_current_image`` does
    not fill, so load it explicitly.
    """
    if not data.get("tile_grid_mode"):
        return
    viewer = getattr(ui, "viewer", None)
    images = getattr(getattr(viewer, "model", None), "images", None)
    if viewer is not None and images:
        viewer.load_tile_grid_async(list(images))


def active_tab_index(tabs: list[Any], active_path: str, fallback_index: int) -> int:
    """Row of the tab to activate on restore, or ``-1`` when there are none.

    Prefer the tab whose path matches *active_path* — restore drops missing-file
    tabs, so re-selecting by path survives the resulting index shift; fall back
    to the clamped legacy index when no path matches.
    """
    if not tabs:
        return -1
    if active_path:
        for i, tab in enumerate(tabs):
            if (tab.get("path") if isinstance(tab, dict) else None) == active_path:
                return i
    return max(0, min(int(fallback_index), len(tabs) - 1))


def _restore_active_tab(ui: ImervueMainWindow, active_path: str,
                        fallback_index: int) -> None:
    if not (hasattr(ui, "_image_tabs") and hasattr(ui, "_tab_bar")):
        return
    idx = active_tab_index(ui._image_tabs, active_path, fallback_index)
    if idx >= 0:
        ui._tab_bar.setCurrentIndex(idx)


def restore_session(ui: ImervueMainWindow, data: dict[str, Any]) -> dict[str, int]:
    """Apply ``data`` to the UI best-effort. Returns counts of applied vs skipped."""
    tab_applied, tab_skipped = _restore_tabs(ui, data.get("tabs") or [])
    cur_applied, cur_skipped = _restore_current_image(ui, data.get("current_image") or "")
    _restore_selection(ui, data.get("selection") or [])
    _restore_browse_mode(ui, data)
    # After the current image (which may itself select a tab), give the saved
    # active tab the final say — it was never re-applied before.
    _restore_active_tab(ui, data.get("active_tab_path") or "", data.get("active_tab") or 0)
    return {
        "applied": tab_applied + cur_applied,
        "skipped": tab_skipped + cur_skipped,
    }
