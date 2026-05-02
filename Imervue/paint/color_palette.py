"""Named color palettes — built-in sets + user-defined persistence.

Painters reach for the same shortlist of swatches across many
strokes. Stuffing every colour into the existing ``color_history``
list washes out the deliberate choices the user made earlier in the
session; named palettes solve this by giving each shortlist its own
storage and letting the user switch between them without losing the
previous set.

Three built-in palettes ship out of the box:

* ``Standard`` — primaries + secondaries + greys, the safe-default
  16-colour set every paint app provides.
* ``Pastel``   — gentle high-luma colours for soft / cute styles.
* ``Manga``    — black + white + four greyscale tones, the
  screen-tone-replacement set comic artists use most.

Custom palettes round-trip through
``user_setting_dict["paint_color_palettes"]``; corrupt persisted
entries are silently dropped on load so a hand-edited settings file
can never crash boot.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_color_palettes"

MAX_PALETTE_SIZE = 256


@dataclass(frozen=True)
class Palette:
    """A named ordered list of RGB swatches."""

    name: str
    colors: tuple[tuple[int, int, int], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("palette name must be non-empty")
        if len(self.colors) > MAX_PALETTE_SIZE:
            raise ValueError(
                f"palette must contain at most {MAX_PALETTE_SIZE} colours, "
                f"got {len(self.colors)}",
            )
        for c in self.colors:
            if not isinstance(c, tuple) or len(c) != 3:
                raise ValueError(
                    f"every color must be an (R, G, B) 3-tuple, got {c!r}",
                )
            for component in c:
                if not 0 <= int(component) <= 255:
                    raise ValueError(
                        f"color components must be in [0, 255], got {c!r}",
                    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "colors": [list(c) for c in self.colors],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Palette:
        if not isinstance(raw, dict):
            raise ValueError(
                f"palette payload must be a dict, got {type(raw).__name__}",
            )
        colors_raw = raw.get("colors") or []
        if not isinstance(colors_raw, list):
            raise ValueError("colors must be a list")
        normalised: list[tuple[int, int, int]] = []
        for c in colors_raw:
            if isinstance(c, (list, tuple)) and len(c) == 3:
                try:
                    rgb = tuple(max(0, min(255, int(v))) for v in c)
                    normalised.append(rgb)   # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
        return cls(
            name=str(raw.get("name", "")).strip() or "palette",
            colors=tuple(normalised),
        )


# ---------------------------------------------------------------------------
# Built-in palettes
# ---------------------------------------------------------------------------


BUILT_IN_PALETTES: tuple[Palette, ...] = (
    Palette(
        name="Standard",
        colors=(
            (0, 0, 0), (64, 64, 64), (128, 128, 128), (192, 192, 192),
            (255, 255, 255),
            (255, 0, 0), (255, 128, 0), (255, 255, 0),
            (0, 255, 0), (0, 255, 255), (0, 0, 255),
            (128, 0, 255), (255, 0, 255),
            (139, 69, 19), (210, 180, 140), (245, 222, 179),
        ),
    ),
    Palette(
        name="Pastel",
        colors=(
            (255, 209, 220), (255, 233, 200), (255, 250, 200),
            (212, 240, 200), (200, 240, 230), (200, 220, 245),
            (220, 200, 240), (245, 200, 240),
            (255, 235, 235), (255, 250, 235), (240, 255, 240),
            (235, 245, 255),
        ),
    ),
    Palette(
        name="Manga",
        colors=(
            (0, 0, 0),
            (51, 51, 51),
            (102, 102, 102),
            (153, 153, 153),
            (204, 204, 204),
            (255, 255, 255),
        ),
    ),
)


def find_built_in(name: str) -> Palette | None:
    for palette in BUILT_IN_PALETTES:
        if palette.name == name:
            return palette
    return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_palettes(palettes: list[Palette]) -> None:
    """Persist user-defined palettes to user_setting_dict (whole list)."""
    user_setting_dict[_USER_SETTING_KEY] = [p.to_dict() for p in palettes]
    schedule_save()


def load_palettes() -> list[Palette]:
    """Return the persisted user palettes; corrupt entries dropped."""
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[Palette] = []
    for entry in raw:
        try:
            palette = Palette.from_dict(entry)
        except (ValueError, TypeError):
            continue
        out.append(palette)
    return out


def all_palettes() -> list[Palette]:
    """Built-ins followed by user palettes — display order."""
    return list(BUILT_IN_PALETTES) + load_palettes()
