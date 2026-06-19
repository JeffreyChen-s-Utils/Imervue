"""LSB steganography — hide and reveal a UTF-8 message in an image.

The encode/decode counterpart to the sanitizer (which only *destroys* hidden
data). A 32-bit big-endian length header is written into the least-significant
bits of the RGB channels, followed by the UTF-8 payload bits. Lossless output
(PNG) is required to survive the round-trip. Pure NumPy.
"""
from __future__ import annotations

import numpy as np

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_HEADER_BITS = 32
_BITS_PER_BYTE = 8


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape}")


def capacity_bytes(arr: np.ndarray) -> int:
    """Maximum payload size (bytes) that fits in *arr*'s RGB least-significant bits."""
    _validate(arr)
    usable_bits = arr.shape[0] * arr.shape[1] * _RGB_CHANNELS - _HEADER_BITS
    return max(0, usable_bits // _BITS_PER_BYTE)


def _int_to_bits(value: int, width: int) -> np.ndarray:
    return ((value >> np.arange(width - 1, -1, -1)) & 1).astype(np.uint8)


def hide_message(arr: np.ndarray, message: str) -> np.ndarray:
    """Return a copy of *arr* with *message* embedded in its RGB LSBs."""
    _validate(arr)
    payload = message.encode("utf-8")
    if len(payload) > capacity_bytes(arr):
        raise ValueError("message too long for this image")
    header = _int_to_bits(len(payload), _HEADER_BITS)
    payload_bits = (np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
                    if payload else np.empty(0, dtype=np.uint8))
    bits = np.concatenate([header, payload_bits])
    out = arr.copy()
    # ``out[..., :3]`` is a non-contiguous view, so reshape would copy; work on
    # a contiguous RGB buffer and write it back.
    rgb = np.ascontiguousarray(out[..., :_RGB_CHANNELS])
    flat = rgb.reshape(-1)
    flat[:bits.size] = (flat[:bits.size] & 0xFE) | bits
    out[..., :_RGB_CHANNELS] = rgb
    return out


def reveal_message(arr: np.ndarray) -> str:
    """Extract a message previously hidden by :func:`hide_message`; '' if none."""
    _validate(arr)
    channels = arr[..., :_RGB_CHANNELS].reshape(-1)
    if channels.size < _HEADER_BITS:
        return ""
    length = int.from_bytes(np.packbits(channels[:_HEADER_BITS] & 1).tobytes(), "big")
    needed = _HEADER_BITS + length * _BITS_PER_BYTE
    if length <= 0 or needed > channels.size:
        return ""
    payload_bits = channels[_HEADER_BITS:needed] & 1
    payload = np.packbits(payload_bits).tobytes()[:length]
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return ""
