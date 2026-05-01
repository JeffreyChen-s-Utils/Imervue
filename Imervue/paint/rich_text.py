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

# Ruby (furigana) annotation — small reading glyphs drawn above the
# base run for CJK comic typesetting. The ratio matches the printing
# convention of ruby being half the base point size; the gap is the
# vertical space between ruby baseline and base run top so the two
# do not collide. The constants are module-level so the layout +
# render passes use the exact same numbers.
RUBY_FONT_RATIO = 0.5
RUBY_GAP_PX = 2

# Paragraph alignment within the rendered buffer. ``left`` is the
# default Western convention; ``right`` matches Arabic / Hebrew or
# right-aligned manga callouts; ``center`` is what speech bubbles
# typically use; ``justify`` stretches inter-word whitespace so the
# line fills the full content width (last line of each paragraph
# stays left-aligned, matching print typography).
TEXT_ALIGNMENTS = ("left", "center", "right", "justify")
DEFAULT_TEXT_ALIGNMENT = "left"


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
    """One ``(text, style)`` pair in a :class:`StyledText`.

    ``ruby_text`` is the optional furigana / phonetic reading drawn
    above the run at :data:`RUBY_FONT_RATIO` of the base font size.
    The renderer leaves vertical room above the line for the ruby
    glyphs so they do not crash into the previous line. An empty
    string (the default) means "no ruby" — the run lays out as plain
    text.
    """

    text: str
    style: TextStyle = field(default_factory=TextStyle)
    ruby_text: str = ""

    def __post_init__(self) -> None:
        # Disallow ``None``-typed text — every run must be a string,
        # even an empty one.
        if not isinstance(self.text, str):
            raise ValueError(
                f"run text must be str, got {type(self.text).__name__}",
            )
        if not isinstance(self.ruby_text, str):
            raise ValueError(
                f"ruby_text must be str, got {type(self.ruby_text).__name__}",
            )

    def to_dict(self) -> dict:
        out: dict = {"text": self.text, "style": self.style.to_dict()}
        if self.ruby_text:
            out["ruby_text"] = self.ruby_text
        return out

    @classmethod
    def from_dict(cls, raw: dict) -> StyledRun:
        if not isinstance(raw, dict):
            return cls(text="")
        return cls(
            text=str(raw.get("text", "")),
            style=TextStyle.from_dict(raw.get("style", {})),
            ruby_text=str(raw.get("ruby_text", "")),
        )


@dataclass
class StyledText:
    """Ordered list of :class:`StyledRun` runs.

    Adjacent runs that share a style are NOT auto-merged — the user
    might be in the middle of typing and we don't want to disturb
    their cursor by collapsing runs out from under them. Call
    :meth:`merge_adjacent` explicitly when persisting / serialising.

    ``alignment`` controls per-line horizontal placement (left /
    center / right / justify). The renderer measures each line's
    rendered width then shifts every run on that line so the line
    sits where the alignment requests; ``justify`` stretches inter-
    run gaps to make lines flush at both edges.
    """

    runs: list[StyledRun] = field(default_factory=list)
    alignment: str = DEFAULT_TEXT_ALIGNMENT

    def __post_init__(self) -> None:
        if self.alignment not in TEXT_ALIGNMENTS:
            raise ValueError(
                f"unknown alignment {self.alignment!r}; "
                f"expected one of {TEXT_ALIGNMENTS}",
            )

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
        """Collapse consecutive runs that share a TextStyle and ruby.

        Mutates in place. Empty-text runs are always dropped — they
        have no visible effect and confuse downstream renderers. Ruby
        annotation participates in the equality check so two runs
        with different ruby readings stay separate even when their
        font / colour matches.
        """
        out: list[StyledRun] = []
        for run in self.runs:
            if not run.text:
                continue
            if (
                out
                and out[-1].style == run.style
                and out[-1].ruby_text == run.ruby_text
            ):
                out[-1] = StyledRun(
                    text=out[-1].text + run.text,
                    style=out[-1].style,
                    ruby_text=out[-1].ruby_text,
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
                    ruby_text=run.ruby_text,
                ))
            new_runs.append(StyledRun(
                text=run.text[local_start:local_end], style=style,
                ruby_text=run.ruby_text,
            ))
            if local_end < len(run.text):
                new_runs.append(StyledRun(
                    text=run.text[local_end:], style=run.style,
                    ruby_text=run.ruby_text,
                ))
            cursor = run_end
        self.runs = new_runs

    def to_dict(self) -> dict:
        out: dict = {"runs": [r.to_dict() for r in self.runs]}
        if self.alignment != DEFAULT_TEXT_ALIGNMENT:
            out["alignment"] = self.alignment
        return out

    @classmethod
    def from_dict(cls, raw: dict) -> StyledText:
        if not isinstance(raw, dict):
            return cls()
        rows = raw.get("runs", ())
        if not isinstance(rows, list):
            return cls()
        out_runs: list[StyledRun] = []
        for row in rows:
            if isinstance(row, dict):
                out_runs.append(StyledRun.from_dict(row))
        alignment = raw.get("alignment", DEFAULT_TEXT_ALIGNMENT)
        if alignment not in TEXT_ALIGNMENTS:
            alignment = DEFAULT_TEXT_ALIGNMENT
        return cls(runs=out_runs, alignment=alignment)

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
        if run.ruby_text:
            _draw_ruby(draw, run, font, placement)
    return np.ascontiguousarray(np.array(pil, dtype=np.uint8))


def _draw_ruby(
    draw: ImageDraw.ImageDraw,
    run: StyledRun,
    base_font: ImageFont.ImageFont,
    placement: dict,
) -> None:
    """Render the run's ruby annotation centred above the base text.

    The ruby font is :data:`RUBY_FONT_RATIO` × the base size; its
    horizontal centre matches the base run's, and its baseline sits
    :data:`RUBY_GAP_PX` above the base run's top edge. The layout
    pass reserves the vertical space so the result never overlaps
    the previous line.
    """
    ruby_size = max(TEXT_SIZE_MIN, int(run.style.font_size * RUBY_FONT_RATIO))
    ruby_style = replace(run.style, font_size=ruby_size)
    ruby_font = _load_font(ruby_style)
    base_w, _ = _measure(base_font, run.text)
    ruby_w, ruby_h = _measure(ruby_font, run.ruby_text)
    base_x = placement["x"] + LAYOUT_PADDING_PX
    base_y = placement["y"] + LAYOUT_PADDING_PX
    ruby_x = base_x + max(0, (base_w - ruby_w) // 2)
    ruby_y = base_y - ruby_h - RUBY_GAP_PX
    draw.text(
        (ruby_x, ruby_y),
        run.ruby_text,
        font=ruby_font,
        fill=tuple(int(c) for c in run.style.color),
    )


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

    Reserves vertical space above the first line for any ruby
    annotation on the runs in that line, so the rendered ruby glyphs
    never run off the top of the buffer or collide with the run
    above.

    Returns a dict with ``width`` / ``height`` of the laid-out text
    plus a ``placements`` list of ``{run, x, y}`` entries.
    """
    placements: list[dict] = []
    ruby_top_offset = _ruby_height_for_first_line(text)
    pen_x = 0
    pen_y = ruby_top_offset
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
                "run": StyledRun(
                    text=segment, style=run.style, ruby_text=run.ruby_text,
                ),
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
    if text.alignment != "left" and placements:
        _apply_alignment(placements, text.alignment, int(max_width))
    return {
        "placements": placements,
        "width": int(max_width),
        "height": int(total_height),
    }


def _apply_alignment(
    placements: list[dict], alignment: str, content_width: int,
) -> None:
    """Shift each line's placements horizontally to honour ``alignment``.

    Mutates the ``placements`` list in place. Lines are identified by
    their ``y`` value — runs that share a y are co-line. ``justify``
    spreads inter-run gaps across the line (the last line of the
    output always falls back to ``left`` so a one-word last line
    isn't stretched into the canvas margins).
    """
    # Group by y, preserving insertion order so the last group is
    # the last line.
    groups: list[tuple[int, list[dict]]] = []
    for placement in placements:
        y = int(placement["y"])
        if groups and groups[-1][0] == y:
            groups[-1][1].append(placement)
        else:
            groups.append((y, [placement]))
    for line_index, (_y, line_runs) in enumerate(groups):
        line_width = _line_width(line_runs)
        slack = content_width - line_width
        if slack <= 0:
            continue
        if alignment == "center":
            offset = slack // 2
            for placement in line_runs:
                placement["x"] += offset
        elif alignment == "right":
            for placement in line_runs:
                placement["x"] += slack
        elif alignment == "justify":
            # Justify all but the last line — print typography
            # convention so the trailing word doesn't stretch.
            if line_index == len(groups) - 1 or len(line_runs) < 2:
                continue
            extra_per_gap = slack // (len(line_runs) - 1)
            for i, placement in enumerate(line_runs):
                placement["x"] += extra_per_gap * i


def _line_width(line_runs: list[dict]) -> int:
    """Return the rendered width of a single line of placements."""
    if not line_runs:
        return 0
    max_right = 0
    for placement in line_runs:
        run = placement["run"]
        font = _load_font(run.style)
        seg_w, _ = _measure(font, run.text)
        right = int(placement["x"]) + seg_w
        max_right = max(max_right, right)
    leftmost = min(int(placement["x"]) for placement in line_runs)
    return max(0, max_right - leftmost)


def _ruby_height_for_first_line(text: StyledText) -> int:
    """Return the vertical reservation needed for ruby on the first line.

    Walks runs left-to-right and stops at the first newline since
    that opens a new line; ruby on later lines is handled by the
    line-height bump in the regular layout loop. Zero when no run in
    the first line carries ruby annotation.
    """
    needed = 0
    for run in text.runs:
        if "\n" in run.text:
            # Once a line break is seen the first line is complete;
            # ruby on subsequent runs belongs to a later line.
            head = run.text.split("\n", 1)[0]
            if head and run.ruby_text:
                needed = max(needed, _ruby_block_height(run))
            break
        if run.ruby_text and run.text:
            needed = max(needed, _ruby_block_height(run))
    return needed


def _ruby_block_height(run: StyledRun) -> int:
    """Pixel height a ruby annotation reserves above the base text."""
    ruby_size = max(TEXT_SIZE_MIN, int(run.style.font_size * RUBY_FONT_RATIO))
    return ruby_size + RUBY_GAP_PX


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
