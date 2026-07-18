"""A truncated .motion3.json must raise CubismFormatError, not IndexError.

_consume_segment read raw[cursor + N] unchecked, so a truncated segment array
raised IndexError, which the importer's except tuple doesn't catch.
"""
from __future__ import annotations

import pytest

from Imervue.puppet.cubism_import import (
    _CUBISM_BEZIER,
    _CUBISM_LINEAR,
    CubismFormatError,
    _consume_segment,
)


def test_truncated_segment_raises_format_error():
    # Bezier needs 6 floats; only 3 are present from the cursor.
    with pytest.raises(CubismFormatError, match="truncated"):
        _consume_segment([0.0, 1.0, 2.0], 0, _CUBISM_BEZIER, (0.0, 0.0))


def test_unknown_segment_type_raises_format_error():
    with pytest.raises(CubismFormatError, match="unknown"):
        _consume_segment([0.0] * 10, 0, 999, (0.0, 0.0))


def test_valid_linear_segment_parses():
    seg, p1, cursor = _consume_segment(
        [1.0, 2.0, 9.0], 0, _CUBISM_LINEAR, (0.0, 0.0))
    assert seg.p1 == (1.0, 2.0)
    assert p1 == (1.0, 2.0)
    assert cursor == 2
