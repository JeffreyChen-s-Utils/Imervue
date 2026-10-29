"""PSD reader — layer channel planes and the trailing composite image.

Decodes raw / PackBits-RLE channel planes, pastes a layer's channels onto
a full-canvas RGBA image (clipping layers that overhang the canvas) and
parses the composite image-data section a layerless PSD falls back to.
"""
from __future__ import annotations

import struct

import numpy as np

from Imervue.paint.compositing import LAYER_BLEND_MODES
from Imervue.paint.document import Layer
from Imervue.paint.psd_io_format import (
    _COMPRESSION_RAW,
    _COMPRESSION_RLE,
    _LAYER_FLAG_HIDDEN,
    _LAYER_FLAG_TRANSPARENCY_PROTECTED,
    _PSD_TO_BLEND_MODE,
    CHANNEL_ORDER,
    PSD_CHANNELS_RGBA,
    _packbits_decode,
)


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
    # A layer can legally overhang the canvas (top<0 / left<0 / bottom>h /
    # right>w, common in Photoshop/Krita/Procreate files). Clip the on-canvas
    # rectangle and slice the SOURCE channels to match, or the raw-bounds source
    # would mismatch the clamped destination and raise a broadcast ValueError.
    dst_top, dst_left = max(0, top), max(0, left)
    dst_bottom, dst_right = min(h, bottom), min(w, right)
    if dst_bottom <= dst_top or dst_right <= dst_left:
        return image   # layer is entirely off-canvas
    src_top, src_left = dst_top - top, dst_left - left
    src_bottom = src_top + (dst_bottom - dst_top)
    src_right = src_left + (dst_right - dst_left)
    dst_rows, dst_cols = slice(dst_top, dst_bottom), slice(dst_left, dst_right)
    src_rows, src_cols = slice(src_top, src_bottom), slice(src_left, src_right)
    for channel in (0, 1, 2):
        if channel in channels_raw:
            image[dst_rows, dst_cols, channel] = (
                channels_raw[channel][src_rows, src_cols])
    alpha = channels_raw.get(-1)
    if alpha is None:
        image[dst_rows, dst_cols, 3] = 255
    else:
        image[dst_rows, dst_cols, 3] = alpha[src_rows, src_cols]
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
