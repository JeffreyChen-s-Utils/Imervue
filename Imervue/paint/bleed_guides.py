"""Trim / bleed / safe-area guide overlays for comic pages.

Three concentric rectangles painted over the canvas:

* **Trim** — where the printed page is cut. Anything outside is
  discarded by the printer.
* **Bleed** — extra margin past the trim that ink fills, so a
  slight cutting misalignment doesn't leave a white edge. Print
  shops typically ask for 3 mm of bleed on every side.
* **Safe** — interior margin past which critical content
  (dialogue, faces, text) shouldn't sit so it survives if the
  trim shifts inward.

Pure-math / Qt-free. The canvas widget renders the three rects via
its own overlay path; this module owns the geometry plus a small
preset table for the JIS B5 / A4 manga conventions.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_BLEED_MM = 3.0
DEFAULT_SAFE_MM = 5.0
MIN_MARGIN_MM = 0.0
MAX_MARGIN_MM = 50.0
DEFAULT_DPI = 350


@dataclass(frozen=True)
class BleedGuides:
    """Trim / bleed / safe geometry for one page.

    All three rects share the same centre — the trim is the page's
    nominal printed size; bleed sits outside it by ``bleed_mm``;
    safe sits inside by ``safe_mm``. ``dpi`` plus the millimetre
    margins are converted to pixel rects via the helpers below.
    """

    trim_width_mm: float
    trim_height_mm: float
    bleed_mm: float = DEFAULT_BLEED_MM
    safe_mm: float = DEFAULT_SAFE_MM
    dpi: int = DEFAULT_DPI

    def __post_init__(self) -> None:
        if self.trim_width_mm <= 0:
            raise ValueError(
                f"trim_width_mm must be > 0, got {self.trim_width_mm!r}",
            )
        if self.trim_height_mm <= 0:
            raise ValueError(
                f"trim_height_mm must be > 0, got {self.trim_height_mm!r}",
            )
        if not MIN_MARGIN_MM <= self.bleed_mm <= MAX_MARGIN_MM:
            raise ValueError(
                f"bleed_mm must be in [{MIN_MARGIN_MM}, {MAX_MARGIN_MM}], "
                f"got {self.bleed_mm!r}",
            )
        if not MIN_MARGIN_MM <= self.safe_mm <= MAX_MARGIN_MM:
            raise ValueError(
                f"safe_mm must be in [{MIN_MARGIN_MM}, {MAX_MARGIN_MM}], "
                f"got {self.safe_mm!r}",
            )
        if self.dpi <= 0:
            raise ValueError(f"dpi must be > 0, got {self.dpi!r}")
        # Safe margin can't eat away more than half the page.
        if self.safe_mm * 2 >= min(self.trim_width_mm, self.trim_height_mm):
            raise ValueError(
                f"safe_mm {self.safe_mm} too large for trim "
                f"{self.trim_width_mm}×{self.trim_height_mm}",
            )

    @property
    def page_pixel_size(self) -> tuple[int, int]:
        """Outer page size in pixels (trim + bleed on every side)."""
        return (
            _mm_to_px(self.trim_width_mm + 2 * self.bleed_mm, self.dpi),
            _mm_to_px(self.trim_height_mm + 2 * self.bleed_mm, self.dpi),
        )

    def trim_rect_px(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` of the trim rect in canvas pixels."""
        bleed_px = _mm_to_px(self.bleed_mm, self.dpi)
        return (
            bleed_px,
            bleed_px,
            _mm_to_px(self.trim_width_mm, self.dpi),
            _mm_to_px(self.trim_height_mm, self.dpi),
        )

    def bleed_rect_px(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` of the bleed rect — the outermost border."""
        page_w, page_h = self.page_pixel_size
        return (0, 0, page_w, page_h)

    def safe_rect_px(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` of the safe rect — innermost border."""
        bleed_px = _mm_to_px(self.bleed_mm, self.dpi)
        safe_px = _mm_to_px(self.safe_mm, self.dpi)
        return (
            bleed_px + safe_px,
            bleed_px + safe_px,
            _mm_to_px(self.trim_width_mm - 2 * self.safe_mm, self.dpi),
            _mm_to_px(self.trim_height_mm - 2 * self.safe_mm, self.dpi),
        )


# ---------------------------------------------------------------------------
# Preset library
# ---------------------------------------------------------------------------


PRESETS: dict[str, BleedGuides] = {
    # JIS B5 manga single page — 182 × 257 mm trim, +3 mm bleed.
    "manga_b5": BleedGuides(
        trim_width_mm=182.0, trim_height_mm=257.0, dpi=350,
    ),
    # JIS B4 — double-page spread / professional manga size.
    "manga_b4": BleedGuides(
        trim_width_mm=257.0, trim_height_mm=364.0, dpi=350,
    ),
    # ISO A4.
    "a4": BleedGuides(
        trim_width_mm=210.0, trim_height_mm=297.0, dpi=350,
    ),
    # ISO A5 — common doujin size.
    "a5": BleedGuides(
        trim_width_mm=148.0, trim_height_mm=210.0, dpi=350,
    ),
}


def preset(name: str) -> BleedGuides:
    """Look up a named bleed-guide preset."""
    if name not in PRESETS:
        raise KeyError(
            f"unknown bleed-guide preset {name!r}; "
            f"expected one of {tuple(PRESETS)}",
        )
    return PRESETS[name]


def available_presets() -> tuple[str, ...]:
    return tuple(PRESETS.keys())


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _mm_to_px(mm: float, dpi: int) -> int:
    """Convert millimetres to pixels at the given DPI."""
    return max(0, int(round(float(mm) * int(dpi) / 25.4)))
