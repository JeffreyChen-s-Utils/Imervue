"""Contract tests pinning the PSD writer's bytes and the reader's behaviour.

The writer's output is a file format, so representative documents are pinned
by the SHA-256 of the exact bytes written. The reader is exercised with
hand-built PSDs covering the record shapes the round-trip tests never produce
(legacy names, RLE layer channels, ``8B64`` / zero-padded additional info,
negative layer counts, corrupt group headers) and the exact error messages
raised on malformed input.
"""
from __future__ import annotations

import hashlib
import struct

import numpy as np
import pytest

from Imervue.paint.document import Layer, PaintDocument
from Imervue.paint.psd_io import (
    _pack_layer_and_mask_section,
    load_psd,
    save_psd,
)

_NORMAL = b"norm"


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gradient(h: int, w: int, seed: int) -> np.ndarray:
    idx = np.arange(h * w * 4, dtype=np.uint32).reshape((h, w, 4))
    return ((idx * (seed * 2 + 1) + seed * 17) % 251).astype(np.uint8)


def _flat_doc() -> PaintDocument:
    doc = PaintDocument()
    doc.load_image(_gradient(5, 7, 1))
    top = doc.add_layer(name="Ünï — 草稿")          # odd UTF-16 length + latin-1 loss
    top.image[...] = _gradient(5, 7, 2)
    top.opacity = 0.333
    top.blend_mode = "screen"
    top.visible = False
    top.lock_alpha = True
    long_layer = doc.add_layer(name="x" * 300)      # Pascal name truncated to 255
    long_layer.image[...] = _gradient(5, 7, 3)
    long_layer.opacity = 1.0
    return doc


def _grouped_doc() -> PaintDocument:
    doc = PaintDocument()
    doc.load_image(_gradient(4, 3, 4))
    for n in range(4):
        layer = doc.add_layer(name=f"L{n}")
        layer.image[...] = _gradient(4, 3, 5 + n)
    doc.create_group("Open", opacity=0.5, blend_mode="multiply")
    doc.create_group("Closed", visible=False, expanded=False)
    doc.set_layer_group(index=1, group="Open")
    doc.set_layer_group(index=2, group="Open")
    doc.set_layer_group(index=3, group="Closed")
    return doc


# ---------------------------------------------------------------------------
# Writer — exact bytes
# ---------------------------------------------------------------------------


def test_flat_document_bytes_are_pinned(tmp_path):
    path = tmp_path / "flat.psd"
    save_psd(_flat_doc(), path)
    assert path.stat().st_size == 1796
    assert _sha(path) == (
        "c5cb5b4f0f90467431e1b0d948ff96284dcb83770c85bb01da8abcbe2395c6f1"
    )


def test_grouped_document_bytes_are_pinned(tmp_path):
    path = tmp_path / "groups.psd"
    save_psd(_grouped_doc(), path)
    assert _sha(path) == (
        "583b4008b78e58fc7f3ac60239ce07ded6bba92a87fb11bcb74084173e3286a2"
    )


def test_layer_and_mask_section_bytes_without_group_objects():
    """A layer tagged with a group the dict doesn't know gets a default header."""
    layer = Layer(name="a", image=np.full((1, 2, 4), 9, dtype=np.uint8))
    layer.group = "ghost"
    layer.blend_mode = "not-a-psd-mode"           # falls back to ``norm``
    layer.opacity = 3.0                           # clamped to 255
    out = _pack_layer_and_mask_section([layer], 1, 2)
    assert hashlib.sha256(out).hexdigest() == (
        "99a887fcb2432f9861892443a0b867eb724bc83953269b55d00f0913a1821b65")
    assert out.count(b"8BIMnorm") == 3            # end divider, layer, header
    assert b"\xff\x00\x08\x00" in out             # opacity 255, visible flags


def test_mismatched_layer_shape_raises_with_names():
    layer = Layer(name="bad", image=np.zeros((2, 2, 4), dtype=np.uint8))
    with pytest.raises(ValueError, match=r"^layer 'bad' shape \(2, 2, 4\) does not "
                                         r"match document \(3, 2, 4\)$"):
        _pack_layer_and_mask_section([layer], 3, 2)


def test_save_document_without_shape_raises(tmp_path):
    doc = PaintDocument()
    doc.layers = lambda: [object()]
    with pytest.raises(ValueError, match="cannot save document with unknown shape"):
        save_psd(doc, tmp_path / "x.psd")


# ---------------------------------------------------------------------------
# Writer → reader round-trip of everything the writer encodes
# ---------------------------------------------------------------------------


def test_round_trip_flat_document(tmp_path):
    src = _flat_doc()
    path = tmp_path / "flat.psd"
    save_psd(src, path)
    loaded = load_psd(path)
    assert [la.name for la in loaded.layers()] == [la.name for la in src.layers()]
    for got, want in zip(loaded.layers(), src.layers(), strict=True):
        assert np.array_equal(got.image, want.image)
        assert got.blend_mode == want.blend_mode
        assert got.visible == want.visible
        assert got.lock_alpha == want.lock_alpha
        assert got.opacity == pytest.approx(round(want.opacity * 255) / 255)
    assert loaded.active_layer() is loaded.layers()[-1]


def test_round_trip_grouped_document(tmp_path):
    path = tmp_path / "groups.psd"
    save_psd(_grouped_doc(), path)
    loaded = load_psd(path)
    assert [(la.name, la.group) for la in loaded.layers()] == [
        ("Background", None), ("L0", "Open"), ("L1", "Open"),
        ("L2", "Closed"), ("L3", None),
    ]
    open_grp, closed = loaded.group("Open"), loaded.group("Closed")
    assert (open_grp.visible, open_grp.blend_mode, open_grp.expanded) == (
        True, "multiply", True)
    assert open_grp.opacity == pytest.approx(128 / 255)
    assert (closed.visible, closed.blend_mode, closed.expanded) == (
        False, "pass_through", False)


# ---------------------------------------------------------------------------
# Reader — hand-built PSDs
# ---------------------------------------------------------------------------


def _header(h, w, *, channels=4, version=1, depth=8, mode=3, sig=b"8BPS"):
    return struct.pack(">4sH6xHIIHH", sig, version, channels, h, w, depth, mode)


def _block(key: bytes, payload: bytes, sig: bytes = b"8BIM") -> bytes:
    return sig + key + struct.pack(">I", len(payload)) + payload


def _record(bounds, channels, *, name=b"", blend=_NORMAL, opacity=255, flags=8,
            tail=b""):
    pascal = bytes([len(name)]) + name
    pascal += b"\x00" * ((-len(pascal)) % 4)
    extra = struct.pack(">II", 0, 0) + pascal + tail
    out = struct.pack(">iiiiH", *bounds, len(channels))
    out += b"".join(struct.pack(">hI", cid, len(data)) for cid, data in channels)
    out += b"8BIM" + blend + struct.pack(">BBBB", opacity, 0, flags, 0)
    return out + struct.pack(">I", len(extra)) + extra


def _lsct(divider_type: int) -> bytes:
    return _block(b"lsct", struct.pack(">I", divider_type))


def _psd(h, w, records, channel_data=b"", *, count=None, composite=b""):
    n = len(records) if count is None else count
    info = struct.pack(">h", n) + b"".join(records) + channel_data
    section = struct.pack(">I", len(info)) + info + struct.pack(">I", 0)
    return (_header(h, w) + struct.pack(">II", 0, 0)
            + struct.pack(">I", len(section)) + section + composite)


def _raw(plane: bytes) -> bytes:
    return struct.pack(">H", 0) + plane


def _load(tmp_path, data: bytes) -> PaintDocument:
    path = tmp_path / "in.psd"
    path.write_bytes(data)
    return load_psd(path)


def test_legacy_name_unknown_blend_and_missing_alpha(tmp_path):
    chans = [(0, _raw(b"\x01\x02")), (1, _raw(b"\x03\x04")), (2, _raw(b"\x05\x06"))]
    rec = _record((0, 0, 1, 2), chans, name=b"Old", blend=b"zzzz", opacity=51,
                  flags=8 | 2 | 1)
    doc = _load(tmp_path, _psd(1, 2, [rec], b"".join(d for _, d in chans)))
    (layer,) = doc.layers()
    assert layer.name == "Old"
    assert layer.blend_mode == "normal"
    assert layer.opacity == pytest.approx(0.2)
    assert (layer.visible, layer.lock_alpha) == (False, True)
    assert layer.image.tolist() == [[[1, 3, 5, 255], [2, 4, 6, 255]]]


def test_rle_layer_channel_and_negative_count(tmp_path):
    # Row 0: repeat 7 three times; row 1: literal 1,2 then -128 no-op (short → pad).
    rle = struct.pack(">HHH", 1, 2, 4) + b"\xfe\x07" + b"\x01\x01\x02\x80"
    chans = [(-1, rle)]
    rec = _record((0, 0, 2, 3), chans, name=b"R")
    doc = _load(tmp_path, _psd(2, 3, [rec], rle, count=-1))
    (layer,) = doc.layers()
    assert layer.image[..., 3].tolist() == [[7, 7, 7], [1, 2, 0]]
    assert not layer.image[..., :3].any()


def test_additional_info_variants(tmp_path):
    luni = struct.pack(">I", 1) + "Ω".encode("utf-16-be") + b"\x00"   # odd → pad
    tail = (_block(b"xxxx", b"\x09") + b"\x00"                           # odd skip
            + _block(b"luni", luni, sig=b"8B64")
            + b"\x00" * 12)                                              # zero pad
    chans = [(-1, _raw(b"\x10"))]
    rec = _record((0, 0, 1, 1), chans, name=b"legacy", tail=tail)
    doc = _load(tmp_path, _psd(1, 1, [rec], chans[0][1]))
    assert doc.layers()[0].name == "Ω"


def test_short_luni_block_is_ignored(tmp_path):
    chans = [(-1, _raw(b"\x10"))]
    rec = _record((0, 0, 1, 1), chans, name=b"keep",
                  tail=_block(b"luni", b"\x00\x00") + _block(b"lsct", b"\x00"))
    doc = _load(tmp_path, _psd(1, 1, [rec], chans[0][1]))
    assert doc.layers()[0].name == "keep"


def test_corrupt_group_header_is_skipped_but_members_are_tagged(tmp_path):
    chans = [(-1, _raw(b"\x10"))]
    records = [
        _record((0, 0, 0, 0), [], tail=_lsct(3)),
        _record((0, 0, 1, 1), chans, name=b"m"),
        _record((0, 0, 0, 0), [], name=b"  ", tail=_lsct(2)),   # blank name
        _record((0, 0, 0, 0), [], name=b"G", tail=_lsct(1)),    # depth already 0
    ]
    doc = _load(tmp_path, _psd(1, 1, records, chans[0][1]))
    assert [(la.name, la.group) for la in doc.layers()] == [("m", "  ")]
    assert [g.name for g in doc.groups()] == ["G"]


def test_layer_entirely_off_canvas_is_blank(tmp_path):
    chans = [(-1, _raw(b"\x10"))]
    rec = _record((5, 5, 6, 6), chans, name=b"off")
    doc = _load(tmp_path, _psd(2, 2, [rec], chans[0][1]))
    assert not doc.layers()[0].image.any()


def test_empty_layer_section_falls_back_to_composite(tmp_path):
    comp = _raw(b"\x01\x02" + b"\x03\x04" + b"\x05\x06" + b"\x00\x00")
    data = _header(1, 2) + struct.pack(">III", 0, 0, 0) + comp
    doc = _load(tmp_path, data)
    (layer,) = doc.layers()
    assert layer.image.tolist() == [[[1, 3, 5, 255], [2, 4, 6, 255]]]


def test_zero_layer_info_falls_back_to_composite(tmp_path):
    comp = _raw(b"\x01" + b"\x02" + b"\x03" + b"\x04")
    section = struct.pack(">II", 0, 0)
    data = (_header(1, 1) + struct.pack(">II", 0, 0)
            + struct.pack(">I", len(section)) + section + comp)
    doc = _load(tmp_path, data)
    assert doc.layers()[0].image.tolist() == [[[1, 2, 3, 4]]]


@pytest.mark.parametrize(("data", "message"), [
    (_header(1, 1, version=2), "unsupported PSD version 2"),
    (_header(1, 1, channels=0), "PSD channel count 0 out of range"),
    (_header(1, 1, channels=57), "PSD channel count 57 out of range"),
    (_header(1, 1, depth=16), "unsupported PSD depth 16; expected 8"),
    (_header(1, 1, mode=1), "unsupported PSD color mode 1; expected RGB (3)"),
    (b"8BPS\x00", "PSD truncated: tried to read 2 bytes at offset 4 of 5"),
    (_header(1, 1, sig=b"8BPB"), "not a PSD file: signature b'8BPB'"),
])
def test_header_errors(tmp_path, data, message):
    with pytest.raises(ValueError) as info:
        _load(tmp_path, data)
    assert str(info.value) == message


def test_layer_signature_mismatch_message(tmp_path):
    rec = bytearray(_record((0, 0, 1, 1), [], name=b"a"))
    rec[18:22] = b"XXXX"
    with pytest.raises(ValueError) as info:
        _load(tmp_path, _psd(1, 1, [bytes(rec)]))
    assert str(info.value) == "layer record signature mismatch: b'XXXX'"


def test_unsupported_layer_compression_message(tmp_path):
    data = struct.pack(">H", 2) + b"\x00"
    rec = _record((0, 0, 1, 1), [(0, data)], name=b"a")
    with pytest.raises(ValueError) as info:
        _load(tmp_path, _psd(1, 1, [rec], data))
    assert str(info.value) == "unsupported PSD compression 2"


def test_composite_unknown_compression_message(tmp_path):
    data = _header(1, 1) + struct.pack(">III", 0, 0, 0) + struct.pack(">H", 5)
    with pytest.raises(ValueError) as info:
        _load(tmp_path, data)
    assert str(info.value) == "unsupported composite compression 5"


def test_load_missing_file_message(tmp_path):
    target = tmp_path / "nope.psd"
    with pytest.raises(FileNotFoundError) as info:
        load_psd(target)
    assert str(info.value) == f"PSD file {target!s} does not exist"
