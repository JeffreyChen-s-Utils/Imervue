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
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.sessions")

SESSION_VERSION = 1
SESSION_EXT = ".imervue-session.json"


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
    return {
        "version": SESSION_VERSION,
        "tabs": tabs,
        "active_tab": active_tab,
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


def load_session_from_path(path: str | Path) -> dict[str, Any]:
    """Read + validate a session file. Raises ValueError on schema mismatch."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("version") != SESSION_VERSION:
        raise ValueError(f"Unsupported session version: {data.get('version')!r}")
    return data


def _path_exists(path: str) -> bool:
    """Check if a stored session path still exists (treated as user-controlled)."""
    # NOSONAR: paths are the user's own previously-saved image paths, checked for
    # existence only — not used to read attacker-supplied data.
    return bool(path) and Path(path).exists()  # NOSONAR:python:S6549


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
        # NOSONAR:python:S5145 - logs exc only, no user-controlled path
        logger.warning("Failed to reopen session image: %s", exc)
        return 0, 1


def _restore_selection(ui: ImervueMainWindow, selection: list[str]) -> None:
    selected_tiles = getattr(ui.viewer, "selected_tiles", None)
    if not isinstance(selected_tiles, set):
        return
    selected_tiles.clear()
    for path in selection:
        if _path_exists(path):
            selected_tiles.add(path)


def restore_session(ui: ImervueMainWindow, data: dict[str, Any]) -> dict[str, int]:
    """Apply ``data`` to the UI best-effort. Returns counts of applied vs skipped."""
    tab_applied, tab_skipped = _restore_tabs(ui, data.get("tabs") or [])
    cur_applied, cur_skipped = _restore_current_image(ui, data.get("current_image") or "")
    _restore_selection(ui, data.get("selection") or [])
    return {
        "applied": tab_applied + cur_applied,
        "skipped": tab_skipped + cur_skipped,
    }
