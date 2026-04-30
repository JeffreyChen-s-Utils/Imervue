"""Pure helpers for layer composition ops — merge down / merge visible / flatten.

These helpers operate on :class:`Imervue.paint.document.Layer` objects
and return fresh :class:`Layer` instances; the caller (a
:class:`PaintDocument` method) is responsible for swapping the
returned layer back into the stack and notifying listeners.

Pure numpy / Qt-free; the document-level glue ``merge_down`` etc.
lives on :class:`PaintDocument` because it touches the stack, the
active-layer pointer, and the listener bus — wrapping that thin shell
inside the document keeps single-responsibility (this module owns the
*compositing*, the document owns the *bookkeeping*).

Merge-down semantics
--------------------

When merging ``above`` down onto ``below``, the merged pixels are::

    composite_layer_pair(below.image, above.image,
                         opacity=above.opacity,
                         blend_mode=above.blend_mode,
                         mask=above.mask)

The merged Layer adopts BELOW's blend_mode, opacity, name, visible,
locked and clip flags; the layer mask is dropped because the above
layer's mask has been baked into the pixels. This matches MediBang's
behaviour: the merged result still composites against the canvas
through the lower layer's blend mode, while the upper layer's
contribution is incorporated as flat pixels.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from Imervue.paint.compositing import composite_layer_pair

if TYPE_CHECKING:
    from Imervue.paint.document import Layer

DEFAULT_FLATTEN_NAME = "Background"


def merge_layer_pair(below: Layer, above: Layer) -> Layer:
    """Composite ``above`` onto ``below``; return a fresh Layer.

    The merged Layer keeps below's blend_mode, opacity and metadata
    flags (visible / locked / clip) but uses below's name. The mask
    is dropped (it has been baked into the merged pixels). The
    returned Layer's image is a brand-new array — the inputs are not
    mutated.
    """
    from Imervue.paint.document import Layer
    if below.image.shape != above.image.shape:
        raise ValueError(
            f"merge_down requires equal-shape layers, got "
            f"{below.image.shape} vs {above.image.shape}",
        )
    merged_pixels = composite_layer_pair(
        below.image, above.image,
        opacity=above.opacity,
        blend_mode=above.blend_mode,
        mask=above.mask,
    )
    return Layer(
        name=below.name,
        image=merged_pixels,
        opacity=below.opacity,
        blend_mode=below.blend_mode,
        visible=below.visible,
        locked=below.locked,
        mask=None,    # below's mask is preserved? See note in composite_visible_layers.
        clip=below.clip,
    )


def composite_visible_layers(
    layers: list[Layer], shape: tuple[int, int],
) -> Layer | None:
    """Composite the visible, non-zero-opacity layers into one Layer.

    Returns ``None`` if no layer would contribute (all hidden or all
    opacity == 0). The result uses the lowest visible layer's name
    plus normal / opacity-1 blending — its pixels carry the baked
    contribution of every visible layer.
    """
    from Imervue.paint.document import Layer
    visibles = [layer for layer in layers if layer.visible and layer.opacity > 0]
    if not visibles:
        return None
    h, w = shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    for layer in visibles:
        if layer.image.shape[:2] != (h, w):
            raise ValueError(
                f"layer {layer.name!r} shape {layer.image.shape[:2]} "
                f"does not match document {shape}",
            )
        out = composite_layer_pair(
            out, layer.image,
            opacity=layer.opacity,
            blend_mode=layer.blend_mode,
            mask=layer.mask,
        )
    return Layer(name=visibles[0].name, image=out)


def flatten_layers(
    layers: list[Layer], shape: tuple[int, int],
) -> Layer:
    """Composite the visible layers and return one ``Background`` layer.

    Hidden layers are dropped — that's the difference from
    :func:`composite_visible_layers`, which preserves them in the
    stack. ``flatten`` is the document's "give me one layer holding
    every pixel that's currently on screen" operation. Even when the
    document is empty the result is a fully-transparent canvas of
    ``shape`` so downstream code can skip a None branch.
    """
    from Imervue.paint.document import Layer
    merged = composite_visible_layers(layers, shape)
    if merged is None:
        h, w = shape
        return Layer(
            name=DEFAULT_FLATTEN_NAME,
            image=np.zeros((h, w, 4), dtype=np.uint8),
        )
    return Layer(name=DEFAULT_FLATTEN_NAME, image=merged.image)
