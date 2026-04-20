"""Named workspace presets — window geometry + layout snapshots.

A *workspace* captures the parts of the main window that the user might want
to flip between — root folder, window geometry, dock / toolbar state, and
the current splitter sizes. Users can save the current layout under a name
and restore it later (think Lightroom workspaces or VS Code profiles).

The data is persisted in ``user_setting_dict`` under the ``workspaces`` key
so workspaces survive across sessions without a separate config file.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

logger = logging.getLogger("Imervue.workspaces")

_SETTING_KEY = "workspaces"
_MAX_NAME_LEN = 64


@dataclass
class Workspace:
    """Snapshot of the main window layout the user wants to restore later."""

    name: str
    geometry_b64: str = ""
    state_b64: str = ""
    maximized: bool = True
    root_folder: str = ""
    splitter_sizes: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workspace:
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("Workspace name is required")
        return cls(
            name=name[:_MAX_NAME_LEN],
            geometry_b64=str(data.get("geometry_b64", "")),
            state_b64=str(data.get("state_b64", "")),
            maximized=bool(data.get("maximized", True)),
            root_folder=str(data.get("root_folder", "")),
            splitter_sizes=[int(v) for v in (data.get("splitter_sizes") or [])],
        )


class WorkspaceManager:
    """Load/save named workspace presets from ``user_setting_dict``.

    The on-disk representation lives under ``user_setting_dict["workspaces"]``
    as a list of plain dicts — they round-trip cleanly through JSON and do
    not pull any PySide6 imports into the settings layer.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Workspace] | None = None

    # ---- persistence -------------------------------------------------

    def _load(self) -> dict[str, Workspace]:
        if self._cache is not None:
            return self._cache
        raw = user_setting_dict.get(_SETTING_KEY) or []
        workspaces: dict[str, Workspace] = {}
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                ws = Workspace.from_dict(entry)
            except (ValueError, TypeError):
                logger.warning("Skipping malformed workspace entry: %r", entry)
                continue
            workspaces[ws.name] = ws
        self._cache = workspaces
        return workspaces

    def _flush(self) -> None:
        cache = self._cache if self._cache is not None else self._load()
        user_setting_dict[_SETTING_KEY] = [ws.to_dict() for ws in cache.values()]
        schedule_save()

    def invalidate(self) -> None:
        """Drop the in-memory cache so the next ``list_all`` re-reads settings."""
        self._cache = None

    # ---- queries -----------------------------------------------------

    def list_all(self) -> list[Workspace]:
        return sorted(self._load().values(), key=lambda ws: ws.name.lower())

    def get(self, name: str) -> Workspace | None:
        return self._load().get(name)

    # ---- mutations ---------------------------------------------------

    def save(self, workspace: Workspace) -> None:
        name = workspace.name.strip()
        if not name:
            raise ValueError("Workspace name cannot be empty")
        workspace.name = name[:_MAX_NAME_LEN]
        cache = self._load()
        cache[workspace.name] = workspace
        self._flush()

    def delete(self, name: str) -> bool:
        cache = self._load()
        if name in cache:
            del cache[name]
            self._flush()
            return True
        return False

    def rename(self, old_name: str, new_name: str) -> bool:
        new_name = new_name.strip()[:_MAX_NAME_LEN]
        if not new_name:
            raise ValueError("New workspace name cannot be empty")
        cache = self._load()
        if old_name not in cache or new_name in cache:
            return False
        ws = cache.pop(old_name)
        ws.name = new_name
        cache[new_name] = ws
        self._flush()
        return True


def encode_bytes(data: bytes) -> str:
    """Encode raw bytes (e.g. ``QByteArray`` data) as a base64 ASCII string."""
    return base64.b64encode(bytes(data)).decode("ascii")


def decode_bytes(text: str) -> bytes:
    """Inverse of ``encode_bytes`` — returns raw bytes, or b"" on invalid input."""
    if not text:
        return b""
    try:
        return base64.b64decode(text.encode("ascii"))
    except (ValueError, TypeError):
        logger.warning("Invalid base64 payload in workspace")
        return b""


workspace_manager = WorkspaceManager()
