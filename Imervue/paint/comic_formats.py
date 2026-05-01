"""Comic-format presets — bundle canvas size + bleed guide + panel hint.

Bridges the existing :mod:`Imervue.paint.canvas_presets` (canvas
dimensions in pixels) and :mod:`Imervue.paint.bleed_guides` (trim /
bleed / safe in millimetres) into one named preset for the
"New Manga Page" / "New Doujinshi Page" workflow MediBang ships in
its New-Document dialog.

The user picks one entry from :data:`COMIC_FORMATS` and the
workspace seeds:

1. A blank canvas at the preset's ``page_pixel_size``.
2. The matching :class:`BleedGuides` so the trim / bleed / safe
   overlays are correct.
3. Optionally, a default panel layout (rows × cols) for the page.

Pure data — no Qt / numpy. The tests exercise the dimensions and
the bleed-guide round-trip without a display server.
"""
from __future__ import annotations

from dataclasses import dataclass

from Imervue.paint.bleed_guides import BleedGuides

# Standard print resolutions for manga work — 350 dpi is the JIS
# convention; 300 dpi works for amateur / web-first work.
DPI_PRINT = 350
DPI_AMATEUR = 300


@dataclass(frozen=True)
class ComicFormat:
    """One named comic-format preset.

    ``trim_width_mm`` × ``trim_height_mm`` is the page's nominal
    printed size. ``bleed_mm`` extends the canvas outside that on
    every side; ``safe_mm`` keeps the safe-zone inside the trim by
    that margin. Optional ``default_rows`` / ``default_cols`` hint
    a starting panel grid the New-Page wizard can apply.
    """

    name: str
    label: str
    trim_width_mm: float
    trim_height_mm: float
    bleed_mm: float = 3.0
    safe_mm: float = 5.0
    dpi: int = DPI_PRINT
    default_rows: int | None = None
    default_cols: int | None = None

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("name must be non-empty")
        if not str(self.label).strip():
            raise ValueError("label must be non-empty")
        if self.trim_width_mm <= 0 or self.trim_height_mm <= 0:
            raise ValueError(
                f"trim must be positive, got {self.trim_width_mm} x "
                f"{self.trim_height_mm}",
            )
        if self.bleed_mm < 0 or self.safe_mm < 0:
            raise ValueError(
                f"bleed/safe must be >= 0, got bleed={self.bleed_mm} "
                f"safe={self.safe_mm}",
            )
        if self.dpi <= 0:
            raise ValueError(f"dpi must be > 0, got {self.dpi}")
        if (
            self.default_rows is not None
            and self.default_cols is not None
            and (self.default_rows <= 0 or self.default_cols <= 0)
        ):
            raise ValueError(
                f"default rows/cols must be positive when set, got "
                f"{self.default_rows}x{self.default_cols}",
            )

    def bleed_guides(self) -> BleedGuides:
        """Return the matching :class:`BleedGuides` for this format."""
        return BleedGuides(
            trim_width_mm=self.trim_width_mm,
            trim_height_mm=self.trim_height_mm,
            bleed_mm=self.bleed_mm,
            safe_mm=self.safe_mm,
            dpi=self.dpi,
        )

    def page_pixel_size(self) -> tuple[int, int]:
        """``(width, height)`` of the canvas including bleed in pixels."""
        return self.bleed_guides().page_pixel_size


COMIC_FORMATS: tuple[ComicFormat, ...] = (
    # JIS B5 single page — the dominant manga magazine size.
    ComicFormat(
        name="manga_b5",
        label="Manga B5 (JIS, 350dpi)",
        trim_width_mm=182.0, trim_height_mm=257.0,
    ),
    # JIS B4 spread — professional manga, often used for centerfolds.
    ComicFormat(
        name="manga_b4_spread",
        label="Manga B4 Spread (JIS, 350dpi)",
        trim_width_mm=257.0, trim_height_mm=364.0,
    ),
    # ISO A4 — standard for international doujinshi.
    ComicFormat(
        name="doujin_a4",
        label="Doujinshi A4 (350dpi)",
        trim_width_mm=210.0, trim_height_mm=297.0,
    ),
    # ISO A5 — small doujin.
    ComicFormat(
        name="doujin_a5",
        label="Doujinshi A5 (350dpi)",
        trim_width_mm=148.0, trim_height_mm=210.0,
    ),
    # Japanese magazine submission format — 270 × 390 mm at 350dpi.
    ComicFormat(
        name="magazine_submission",
        label="Manga Magazine Submission (350dpi)",
        trim_width_mm=270.0, trim_height_mm=390.0,
    ),
    # 4-koma vertical — 4 panels stacked, standard newspaper layout.
    ComicFormat(
        name="yonkoma_vertical",
        label="4-koma Vertical (B5, 350dpi)",
        trim_width_mm=130.0, trim_height_mm=257.0,
        default_rows=4, default_cols=1,
    ),
    # 4-koma horizontal — 4 panels in a strip.
    ComicFormat(
        name="yonkoma_horizontal",
        label="4-koma Horizontal (350dpi)",
        trim_width_mm=257.0, trim_height_mm=85.0,
        default_rows=1, default_cols=4,
    ),
    # Webtoon — long vertical scroll commonly used by Korean platforms.
    ComicFormat(
        name="webtoon_vertical",
        label="Webtoon Vertical (72dpi)",
        trim_width_mm=210.0, trim_height_mm=2970.0,
        bleed_mm=0.0, safe_mm=0.0,
        dpi=72,
    ),
)


def find_format(name: str) -> ComicFormat | None:
    """Return the comic format with that ``name``, or ``None``."""
    for fmt in COMIC_FORMATS:
        if fmt.name == name:
            return fmt
    return None


def format_names() -> list[str]:
    """Return every built-in format's name in declaration order."""
    return [fmt.name for fmt in COMIC_FORMATS]
