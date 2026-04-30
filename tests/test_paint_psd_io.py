"""Tests for the PSD import / export subset."""
from __future__ import annotations

import struct

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.psd_io import (
    _packbits_decode,
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
