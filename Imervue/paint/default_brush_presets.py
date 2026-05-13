"""Default brush presets seeded into ``ToolState.sub_tools`` on first run.

raster paint apps Pro ships a stock library of named brushes (G-pen,
mapping pen, sumi, watercolor, airbrush, ...) so a new user has a
useful tool palette without spending time tuning sliders. We mirror
that affordance with a small set of preset :class:`BrushSettings`
snapshots, captured under the ``"brush"`` main tool. The seeder runs
once when ``ToolState.sub_tools`` is empty — subsequent launches keep
whatever the user has saved/edited.

Each preset is a frozen dataclass tuple so the catalogue is easy to
inspect, extend, and unit-test without booting Qt. The seeder is
deliberately idempotent: re-running it is a no-op as long as at
least one ``"brush"`` sub-tool already exists.
"""
from __future__ import annotations

from dataclasses import dataclass

from Imervue.paint.tool_state import BrushSettings


@dataclass(frozen=True)
class BrushPresetSpec:
    """One default brush preset entry.

    ``settings`` is the immutable snapshot, ``name`` is the user-
    facing label written into ``ToolState.sub_tools`` so the brush
    preset dialog can list it without translation lookups.
    """

    name: str
    settings: BrushSettings


_PRESETS: tuple[BrushPresetSpec, ...] = (
    # --- ink / pen family -------------------------------------------------
    BrushPresetSpec(
        "G-pen",
        BrushSettings(kind="pen", size=14, opacity=1.0, hardness=0.95,
                      density=1.0, stabilizer=0.20),
    ),
    BrushPresetSpec(
        "Mapping pen",
        BrushSettings(kind="pen", size=4, opacity=1.0, hardness=1.0,
                      density=1.0, stabilizer=0.30),
    ),
    BrushPresetSpec(
        "Round pen",
        BrushSettings(kind="pen", size=8, opacity=1.0, hardness=0.90,
                      density=1.0, stabilizer=0.15),
    ),
    BrushPresetSpec(
        "Felt pen",
        BrushSettings(kind="marker", size=18, opacity=1.0, hardness=0.85,
                      density=1.0, stabilizer=0.10),
    ),
    # --- pencil family ----------------------------------------------------
    BrushPresetSpec(
        "Pencil HB",
        BrushSettings(kind="pencil", size=6, opacity=0.85, hardness=0.55,
                      density=0.85, scatter=0.15),
    ),
    BrushPresetSpec(
        "Pencil 4B",
        BrushSettings(kind="pencil", size=10, opacity=0.95, hardness=0.40,
                      density=0.95, scatter=0.20),
    ),
    BrushPresetSpec(
        "Crayon",
        BrushSettings(kind="pencil", size=22, opacity=0.85, hardness=0.30,
                      density=0.70, scatter=0.30, color_jitter=0.05),
    ),
    # --- paint family -----------------------------------------------------
    BrushPresetSpec(
        "Watercolour wet",
        BrushSettings(kind="watercolor", size=32, opacity=0.55,
                      hardness=0.20, density=0.80, color_jitter=0.10),
    ),
    BrushPresetSpec(
        "Watercolour dry",
        BrushSettings(kind="watercolor", size=20, opacity=0.75,
                      hardness=0.45, density=0.70, color_jitter=0.05),
    ),
    BrushPresetSpec(
        "Acrylic",
        BrushSettings(kind="marker", size=26, opacity=0.95, hardness=0.65,
                      density=1.0, scatter=0.05),
    ),
    BrushPresetSpec(
        "Highlight",
        BrushSettings(kind="marker", size=18, opacity=0.45, hardness=0.30,
                      density=0.85, blend_mode="screen"),
    ),
    # --- airbrush + sumi --------------------------------------------------
    BrushPresetSpec(
        "Airbrush soft",
        BrushSettings(kind="airbrush", size=64, opacity=0.30,
                      hardness=0.10, density=1.0),
    ),
    BrushPresetSpec(
        "Airbrush hard",
        BrushSettings(kind="airbrush", size=32, opacity=0.50,
                      hardness=0.30, density=1.0),
    ),
    BrushPresetSpec(
        "Sumi calligraphy",
        BrushSettings(kind="sumi", size=40, opacity=1.0, hardness=0.50,
                      density=1.0, follow_tilt=True, stabilizer=0.25),
    ),
    BrushPresetSpec(
        "Smudge",
        BrushSettings(kind="watercolor", size=24, opacity=0.40,
                      hardness=0.20, density=0.50, scatter=0.10),
    ),
    # --- erasers (a single eraser kind exists; presets vary the
    #     opacity / hardness so the user has soft + hard variants).
    BrushPresetSpec(
        "Eraser soft",
        BrushSettings(kind="airbrush", size=48, opacity=0.65,
                      hardness=0.15, density=1.0, blend_mode="erase"),
    ),
    BrushPresetSpec(
        "Eraser hard",
        BrushSettings(kind="pen", size=18, opacity=1.0, hardness=1.0,
                      density=1.0, blend_mode="erase"),
    ),
)


def default_brush_presets() -> tuple[BrushPresetSpec, ...]:
    """Return the immutable preset catalogue.

    Returned as a tuple so callers cannot accidentally mutate the
    shared spec list — each preset is a frozen dataclass.
    """
    return _PRESETS


def seed_default_brush_presets(state) -> int:
    """Capture every default preset under the ``"brush"`` main tool.

    Idempotent: when ``state.sub_tools["brush"]`` already has at
    least one entry the seeder bails out and returns 0. Otherwise
    every preset is added in catalogue order and the count is
    returned. The seeder writes via the public ``add_sub_tool`` /
    settings APIs so persistence + EVENT_SUB_TOOL events fire on
    the same path as user-driven saves.
    """
    if state.sub_tools.get("brush"):
        return 0

    # Stash the live brush so the seeder doesn't perturb the user's
    # current tool — we'll restore it after the loop. ``add_sub_tool``
    # captures whatever ``state.brush`` is at call time, so the easiest
    # way to attach explicit settings is to assign them first.
    saved = state.brush
    count = 0
    for preset in _PRESETS:
        state.brush = preset.settings
        state.add_sub_tool("brush", preset.name)
        count += 1
    state.brush = saved
    return count
