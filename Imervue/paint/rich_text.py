"""Rich text — per-character style runs for the paint text tool.

A "rich text" model gives the artist different fonts / sizes /
colours / weights inside a single text layer (so an exclamation
mark can be bigger and red while the rest of the bubble stays
black). This module is the pure data layer + Pillow-driven raster:

* :class:`TextStyle` — one immutable style "run" (font family, size,
  weight, italics, colour).
* :class:`StyledText` — an ordered list of (text, style) runs plus
  helpers to insert / split / merge spans.
* :func:`render_styled_text` — rasterises a :class:`StyledText` into
  a fresh ``HxWx4`` ``uint8`` RGBA buffer using PIL.

Pure-numpy / PIL — Qt-free so the data-model + render path can be
exercised in unit tests without a display server.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DEFAULT_FONT_FAMILY = "Arial"
DEFAULT_FONT_SIZE = 24
DEFAULT_TEXT_COLOR = (0, 0, 0, 255)
TEXT_SIZE_MIN = 4
TEXT_SIZE_MAX = 1024
LINE_HEIGHT_RATIO = 1.25   # line height = font_size * this

# Layout padding around the rendered text — gives the bubble /
# selection a small margin so glyph descenders / italic overhang
# don't clip at the buffer edge.
LAYOUT_PADDING_PX = 8


@dataclass(frozen=True)
class TextStyle:
    """One immutable style run."""

    font_family: str = DEFAULT_FONT_FAMILY
    font_size: int = DEFAULT_FONT_SIZE
    bold: bool = False
    italic: bool = False
    color: tuple[int, int, int, int] = DEFAULT_TEXT_COLOR

    def __post_init__(self) -> None:
        if not TEXT_SIZE_MIN <= int(self.font_size) <= TEXT_SIZE_MAX:
            raise ValueError(
                f"font_size must be in [{TEXT_SIZE_MIN}, {TEXT_SIZE_MAX}],"
                f" got {self.font_size}",
            )
        if len(self.color) != 4 or any(
            not 0 <= int(c) <= 255 for c in self.color
        ):
            raise ValueError(
                f"color must be a 4-tuple of 0..255 ints, got {self.color!r}",
            )

    def to_dict(self) -> dict:
        return {
            "font_family": str(self.font_family),
            "font_size": int(self.font_size),
            "bold": bool(self.bold),
            "italic": bool(self.italic),
            "color": list(self.color),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> TextStyle:
        if not isinstance(raw, dict):
            return cls()
        try:
            return cls(
                font_family=str(raw.get("font_family", DEFAULT_FONT_FAMILY)),
                font_size=int(raw.get("font_size", DEFAULT_FONT_SIZE)),
                bold=bool(raw.get("bold", False)),
                italic=bool(raw.get("italic", False)),
                color=tuple(
                    max(0, min(255, int(c)))
                    for c in raw.get("color", DEFAULT_TEXT_COLOR)
                ),
            )
        except (TypeError, ValueError):
            return cls()


@dataclass
class StyledRun:
    """One ``(text, style)`` pair in a :class:`StyledText`."""

    text: str
    style: TextStyle = field(default_factory=TextStyle)

    def __post_init__(self) -> None:
        # Disallow ``None``-typed text — every run must be a string,
        # even an empty one.
        if not isinstance(self.text, str):
            raise ValueError(
                f"run text must be str, got {type(self.text).__name__}",
            )

    def to_dict(self) -> dict:
        return {"text": self.text, "style": self.style.to_dict()}

    @classmethod
    def from_dict(cls, raw: dict) -> StyledRun:
        if not isinstance(raw, dict):
            return cls(text="")
        return cls(
            text=str(raw.get("text", "")),
            style=TextStyle.from_dict(raw.get("style", {})),
        )


@dataclass
class StyledText:
    """Ordered list of :class:`StyledRun` runs.

    Adjacent runs that share a style are NOT auto-merged — the user
    might be in the middle of typing and we don't want to disturb
    their cursor by collapsing runs out from under them. Call
    :meth:`merge_adjacent` explicitly when persisting / serialising.
    """

    runs: list[StyledRun] = field(default_factory=list)

    def append(self, text: str, style: TextStyle | None = None) -> None:
        self.runs.append(StyledRun(
            text=text, style=style or TextStyle(),
        ))

    def plain_text(self) -> str:
        """Return the concatenation of every run's text."""
        return "".join(r.text for r in self.runs)

    def total_length(self) -> int:
        return sum(len(r.text) for r in self.runs)

    def merge_adjacent(self) -> None:
        """Collapse consecutive runs that share a TextStyle.

        Mutates in place. Empty-text runs are always dropped — they
        have no visible effect and confuse downstream renderers.
        """
        out: list[StyledRun] = []
        for run in self.runs:
            if not run.text:
                continue
            if out and out[-1].style == run.style:
                out[-1] = StyledRun(
                    text=out[-1].text + run.text, style=out[-1].style,
                )
            else:
                out.append(replace(run))
        self.runs = out

    def apply_style(
        self, *, start: int, end: int, style: TextStyle,
    ) -> None:
        """Replace the style of characters in ``[start, end)`` with
        ``style``. Out-of-range indices clamp to the document bounds
        so callers don't have to validate upstream."""
        total = self.total_length()
        start = max(0, min(int(start), total))
        end = max(start, min(int(end), total))
        if start == end:
            return
        new_runs: list[StyledRun] = []
        cursor = 0
        for run in self.runs:
            run_end = cursor + len(run.text)
            if run_end <= start or cursor >= end:
                new_runs.append(replace(run))
                cursor = run_end
                continue
            local_start = max(0, start - cursor)
            local_end = min(len(run.text), end - cursor)
            if local_start > 0:
                new_runs.append(StyledRun(
                    text=run.text[:local_start], style=run.style,
                ))
            new_runs.append(StyledRun(
                text=run.text[local_start:local_end], style=style,
            ))
            if local_end < len(run.text):
                new_runs.append(StyledRun(
                    text=run.text[local_end:], style=run.style,
                ))
            cursor = run_end
        self.runs = new_runs

    def to_dict(self) -> dict:
        return {"runs": [r.to_dict() for r in self.runs]}

    @classmethod
    def from_dict(cls, raw: dict) -> StyledText:
        if not isinstance(raw, dict):
            return cls()
        rows = raw.get("runs", ())
        if not isinstance(rows, list):
            return cls()
        out: list[StyledRun] = []
        for row in rows:
            if isinstance(row, dict):
                out.append(StyledRun.from_dict(row))
        return cls(runs=out)

    @classmethod
    def from_plain(
        cls, text: str, style: TextStyle | None = None,
    ) -> StyledText:
        out = cls()
        out.append(text or "", style=style)
        return out


def render_styled_text(
    text: StyledText, *,
    canvas_size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Rasterise ``text`` into a HxWx4 RGBA buffer.

    If ``canvas_size`` is ``None`` the buffer is sized to fit the
    bounding box of the rendered text (plus :data:`LAYOUT_PADDING_PX`
    on each side). Otherwise it's clipped to the supplied size.

    Empty text returns a 1×1 transparent pixel so downstream code can
    safely paste the result without special-casing the empty case.
    """
    if not text.runs or not text.plain_text():
        return np.zeros((1, 1, 4), dtype=np.uint8)
    # Layout pass — measure each run with PIL so we know the canvas
    # size before allocating the buffer.
    layout = _layout_runs(text)
    if canvas_size is None:
        w = max(1, layout["width"] + LAYOUT_PADDING_PX * 2)
        h = max(1, layout["height"] + LAYOUT_PADDING_PX * 2)
    else:
        w, h = canvas_size
        if w <= 0 or h <= 0:
            raise ValueError(
                f"canvas_size must be positive, got {canvas_size}",
            )
    pil = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pil)
    for placement in layout["placements"]:
        run = placement["run"]
        font = _load_font(run.style)
        draw.text(
            (placement["x"] + LAYOUT_PADDING_PX,
             placement["y"] + LAYOUT_PADDING_PX),
            run.text,
            font=font,
            fill=tuple(int(c) for c in run.style.color),
        )
    return np.ascontiguousarray(np.array(pil, dtype=np.uint8))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _load_font(style: TextStyle) -> ImageFont.ImageFont:
    """Best-effort font loader — falls back to PIL's default font if
    the requested family isn't installed.

    Bold / italic try a couple of common filename suffixes (``Bold``,
    ``Italic``, ``Bold Italic``) so the user's documented preference
    works on systems where the font ships with that exact filename.
    PIL's ``truetype`` will raise OSError when the file isn't found;
    we swallow it and fall back so a missing font never crashes the
    paint workflow.
    """
    suffix = ""
    if style.bold and style.italic:
        suffix = " Bold Italic"
    elif style.bold:
        suffix = " Bold"
    elif style.italic:
        suffix = " Italic"
    candidates: Iterable[str] = (
        f"{style.font_family}{suffix}.ttf",
        f"{style.font_family}.ttf",
        f"{style.font_family}{suffix.lower().replace(' ', '')}.ttf",
        style.font_family,
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, int(style.font_size))
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def _layout_runs(text: StyledText) -> dict:
    """Naive single-line layout: walk each run left-to-right, advance
    by the rendered glyph width. Newlines in the text break to a new
    line (multi-line bubbles) — line height is the largest font size
    in the line × :data:`LINE_HEIGHT_RATIO`.

    Returns a dict with ``width`` / ``height`` of the laid-out text
    plus a ``placements`` list of ``{run, x, y}`` entries.
    """
    placements: list[dict] = []
    pen_x = 0
    pen_y = 0
    line_height = 0
    max_width = 0
    for run in text.runs:
        if not run.text:
            continue
        font = _load_font(run.style)
        # Split the run on newlines so each segment lays out on its
        # own line (multi-line bubble support).
        segments = run.text.split("\n")
        for i, segment in enumerate(segments):
            if i > 0:
                pen_x = 0
                pen_y += int(line_height) if line_height else int(
                    run.style.font_size * LINE_HEIGHT_RATIO,
                )
                line_height = 0
            if not segment:
                continue
            placements.append({
                "run": StyledRun(text=segment, style=run.style),
                "x": pen_x,
                "y": pen_y,
            })
            seg_w, seg_h = _measure(font, segment)
            pen_x += seg_w
            line_height = max(
                line_height,
                seg_h,
                int(run.style.font_size * LINE_HEIGHT_RATIO),
            )
            max_width = max(max_width, pen_x)
    total_height = pen_y + (
        int(line_height) if line_height else DEFAULT_FONT_SIZE
    )
    return {
        "placements": placements,
        "width": int(max_width),
        "height": int(total_height),
    }


def _measure(font, segment: str) -> tuple[int, int]:
    """Pillow's text-size API differs across versions. Try the modern
    ``getbbox`` first; fall back to the legacy ``getsize`` for older
    builds."""
    if hasattr(font, "getbbox"):
        bbox = font.getbbox(segment)
        return (int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1]))
    if hasattr(font, "getsize"):
        return font.getsize(segment)   # type: ignore[no-any-return]
    return (len(segment) * 8, 16)
