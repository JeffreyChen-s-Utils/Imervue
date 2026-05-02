"""Tests for foreign-format palette importers."""
from __future__ import annotations

import struct

import pytest

from Imervue.paint.color_palette_io import (
    PaletteColor,
    import_adobe_color,
    import_adobe_swatch_exchange,
    import_gimp_palette,
    import_palette,
)


# ---------------------------------------------------------------------------
# PaletteColor
# ---------------------------------------------------------------------------


def test_palette_color_holds_rgb():
    c = PaletteColor(r=10, g=20, b=30, name="x")
    assert c.rgb == (10, 20, 30)
    assert c.name == "x"


def test_palette_color_rejects_out_of_range_component():
    with pytest.raises(ValueError, match=r"\[0, 255\]"):
        PaletteColor(r=300, g=0, b=0)


# ---------------------------------------------------------------------------
# .gpl reader
# ---------------------------------------------------------------------------


def _write_gpl(tmp_path, body: str):
    target = tmp_path / "palette.gpl"
    target.write_text(body, encoding="utf-8")
    return target


def test_gpl_parses_named_rows(tmp_path):
    target = _write_gpl(tmp_path, """\
GIMP Palette
Name: Demo
Columns: 4
#
255   0   0	Red
  0 255   0	Green
  0   0 255	Blue
""")
    out = import_gimp_palette(target)
    assert [(c.r, c.g, c.b, c.name) for c in out] == [
        (255, 0, 0, "Red"), (0, 255, 0, "Green"), (0, 0, 255, "Blue"),
    ]


def test_gpl_skips_comments_and_blank_lines(tmp_path):
    target = _write_gpl(tmp_path, """\
GIMP Palette
# this is a comment
Name: Test

# another comment

100 100 100 Grey
""")
    out = import_gimp_palette(target)
    assert len(out) == 1


def test_gpl_drops_malformed_rows(tmp_path):
    target = _write_gpl(tmp_path, """\
GIMP Palette
255 0 0 OK
not a colour
12 34 SeventyEight
99 88 77 Trailing
""")
    out = import_gimp_palette(target)
    # Row 2 has a non-numeric component → drop. Row 3 has fewer than
    # three parts after splitting at "Seventy" → drop. Two valid rows.
    assert [c.name for c in out] == ["OK", "Trailing"]


def test_gpl_clamps_out_of_range_components(tmp_path):
    target = _write_gpl(tmp_path, """\
GIMP Palette
-50 300 100 Clipped
""")
    out = import_gimp_palette(target)
    assert (out[0].r, out[0].g, out[0].b) == (0, 255, 100)


def test_gpl_handles_no_name_column(tmp_path):
    target = _write_gpl(tmp_path, """\
GIMP Palette
255 0 0
0 255 0
""")
    out = import_gimp_palette(target)
    assert all(c.name == "" for c in out)
    assert len(out) == 2


# ---------------------------------------------------------------------------
# .aco reader (binary)
# ---------------------------------------------------------------------------


def _build_aco_v1(rows: list[tuple[int, int, int]]) -> bytes:
    payload = struct.pack(">HH", 1, len(rows))
    for r, g, b in rows:
        # space=0 (RGB), each component scaled to 16-bit.
        payload += struct.pack(">HHHHH", 0, r * 257, g * 257, b * 257, 0)
    return payload


def test_aco_v1_reads_rgb_rows(tmp_path):
    target = tmp_path / "demo.aco"
    target.write_bytes(_build_aco_v1([(255, 0, 0), (0, 255, 0), (0, 0, 255)]))
    out = import_adobe_color(target)
    assert [(c.r, c.g, c.b) for c in out] == [
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
    ]


def test_aco_v2_reads_named_rgb_rows(tmp_path):
    """v1 block + v2 block in the same file — the reader should
    return the v2 colours (with names) rather than v1."""
    rows = [(200, 50, 50)]
    v1 = _build_aco_v1(rows)
    name = "Crimson"
    name_bytes = (name + "\x00").encode("utf-16-be")
    name_len = len(name) + 1   # length includes the null terminator
    v2_block = struct.pack(">HH", 2, len(rows))
    for r, g, b in rows:
        v2_block += struct.pack(">HHHHH", 0, r * 257, g * 257, b * 257, 0)
        v2_block += b"\x00\x00"   # 2-byte zero pad
        v2_block += struct.pack(">H", name_len)
        v2_block += name_bytes
    target = tmp_path / "named.aco"
    target.write_bytes(v1 + v2_block)
    out = import_adobe_color(target)
    assert out[0].name == "Crimson"
    assert out[0].rgb == (200, 50, 50)


def test_aco_short_file_returns_empty(tmp_path):
    target = tmp_path / "short.aco"
    target.write_bytes(b"\x00")
    assert import_adobe_color(target) == []


def test_aco_unknown_version_returns_empty(tmp_path):
    target = tmp_path / "v99.aco"
    target.write_bytes(struct.pack(">HH", 99, 1))
    assert import_adobe_color(target) == []


def test_aco_grey_space_converts_to_three_equal_channels(tmp_path):
    """Space tag 8 is greyscale; the 0..10000 value scales to 0..255
    on every channel."""
    target = tmp_path / "grey.aco"
    payload = struct.pack(">HH", 1, 1)
    # Greyscale at half (5000/10000 → 127).
    payload += struct.pack(">HHHHH", 8, 5000, 0, 0, 0)
    target.write_bytes(payload)
    out = import_adobe_color(target)
    # 5000 / 10000 * 255 = 127.5 → rounds to 128.
    assert out[0].rgb == (128, 128, 128)


# ---------------------------------------------------------------------------
# .ase reader (binary)
# ---------------------------------------------------------------------------


def _build_ase(blocks: list[bytes]) -> bytes:
    body = b"".join(blocks)
    return b"ASEF" + struct.pack(">HHI", 1, 0, len(blocks)) + body


def _ase_color_block(name: str, r: float, g: float, b: float) -> bytes:
    name_chars = name + "\x00"
    name_bytes = name_chars.encode("utf-16-be")
    name_len = len(name_chars)
    body = struct.pack(">H", name_len) + name_bytes
    body += b"RGB "
    body += struct.pack(">fff", r, g, b)
    body += b"\x00\x00"   # colour-type tag (2 bytes)
    return struct.pack(">HI", 0x0001, len(body)) + body


def test_ase_reads_rgb_color_block(tmp_path):
    target = tmp_path / "demo.ase"
    target.write_bytes(_build_ase([
        _ase_color_block("Pink", 1.0, 0.5, 0.5),
        _ase_color_block("Sky", 0.0, 0.5, 1.0),
    ]))
    out = import_adobe_swatch_exchange(target)
    assert [c.name for c in out] == ["Pink", "Sky"]
    assert out[0].rgb == (255, 128, 128)
    assert out[1].rgb == (0, 128, 255)


def test_ase_skips_unknown_block_type(tmp_path):
    """Group-start / group-end blocks must be walked past without
    being treated as colour rows."""
    group_start = struct.pack(">HI", 0xC001, 2) + b"\x00\x00"
    group_end = struct.pack(">HI", 0xC002, 0)
    target = tmp_path / "groups.ase"
    target.write_bytes(b"ASEF" + struct.pack(">HHI", 1, 0, 3) + (
        group_start + _ase_color_block("Red", 1.0, 0.0, 0.0) + group_end
    ))
    out = import_adobe_swatch_exchange(target)
    assert [c.name for c in out] == ["Red"]


def test_ase_rejects_non_asef_header(tmp_path):
    target = tmp_path / "bad.ase"
    target.write_bytes(b"NOPE" + b"\x00" * 16)
    assert import_adobe_swatch_exchange(target) == []


def test_ase_short_header_returns_empty(tmp_path):
    target = tmp_path / "tiny.ase"
    target.write_bytes(b"ASE")
    assert import_adobe_swatch_exchange(target) == []


# ---------------------------------------------------------------------------
# Universal dispatcher
# ---------------------------------------------------------------------------


def test_import_palette_routes_by_extension(tmp_path):
    gpl = _write_gpl(tmp_path, "GIMP Palette\n255 0 0 R\n")
    assert import_palette(gpl)[0].rgb == (255, 0, 0)

    aco = tmp_path / "demo.aco"
    aco.write_bytes(_build_aco_v1([(0, 255, 0)]))
    assert import_palette(aco)[0].rgb == (0, 255, 0)

    ase = tmp_path / "demo.ase"
    ase.write_bytes(_build_ase([_ase_color_block("Blue", 0.0, 0.0, 1.0)]))
    assert import_palette(ase)[0].rgb == (0, 0, 255)


def test_import_palette_rejects_unknown_extension(tmp_path):
    target = tmp_path / "unknown.xyz"
    target.write_text("dummy")
    with pytest.raises(ValueError, match="unknown palette extension"):
        import_palette(target)
