"""Workspace layout presets — named dock configurations.

The Paint workspace ships with five docks (Layers / Color / Brush /
Navigator / History) that the user can show, hide, dock to either
side, or float. Multi-monitor setups in particular benefit from
saving the layout as a named preset and switching between them.

This module is the Qt-free data model:

* :class:`DockState` — per-dock state: visibility, area
  (left/right/top/bottom/floating), display order within the area,
  and a width in pixels for sized panels.
* :class:`WorkspacePreset` — named bundle of dock states + the
  layout's overall size hint.
* Built-in presets cover four common workflows:
  ``Default`` — all docks visible, balanced layout
  ``Drawing`` — minimal dock chrome, brush + colour only
  ``Comic`` — manga workflow with reference + history docks
  ``Compact`` — everything tucked into the right column

Persistence + the lookup / list helpers mirror the canvas-preset
and brush-preset registries; the UI layer wires up the actual
widget moves above this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_workspace_presets"

DOCK_AREAS = ("left", "right", "top", "bottom", "floating")
DEFAULT_AREA = "right"

DOCK_NAMES = (
    "layers",
    "color",
    "brush",
    "navigator",
    "history",
    "reference",
)
MIN_SIZE_PX = 80
MAX_SIZE_PX = 4096


@dataclass(frozen=True)
class DockState:
    """Per-dock layout state."""

    name: str
    visible: bool = True
    area: str = DEFAULT_AREA
    order: int = 0
    size_px: int = 240

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("dock name must be non-empty")
        if self.area not in DOCK_AREAS:
            raise ValueError(
                f"unknown dock area {self.area!r}; expected one of {DOCK_AREAS}",
            )
        if not MIN_SIZE_PX <= int(self.size_px) <= MAX_SIZE_PX:
            raise ValueError(
                f"size_px must be in [{MIN_SIZE_PX}, {MAX_SIZE_PX}], "
                f"got {self.size_px!r}",
            )

    def to_dict(self) -> dict:
        return {
            "name": str(self.name),
            "visible": bool(self.visible),
            "area": str(self.area),
            "order": int(self.order),
            "size_px": int(self.size_px),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> DockState:
        if not isinstance(raw, dict):
            raise ValueError(
                f"dock state payload must be a dict, got {type(raw).__name__}",
            )
        area = str(raw.get("area", DEFAULT_AREA))
        if area not in DOCK_AREAS:
            area = DEFAULT_AREA
        return cls(
            name=str(raw.get("name", "")).strip() or "dock",
            visible=bool(raw.get("visible", True)),
            area=area,
            order=int(raw.get("order", 0)),
            size_px=max(MIN_SIZE_PX, min(MAX_SIZE_PX, int(raw.get("size_px", 240)))),
        )


@dataclass(frozen=True)
class WorkspacePreset:
    """Named layout — bundle of dock states."""

    name: str
    docks: tuple[DockState, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("workspace preset name must be non-empty")
        seen: set[str] = set()
        for dock in self.docks:
            if dock.name in seen:
                raise ValueError(
                    f"workspace preset {self.name!r} has duplicate dock {dock.name!r}",
                )
            seen.add(dock.name)

    def dock(self, name: str) -> DockState | None:
        for d in self.docks:
            if d.name == name:
                return d
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "docks": [d.to_dict() for d in self.docks],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> WorkspacePreset:
        if not isinstance(raw, dict):
            raise ValueError(
                f"preset payload must be a dict, got {type(raw).__name__}",
            )
        docks_raw = raw.get("docks") or []
        if not isinstance(docks_raw, list):
            docks_raw = []
        docks = []
        for d in docks_raw:
            try:
                docks.append(DockState.from_dict(d))
            except (ValueError, TypeError):
                continue
        # Drop duplicates with first-wins semantics.
        seen: set[str] = set()
        unique = []
        for d in docks:
            if d.name in seen:
                continue
            seen.add(d.name)
            unique.append(d)
        return cls(
            name=str(raw.get("name", "")).strip() or "preset",
            docks=tuple(unique),
        )


# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------


BUILT_IN_PRESETS: tuple[WorkspacePreset, ...] = (
    WorkspacePreset(
        name="Default",
        docks=(
            DockState("layers", area="right", order=0, size_px=240),
            DockState("color", area="right", order=1, size_px=240),
            DockState("brush", area="left", order=0, size_px=240),
            DockState("navigator", area="left", order=1, size_px=200),
            DockState("history", area="right", order=2, size_px=200),
            DockState("reference", visible=False),
        ),
    ),
    WorkspacePreset(
        name="Drawing",
        docks=(
            DockState("brush", area="left", order=0, size_px=260),
            DockState("color", area="left", order=1, size_px=260),
            DockState("layers", area="right", order=0, size_px=240),
            DockState("navigator", visible=False),
            DockState("history", visible=False),
            DockState("reference", visible=False),
        ),
    ),
    WorkspacePreset(
        name="Comic",
        docks=(
            DockState("brush", area="left", order=0, size_px=240),
            DockState("color", area="left", order=1, size_px=240),
            DockState("reference", area="left", order=2, size_px=320, visible=True),
            DockState("layers", area="right", order=0, size_px=260),
            DockState("history", area="right", order=1, size_px=200),
            DockState("navigator", area="right", order=2, size_px=200),
        ),
    ),
    WorkspacePreset(
        name="Compact",
        docks=(
            DockState("layers", area="right", order=0, size_px=220),
            DockState("color", area="right", order=1, size_px=220),
            DockState("brush", area="right", order=2, size_px=220),
            DockState("navigator", area="right", order=3, size_px=180),
            DockState("history", visible=False),
            DockState("reference", visible=False),
        ),
    ),
)


def find_built_in(name: str) -> WorkspacePreset | None:
    for preset in BUILT_IN_PRESETS:
        if preset.name == name:
            return preset
    return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_workspace_presets(presets: list[WorkspacePreset]) -> None:
    """Persist user-defined presets (whole list replace)."""
    user_setting_dict[_USER_SETTING_KEY] = [p.to_dict() for p in presets]
    schedule_save()


def load_workspace_presets() -> list[WorkspacePreset]:
    """Return persisted user presets; corrupt entries skipped."""
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[WorkspacePreset] = []
    for entry in raw:
        try:
            out.append(WorkspacePreset.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return out


def all_workspace_presets() -> list[WorkspacePreset]:
    """Built-ins + user presets in display order."""
    return list(BUILT_IN_PRESETS) + load_workspace_presets()
