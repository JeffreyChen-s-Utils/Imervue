"""Pure helpers for the desktop-pet drop shadow.

The shadow is a radially-faded ellipse drawn below the puppet
before the drawables, so the rig appears to "sit" on the desktop
instead of floating disconnected. Renders as one textured quad
(2×2 → arbitrary size via stretch) so it costs ~one draw call
even on rigs with hundreds of drawables.

Two pure helpers live here so the math is testable without a GL
context:

* :func:`make_shadow_pixels` produces the RGBA byte array uploaded
  to the GL texture — radial alpha falloff, configurable softness.
* :func:`shadow_quad_geometry` computes the on-document rectangle
  the quad covers — bottom-centred ellipse scaled to the puppet's
  width.

The canvas owns the GL state (texture id + draw call) and reads
these helpers' output verbatim.
"""
from __future__ import annotations

DEFAULT_TEXTURE_SIZE: int = 64
"""Resolution of the cached shadow texture. 64×64 is enough to
look smooth when stretched to thousands of pixels because GL's
linear filtering smooths the radial gradient further."""

DEFAULT_FALLOFF_EXP: float = 1.5
"""Exponent applied to the linear radial falloff. ``1.0`` is a
hard ellipse edge; ``> 1`` softens the fade; ``< 1`` sharpens it.
``1.5`` reads as "soft shadow" without bleeding too far out."""

DEFAULT_MAX_ALPHA: int = 180
"""Peak alpha at the centre of the shadow, 0-255. ``180/255`` ≈
70 % opaque — strong enough to ground the rig on a bright desktop
without overpowering darker wallpapers. Combined with the
caller's per-pet opacity multiplier this gives a final range
the user can tune."""

DEFAULT_WIDTH_RATIO: float = 0.4
"""Shadow width as a fraction of the puppet canvas width.
``0.4`` lands roughly under the rig's feet without bleeding past
hips for typical Live2D portraits. Users can scale this via the
``pet_shadow_scale`` setting."""

DEFAULT_HEIGHT_RATIO: float = 0.25
"""Shadow height as a fraction of its own width. A 4:1
flattened ellipse reads as "ground shadow" rather than "sphere
shadow"."""

DEFAULT_VERTICAL_OFFSET: float = 0.92
"""Y position of the shadow's centre as a fraction of the canvas
height. ``0.92`` puts the shadow near the bottom; rigs that
extend their feet past the document.size box may need a higher
value, exposed via the ``pet_shadow_vertical`` setting in
follow-up work."""


def make_shadow_pixels(
    *,
    size: int = DEFAULT_TEXTURE_SIZE,
    falloff_exp: float = DEFAULT_FALLOFF_EXP,
    max_alpha: int = DEFAULT_MAX_ALPHA,
) -> list[list[tuple[int, int, int, int]]]:
    """Build the radial-alpha-gradient pixel grid for the shadow
    texture.

    Returns a row-major 2-D list of ``(r, g, b, a)`` tuples — pure
    Python so tests don't need numpy. The canvas converts to a
    numpy array before uploading; this helper stays array-library-
    agnostic so it can run on a minimal install.

    Args:
        size: width / height of the texture (square). Defaults to
            :data:`DEFAULT_TEXTURE_SIZE`.
        falloff_exp: alpha = ``(1 - r/r_max) ** falloff_exp``.
        max_alpha: peak alpha value at the centre, ``[0, 255]``.

    Robust against ``size <= 0`` (returns a 1×1 transparent pixel)
    and clamps ``max_alpha`` to ``[0, 255]`` so a misconfigured
    caller can't push out-of-range bytes."""
    if size <= 0:
        return [[(0, 0, 0, 0)]]
    capped_alpha = max(0, min(255, int(max_alpha)))
    half = (size - 1) / 2.0
    max_r = size / 2.0
    falloff = max(0.0001, float(falloff_exp))
    rows: list[list[tuple[int, int, int, int]]] = []
    for y in range(size):
        row: list[tuple[int, int, int, int]] = []
        for x in range(size):
            dx = x - half
            dy = y - half
            r = (dx * dx + dy * dy) ** 0.5
            t = 1.0 - r / max_r
            if t <= 0.0:
                row.append((0, 0, 0, 0))
                continue
            alpha = int(round(capped_alpha * (t ** falloff)))
            row.append((0, 0, 0, max(0, min(capped_alpha, alpha))))
        rows.append(row)
    return rows


def shadow_quad_geometry(
    document_size: tuple[int, int],
    *,
    scale: float = 1.0,
    width_ratio: float = DEFAULT_WIDTH_RATIO,
    height_ratio: float = DEFAULT_HEIGHT_RATIO,
    vertical: float = DEFAULT_VERTICAL_OFFSET,
) -> tuple[float, float, float, float]:
    """Return ``(x, y, w, h)`` for the shadow quad in document
    coordinates.

    The shadow is horizontally centred and flattened:

    * ``w = doc_w * width_ratio * scale`` — caller-configurable
      shadow size.
    * ``h = w * height_ratio`` — 4:1 default keeps it reading as
      a ground shadow.
    * Centre at ``(doc_w / 2, doc_h * vertical)`` — bottom area
      of the canvas.

    Returns the unrotated bounding box; the canvas draws a textured
    quad inside it. Robust against zero-sized documents (returns a
    zero-sized quad)."""
    doc_w, doc_h = document_size
    if doc_w <= 0 or doc_h <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    width = max(0.0, float(doc_w) * float(width_ratio) * max(0.0, float(scale)))
    height = max(0.0, width * float(height_ratio))
    cx = float(doc_w) * 0.5
    cy = float(doc_h) * float(vertical)
    x = cx - width * 0.5
    y = cy - height * 0.5
    return (x, y, width, height)
