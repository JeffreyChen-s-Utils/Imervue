"""Per-kind brush kernel modifiers.

Turns the five brush kinds (pencil / pen / marker / airbrush / watercolor)
into something more than cosmetic labels by reshaping the per-dab alpha
kernel before compositing:

* **pencil** — multiplies the kernel by a per-pixel noise field so the
  stroke leaves a granular trail rather than a smooth wash.
* **pen** — identity. Crisp, clean ink line.
* **marker** — identity kernel; the dispatcher applies a multiply
  blend so successive strokes saturate.
* **airbrush** — Bernoulli-samples the kernel against a per-pixel
  random threshold so a single dab leaves sparse dots; spacing is
  driven by stacked dabs along a path.
* **watercolor** — boosts alpha at the dab boundary (wet edge) and
  attenuates interior, mimicking pigment pooling at the rim of a
  watercolour stroke.

Pure numpy. The dispatcher passes a seeded RNG so identical
strokes produce identical noise — important for undo / replay.
"""
from __future__ import annotations

import numpy as np

BRUSH_KINDS = ("pencil", "pen", "marker", "airbrush", "watercolor")


def stylise_kernel(
    kernel: np.ndarray,
    kind: str,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Return a kind-specific variant of ``kernel`` (HxW float32, [0..1]).

    Pen and marker fall through unchanged; the dispatcher modulates
    them via blend mode and opacity rather than kernel reshaping.
    Unknown kinds also fall through so a typo can never crash the
    paint loop.
    """
    if kernel.ndim != 2:
        raise ValueError(f"kernel must be 2-D, got shape {kernel.shape}")
    if kernel.dtype != np.float32:
        raise ValueError(f"kernel dtype must be float32, got {kernel.dtype}")
    if rng is None:
        rng = np.random.default_rng(0xC0FFEE)
    if kind == "pencil":
        return _pencil(kernel, rng)
    if kind == "airbrush":
        return _airbrush(kernel, rng)
    if kind == "watercolor":
        return _watercolor(kernel)
    return kernel.copy()


# ---------------------------------------------------------------------------
# Per-kind modifiers
# ---------------------------------------------------------------------------


def _pencil(kernel: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Granular texture — multiply by noise in [0.5, 1.0]."""
    noise = rng.random(kernel.shape, dtype=np.float32) * 0.5 + 0.5
    return (kernel * noise).astype(np.float32)


def _airbrush(kernel: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Sparse dot pattern — Bernoulli-sample weighted by kernel alpha."""
    threshold = rng.random(kernel.shape, dtype=np.float32)
    keep = threshold < (kernel * 0.4)
    return (kernel * keep.astype(np.float32) * 0.6).astype(np.float32)


def _watercolor(kernel: np.ndarray) -> np.ndarray:
    """Wet-edge boost — emphasise the boundary, attenuate the interior.

    Computes a cheap one-pixel erosion of ``kernel`` via 4-direction
    minimum-pool, takes ``kernel - eroded`` as the edge ring, then
    returns ``0.5 * interior + 1.6 * edge`` clipped to ``[0, 1]``. Pure
    numpy; no scipy.
    """
    h, w = kernel.shape
    if h < 3 or w < 3:
        return kernel.copy()
    shifts = [
        np.pad(kernel, ((1, 0), (0, 0)), mode="edge")[:-1],
        np.pad(kernel, ((0, 1), (0, 0)), mode="edge")[1:],
        np.pad(kernel, ((0, 0), (1, 0)), mode="edge")[:, :-1],
        np.pad(kernel, ((0, 0), (0, 1)), mode="edge")[:, 1:],
    ]
    eroded = np.minimum.reduce(shifts)
    edge = np.maximum(kernel - eroded, 0.0)
    out = kernel * 0.5 + edge * 1.6
    return np.clip(out, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Pen pressure → (size, opacity) — used by the dispatcher
# ---------------------------------------------------------------------------


def pressure_size_factor(pressure: float) -> float:
    """Scale the brush size by pen pressure with a documented floor.

    MediBang scales size by roughly ``0.3 + 0.7 * pressure`` so light
    pressure still draws a thin line rather than vanishing. The floor
    keeps cheap mice (which always report 1.0) at full size.
    """
    p = max(0.0, min(1.0, float(pressure)))
    return 0.3 + 0.7 * p


def pressure_opacity_factor(pressure: float) -> float:
    """Scale opacity by pen pressure with a 0.1 floor."""
    p = max(0.0, min(1.0, float(pressure)))
    return max(0.1, p)
