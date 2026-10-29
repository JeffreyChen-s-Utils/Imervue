"""PSD writer sections — header, layer + mask section and composite.

Packs every section :func:`Imervue.paint.psd_io.save_psd` writes, in file
order. Raw (uncompressed) channel data only, so the bytes are fully
deterministic. Layer groups are encoded with ``lsct`` section-divider
records and every name also carries a ``luni`` Unicode block.
"""
from __future__ import annotations

import struct

import numpy as np

from Imervue.paint.document import Layer, LayerGroup, PaintDocument
from Imervue.paint.psd_io_format import (
    _BLEND_MODE_TO_PSD,
    _COMPRESSION_RAW,
    _LAYER_FLAG_HIDDEN,
    _LAYER_FLAG_PHOTOSHOP_5_PLUS,
    _LAYER_FLAG_TRANSPARENCY_PROTECTED,
    _SECTION_CLOSED_GROUP,
    _SECTION_END,
    _SECTION_END_NAME,
    _SECTION_OPEN_GROUP,
    CHANNEL_ORDER,
    PSD_CHANNELS_RGBA,
    PSD_COLOR_MODE_RGB,
    PSD_DEPTH_8BIT,
    PSD_SIGNATURE,
    PSD_VERSION,
    _channel_plane,
    _pack_pascal_padded,
)


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
