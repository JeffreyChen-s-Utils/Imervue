"""A 1D .cube LUT must honour its DOMAIN_MIN/MAX like the 3D path does."""
from __future__ import annotations

import numpy as np

from Imervue.image.lut import CubeLut, _apply_1d


def _identity_1d(size: int = 2) -> np.ndarray:
    xs = np.linspace(0.0, 1.0, size, dtype=np.float32)
    return np.stack([xs, xs, xs], axis=1)   # (size, 3), identity per channel


def test_apply_1d_normalizes_by_domain():
    lut = CubeLut(
        size=2, table=_identity_1d(2),
        domain_min=(0.0, 0.0, 0.0), domain_max=(0.5, 0.5, 0.5),
    )
    # 128/255 ~= 0.502 sits at the top of the [0, 0.5] domain -> maps to ~1.0.
    out = _apply_1d(np.full((2, 2, 3), 128, dtype=np.uint8), lut)
    assert np.all(out >= 0.99)


def test_apply_1d_default_domain_is_identity():
    lut = CubeLut(size=2, table=_identity_1d(2))   # domain [0, 1]
    out = _apply_1d(np.full((2, 2, 3), 128, dtype=np.uint8), lut)
    # No domain scaling: 0.502 stays ~0.502.
    assert np.allclose(out, 128 / 255.0, atol=0.01)
