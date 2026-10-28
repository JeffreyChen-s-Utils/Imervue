"""Immutable tool snapshots, supported choices, defaults, and event channels."""
from __future__ import annotations

from dataclasses import dataclass, field

TOOLS = (
    "brush",
    "eraser",
    "fill",
    "eyedropper",
    "select_rect",
    "select_lasso",
    "select_wand",
    "select_quick",
    "move",
    "text",
    "gradient",
    "blur",
    "smudge",
    "dodge",
    "burn",
    "sponge",
    "hand",
    "zoom",
    "bezier_pen",
    "clone_stamp",
    "transform",
    "speech_bubble",
    "shape_rect",
    "shape_ellipse",
    "shape_line",
    "shape_polygon",
    "crop",
)
DEFAULT_TOOL = "brush"

# Brush sub-types — the brush tool dispatches by this identifier so a single
# tool entry covers pencil / pen / marker / airbrush / watercolour without
# multiplying the toolbar.
BRUSH_KINDS = ("pencil", "pen", "marker", "airbrush", "watercolor", "sumi")
DEFAULT_BRUSH_KIND = "pen"

# Blend modes the brush can paint with. Mirrors the layer blend modes the
# rest of Imervue already understands.
BLEND_MODES = (
    "normal",
    "multiply",
    "screen",
    "overlay",
    "darken",
    "lighten",
    "color_dodge",
    "color_burn",
    "soft_light",
    "hard_light",
    "linear_burn",
    "linear_dodge",
)
DEFAULT_BLEND_MODE = "normal"

# Brush parameter ranges — identical to raster paint apps' UI sliders. Settings are
# stored as plain ints/floats; clamping happens on assignment.
BRUSH_SIZE_MIN = 1
BRUSH_SIZE_MAX = 500
BRUSH_OPACITY_MIN = 0.0
BRUSH_OPACITY_MAX = 1.0
BRUSH_HARDNESS_MIN = 0.0
BRUSH_HARDNESS_MAX = 1.0
BRUSH_DENSITY_MIN = 0.0
BRUSH_DENSITY_MAX = 1.0

COLOR_HISTORY_MAX = 12
DEFAULT_FG = (0, 0, 0)
# ``None`` denotes "transparent / no colour" — the user-facing
# affordance is the swatch dock's "Transparent" button. The brush
# tool no-ops when foreground is ``None``; the gradient tool fades
# its endpoint alpha to zero. Defaulting BG to ``None`` matches the
# raster paint apps "BG slot starts empty" convention so a fresh
# ``foreground → background`` gradient produces a clean alpha fade
# without the user having to clear a stale white BG first.
DEFAULT_BG: tuple[int, int, int] | None = None
# Type alias for "either an RGB triple or transparent".
Color = "tuple[int, int, int] | None"


# ---------------------------------------------------------------------------
# Listener event channels
# ---------------------------------------------------------------------------
EVENT_TOOL = "tool"            # current tool changed
EVENT_BRUSH = "brush"          # any brush setting changed
EVENT_COLOR = "color"          # foreground / background changed
EVENT_HISTORY = "history"      # color history changed
EVENT_FILL = "fill"            # any fill setting changed
EVENT_SELECTION_MODE = "selection_mode"   # selection combine mode changed
EVENT_GRADIENT = "gradient"    # gradient kind / reverse changed
EVENT_SYMMETRY = "symmetry"    # symmetry mirror mode changed
EVENT_RULER = "ruler"          # ruler mode / geometry changed
EVENT_SUB_TOOL = "sub_tool"    # sub-tool registry / active sub-tool changed
EVENT_EYEDROPPER = "eyedropper"   # eyedropper sampling mode changed
EVENT_PRESSURE_CURVE = "pressure_curve"   # tablet pressure response changed
EVENT_PEN = "pen"              # pen tool's Smooth curve setting changed


@dataclass(frozen=True)
class BrushSettings:
    """Snapshot of brush parameters; immutable so listeners can compare."""

    kind: str = DEFAULT_BRUSH_KIND
    size: int = 12
    opacity: float = 1.0
    hardness: float = 0.8
    density: float = 1.0
    blend_mode: str = DEFAULT_BLEND_MODE
    stabilizer: float = 0.0   # 0 = off, 0..1 — input low-pass strength
    tip_path: str | None = None   # custom PNG used as kernel; None = round
    scatter: float = 0.0      # 0..1 — per-dab random offset, fraction of brush size
    color_jitter: float = 0.0 # 0..1 — per-dab HSV perturbation strength
    follow_tilt: bool = False # rotate kernel by pen tilt direction


# Fill bucket parameters live alongside brush so the dock panels and
# the dispatcher both pull from the same place.
FILL_TOLERANCE_MIN = 0
FILL_TOLERANCE_MAX = 255
# Mirrors :data:`Imervue.paint.fill.MAX_EXPAND` — duplicated as a plain
# constant so the tool-state dataclass can be imported without dragging
# in numpy / fill at module-load time.
FILL_EXPAND_MIN = 0
FILL_EXPAND_MAX = 32
FILL_GAP_CLOSE_MIN = 0
FILL_GAP_CLOSE_MAX = 16


@dataclass(frozen=True)
class FillSettings:
    """Fill bucket options."""

    tolerance: int = 32
    contiguous: bool = True
    sample_all_layers: bool = False
    expand_px: int = 0
    use_reference_layer: bool = False
    gap_close_px: int = 0


# Each entry in :attr:`ToolState.sub_tools` is a frozen snapshot of the
# brush + fill settings the user wants to recall under ``name`` for a
# given main tool. Stored under the tool id as the dict key — matching
# raster paint apps / Clip Studio's "sub-tool" tabs that hang under each main
# tool. Only the slices relevant to the tool are remembered; switching
# tools re-applies the named preset's full snapshot.
SUB_TOOL_NAME_MAX_LEN = 80


@dataclass(frozen=True)
class SubTool:
    """One saved sub-tool preset for a main tool.

    ``brush`` and ``fill`` are full settings snapshots (the same
    immutable dataclasses the live state uses) so applying a preset
    is just a swap rather than a partial diff. Sub-tools whose main
    tool doesn't use one of these slices simply ignore the unused
    field on apply.
    """

    name: str
    brush: BrushSettings = field(default_factory=BrushSettings)
    fill: FillSettings = field(default_factory=FillSettings)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("sub-tool name must be non-empty")
        if len(str(self.name)) > SUB_TOOL_NAME_MAX_LEN:
            raise ValueError(
                f"sub-tool name must be <= {SUB_TOOL_NAME_MAX_LEN} chars",
            )




def validate_choice(value: str, choices: tuple[str, ...], label: str) -> None:
    """Reject unsupported choices with the setter's established error message."""
    if value not in choices:
        raise ValueError(f"unknown {label} {value!r}; expected one of {choices}")


def recover_choice(value: str, choices: tuple[str, ...], default: str) -> str:
    """Recover a supported stored choice or its established default."""
    return value if value in choices else default
