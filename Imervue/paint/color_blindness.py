"""Color-vision-deficiency (CVD) simulation overlays.

Apply a 3×3 RGB transform that approximates how a viewer with the
named deficiency would perceive the canvas. The dispatcher / canvas
widget can render the document, pipe the composite through this
helper, and display the result so the user can sanity-check that
their palette stays legible for the ~8% of viewers with red-green
colour blindness.

Four kinds:

* ``protanopia``    — red-blind (missing L cones)
* ``deuteranopia``  — green-blind (missing M cones); the most common
                      red-green CVD
* ``tritanopia``    — blue-blind (missing S cones)
* ``achromatopsia`` — full monochromatic vision (greyscale)

The matrices come from the standard Brettel et al. simulation
applied directly to non-linear sRGB. That's the same approximation
Photoshop's "View › Proof Setup › Color Blindness" uses — close
enough for design checks; not a colour-science reference.

``simulate(image, kind, severity)`` linearly interpolates between
the identity matrix (severity 0) and the full deficiency matrix
(severity 1) so a "what would mild deuteranopia look like" check
needs only one helper.
"""
from __future__ import annotations

import numpy as np

SIMULATION_KINDS = (
    "protanopia",
    "deuteranopia",
    "tritanopia",
    "achromatopsia",
)


_CVD_MATRICES = {
    "protanopia": np.array([
        [0.567, 0.433, 0.000],
        [0.558, 0.442, 0.000],
        [0.000, 0.242, 0.758],
    ], dtype=np.float32),
    "deuteranopia": np.array([
        [0.625, 0.375, 0.000],
        [0.700, 0.300, 0.000],
        [0.000, 0.300, 0.700],
    ], dtype=np.float32),
    "tritanopia": np.array([
        [0.950, 0.050, 0.000],
        [0.000, 0.433, 0.567],
        [0.000, 0.475, 0.525],
    ], dtype=np.float32),
    # Rec. 709 luma — converts every channel to the same grey.
    "achromatopsia": np.array([
        [0.299, 0.587, 0.114],
        [0.299, 0.587, 0.114],
        [0.299, 0.587, 0.114],
    ], dtype=np.float32),
}


def simulate(
    image: np.ndarray,
    kind: str,
    *,
    severity: float = 1.0,
) -> np.ndarray:
    """Apply CVD simulation matrix; return a fresh HxWx4 RGBA buffer.

    ``severity`` in ``[0, 1]`` blends between the identity matrix
    (no simulation) and the full deficiency matrix. Out-of-range
    values are clamped. ``severity == 0`` short-circuits to a copy
    of the input.
    """
    if (
        image.ndim != 3
        or image.shape[2] != 4
        or image.dtype != np.uint8
    ):
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    if kind not in SIMULATION_KINDS:
        raise ValueError(
            f"unknown CVD kind {kind!r}; expected one of {SIMULATION_KINDS}",
        )
    severity = max(0.0, min(1.0, float(severity)))
    if severity == 0.0:
        return image.copy()

    matrix = _CVD_MATRICES[kind]
    identity = np.eye(3, dtype=np.float32)
    blended = (1.0 - severity) * identity + severity * matrix

    rgb = image[..., :3].astype(np.float32) / 255.0
    transformed = rgb @ blended.T

    out = image.copy()
    out[..., :3] = np.clip(transformed * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


def matrix_for(kind: str) -> np.ndarray:
    """Return the underlying 3×3 simulation matrix for ``kind``.

    Useful for callers that want to build their own pipeline (e.g.
    chain CVD simulation with another colour transform without
    converting to / from RGBA twice). Returns a fresh copy so the
    module's stored matrix stays immutable.
    """
    if kind not in SIMULATION_KINDS:
        raise ValueError(
            f"unknown CVD kind {kind!r}; expected one of {SIMULATION_KINDS}",
        )
    return _CVD_MATRICES[kind].copy()
