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

    return {
        "version": SESSION_VERSION,
        "tabs": tabs,
        "active_tab": getattr(ui, "_tab_bar", None).currentIndex() if hasattr(ui, "_tab_bar") else 0,
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


def restore_session(ui: ImervueMainWindow, data: dict[str, Any]) -> dict[str, int]:
    """Apply ``data`` to the UI best-effort. Returns counts of applied vs skipped."""
    from Imervue.gpu_image_view.images.image_loader import open_path

    applied = 0
    skipped = 0

    tabs = data.get("tabs") or []
    if hasattr(ui, "_image_tabs") and hasattr(ui, "_tab_bar"):
        ui._tab_switching = True
        try:
            while ui._tab_bar.count() > 0:
                ui._tab_bar.removeTab(0)
            ui._image_tabs.clear()
            for tab in tabs:
                path = tab.get("path", "") if isinstance(tab, dict) else ""
                if path and not Path(path).exists():
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

    current = data.get("current_image") or ""
    if current and Path(current).exists():
        try:
            open_path(main_gui=ui.viewer, path=current)
            applied += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to reopen %s: %s", current, exc)
            skipped += 1

    selection = data.get("selection") or []
    selected_tiles = getattr(ui.viewer, "selected_tiles", None)
    if isinstance(selected_tiles, set):
        selected_tiles.clear()
        for path in selection:
            if Path(path).exists():
                selected_tiles.add(path)

    return {"applied": applied, "skipped": skipped}
