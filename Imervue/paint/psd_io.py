"""Photoshop ``.psd`` import / export — interop subset.

Supports a defined subset of the PSD format that round-trips
PaintDocuments cleanly:

* 8-bit RGBA, color mode RGB (3), single resolution
* Flat layer stack with names, opacity, visibility, blend mode
* Raw uncompressed channel data on write; raw + PackBits RLE on read
  (PackBits is the most common compression in PSDs from Photoshop /
  MediBang / Procreate, so reads from those tools work)
* Composite image rebuilt on save and stored in the trailing image
  data section so non-layered viewers can still display the file

Out of scope for this commit (10a): layer groups (no section dividers
in the writer or parser yet), layer masks, layer effects, smart
objects, vector layers, type layers, image resources, ICC profiles.
Layer groups + Unicode names + RLE write are coming in 10b.

The writer chooses raw compression so the byte layout is fully
deterministic — every test that asserts on file content stays
stable across numpy / Python versions. RLE decoding is included on
the read path so PSDs from other apps still load.

Format reference: ``Adobe Photoshop File Formats Specification``,
section "Document file format" (the canonical PDF / HTML).
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from Imervue.paint.compositing import LAYER_BLEND_MODES
from Imervue.paint.document import Layer, PaintDocument

PSD_SIGNATURE = b"8BPS"
PSD_VERSION = 1
PSD_DEPTH_8BIT = 8
PSD_COLOR_MODE_RGB = 3
PSD_CHANNELS_RGBA = 4

# Channel ids per Photoshop spec: 0..2 = R/G/B, -1 = transparency mask.
CHANNEL_ORDER = (0, 1, 2, -1)
CHANNEL_NAMES = {0: "R", 1: "G", 2: "B", -1: "A"}

# Blend-mode keys per Photoshop spec (4 ASCII bytes).
_BLEND_MODE_TO_PSD = {
    "normal": b"norm",
    "multiply": b"mul ",
    "screen": b"scrn",
    "overlay": b"over",
    "darken": b"dark",
    "lighten": b"lite",
    "color_dodge": b"div ",
    "color_burn": b"idiv",
    "soft_light": b"sLit",
    "hard_light": b"hLit",
    "linear_burn": b"lbrn",
    "linear_dodge": b"lddg",
}
_PSD_TO_BLEND_MODE = {v: k for k, v in _BLEND_MODE_TO_PSD.items()}

# Layer-record flags (bit values, big-endian byte).
_LAYER_FLAG_TRANSPARENCY_PROTECTED = 0x01
_LAYER_FLAG_HIDDEN = 0x02
# Bit 3 must be 1 to indicate Photoshop 5.0+ flag layout (otherwise bit
# 4 is reserved). We always set it on write.
_LAYER_FLAG_PHOTOSHOP_5_PLUS = 0x08

# Compression types in channel / image data sections.
_COMPRESSION_RAW = 0
_COMPRESSION_RLE = 1


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def save_psd(document: PaintDocument, path: str | Path) -> None:
    """Write ``document`` to a Photoshop ``.psd`` file (subset)."""
    layers = document.layers()
    if not layers:
        raise ValueError("cannot save an empty PaintDocument as PSD")
    shape = document.shape
    if shape is None:
        raise ValueError("cannot save document with unknown shape")
    h, w = shape

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as fh:
        fh.write(_pack_header(h, w))
        fh.write(_pack_color_mode_section())
        fh.write(_pack_image_resources_section())
        fh.write(_pack_layer_and_mask_section(layers, h, w))
        fh.write(_pack_image_data_section(document, h, w))


def _pack_header(h: int, w: int) -> bytes:
    return struct.pack(
        ">4sH6xHIIHH",
        PSD_SIGNATURE, PSD_VERSION,
        PSD_CHANNELS_RGBA, h, w, PSD_DEPTH_8BIT, PSD_COLOR_MODE_RGB,
    )


def _pack_color_mode_section() -> bytes:
    # Empty for RGB color mode — only Indexed / Duotone use this section.
    return struct.pack(">I", 0)


def _pack_image_resources_section() -> bytes:
    # No resources written (no ICC, no resolution block, no thumbnail).
    return struct.pack(">I", 0)


def _pack_layer_and_mask_section(layers: list[Layer], h: int, w: int) -> bytes:
    # Build per-layer records + channel-data blob in one pass so the
    # channel-info "data length" entries inside the records line up
    # exactly with what we write afterwards.
    records = bytearray()
    channel_blob = bytearray()
    for layer in layers:
        record, channel_bytes = _pack_one_layer(layer, h, w)
        records.extend(record)
        channel_blob.extend(channel_bytes)

    # Layer info: u16 layer count, then concatenated records, then the
    # channel-data blob. Pad to even length per spec.
    layer_count_word = struct.pack(">H", len(layers))
    layer_info_payload = layer_count_word + bytes(records) + bytes(channel_blob)
    if len(layer_info_payload) % 2:
        layer_info_payload += b"\x00"
    layer_info_section = struct.pack(">I", len(layer_info_payload)) + layer_info_payload

    # Global layer mask info — empty.
    global_mask = struct.pack(">I", 0)

    block = layer_info_section + global_mask
    return struct.pack(">I", len(block)) + block


def _pack_one_layer(layer: Layer, h: int, w: int) -> tuple[bytes, bytes]:
    """Return (layer record bytes, concatenated channel data)."""
    if layer.image.shape != (h, w, 4):
        raise ValueError(
            f"layer {layer.name!r} shape {layer.image.shape} does not match "
            f"document {(h, w, 4)}",
        )
    blend_key = _BLEND_MODE_TO_PSD.get(
        layer.blend_mode, _BLEND_MODE_TO_PSD["normal"],
    )
    opacity = max(0, min(255, int(round(layer.opacity * 255))))
    flags = _LAYER_FLAG_PHOTOSHOP_5_PLUS
    if not layer.visible:
        flags |= _LAYER_FLAG_HIDDEN
    if layer.lock_alpha:
        flags |= _LAYER_FLAG_TRANSPARENCY_PROTECTED

    # Channel data is always 2 bytes (compression) + h*w (raw plane)
    # under the writer's raw scheme.
    raw_channel_size = 2 + h * w
    channel_info = b"".join(
        struct.pack(">hI", ch_id, raw_channel_size) for ch_id in CHANNEL_ORDER
    )
    name_bytes = _pack_pascal_padded(layer.name, pad_to=4)
    extra = (
        struct.pack(">I", 0)        # layer mask data length
        + struct.pack(">I", 0)      # blending ranges length
        + name_bytes
    )
    extra_with_length = struct.pack(">I", len(extra)) + extra

    record = (
        struct.pack(">iiiiH", 0, 0, h, w, PSD_CHANNELS_RGBA)
        + channel_info
        + b"8BIM"
        + blend_key
        + struct.pack(">BBBB", opacity, 0, flags, 0)
        + extra_with_length
    )

    # Channel data — raw planar in (R, G, B, A) order.
    channel_data = bytearray()
    for ch_id in CHANNEL_ORDER:
        plane = _channel_plane(layer.image, ch_id)
        channel_data.extend(struct.pack(">H", _COMPRESSION_RAW))
        channel_data.extend(plane.tobytes())
    return record, bytes(channel_data)


def _pack_image_data_section(
    document: PaintDocument, h: int, w: int,
) -> bytes:
    """Pack the trailing composite image data section.

    Non-layer-aware viewers (e.g. ``file`` previews, web galleries)
    show this composite. Stored as raw planar uint8 RGBA so the bytes
    are deterministic.
    """
    composite = document.composite()
    if composite is None:
        composite = np.zeros((h, w, 4), dtype=np.uint8)
    out = bytearray(struct.pack(">H", _COMPRESSION_RAW))
    for ch_id in CHANNEL_ORDER:
        out.extend(_channel_plane(composite, ch_id).tobytes())
    return bytes(out)


def _channel_plane(image: np.ndarray, channel_id: int) -> np.ndarray:
    """Map PSD channel ID → numpy slice on an HxWx4 RGBA array."""
    if channel_id == -1:
        return np.ascontiguousarray(image[..., 3])
    return np.ascontiguousarray(image[..., channel_id])


def _pack_pascal_padded(name: str, *, pad_to: int) -> bytes:
    """Pascal string (1-byte length + bytes) padded so total is a
    multiple of ``pad_to``."""
    encoded = name.encode("latin-1", errors="replace")
    if len(encoded) > 255:
        encoded = encoded[:255]
    payload = bytes([len(encoded)]) + encoded
    pad_len = (-len(payload)) % pad_to
    return payload + b"\x00" * pad_len


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_psd(path: str | Path) -> PaintDocument:
    """Read a PSD file and return a :class:`PaintDocument`.

    Supports flat 8-bit RGB[A] PSDs with raw or PackBits-RLE channel
    compression. Layer groups are flattened (section dividers are
    skipped). Anything outside the documented subset raises
    ``ValueError`` with a specific message rather than producing a
    half-loaded document.
    """
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"PSD file {target!s} does not exist")
    with open(target, "rb") as fh:
        raw = fh.read()
    cursor = _Cursor(raw)
    h, w = _parse_header(cursor)
    _skip_color_mode_section(cursor)
    _skip_image_resources_section(cursor)
    layers = _parse_layer_and_mask_section(cursor, h, w)
    document = PaintDocument()
    if not layers:
        # No layers — treat the trailing composite as a single
        # background layer so the user still gets pixels back.
        composite = _parse_image_data_section(cursor, h, w)
        document.load_image(composite)
        return document
    # Discard the trailing composite — we have the layer pixels.
    document.replace_state(layers=layers, active_index=len(layers) - 1)
    return document


def _parse_header(cursor) -> tuple[int, int]:
    sig = cursor.read(4)
    if sig != PSD_SIGNATURE:
        raise ValueError(f"not a PSD file: signature {sig!r}")
    version = cursor.read_u16()
    if version != PSD_VERSION:
        raise ValueError(f"unsupported PSD version {version}")
    cursor.skip(6)   # reserved
    channels = cursor.read_u16()
    if not 1 <= channels <= 56:
        raise ValueError(f"PSD channel count {channels} out of range")
    h = cursor.read_u32()
    w = cursor.read_u32()
    depth = cursor.read_u16()
    if depth != PSD_DEPTH_8BIT:
        raise ValueError(f"unsupported PSD depth {depth}; expected 8")
    color_mode = cursor.read_u16()
    if color_mode != PSD_COLOR_MODE_RGB:
        raise ValueError(
            f"unsupported PSD color mode {color_mode}; expected RGB (3)",
        )
    return h, w


def _skip_color_mode_section(cursor) -> None:
    length = cursor.read_u32()
    cursor.skip(length)


def _skip_image_resources_section(cursor) -> None:
    length = cursor.read_u32()
    cursor.skip(length)


def _parse_layer_and_mask_section(cursor, h: int, w: int) -> list[Layer]:
    section_length = cursor.read_u32()
    if section_length == 0:
        return []
    section_end = cursor.pos + section_length
    layer_info_length = cursor.read_u32()
    if layer_info_length == 0:
        cursor.seek(section_end)
        return []
    layer_info_end = cursor.pos + layer_info_length

    layer_count_signed = cursor.read_i16()
    # Negative layer count means the first alpha channel of the merged
    # image holds transparency information for the base layer — for our
    # subset we just take the absolute count.
    layer_count = abs(layer_count_signed)

    records: list[dict] = []
    for _ in range(layer_count):
        records.append(_parse_layer_record(cursor))

    layers: list[Layer] = []
    for record in records:
        layer = _read_layer_channel_data(cursor, record, h, w)
        if layer is not None:
            layers.append(layer)

    cursor.seek(layer_info_end)
    cursor.seek(section_end)
    return layers


def _parse_layer_record(cursor) -> dict:
    top = cursor.read_i32()
    left = cursor.read_i32()
    bottom = cursor.read_i32()
    right = cursor.read_i32()
    n_channels = cursor.read_u16()
    channels: list[tuple[int, int]] = []
    for _ in range(n_channels):
        ch_id = cursor.read_i16()
        ch_size = cursor.read_u32()
        channels.append((ch_id, ch_size))
    blend_sig = cursor.read(4)
    if blend_sig != b"8BIM":
        raise ValueError(f"layer record signature mismatch: {blend_sig!r}")
    blend_key = bytes(cursor.read(4))
    opacity = cursor.read_u8()
    cursor.read_u8()   # clipping
    flags = cursor.read_u8()
    cursor.read_u8()   # filler
    extra_length = cursor.read_u32()
    extra_start = cursor.pos
    mask_data_length = cursor.read_u32()
    cursor.skip(mask_data_length)
    blending_ranges_length = cursor.read_u32()
    cursor.skip(blending_ranges_length)
    name = _read_pascal_padded(cursor, pad_to=4)
    cursor.seek(extra_start + extra_length)
    return {
        "bounds": (top, left, bottom, right),
        "channels": channels,
        "blend_key": blend_key,
        "opacity": opacity,
        "flags": flags,
        "name": name,
    }


def _read_layer_channel_data(
    cursor, record: dict, h: int, w: int,
) -> Layer | None:
    """Read one layer's channels and produce a Layer.

    Returns ``None`` when the record is empty (zero-sized bounds, e.g.
    a section divider — not currently emitted by our writer but
    tolerated when reading PSDs from other apps).
    """
    top, left, bottom, right = record["bounds"]
    layer_h = max(0, bottom - top)
    layer_w = max(0, right - left)

    channels_raw: dict[int, np.ndarray] = {}
    for ch_id, ch_size in record["channels"]:
        ch_end = cursor.pos + ch_size
        if layer_h > 0 and layer_w > 0:
            compression = cursor.read_u16()
            if compression == _COMPRESSION_RAW:
                channels_raw[ch_id] = np.frombuffer(
                    cursor.read(layer_h * layer_w),
                    dtype=np.uint8,
                ).reshape((layer_h, layer_w))
            elif compression == _COMPRESSION_RLE:
                row_lengths = struct.unpack(
                    f">{layer_h}H", cursor.read(layer_h * 2),
                )
                planes: list[np.ndarray] = []
                for row_len in row_lengths:
                    raw = cursor.read(row_len)
                    planes.append(_packbits_decode(raw, layer_w))
                channels_raw[ch_id] = np.stack(planes, axis=0)
            else:
                raise ValueError(
                    f"unsupported PSD compression {compression}",
                )
        cursor.seek(ch_end)

    if layer_h == 0 or layer_w == 0:
        return None

    # Build full-canvas RGBA image — start fully transparent black,
    # then paste the layer at (top, left).
    image = np.zeros((h, w, 4), dtype=np.uint8)
    if 0 in channels_raw:
        image[top:bottom, left:right, 0] = channels_raw[0]
    if 1 in channels_raw:
        image[top:bottom, left:right, 1] = channels_raw[1]
    if 2 in channels_raw:
        image[top:bottom, left:right, 2] = channels_raw[2]
    # No alpha channel — fully opaque inside the bounds.
    image[top:bottom, left:right, 3] = channels_raw.get(-1, 255)

    blend_mode = _PSD_TO_BLEND_MODE.get(
        record["blend_key"], "normal",
    )
    if blend_mode not in LAYER_BLEND_MODES:
        blend_mode = "normal"
    flags = record["flags"]
    visible = not bool(flags & _LAYER_FLAG_HIDDEN)
    lock_alpha = bool(flags & _LAYER_FLAG_TRANSPARENCY_PROTECTED)
    return Layer(
        name=record["name"],
        image=image,
        opacity=record["opacity"] / 255.0,
        blend_mode=blend_mode,
        visible=visible,
        lock_alpha=lock_alpha,
    )


def _parse_image_data_section(cursor, h: int, w: int) -> np.ndarray:
    """Parse the trailing composite image data and return HxWx4 RGBA."""
    if cursor.pos >= len(cursor.buf):
        return np.zeros((h, w, 4), dtype=np.uint8)
    compression = cursor.read_u16()
    image = np.zeros((h, w, 4), dtype=np.uint8)
    if compression == _COMPRESSION_RAW:
        for ch_id in CHANNEL_ORDER:
            plane_bytes = cursor.read(h * w)
            plane = np.frombuffer(plane_bytes, dtype=np.uint8).reshape((h, w))
            if ch_id == -1:
                image[..., 3] = plane
            else:
                image[..., ch_id] = plane
    elif compression == _COMPRESSION_RLE:
        # Total channels in composite = 4 (RGBA) — read row-length tables
        # for all channels first, then the packed data.
        total_rows = h * PSD_CHANNELS_RGBA
        row_lengths = struct.unpack(
            f">{total_rows}H", cursor.read(total_rows * 2),
        )
        for ch_pos, ch_id in enumerate(CHANNEL_ORDER):
            plane = np.zeros((h, w), dtype=np.uint8)
            for row in range(h):
                row_len = row_lengths[ch_pos * h + row]
                plane[row] = _packbits_decode(cursor.read(row_len), w)
            if ch_id == -1:
                image[..., 3] = plane
            else:
                image[..., ch_id] = plane
    else:
        raise ValueError(f"unsupported composite compression {compression}")
    if not image[..., 3].any():
        # No alpha was stored — fall back to fully opaque so the pixels
        # actually render.
        image[..., 3] = 255
    return image


# ---------------------------------------------------------------------------
# PackBits RLE decode
# ---------------------------------------------------------------------------


def _packbits_decode(raw: bytes, expected_length: int) -> np.ndarray:
    """Decode one PackBits RLE row into a uint8 ndarray.

    PackBits convention (Apple / TIFF / PSD):

    * n in [0, 127]   — copy next ``n + 1`` bytes literally
    * n in [-127, -1] — repeat next byte ``-n + 1`` times
    * n == -128       — no-op (skipped)
    """
    out = bytearray()
    i = 0
    raw_len = len(raw)
    while i < raw_len:
        header = raw[i]
        i += 1
        if header < 128:
            run_len = header + 1
            out.extend(raw[i:i + run_len])
            i += run_len
        elif header == 128:
            continue
        else:
            run_len = 257 - header
            if i >= raw_len:
                break
            out.extend(bytes([raw[i]]) * run_len)
            i += 1
    if len(out) != expected_length:
        # Tolerate a slightly-short row by zero-padding rather than
        # raising — some encoders pad differently.
        if len(out) < expected_length:
            out.extend(b"\x00" * (expected_length - len(out)))
        else:
            del out[expected_length:]
    return np.frombuffer(bytes(out), dtype=np.uint8)


def _read_pascal_padded(cursor, *, pad_to: int) -> str:
    length = cursor.read_u8()
    name_bytes = cursor.read(length)
    total = 1 + length
    pad = (-total) % pad_to
    cursor.skip(pad)
    return name_bytes.decode("latin-1", errors="replace")


# ---------------------------------------------------------------------------
# Cursor helper
# ---------------------------------------------------------------------------


class _Cursor:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0

    def read(self, n: int) -> bytes:
        if self.pos + n > len(self.buf):
            raise ValueError(
                f"PSD truncated: tried to read {n} bytes at offset {self.pos} "
                f"of {len(self.buf)}",
            )
        out = self.buf[self.pos:self.pos + n]
        self.pos += n
        return out

    def skip(self, n: int) -> None:
        self.pos = min(self.pos + max(0, int(n)), len(self.buf))

    def seek(self, pos: int) -> None:
        self.pos = max(0, min(int(pos), len(self.buf)))

    def read_u8(self) -> int:
        return self.read(1)[0]

    def read_u16(self) -> int:
        return struct.unpack(">H", self.read(2))[0]

    def read_i16(self) -> int:
        return struct.unpack(">h", self.read(2))[0]

    def read_u32(self) -> int:
        return struct.unpack(">I", self.read(4))[0]

    def read_i32(self) -> int:
        return struct.unpack(">i", self.read(4))[0]
