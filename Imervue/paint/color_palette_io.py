"""Foreign-format colour palette importers.

Three formats:

* ``.gpl`` — external image editors Palette: line-oriented ASCII, the easiest to write
  a parser for (one ``R G B name`` row per colour).
* ``.aco`` — Adobe Color Swatch: binary, big-endian. v1 is plain RGB
  rows, v2 prepends a Pascal-string colour name to each row. The
  reader handles both versions.
* ``.ase`` — Adobe Swatch Exchange: hierarchical group / colour
  blocks identified by 16-bit tags. We extract every colour block
  in the file and ignore the group structure since the colour dock's
  swatch list is flat.

Every parser returns a list of :class:`PaletteColor` rows containing
``(r, g, b, name)``. Unknown / unsupported colour spaces (CMYK / Lab
in ``.aco`` and ``.ase``) are converted to RGB with a coarse
approximation; the user gets *something* instead of a hard error.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

GPL_PALETTE_EXTENSION = ".gpl"
ADOBE_COLOR_EXTENSION = ".aco"
ADOBE_SWATCH_EXCHANGE_EXTENSION = ".ase"


@dataclass(frozen=True)
class PaletteColor:
    """One swatch — RGB plus an optional name."""

    r: int
    g: int
    b: int
    name: str = ""

    @property
    def rgb(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)

    def __post_init__(self) -> None:
        for label, value in (("r", self.r), ("g", self.g), ("b", self.b)):
            if not 0 <= int(value) <= 255:
                raise ValueError(
                    f"{label} must be in [0, 255], got {value!r}",
                )


# ---------------------------------------------------------------------------
# .gpl — external image editors Palette (ASCII)
# ---------------------------------------------------------------------------


def import_gimp_palette(path: str | Path) -> list[PaletteColor]:
    """Read a external image editors ``.gpl`` palette file."""
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    out: list[PaletteColor] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Skip the "external image editors Palette" header / metadata lines.
        if stripped.startswith(("external image editors", "Name:", "Columns:")):
            continue
        parts = stripped.split(maxsplit=3)
        if len(parts) < 3:
            continue
        try:
            r = max(0, min(255, int(parts[0])))
            g = max(0, min(255, int(parts[1])))
            b = max(0, min(255, int(parts[2])))
        except ValueError:
            continue
        name = parts[3] if len(parts) > 3 else ""
        out.append(PaletteColor(r=r, g=g, b=b, name=name))
    return out


# ---------------------------------------------------------------------------
# .aco — Adobe Color Swatch (binary, big-endian)
# ---------------------------------------------------------------------------


_ACO_COLOR_SPACE_RGB = 0
_ACO_COLOR_SPACE_HSB = 1
_ACO_COLOR_SPACE_CMYK = 2
_ACO_COLOR_SPACE_GREY = 8


def import_adobe_color(path: str | Path) -> list[PaletteColor]:
    """Read an Adobe ``.aco`` swatch file (v1 or v2)."""
    blob = Path(path).read_bytes()
    if len(blob) < 4:
        return []
    version, count = struct.unpack(">HH", blob[:4])
    if version not in (1, 2):
        return []
    out, _ = _parse_aco_block(blob, offset=4, count=count, version=version)
    if version == 1 and len(blob) > 4 + count * 10:
        # File contains a v2 block right after the v1 block; v2 has
        # the same colours but with names attached.
        v2_offset = 4 + count * 10
        if len(blob) >= v2_offset + 4:
            _, count2 = struct.unpack(">HH", blob[v2_offset:v2_offset + 4])
            out2, _ = _parse_aco_block(
                blob, offset=v2_offset + 4, count=count2, version=2,
            )
            if out2:
                return out2
    return out


def _parse_aco_block(
    blob: bytes, *, offset: int, count: int, version: int,
) -> tuple[list[PaletteColor], int]:
    """Parse ``count`` colour rows starting at ``offset``.

    Returns ``(colours, end_offset)``. v1 rows are 10 bytes each;
    v2 rows are 10 bytes plus a 2-byte zero pad and a UTF-16BE
    Pascal string with a 4-byte length prefix.
    """
    out: list[PaletteColor] = []
    pos = offset
    for _ in range(count):
        if pos + 10 > len(blob):
            break
        space, w, x, y, _z = struct.unpack(">HHHHH", blob[pos:pos + 10])
        pos += 10
        name = ""
        if version == 2 and pos + 4 <= len(blob):
            # 2-byte zero pad + 2-byte length (in UTF-16 code units,
            # NOT bytes) + UTF-16BE chars + null terminator.
            pos += 2
            (name_len,) = struct.unpack(">H", blob[pos:pos + 2])
            pos += 2
            name_bytes = blob[pos:pos + name_len * 2]
            try:
                name = name_bytes.decode("utf-16-be").rstrip("\x00")
            except UnicodeDecodeError:
                name = ""
            pos += name_len * 2
        rgb = _aco_to_rgb(space, w, x, y)
        if rgb is None:
            continue
        r, g, b = rgb
        out.append(PaletteColor(r=r, g=g, b=b, name=name))
    return out, pos


def _aco_to_rgb(
    space: int, w: int, x: int, y: int,
) -> tuple[int, int, int] | None:
    """Convert an .aco colour record to 8-bit RGB."""
    if space == _ACO_COLOR_SPACE_RGB:
        # Each component is 0..65535 over the same range.
        return (w >> 8, x >> 8, y >> 8)
    if space == _ACO_COLOR_SPACE_GREY:
        # Greyscale: w is 0..10000.
        v = max(0, min(255, int(round(w * 255 / 10000))))
        return (v, v, v)
    if space == _ACO_COLOR_SPACE_HSB:
        # Approximate HSB→RGB via colorsys-style maths inline.
        import colorsys
        h = w / 65535.0
        s = x / 65535.0
        v = y / 65535.0
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
    if space == _ACO_COLOR_SPACE_CMYK:
        # CMYK: each component is 0..65535 representing 100..0% (Adobe
        # stores inverted). Convert to RGB via the naïve formula.
        c = 1.0 - w / 65535.0
        m = 1.0 - x / 65535.0
        y_ = 1.0 - y / 65535.0
        # We don't have K from the 4-tuple here, so treat CMY only.
        r = int(round(255 * (1.0 - c)))
        g = int(round(255 * (1.0 - m)))
        b = int(round(255 * (1.0 - y_)))
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    return None


# ---------------------------------------------------------------------------
# .ase — Adobe Swatch Exchange
# ---------------------------------------------------------------------------


_ASE_BLOCK_GROUP_START = 0xC001
_ASE_BLOCK_GROUP_END = 0xC002
_ASE_BLOCK_COLOR = 0x0001


def import_adobe_swatch_exchange(path: str | Path) -> list[PaletteColor]:
    """Read a flat list of colours from an Adobe ``.ase`` file."""
    blob = Path(path).read_bytes()
    if len(blob) < 12 or blob[:4] != b"ASEF":
        return []
    block_count = struct.unpack(">I", blob[8:12])[0]
    pos = 12
    out: list[PaletteColor] = []
    for _ in range(block_count):
        if pos + 6 > len(blob):
            break
        block_type, block_len = struct.unpack(">HI", blob[pos:pos + 6])
        body_start = pos + 6
        body_end = body_start + block_len
        if body_end > len(blob):
            break
        if block_type == _ASE_BLOCK_COLOR:
            colour = _parse_ase_color_block(blob[body_start:body_end])
            if colour is not None:
                out.append(colour)
        pos = body_end
    return out


def _parse_ase_color_block(body: bytes) -> PaletteColor | None:
    """Parse one ASE colour block body."""
    if len(body) < 2:
        return None
    pos = 0
    # Name: UTF-16BE length-prefixed (length in UTF-16 code units,
    # *including* the null terminator).
    (name_len,) = struct.unpack(">H", body[:2])
    pos += 2
    name_bytes = body[pos:pos + name_len * 2]
    try:
        name = name_bytes.decode("utf-16-be").rstrip("\x00")
    except UnicodeDecodeError:
        name = ""
    pos += name_len * 2
    if pos + 4 > len(body):
        return None
    space_tag = body[pos:pos + 4].rstrip(b" ")
    pos += 4
    if space_tag == b"RGB":
        if pos + 12 > len(body):
            return None
        r, g, b = struct.unpack(">fff", body[pos:pos + 12])
        return PaletteColor(
            r=_clamp_unit_to_byte(r),
            g=_clamp_unit_to_byte(g),
            b=_clamp_unit_to_byte(b),
            name=name,
        )
    if space_tag == b"GRAY":
        if pos + 4 > len(body):
            return None
        (v,) = struct.unpack(">f", body[pos:pos + 4])
        gray = _clamp_unit_to_byte(v)
        return PaletteColor(r=gray, g=gray, b=gray, name=name)
    if space_tag == b"CMYK":
        if pos + 16 > len(body):
            return None
        c, m, y_, k = struct.unpack(">ffff", body[pos:pos + 16])
        # Naïve CMYK→RGB. Good enough for swatch import; users can
        # tweak inside Imervue.
        r = (1.0 - c) * (1.0 - k)
        g = (1.0 - m) * (1.0 - k)
        b = (1.0 - y_) * (1.0 - k)
        return PaletteColor(
            r=_clamp_unit_to_byte(r),
            g=_clamp_unit_to_byte(g),
            b=_clamp_unit_to_byte(b),
            name=name,
        )
    if space_tag == b"LAB":
        if pos + 12 > len(body):
            return None
        # Coarse L*a*b → RGB approximation (linear lightness, ignore
        # a/b chroma). Same "good enough" stance as CMYK.
        l_, _a, _b = struct.unpack(">fff", body[pos:pos + 12])
        gray = _clamp_unit_to_byte(l_)
        return PaletteColor(r=gray, g=gray, b=gray, name=name)
    return None


def _clamp_unit_to_byte(value: float) -> int:
    return max(0, min(255, int(round(value * 255))))


# ---------------------------------------------------------------------------
# Universal entry point
# ---------------------------------------------------------------------------


def import_palette(path: str | Path) -> list[PaletteColor]:
    """Pick the right reader based on file extension."""
    suffix = Path(path).suffix.lower()
    if suffix == GPL_PALETTE_EXTENSION:
        return import_gimp_palette(path)
    if suffix == ADOBE_COLOR_EXTENSION:
        return import_adobe_color(path)
    if suffix == ADOBE_SWATCH_EXCHANGE_EXTENSION:
        return import_adobe_swatch_exchange(path)
    raise ValueError(
        f"unknown palette extension {suffix!r}; "
        f"expected one of {{{GPL_PALETTE_EXTENSION}, "
        f"{ADOBE_COLOR_EXTENSION}, {ADOBE_SWATCH_EXCHANGE_EXTENSION}}}",
    )
