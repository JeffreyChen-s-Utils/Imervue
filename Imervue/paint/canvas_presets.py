"""Canvas-size presets for the Paint workspace's "New Canvas" dialog.

Three groups of presets ship out of the box:

* **Paper** — A-series, B-series, and US Letter at 300 dpi for print.
* **Manga** — single-page sizes for B5 commercial / A4 doujinshi
  layouts at 300 dpi.
* **Screen** — common web / video resolutions at 72 dpi.

Plus three sensible fall-backs (square / portrait / landscape) so a
user clicking "Custom" still gets a starting point. The presets are
JSON-friendly: :class:`CanvasPreset` is a frozen dataclass and the
helpers serialise to plain dicts for persistence.

Custom user presets can be saved alongside the built-ins via
:func:`save_custom_presets` / :func:`load_custom_presets`, which
round-trip through ``user_setting_dict["paint_canvas_presets"]``.
"""
from __future__ import annotations

from dataclasses import dataclass

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_canvas_presets"

# Paper conversion constants — handy when callers want to compute
# their own sizes from physical units.
MM_PER_INCH = 25.4

# Hard ceilings — protect against accidental ``width=2_000_000`` from a
# config file that survived a crash mid-edit.
MIN_DIMENSION_PX = 1
MAX_DIMENSION_PX = 16384


@dataclass(frozen=True)
class CanvasPreset:
    """One named canvas size.

    ``dpi`` is informational — the workspace creates the canvas at
    ``width_px × height_px`` regardless of dpi. Storing it lets
    print-oriented presets carry the metadata so an export pipeline
    can use it later.
    """

    name: str
    width_px: int
    height_px: int
    dpi: int = 72
    category: str = "custom"

    def __post_init__(self) -> None:
        for key, value in (("width_px", self.width_px), ("height_px", self.height_px)):
            if not MIN_DIMENSION_PX <= int(value) <= MAX_DIMENSION_PX:
                raise ValueError(
                    f"{key} must be in [{MIN_DIMENSION_PX}, "
                    f"{MAX_DIMENSION_PX}], got {value!r}",
                )
        if int(self.dpi) <= 0:
            raise ValueError(f"dpi must be positive, got {self.dpi!r}")
        if not str(self.name).strip():
            raise ValueError("preset name must be non-empty")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "width_px": int(self.width_px),
            "height_px": int(self.height_px),
            "dpi": int(self.dpi),
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> CanvasPreset:
        if not isinstance(raw, dict):
            raise ValueError(f"preset payload must be a dict, got {type(raw).__name__}")
        return cls(
            name=str(raw.get("name", "")).strip() or "custom",
            width_px=int(raw.get("width_px", 1024)),
            height_px=int(raw.get("height_px", 1024)),
            dpi=int(raw.get("dpi", 72)),
            category=str(raw.get("category", "custom")),
        )


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def mm_to_pixels(mm: float, dpi: int) -> int:
    """Convert millimetres to pixels at ``dpi``, rounded to the nearest int."""
    if dpi <= 0:
        raise ValueError(f"dpi must be positive, got {dpi!r}")
    return int(round(float(mm) / MM_PER_INCH * float(dpi)))


def inches_to_pixels(inches: float, dpi: int) -> int:
    """Convert inches to pixels at ``dpi``, rounded to the nearest int."""
    if dpi <= 0:
        raise ValueError(f"dpi must be positive, got {dpi!r}")
    return int(round(float(inches) * float(dpi)))


# ---------------------------------------------------------------------------
# Built-in preset list
# ---------------------------------------------------------------------------


BUILT_IN_PRESETS: tuple[CanvasPreset, ...] = (
    # Paper — A / B series and Letter at 300 dpi.
    CanvasPreset("A4 Portrait (300dpi)", 2480, 3508, dpi=300, category="paper"),
    CanvasPreset("A4 Landscape (300dpi)", 3508, 2480, dpi=300, category="paper"),
    CanvasPreset("A5 Portrait (300dpi)", 1748, 2480, dpi=300, category="paper"),
    CanvasPreset("B5 Portrait (300dpi)", 2079, 2953, dpi=300, category="paper"),
    CanvasPreset("Letter Portrait (300dpi)", 2550, 3300, dpi=300, category="paper"),
    # Manga — typical commercial / doujin page sizes.
    CanvasPreset("Manga B5 single (300dpi)", 2150, 3035, dpi=300, category="manga"),
    CanvasPreset("Manga A4 doujin (300dpi)", 2480, 3508, dpi=300, category="manga"),
    CanvasPreset("Manga A5 single (300dpi)", 1748, 2480, dpi=300, category="manga"),
    # Screen — web / social / video.
    CanvasPreset("HD 1080p", 1920, 1080, dpi=72, category="screen"),
    CanvasPreset("4K UHD", 3840, 2160, dpi=72, category="screen"),
    CanvasPreset("Square 1080", 1080, 1080, dpi=72, category="screen"),
    CanvasPreset("Square 2048", 2048, 2048, dpi=72, category="screen"),
    # Generic fall-backs.
    CanvasPreset("Default 1024", 1024, 1024, dpi=72, category="generic"),
)


def preset_names() -> list[str]:
    """List every built-in preset name."""
    return [preset.name for preset in BUILT_IN_PRESETS]


def find_preset(name: str) -> CanvasPreset | None:
    """Return the built-in preset with that name, or ``None``."""
    for preset in BUILT_IN_PRESETS:
        if preset.name == name:
            return preset
    return None


def presets_in_category(category: str) -> list[CanvasPreset]:
    """Return every built-in preset belonging to ``category``."""
    return [preset for preset in BUILT_IN_PRESETS if preset.category == category]


# ---------------------------------------------------------------------------
# Custom-preset persistence
# ---------------------------------------------------------------------------


def save_custom_presets(presets: list[CanvasPreset]) -> None:
    """Persist a list of user-defined presets to user_setting_dict.

    The list is replaced wholesale — callers that want to add one
    preset should ``load_custom_presets()``, append, and save. Empty
    lists clear the storage.
    """
    user_setting_dict[_USER_SETTING_KEY] = [preset.to_dict() for preset in presets]
    schedule_save()


def load_custom_presets() -> list[CanvasPreset]:
    """Return the list of user-defined presets from user_setting_dict.

    Corrupt entries are silently dropped — a hand-edited settings
    file should never crash the New Canvas dialog.
    """
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[CanvasPreset] = []
    for entry in raw:
        try:
            out.append(CanvasPreset.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return out
