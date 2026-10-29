"""PSD reader — layer records, additional info and group assembly.

Parses the layer + mask section: each layer record with its ``luni`` /
``lsct`` additional-info blocks, then walks the records bottom-to-top,
reading their channel data and rebuilding layer groups from the
section-divider records.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

from Imervue.paint.compositing import LAYER_BLEND_MODES
from Imervue.paint.document import Layer, LayerGroup
from Imervue.paint.psd_io_format import (
    _LAYER_FLAG_HIDDEN,
    _PSD_TO_BLEND_MODE,
    _SECTION_CLOSED_GROUP,
    _SECTION_END,
    _SECTION_OPEN_GROUP,
    _read_pascal_padded,
)
from Imervue.paint.psd_io_read_pixels import _read_layer_channel_data


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

