"""Tests for the PSD import / export subset."""
from __future__ import annotations

import struct

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.psd_io import (
    _COMPRESSION_RAW,
    _COMPRESSION_RLE,
    _Cursor,
    _assign_composite_channel,
    _packbits_decode,
    _parse_image_data_section,
    load_psd,
    save_psd,
)


# ---------------------------------------------------------------------------
# Round-trip via our own writer + reader
# ---------------------------------------------------------------------------


def _make_doc(h=8, w=10):
    doc = PaintDocument()
    base = np.zeros((h, w, 4), dtype=np.uint8)
    base[..., :3] = (200, 100, 50)
    base[..., 3] = 255
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (10, 200, 30)
    above.image[..., 3] = 200
    above.opacity = 0.7
    above.blend_mode = "multiply"
    return doc


def test_save_then_load_round_trips_layer_count(tmp_path):
    doc = _make_doc()
    path = tmp_path / "round.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    assert loaded.layer_count == doc.layer_count


def test_save_then_load_preserves_layer_names(tmp_path):
    doc = _make_doc()
    path = tmp_path / "names.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    assert [layer.name for layer in loaded.layers()] == [
        layer.name for layer in doc.layers()
    ]


def test_save_then_load_preserves_blend_mode_and_opacity(tmp_path):
    doc = _make_doc()
    path = tmp_path / "blend.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    above_load = loaded.layers()[1]
    assert above_load.blend_mode == "multiply"
    # Opacity stored as 0..255 → may round; tolerate ±1/255.
    assert abs(above_load.opacity - 0.7) <= 1.0 / 255.0 + 1e-6


def test_save_then_load_preserves_visibility(tmp_path):
    doc = _make_doc()
    above = doc.layers()[1]
    above.visible = False
    path = tmp_path / "vis.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    assert loaded.layers()[1].visible is False


def test_save_then_load_preserves_pixels(tmp_path):
    doc = _make_doc()
    path = tmp_path / "pixels.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    for original, restored in zip(doc.layers(), loaded.layers(), strict=True):
        np.testing.assert_array_equal(original.image, restored.image)


def test_save_then_load_preserves_lock_alpha(tmp_path):
    doc = _make_doc()
    above = doc.layers()[1]
    above.lock_alpha = True
    path = tmp_path / "lock.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    assert loaded.layers()[1].lock_alpha is True


def test_save_creates_parent_directory(tmp_path):
    doc = _make_doc()
    nested = tmp_path / "a" / "b" / "c.psd"
    save_psd(doc, nested)
    assert nested.exists()


# ---------------------------------------------------------------------------
# Header bytes
# ---------------------------------------------------------------------------


def test_save_writes_8bps_signature(tmp_path):
    doc = _make_doc()
    path = tmp_path / "sig.psd"
    save_psd(doc, path)
    assert path.read_bytes()[:4] == b"8BPS"


def test_save_writes_correct_dimensions(tmp_path):
    doc = _make_doc(h=12, w=20)
    path = tmp_path / "dims.psd"
    save_psd(doc, path)
    raw = path.read_bytes()
    # Header layout: 4 sig + 2 version + 6 reserved + 2 channels + 4 height + 4 width
    h, w = struct.unpack(">II", raw[14:22])
    assert h == 12
    assert w == 20


# ---------------------------------------------------------------------------
# save_psd error paths
# ---------------------------------------------------------------------------


def test_save_empty_document_raises(tmp_path):
    doc = PaintDocument()
    with pytest.raises(ValueError, match="empty"):
        save_psd(doc, tmp_path / "empty.psd")


# ---------------------------------------------------------------------------
# load_psd error paths
# ---------------------------------------------------------------------------


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_psd(tmp_path / "ghost.psd")


def test_load_rejects_non_psd_signature(tmp_path):
    path = tmp_path / "notpsd.psd"
    path.write_bytes(b"NOPE" + b"\x00" * 100)
    with pytest.raises(ValueError, match="signature"):
        load_psd(path)


def test_load_rejects_unsupported_depth(tmp_path):
    """A PSD with 16-bit depth should be rejected, not silently
    corrupted."""
    body = struct.pack(">4sH6xHIIHH", b"8BPS", 1, 4, 4, 4, 16, 3)
    path = tmp_path / "16bit.psd"
    path.write_bytes(body + b"\x00" * 200)
    with pytest.raises(ValueError, match="depth"):
        load_psd(path)


def test_load_rejects_indexed_color_mode(tmp_path):
    body = struct.pack(">4sH6xHIIHH", b"8BPS", 1, 1, 4, 4, 8, 2)  # color mode 2 = indexed
    path = tmp_path / "indexed.psd"
    path.write_bytes(body + b"\x00" * 200)
    with pytest.raises(ValueError, match="color mode"):
        load_psd(path)


# ---------------------------------------------------------------------------
# PackBits decoder
# ---------------------------------------------------------------------------


def test_packbits_decodes_literal_run():
    # Header 3 (= n+1=4 literal bytes), then four bytes.
    raw = bytes([3, 1, 2, 3, 4])
    out = _packbits_decode(raw, 4)
    np.testing.assert_array_equal(out, np.array([1, 2, 3, 4], dtype=np.uint8))


def test_packbits_decodes_repeat_run():
    # Header -2 (256 - 2 = 254) → repeat next byte 3 times.
    raw = bytes([254, 9])
    out = _packbits_decode(raw, 3)
    np.testing.assert_array_equal(out, np.array([9, 9, 9], dtype=np.uint8))


def test_packbits_skips_no_op_byte():
    # Header 0x80 (-128 in signed) is a no-op; the next byte 0 is a
    # 1-byte literal run with payload 5.
    raw = bytes([0x80, 0, 5])
    out = _packbits_decode(raw, 1)
    np.testing.assert_array_equal(out, np.array([5], dtype=np.uint8))


def test_packbits_handles_short_row_with_zero_pad():
    """If the encoded data ends short of expected_length, the decoder
    pads the rest with zeros rather than raising."""
    raw = bytes([0, 1])  # one literal byte = 1
    out = _packbits_decode(raw, 4)
    np.testing.assert_array_equal(out, np.array([1, 0, 0, 0], dtype=np.uint8))


# ---------------------------------------------------------------------------
# Single-layer round-trip on bigger random data
# ---------------------------------------------------------------------------


def test_random_pixels_round_trip_byte_for_byte(tmp_path):
    rng = np.random.default_rng(seed=12345)
    doc = PaintDocument()
    base = rng.integers(0, 256, (16, 24, 4), dtype=np.uint8)
    doc.load_image(base)
    path = tmp_path / "random.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    np.testing.assert_array_equal(loaded.layers()[0].image, base)


# ---------------------------------------------------------------------------
# Unicode names
# ---------------------------------------------------------------------------


def test_layer_name_round_trips_chinese_characters(tmp_path):
    doc = _make_doc()
    doc.layers()[1].name = "插畫"
    path = tmp_path / "cjk.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    assert loaded.layers()[1].name == "插畫"


def test_layer_name_round_trips_japanese_kana(tmp_path):
    doc = _make_doc()
    doc.layers()[1].name = "キャラクター"
    path = tmp_path / "jp.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    assert loaded.layers()[1].name == "キャラクター"


def test_layer_name_round_trips_mixed_unicode(tmp_path):
    doc = _make_doc()
    doc.layers()[1].name = "Sketch — 草稿 (v2)"
    path = tmp_path / "mixed.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    assert loaded.layers()[1].name == "Sketch — 草稿 (v2)"


# ---------------------------------------------------------------------------
# Layer groups
# ---------------------------------------------------------------------------


def test_groups_round_trip_layer_membership(tmp_path):
    doc = _make_doc()
    doc.create_group("Inks")
    doc.set_layer_group(group="Inks")
    path = tmp_path / "groups.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    # Members of "Inks" should still be tagged with the group on read.
    in_group = [layer for layer in loaded.layers() if layer.group == "Inks"]
    assert len(in_group) >= 1
    assert "Inks" in [g.name for g in loaded.groups()]


def test_groups_round_trip_group_visibility(tmp_path):
    doc = _make_doc()
    doc.create_group("Inks", visible=False)
    doc.set_layer_group(group="Inks")
    path = tmp_path / "hidden_group.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    grp = loaded.group("Inks")
    assert grp is not None
    assert grp.visible is False


def test_groups_round_trip_group_opacity(tmp_path):
    doc = _make_doc()
    doc.create_group("Inks", opacity=0.5)
    doc.set_layer_group(group="Inks")
    path = tmp_path / "opacity_group.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    grp = loaded.group("Inks")
    assert grp is not None
    assert abs(grp.opacity - 0.5) <= 1.0 / 255.0 + 1e-6


def test_groups_outside_layer_unaffected(tmp_path):
    """A layer above the group with no group tag round-trips with no
    spurious group assignment."""
    doc = _make_doc()
    doc.create_group("Inks")
    # Move only the bottom layer into the group.
    doc.set_layer_group(index=0, group="Inks")
    # Layer at index 1 ("Above") is intentionally NOT in the group.
    path = tmp_path / "outside.psd"
    save_psd(doc, path)
    loaded = load_psd(path)
    # The "Above" layer should keep no group on read.
    above = [layer for layer in loaded.layers() if layer.name == "Above"]
    assert above
    assert above[0].group is None


# ---------------------------------------------------------------------------
# Composite image-data section — focused coverage of the parser's branches
# (the writer always emits RAW, so RLE / alpha-fallback / unsupported-compression
# are otherwise untested by the round-trip tests).
# ---------------------------------------------------------------------------


def test_assign_composite_channel_routes_alpha_to_slot_3():
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    plane = np.full((2, 2), 99, dtype=np.uint8)
    _assign_composite_channel(image, plane, ch_id=-1)
    assert (image[..., 3] == 99).all()
    assert (image[..., :3] == 0).all()


def test_assign_composite_channel_routes_rgb_to_indexed_slot():
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    plane = np.full((2, 2), 42, dtype=np.uint8)
    _assign_composite_channel(image, plane, ch_id=1)
    assert (image[..., 1] == 42).all()
    assert (image[..., 0] == 0).all()
    assert (image[..., 2] == 0).all()
    assert (image[..., 3] == 0).all()


def _build_raw_composite(h: int, w: int, planes: dict[int, np.ndarray]) -> bytes:
    """Compose a composite image-data section using RAW compression.

    ``planes`` maps channel ids (0=R, 1=G, 2=B, -1=A) to HxW uint8 planes.
    Channels not present default to a zero plane.
    """
    out = bytearray(struct.pack(">H", _COMPRESSION_RAW))
    for ch_id in (0, 1, 2, -1):
        plane = planes.get(ch_id, np.zeros((h, w), dtype=np.uint8))
        out.extend(plane.tobytes())
    return bytes(out)


def test_parse_image_data_section_raw_orders_channels_rgba():
    h, w = 2, 3
    planes = {
        0: np.full((h, w), 10, dtype=np.uint8),
        1: np.full((h, w), 20, dtype=np.uint8),
        2: np.full((h, w), 30, dtype=np.uint8),
        -1: np.full((h, w), 40, dtype=np.uint8),
    }
    cursor = _Cursor(_build_raw_composite(h, w, planes))
    out = _parse_image_data_section(cursor, h, w)
    assert (out[..., 0] == 10).all()
    assert (out[..., 1] == 20).all()
    assert (out[..., 2] == 30).all()
    assert (out[..., 3] == 40).all()


def test_parse_image_data_section_falls_back_to_opaque_alpha():
    """When the stored alpha plane is all zeros the decoder must paint
    fully opaque so the pixels actually render — older PSDs from
    Photoshop omitted the alpha plane entirely."""
    h, w = 2, 2
    cursor = _Cursor(_build_raw_composite(h, w, {0: np.full((h, w), 5, dtype=np.uint8)}))
    out = _parse_image_data_section(cursor, h, w)
    assert (out[..., 3] == 255).all()


def test_parse_image_data_section_rejects_unknown_compression():
    cursor = _Cursor(struct.pack(">H", 99))
    with pytest.raises(ValueError, match="unsupported composite compression"):
        _parse_image_data_section(cursor, 2, 2)


def test_parse_image_data_section_returns_blank_when_cursor_exhausted():
    cursor = _Cursor(b"")
    out = _parse_image_data_section(cursor, 4, 5)
    assert out.shape == (4, 5, 4)
    assert (out == 0).all()


def _packbits_encode(plane: np.ndarray) -> tuple[list[int], bytes]:
    """Encode ``plane`` (HxW uint8) row-by-row using a literal-only
    PackBits stream — minimal but valid input for ``_packbits_decode``."""
    h, w = plane.shape
    row_lengths: list[int] = []
    body = bytearray()
    for row in range(h):
        # literal run header: w-1 (n in [0,127] means "next n+1 bytes literal")
        body.append(w - 1)
        body.extend(plane[row].tobytes())
        row_lengths.append(1 + w)
    return row_lengths, bytes(body)


def test_parse_image_data_section_decodes_rle_compression():
    h, w = 2, 4
    planes = {
        0: np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.uint8),
        1: np.array([[9, 10, 11, 12], [13, 14, 15, 16]], dtype=np.uint8),
        2: np.array([[17, 18, 19, 20], [21, 22, 23, 24]], dtype=np.uint8),
        -1: np.full((h, w), 200, dtype=np.uint8),
    }
    payload = bytearray(struct.pack(">H", _COMPRESSION_RLE))
    all_row_lengths: list[int] = []
    bodies = bytearray()
    for ch_id in (0, 1, 2, -1):
        rl, body = _packbits_encode(planes[ch_id])
        all_row_lengths.extend(rl)
        bodies.extend(body)
    payload.extend(struct.pack(f">{len(all_row_lengths)}H", *all_row_lengths))
    payload.extend(bodies)

    cursor = _Cursor(bytes(payload))
    out = _parse_image_data_section(cursor, h, w)

    assert np.array_equal(out[..., 0], planes[0])
    assert np.array_equal(out[..., 1], planes[1])
    assert np.array_equal(out[..., 2], planes[2])
    assert np.array_equal(out[..., 3], planes[-1])
