"""Named brush configurations — save / load / built-in catalogue.

A brush preset captures every parameter the user has tweaked for a
specific feel (kind, size, opacity, hardness, density, blend mode,
stabiliser, custom tip path) under one human-readable name. The
Paint workspace's brush dock can then jump between presets via a
single click instead of redialling four sliders.

JSON-friendly: :class:`BrushPreset` is a frozen dataclass with
``to_dict`` / ``from_dict`` and the persistence helpers round-trip
through ``user_setting_dict["paint_brush_presets"]``.

Built-in presets ship a small starter catalogue — "Soft Round",
"Hard Pen", "Pencil Sketch", "Marker Bold", "Airbrush" — that
mirrors the kinds the brush rasteriser already supports. Loading
order is built-ins first, then user presets, so a preset with the
same name as a built-in falls *after* it (the UI deduplicates by
showing the user-defined one).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from Imervue.paint.tool_state import (
    BLEND_MODES,
    BRUSH_DENSITY_MAX,
    BRUSH_DENSITY_MIN,
    BRUSH_HARDNESS_MAX,
    BRUSH_HARDNESS_MIN,
    BRUSH_KINDS,
    BRUSH_OPACITY_MAX,
    BRUSH_OPACITY_MIN,
    BRUSH_SIZE_MAX,
    BRUSH_SIZE_MIN,
    BrushSettings,
    DEFAULT_BLEND_MODE,
    DEFAULT_BRUSH_KIND,
)
from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_brush_presets"
_GROUPS_USER_SETTING_KEY = "paint_brush_preset_groups"
MAX_GROUPS = 64
MAX_PRESETS_PER_GROUP = 256


@dataclass(frozen=True)
class BrushPreset:
    """A named, frozen snapshot of brush parameters.

    Construct via :meth:`from_settings` to avoid duplicating the
    field list, or directly via the dataclass constructor when you
    already have the parameters.
    """

    name: str
    kind: str = DEFAULT_BRUSH_KIND
    size: int = 12
    opacity: float = 1.0
    hardness: float = 0.8
    density: float = 1.0
    blend_mode: str = DEFAULT_BLEND_MODE
    stabilizer: float = 0.0
    tip_path: str | None = None

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("preset name must be non-empty")
        if self.kind not in BRUSH_KINDS:
            raise ValueError(
                f"unknown kind {self.kind!r}; expected one of {BRUSH_KINDS}",
            )
        if self.blend_mode not in BLEND_MODES:
            raise ValueError(
                f"unknown blend_mode {self.blend_mode!r}; "
                f"expected one of {BLEND_MODES}",
            )
        if not BRUSH_SIZE_MIN <= int(self.size) <= BRUSH_SIZE_MAX:
            raise ValueError(
                f"size must be in [{BRUSH_SIZE_MIN}, {BRUSH_SIZE_MAX}], "
                f"got {self.size!r}",
            )
        for key, value, lo, hi in (
            ("opacity", self.opacity, BRUSH_OPACITY_MIN, BRUSH_OPACITY_MAX),
            ("hardness", self.hardness, BRUSH_HARDNESS_MIN, BRUSH_HARDNESS_MAX),
            ("density", self.density, BRUSH_DENSITY_MIN, BRUSH_DENSITY_MAX),
            ("stabilizer", self.stabilizer, 0.0, 1.0),
        ):
            if not lo <= float(value) <= hi:
                raise ValueError(
                    f"{key} must be in [{lo}, {hi}], got {value!r}",
                )

    @classmethod
    def from_settings(cls, name: str, brush: BrushSettings) -> BrushPreset:
        return cls(
            name=name,
            kind=brush.kind,
            size=brush.size,
            opacity=brush.opacity,
            hardness=brush.hardness,
            density=brush.density,
            blend_mode=brush.blend_mode,
            stabilizer=brush.stabilizer,
            tip_path=brush.tip_path,
        )

    def to_settings(self) -> BrushSettings:
        return BrushSettings(
            kind=self.kind,
            size=self.size,
            opacity=self.opacity,
            hardness=self.hardness,
            density=self.density,
            blend_mode=self.blend_mode,
            stabilizer=self.stabilizer,
            tip_path=self.tip_path,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> BrushPreset:
        if not isinstance(raw, dict):
            raise ValueError(f"preset payload must be a dict, got {type(raw).__name__}")
        return cls(
            name=str(raw.get("name", "")).strip() or "preset",
            kind=str(raw.get("kind", DEFAULT_BRUSH_KIND)),
            size=int(raw.get("size", 12)),
            opacity=float(raw.get("opacity", 1.0)),
            hardness=float(raw.get("hardness", 0.8)),
            density=float(raw.get("density", 1.0)),
            blend_mode=str(raw.get("blend_mode", DEFAULT_BLEND_MODE)),
            stabilizer=float(raw.get("stabilizer", 0.0)),
            tip_path=raw.get("tip_path") or None,
        )


# ---------------------------------------------------------------------------
# Built-in presets — sensible starting points for new users.
# ---------------------------------------------------------------------------


BUILT_IN_PRESETS: tuple[BrushPreset, ...] = (
    BrushPreset(
        name="Soft Round",
        kind="pen", size=24, opacity=0.85, hardness=0.4,
    ),
    BrushPreset(
        name="Hard Pen",
        kind="pen", size=4, opacity=1.0, hardness=1.0,
    ),
    BrushPreset(
        name="Pencil Sketch",
        kind="pencil", size=3, opacity=0.7, hardness=0.6, stabilizer=0.2,
    ),
    BrushPreset(
        name="Marker Bold",
        kind="marker", size=18, opacity=1.0, hardness=0.95,
        blend_mode="multiply",
    ),
    BrushPreset(
        name="Airbrush",
        kind="airbrush", size=80, opacity=0.25, hardness=0.0,
    ),
    BrushPreset(
        name="Watercolor",
        kind="watercolor", size=40, opacity=0.5, hardness=0.2,
    ),
)


def find_built_in(name: str) -> BrushPreset | None:
    for preset in BUILT_IN_PRESETS:
        if preset.name == name:
            return preset
    return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_brush_presets(presets: list[BrushPreset]) -> None:
    """Persist a list of user-defined brush presets to user_setting_dict.

    Replaces the stored list wholesale. Empty list clears storage.
    """
    user_setting_dict[_USER_SETTING_KEY] = [preset.to_dict() for preset in presets]
    schedule_save()


def load_brush_presets() -> list[BrushPreset]:
    """Return the persisted list of user brush presets.

    Built-in presets are NOT included — UI code that wants the full
    catalogue should concatenate ``BUILT_IN_PRESETS`` with the
    return value of this helper. Corrupt entries are silently
    dropped so a hand-edited settings file can't crash boot.
    """
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[BrushPreset] = []
    for entry in raw:
        try:
            out.append(BrushPreset.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return out


def all_presets() -> list[BrushPreset]:
    """Built-in catalogue + user presets, in display order."""
    return list(BUILT_IN_PRESETS) + load_brush_presets()


# ---------------------------------------------------------------------------
# Preset groups (dock categorisation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PresetGroup:
    """Named ordered collection of brush presets — a dock category.

    Groups are an organisational layer above presets — the brush dock
    can fold each group into a collapsible section so a user with a
    hundred custom presets isn't drowning in a flat list.
    """

    name: str
    presets: tuple[BrushPreset, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("group name must be non-empty")
        if len(self.presets) > MAX_PRESETS_PER_GROUP:
            raise ValueError(
                f"group {self.name!r} has {len(self.presets)} presets; "
                f"max is {MAX_PRESETS_PER_GROUP}",
            )

    def to_dict(self) -> dict:
        return {
            "name": str(self.name),
            "presets": [preset.to_dict() for preset in self.presets],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> PresetGroup:
        if not isinstance(raw, dict):
            raise ValueError(
                f"group payload must be a dict, got {type(raw).__name__}",
            )
        name = str(raw.get("name", "")).strip() or "group"
        presets_raw = raw.get("presets") or []
        if not isinstance(presets_raw, list):
            presets_raw = []
        presets: list[BrushPreset] = []
        for entry in presets_raw[:MAX_PRESETS_PER_GROUP]:
            try:
                presets.append(BrushPreset.from_dict(entry))
            except (ValueError, TypeError):
                continue
        return cls(name=name, presets=tuple(presets))


BUILT_IN_GROUPS: tuple[PresetGroup, ...] = (
    PresetGroup(
        name="Inks",
        presets=(
            BrushPreset(name="Hard Pen", kind="pen", size=4,
                        opacity=1.0, hardness=1.0),
        ),
    ),
    PresetGroup(
        name="Sketch",
        presets=(
            BrushPreset(name="Pencil Sketch", kind="pencil", size=3,
                        opacity=0.7, hardness=0.6, stabilizer=0.2),
        ),
    ),
    PresetGroup(
        name="Color",
        presets=(
            BrushPreset(name="Soft Round", kind="pen", size=24,
                        opacity=0.85, hardness=0.4),
            BrushPreset(name="Marker Bold", kind="marker", size=18,
                        opacity=1.0, hardness=0.95,
                        blend_mode="multiply"),
        ),
    ),
    PresetGroup(
        name="Wash",
        presets=(
            BrushPreset(name="Airbrush", kind="airbrush", size=80,
                        opacity=0.25, hardness=0.0),
            BrushPreset(name="Watercolor", kind="watercolor", size=40,
                        opacity=0.5, hardness=0.2),
        ),
    ),
)


def find_group(name: str) -> PresetGroup | None:
    for group in BUILT_IN_GROUPS:
        if group.name == name:
            return group
    for group in load_brush_preset_groups():
        if group.name == name:
            return group
    return None


def save_brush_preset_groups(groups: list[PresetGroup]) -> None:
    """Persist a list of user-defined groups (whole-list replace)."""
    if len(groups) > MAX_GROUPS:
        raise ValueError(
            f"refusing to save {len(groups)} groups; max is {MAX_GROUPS}",
        )
    user_setting_dict[_GROUPS_USER_SETTING_KEY] = [
        group.to_dict() for group in groups
    ]
    schedule_save()


def load_brush_preset_groups() -> list[PresetGroup]:
    """Return user-defined groups; corrupt entries skipped."""
    raw = user_setting_dict.get(_GROUPS_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[PresetGroup] = []
    for entry in raw:
        try:
            out.append(PresetGroup.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return out


def all_groups() -> list[PresetGroup]:
    """Built-in groups + user-defined groups in display order."""
    return list(BUILT_IN_GROUPS) + load_brush_preset_groups()
