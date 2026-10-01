"""Small ICC profiles for colour-management tests.

``DISPLAY_P3`` is ``DisplayP3-v4.icc`` from Compact-ICC-Profiles
(https://github.com/saucecontrol/Compact-ICC-Profiles), released under CC0-1.0.
:func:`grey_profile` builds a greyscale profile with a plain gamma curve, the
kind Photoshop embeds as ``Gray Gamma 1.8``.
"""
from __future__ import annotations

import base64
import struct

DISPLAY_P3: bytes = base64.b64decode(
    "AAAB4GxjbXMEIAAAbW50clJHQiBYWVogB+IAAwAUAAkADgAdYWNzcE1TRlQAAAAAc2F3c2N0cmwAAAAAAAAAAAAA"
    "AAAAAPbWAAEAAAAA0y1oYW5kwzc6zlf4VsuhS9h6V6sQYQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAK"
    "ZGVzYwAAAPwAAAAiY3BydAAAASAAAAAid3RwdAAAAUQAAAAUY2hhZAAAAVgAAAAsclhZWgAAAYQAAAAUZ1hZWgAA"
    "AZgAAAAUYlhZWgAAAawAAAAUclRSQwAAAcAAAAAgZ1RSQwAAAcAAAAAgYlRSQwAAAcAAAAAgbWx1YwAAAAAAAAAB"
    "AAAADGVuVVMAAAAGAAAAHABzAFAAMwAAbWx1YwAAAAAAAAABAAAADGVuVVMAAAAGAAAAHABDAEMAMAAAWFlaIAAA"
    "AAAAAPbWAAEAAAAA0y1zZjMyAAAAAAABDEIAAAXe///zJQAAB5MAAP2Q///7of///aIAAAPcAADAblhZWiAAAAAA"
    "AACD3wAAPb////+7WFlaIAAAAAAAAEq/AACxNwAACrlYWVogAAAAAAAAKDgAABEKAADIuXBhcmEAAAAAAAMAAAAC"
    "ZmkAAPKnAAANWQAAE9AAAApb"
)


_D50 = (0.9642, 1.0, 0.8249)


def _s15(value: float) -> bytes:
    return struct.pack(">i", round(value * 65536))


def _padded(body: bytes) -> bytes:
    return body + b"\0" * (-len(body) % 4)


def grey_profile(gamma: float, name: str = "Gray Gamma") -> bytes:
    """An ICC v2 greyscale display profile: description, D50 white point, gamma *gamma*."""
    text = name.encode("ascii") + b"\0"
    desc = b"desc" + bytes(4) + struct.pack(">I", len(text)) + text + bytes(4 + 4 + 2 + 1 + 67)
    white = b"XYZ " + bytes(4) + b"".join(_s15(v) for v in _D50)
    curve = b"curv" + bytes(4) + struct.pack(">IH", 1, round(gamma * 256))
    tags = [(b"desc", _padded(desc)), (b"wtpt", white), (b"kTRC", _padded(curve))]
    offset = 128 + 4 + 12 * len(tags)
    table, data = b"", b""
    for signature, body in tags:
        table += signature + struct.pack(">II", offset + len(data), len(body))
        data += body
    header = (struct.pack(">I", offset + len(data)) + b"lcms" + bytes([2, 0x10, 0, 0])
              + b"mntrGRAYXYZ " + struct.pack(">6H", 2026, 9, 26, 0, 0, 0) + b"acsp"
              + bytes(28) + b"".join(_s15(v) for v in _D50) + bytes(48))
    return header + struct.pack(">I", len(tags)) + table + data
