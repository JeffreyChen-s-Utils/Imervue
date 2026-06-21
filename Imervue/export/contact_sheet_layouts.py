"""Named layout presets for contact sheets.

Users repeat the same grid / margin / caption settings, so this module ships a
handful of named layouts (like a print app's contact-sheet presets) that
resolve to a :class:`~Imervue.export.contact_sheet.ContactSheetOptions`. Pure
data + a resolver — page size, title and DPI stay caller-supplied since they're
output-specific.
"""
from __future__ import annotations

from Imervue.export.contact_sheet import ContactSheetOptions

# name -> ContactSheetOptions grid/margin/caption overrides.
_LAYOUTS: dict[str, dict] = {
    "default": {"rows": 5, "cols": 4, "margin_mm": 10.0, "caption": True},
    "compact": {"rows": 8, "cols": 6, "margin_mm": 5.0, "caption": False},
    "proof": {"rows": 6, "cols": 5, "margin_mm": 8.0, "caption": True},
    "editorial": {"rows": 3, "cols": 2, "margin_mm": 18.0, "caption": True},
    "index": {"rows": 10, "cols": 8, "margin_mm": 4.0, "caption": False},
}
LAYOUT_NAMES: tuple[str, ...] = tuple(_LAYOUTS)


def _overrides(name: str) -> dict:
    overrides = _LAYOUTS.get(name)
    if overrides is None:
        raise ValueError(
            f"unknown contact-sheet layout {name!r}; see LAYOUT_NAMES",
        )
    return overrides


def layout_options(
    name: str, *, page_size: str = "A4", title: str = "", dpi: int = 300,
) -> ContactSheetOptions:
    """Return the :class:`ContactSheetOptions` for a named layout.

    *page_size* / *title* / *dpi* are output-specific and supplied by the
    caller. Raises ``ValueError`` for an unknown layout name.
    """
    return ContactSheetOptions(
        page_size=page_size, title=title, dpi=dpi, **_overrides(name),
    )


def layout_grid(name: str) -> tuple[int, int]:
    """Return the ``(rows, cols)`` of a named layout."""
    overrides = _overrides(name)
    return overrides["rows"], overrides["cols"]


def cells_per_page(name: str) -> int:
    """Return how many images a single page of the named layout holds."""
    rows, cols = layout_grid(name)
    return rows * cols
