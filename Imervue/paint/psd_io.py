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

import contextlib
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from Imervue.paint.compositing import LAYER_BLEND_MODES
from Imervue.paint.document import Layer, LayerGroup, PaintDocument

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

# Section-divider types — used by ``lsct`` to mark layer groups.
_SECTION_OTHER = 0
_SECTION_OPEN_GROUP = 1
_SECTION_CLOSED_GROUP = 2
_SECTION_END = 3
_SECTION_END_NAME = "</Layer group>"


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
        fh.write(_pack_layer_and_mask_section(
            layers, h, w, groups={g.name: g for g in document.groups()},
        ))
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


def _pack_layer_and_mask_section(
    layers: list[Layer], h: int, w: int,
    groups: dict[str, LayerGroup] | None = None,
) -> bytes:
    """Pack the layer + mask section.

    Group encoding follows the Photoshop convention (bottom-to-top):

    * a ``section divider end`` (lsct type 3) appears immediately
      before the first member layer of a group;
    * member layers follow in their natural bottom-to-top order;
    * a ``group header`` (lsct type 1 or 2) appears immediately after
      the last member, carrying the group's name + visibility +
      opacity.

    Adjacent layers in different groups round-trip via consecutive
    end / header pairs.
    """
    groups = groups or {}
    records = bytearray()
    channel_blob = bytearray()
    record_count = 0

    def _emit(record_bytes: bytes, channel_bytes: bytes) -> None:
        nonlocal record_count
        records.extend(record_bytes)
        channel_blob.extend(channel_bytes)
        record_count += 1

    current_group: str | None = None
    for layer in layers:
        if layer.group != current_group:
            if current_group is not None:
                # Emit the closing group header for the group we're leaving.
                grp = groups.get(current_group)
                _emit(*_pack_group_header(current_group, grp))
            if layer.group is not None:
                # Open a new group at this position.
                _emit(*_pack_section_end())
            current_group = layer.group
        record, channel_bytes = _pack_one_layer(layer, h, w)
        _emit(record, channel_bytes)
    if current_group is not None:
        grp = groups.get(current_group)
        _emit(*_pack_group_header(current_group, grp))

    layer_count_word = struct.pack(">H", record_count)
    layer_info_payload = layer_count_word + bytes(records) + bytes(channel_blob)
    if len(layer_info_payload) % 2:
        layer_info_payload += b"\x00"
    layer_info_section = struct.pack(">I", len(layer_info_payload)) + layer_info_payload

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
        + _pack_additional_info_luni(layer.name)
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


def _pack_section_end() -> tuple[bytes, bytes]:
    """Pack a ``section divider end`` placeholder layer.

    These have empty bounds + zero channels but a well-known name and
    an ``lsct`` additional-info block of type 3. Photoshop reads them
    as "the bottom-most member of the group above starts here".
    """
    return _pack_section_layer(
        name=_SECTION_END_NAME, divider_type=_SECTION_END,
        visible=True, opacity=1.0, blend_mode="normal",
    )


def _pack_group_header(
    group_name: str, group: LayerGroup | None,
) -> tuple[bytes, bytes]:
    """Pack the ``group header`` layer that names a layer group.

    Carries the group's visibility / opacity / blend mode so a
    Photoshop user sees the same group state after a round-trip.
    """
    visible = True
    opacity = 1.0
    blend_mode = "normal"
    if group is not None:
        visible = bool(group.visible)
        opacity = float(group.opacity)
        if group.blend_mode != "pass_through":
            blend_mode = group.blend_mode
    divider_type = (
        _SECTION_OPEN_GROUP if (group is None or group.expanded)
        else _SECTION_CLOSED_GROUP
    )
    return _pack_section_layer(
        name=group_name, divider_type=divider_type,
        visible=visible, opacity=opacity, blend_mode=blend_mode,
    )


def _pack_section_layer(
    *, name: str, divider_type: int,
    visible: bool, opacity: float, blend_mode: str,
) -> tuple[bytes, bytes]:
    blend_key = _BLEND_MODE_TO_PSD.get(
        blend_mode, _BLEND_MODE_TO_PSD["normal"],
    )
    opacity_byte = max(0, min(255, int(round(opacity * 255))))
    flags = _LAYER_FLAG_PHOTOSHOP_5_PLUS
    if not visible:
        flags |= _LAYER_FLAG_HIDDEN
    # Empty layer — zero bounds, zero channels.
    bounds = struct.pack(">iiiiH", 0, 0, 0, 0, 0)
    name_bytes = _pack_pascal_padded(name, pad_to=4)
    extra = (
        struct.pack(">I", 0)        # layer mask data length
        + struct.pack(">I", 0)      # blending ranges length
        + name_bytes
        + _pack_additional_info_luni(name)
        + _pack_additional_info_lsct(divider_type)
    )
    record = (
        bounds
        + b"8BIM"
        + blend_key
        + struct.pack(">BBBB", opacity_byte, 0, flags, 0)
        + struct.pack(">I", len(extra))
        + extra
    )
    # No channel data for zero-channel layers.
    return record, b""


def _pack_additional_info_luni(name: str) -> bytes:
    """Pack a ``luni`` Unicode-name additional-info block.

    Layout: ``8BIM`` + ``luni`` + length(u32) + payload + 2-byte pad.
    Payload: u32 character count, then UTF-16-BE characters.
    Photoshop prefers ``luni`` over the legacy Pascal name when both
    are present.
    """
    chars = name
    payload = struct.pack(">I", len(chars)) + chars.encode("utf-16-be")
    if len(payload) % 2:
        payload += b"\x00"
    block = b"8BIM" + b"luni" + struct.pack(">I", len(payload)) + payload
    return block


def _pack_additional_info_lsct(divider_type: int) -> bytes:
    """Pack an ``lsct`` section-divider additional-info block."""
    payload = struct.pack(">I", int(divider_type))
    if len(payload) % 2:
        payload += b"\x00"
    return b"8BIM" + b"lsct" + struct.pack(">I", len(payload)) + payload


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
    layers, groups = _parse_layer_and_mask_section(cursor, h, w)
    document = PaintDocument()
    if not layers:
        # No layers — treat the trailing composite as a single
        # background layer so the user still gets pixels back.
        composite = _parse_image_data_section(cursor, h, w)
        document.load_image(composite)
        return document
    # Discard the trailing composite — we have the layer pixels.
    document.replace_state(
        layers=layers, active_index=len(layers) - 1, groups=groups,
    )
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


def _parse_layer_and_mask_section(
    cursor, h: int, w: int,
) -> tuple[list[Layer], dict[str, LayerGroup]]:
    section_length = cursor.read_u32()
    if section_length == 0:
        return [], {}
    section_end = cursor.pos + section_length
    layer_info_length = cursor.read_u32()
    if layer_info_length == 0:
        cursor.seek(section_end)
        return [], {}
    layer_info_end = cursor.pos + layer_info_length

    layer_count_signed = cursor.read_i16()
    # Negative layer count means the first alpha channel of the merged
    # image holds transparency information for the base layer — for our
    # subset we just take the absolute count.
    layer_count = abs(layer_count_signed)

    records: list[dict] = []
    for _ in range(layer_count):
        records.append(_parse_layer_record(cursor))

    # Walk records bottom-to-top, reading channel data, and assemble
    # groups via lsct section dividers. PSD encodes a group as:
    #   ┌── section divider end (lsct=3)
    #   │   member layers (regular records)
    #   └── group header (lsct=1 or 2, name = group name)
    layers: list[Layer] = []
    groups: dict[str, LayerGroup] = {}
    state = _GroupAssemblyState()
    for record in records:
        _consume_record(cursor, record, h, w, layers, groups, state)

    cursor.seek(layer_info_end)
    cursor.seek(section_end)
    return layers, groups


@dataclass
class _GroupAssemblyState:
    """Mutable bookkeeping while walking PSD layer records bottom→top."""

    pending_group_members: list[Layer] = field(default_factory=list)
    in_group_depth: int = 0


def _consume_record(
    cursor, record, h: int, w: int,
    layers: list[Layer],
    groups: dict[str, LayerGroup],
    state: _GroupAssemblyState,
) -> None:
    """Dispatch one PSD layer record to the section-divider /
    group-header / regular-layer handler. Pulled out of
    ``_parse_layer_and_mask_section`` so that function stays under the
    cognitive-complexity budget."""
    section_type = record.get("section_type")
    if section_type == _SECTION_END:
        # The next regular records belong to a group whose header
        # we'll see later. Consume the empty record's channel data
        # and bump the depth.
        _read_layer_channel_data(cursor, record, h, w)
        state.in_group_depth += 1
        return
    if section_type in (_SECTION_OPEN_GROUP, _SECTION_CLOSED_GROUP):
        _consume_group_header(cursor, record, h, w, groups, state)
        return
    layer = _read_layer_channel_data(cursor, record, h, w)
    if layer is None:
        return
    if state.in_group_depth > 0:
        state.pending_group_members.append(layer)
    layers.append(layer)


def _consume_group_header(
    cursor, record, h: int, w: int,
    groups: dict[str, LayerGroup],
    state: _GroupAssemblyState,
) -> None:
    """Materialise the LayerGroup for a section divider record and
    bind its pending member layers."""
    _read_layer_channel_data(cursor, record, h, w)
    group_name = record["name"]
    blend_mode = _PSD_TO_BLEND_MODE.get(record["blend_key"], "normal")
    grp_blend = blend_mode if blend_mode in LAYER_BLEND_MODES else "normal"
    # Skip a corrupt group (bad name / opacity) rather than fail
    # the whole load.
    with contextlib.suppress(ValueError):
        groups[group_name] = LayerGroup(
            name=group_name,
            visible=not bool(record["flags"] & _LAYER_FLAG_HIDDEN),
            opacity=record["opacity"] / 255.0,
            blend_mode=grp_blend if grp_blend != "normal" else "pass_through",
            expanded=record["section_type"] == _SECTION_OPEN_GROUP,
        )
    for member in state.pending_group_members:
        member.group = group_name
    state.pending_group_members = []
    state.in_group_depth = max(0, state.in_group_depth - 1)


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
    legacy_name = _read_pascal_padded(cursor, pad_to=4)
    additional = _parse_additional_info(
        cursor, end=extra_start + extra_length,
    )
    cursor.seek(extra_start + extra_length)
    return {
        "bounds": (top, left, bottom, right),
        "channels": channels,
        "blend_key": blend_key,
        "opacity": opacity,
        "flags": flags,
        # Prefer the Unicode name when present; legacy name is a
        # latin-1 fallback that loses high codepoints.
        "name": additional.get("luni", legacy_name),
        "section_type": additional.get("lsct"),
    }


def _parse_additional_info(cursor, *, end: int) -> dict:
    """Walk the additional-info blocks at the tail of a layer record's
    extra-data section. Recognised keys: ``luni`` (Unicode name),
    ``lsct`` (section divider type)."""
    out: dict = {}
    while cursor.pos + 12 <= end:
        sig = cursor.read(4)
        if sig not in (b"8BIM", b"8B64"):
            # Some encoders pad with zeros — back up so the outer
            # ``cursor.seek(end)`` skips cleanly.
            cursor.seek(cursor.pos - 4)
            break
        key = cursor.read(4)
        length = cursor.read_u32()
        block_start = cursor.pos
        _read_additional_info_block(cursor, key, length, out)
        cursor.seek(block_start + length)
        # Many additional-info payloads are padded to a 2-byte
        # boundary; account for it.
        if (cursor.pos - block_start) % 2:
            cursor.skip(1)
    return out


def _read_additional_info_block(cursor, key: bytes, length: int, out: dict) -> None:
    """Decode the payload of a single additional-info block in place."""
    if key == b"luni" and length >= 4:
        char_count = cursor.read_u32()
        chars_bytes = cursor.read(char_count * 2)
        out["luni"] = chars_bytes.decode("utf-16-be", errors="replace")
    elif key == b"lsct" and length >= 4:
        out["lsct"] = cursor.read_u32()


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

    channels_raw = _read_layer_channels(cursor, record["channels"], layer_h, layer_w)

    if layer_h == 0 or layer_w == 0:
        return None

    image = _assemble_layer_image(channels_raw, h, w, top, left, bottom, right)

    blend_mode = _PSD_TO_BLEND_MODE.get(record["blend_key"], "normal")
    if blend_mode not in LAYER_BLEND_MODES:
        blend_mode = "normal"
    flags = record["flags"]
    return Layer(
        name=record["name"],
        image=image,
        opacity=record["opacity"] / 255.0,
        blend_mode=blend_mode,
        visible=not bool(flags & _LAYER_FLAG_HIDDEN),
        lock_alpha=bool(flags & _LAYER_FLAG_TRANSPARENCY_PROTECTED),
    )


def _read_layer_channels(
    cursor, channels: list[tuple[int, int]], layer_h: int, layer_w: int,
) -> dict[int, np.ndarray]:
    """Read every channel plane for one layer record. Empty bounds are
    tolerated (section dividers ride the same record shape) — the
    cursor is advanced past each channel either way."""
    channels_raw: dict[int, np.ndarray] = {}
    for ch_id, ch_size in channels:
        ch_end = cursor.pos + ch_size
        if layer_h > 0 and layer_w > 0:
            channels_raw[ch_id] = _read_one_channel_plane(
                cursor, layer_h, layer_w,
            )
        cursor.seek(ch_end)
    return channels_raw


def _read_one_channel_plane(cursor, layer_h: int, layer_w: int) -> np.ndarray:
    """Decode a single channel plane (raw or PackBits RLE)."""
    compression = cursor.read_u16()
    if compression == _COMPRESSION_RAW:
        return np.frombuffer(
            cursor.read(layer_h * layer_w),
            dtype=np.uint8,
        ).reshape((layer_h, layer_w))
    if compression == _COMPRESSION_RLE:
        row_lengths = struct.unpack(
            f">{layer_h}H", cursor.read(layer_h * 2),
        )
        planes = [_packbits_decode(cursor.read(row_len), layer_w)
                  for row_len in row_lengths]
        return np.stack(planes, axis=0)
    raise ValueError(f"unsupported PSD compression {compression}")


def _assemble_layer_image(
    channels_raw: dict[int, np.ndarray],
    h: int, w: int,
    top: int, left: int, bottom: int, right: int,
) -> np.ndarray:
    """Build a full-canvas RGBA image and paste the layer's channels at
    the recorded ``(top, left)`` offset. Missing alpha → fully opaque
    inside the bounds (matches PSDs from older Photoshops)."""
    image = np.zeros((h, w, 4), dtype=np.uint8)
    if 0 in channels_raw:
        image[top:bottom, left:right, 0] = channels_raw[0]
    if 1 in channels_raw:
        image[top:bottom, left:right, 1] = channels_raw[1]
    if 2 in channels_raw:
        image[top:bottom, left:right, 2] = channels_raw[2]
    image[top:bottom, left:right, 3] = channels_raw.get(-1, 255)
    return image


def _parse_image_data_section(cursor, h: int, w: int) -> np.ndarray:
    """Parse the trailing composite image data and return HxWx4 RGBA."""
    if cursor.pos >= len(cursor.buf):
        return np.zeros((h, w, 4), dtype=np.uint8)
    compression = cursor.read_u16()
    image = np.zeros((h, w, 4), dtype=np.uint8)
    if compression == _COMPRESSION_RAW:
        _read_composite_raw(cursor, image, h, w)
    elif compression == _COMPRESSION_RLE:
        _read_composite_rle(cursor, image, h, w)
    else:
        raise ValueError(f"unsupported composite compression {compression}")
    if not image[..., 3].any():
        # No alpha was stored — fall back to fully opaque so the pixels
        # actually render.
        image[..., 3] = 255
    return image


def _assign_composite_channel(image: np.ndarray, plane: np.ndarray, ch_id: int) -> None:
    """Drop ``plane`` into the alpha slot when ``ch_id == -1``, otherwise
    into the RGB slot indexed by ``ch_id``."""
    if ch_id == -1:
        image[..., 3] = plane
    else:
        image[..., ch_id] = plane


def _read_composite_raw(cursor, image: np.ndarray, h: int, w: int) -> None:
    for ch_id in CHANNEL_ORDER:
        plane_bytes = cursor.read(h * w)
        plane = np.frombuffer(plane_bytes, dtype=np.uint8).reshape((h, w))
        _assign_composite_channel(image, plane, ch_id)


def _read_composite_rle(cursor, image: np.ndarray, h: int, w: int) -> None:
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
        _assign_composite_channel(image, plane, ch_id)


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
