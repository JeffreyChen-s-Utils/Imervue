"""Photoshop ``.psd`` import / export — interop subset.

Supports a defined subset of the PSD format that round-trips
PaintDocuments cleanly:

* 8-bit RGBA, color mode RGB (3), single resolution
* Flat layer stack with names, opacity, visibility, blend mode
* Raw uncompressed channel data on write; raw + PackBits RLE on read
  (PackBits is the most common compression in PSDs from Photoshop /
  raster paint apps / Procreate, so reads from those tools work)
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

from pathlib import Path

from Imervue.system.atomic_write import replace_atomically
from Imervue.paint.document import PaintDocument
from Imervue.paint.psd_io_format import (
    _BLEND_MODE_TO_PSD,
    _COMPRESSION_RAW,
    _COMPRESSION_RLE,
    _LAYER_FLAG_HIDDEN,
    _LAYER_FLAG_PHOTOSHOP_5_PLUS,
    _LAYER_FLAG_TRANSPARENCY_PROTECTED,
    _PSD_TO_BLEND_MODE,
    _SECTION_CLOSED_GROUP,
    _SECTION_END,
    _SECTION_END_NAME,
    _SECTION_OPEN_GROUP,
    _SECTION_OTHER,
    CHANNEL_NAMES,
    CHANNEL_ORDER,
    PSD_CHANNELS_RGBA,
    PSD_COLOR_MODE_RGB,
    PSD_DEPTH_8BIT,
    PSD_SIGNATURE,
    PSD_VERSION,
    _channel_plane,
    _Cursor,
    _pack_pascal_padded,
    _packbits_decode,
    _read_pascal_padded,
)
from Imervue.paint.psd_io_read_layers import (
    _consume_group_header,
    _consume_record,
    _GroupAssemblyState,
    _parse_additional_info,
    _parse_layer_and_mask_section,
    _parse_layer_record,
    _read_additional_info_block,
)
from Imervue.paint.psd_io_read_pixels import (
    _assemble_layer_image,
    _assign_composite_channel,
    _parse_image_data_section,
    _read_composite_raw,
    _read_composite_rle,
    _read_layer_channel_data,
    _read_layer_channels,
    _read_one_channel_plane,
)
from Imervue.paint.psd_io_write import (
    _pack_additional_info_lsct,
    _pack_additional_info_luni,
    _pack_color_mode_section,
    _pack_group_header,
    _pack_header,
    _pack_image_data_section,
    _pack_image_resources_section,
    _pack_layer_and_mask_section,
    _pack_one_layer,
    _pack_section_end,
    _pack_section_layer,
)

# Format primitives, section packers and reader steps live in the
# ``psd_io_*`` siblings and are re-exported here so every
# ``from Imervue.paint.psd_io import`` keeps working. ``save_psd`` and
# ``load_psd`` resolve their steps through this module's globals, so a patch
# on ``psd_io._pack_layer_and_mask_section`` still reaches the writer.
__all__ = [
    "CHANNEL_NAMES",
    "CHANNEL_ORDER",
    "PSD_CHANNELS_RGBA",
    "PSD_COLOR_MODE_RGB",
    "PSD_DEPTH_8BIT",
    "PSD_SIGNATURE",
    "PSD_VERSION",
    "_BLEND_MODE_TO_PSD",
    "_COMPRESSION_RAW",
    "_COMPRESSION_RLE",
    "_Cursor",
    "_GroupAssemblyState",
    "_LAYER_FLAG_HIDDEN",
    "_LAYER_FLAG_PHOTOSHOP_5_PLUS",
    "_LAYER_FLAG_TRANSPARENCY_PROTECTED",
    "_PSD_TO_BLEND_MODE",
    "_SECTION_CLOSED_GROUP",
    "_SECTION_END",
    "_SECTION_END_NAME",
    "_SECTION_OPEN_GROUP",
    "_SECTION_OTHER",
    "_assemble_layer_image",
    "_assign_composite_channel",
    "_channel_plane",
    "_consume_group_header",
    "_consume_record",
    "_pack_additional_info_lsct",
    "_pack_additional_info_luni",
    "_pack_color_mode_section",
    "_pack_group_header",
    "_pack_header",
    "_pack_image_data_section",
    "_pack_image_resources_section",
    "_pack_layer_and_mask_section",
    "_pack_one_layer",
    "_pack_pascal_padded",
    "_pack_section_end",
    "_pack_section_layer",
    "_packbits_decode",
    "_parse_additional_info",
    "_parse_header",
    "_parse_image_data_section",
    "_parse_layer_and_mask_section",
    "_parse_layer_record",
    "_read_additional_info_block",
    "_read_composite_raw",
    "_read_composite_rle",
    "_read_layer_channel_data",
    "_read_layer_channels",
    "_read_one_channel_plane",
    "_read_pascal_padded",
    "_skip_color_mode_section",
    "_skip_image_resources_section",
    "load_psd",
    "save_psd",
]


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def save_psd(document: PaintDocument, path: str | Path) -> None:
    """Write ``document`` to a Photoshop ``.psd`` file (subset); a failure keeps the old file."""
    layers = document.layers()
    if not layers:
        raise ValueError("cannot save an empty PaintDocument as PSD")
    shape = document.shape
    if shape is None:
        raise ValueError("cannot save document with unknown shape")
    h, w = shape

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    def write(tmp: Path) -> None:
        with open(tmp, "wb") as fh:
            fh.write(_pack_header(h, w))
            fh.write(_pack_color_mode_section())
            fh.write(_pack_image_resources_section())
            fh.write(_pack_layer_and_mask_section(
                layers, h, w, groups={g.name: g for g in document.groups()},
            ))
            fh.write(_pack_image_data_section(document, h, w))

    # Ctrl+S saves over the open PSD: writing it in place truncated the file
    # first, so an error mid-save left the painting's only copy broken.
    replace_atomically(target, write)


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
