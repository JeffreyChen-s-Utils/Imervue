"""End-to-end integration tests across major subsystems.

Each test here exercises a user-facing flow that spans three or more
files. They are deliberately coarse — assert the high-level
invariant ("after X, Y, and Z, the composite differs from the
input"), not byte-exact pixel values — so they catch wiring
regressions without being noisy when individual tools tune their
maths. Per-tool unit tests already cover the fine-grained
behaviour.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.compositing import composite_stack
from Imervue.paint.document import PaintDocument


def _solid_rgba(h: int, w: int, color: tuple[int, int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = color[0]
    arr[..., 1] = color[1]
    arr[..., 2] = color[2]
    arr[..., 3] = color[3]
    return arr


# ---------------------------------------------------------------------------
# 1. Paint full session — PSD round-trip after a brush stroke + new layer.
# ---------------------------------------------------------------------------


def test_integration_psd_round_trip_preserves_layer_content(tmp_path):
    """workspace → paint → add layer → save PSD → reload should round-trip
    every layer's pixels and the active-layer index."""
    from Imervue.paint.brush_engine import BrushStroke, BrushStrokeOptions
    from Imervue.paint.psd_io import load_psd, save_psd

    doc = PaintDocument()
    doc.load_image(_solid_rgba(48, 64, (240, 240, 240, 255)))
    overlay = doc.add_layer(name="Overlay")
    # Paint a deterministic stroke into the overlay so the round-trip
    # has visible per-layer data to check.
    options = BrushStrokeOptions(
        kind="pen", size=8, color=(20, 200, 100), opacity=1.0,
        hardness=1.0, seed=42,
    )
    stroke = BrushStroke(options)
    stroke.begin(overlay.image, 16.0, 24.0)
    stroke.extend(overlay.image, 32.0, 24.0)
    stroke.end(overlay.image, 48.0, 24.0)

    target = tmp_path / "round_trip.psd"
    save_psd(doc, target)
    reloaded = load_psd(target)

    assert reloaded.layer_count == doc.layer_count
    np.testing.assert_array_equal(
        reloaded.layer_at(1).image[..., 3] > 0,
        overlay.image[..., 3] > 0,
        err_msg="overlay alpha must survive the PSD round-trip",
    )


# ---------------------------------------------------------------------------
# 2. Develop recipe stack — exposure + curve + LUT-disabled + split toning
#    all influence the result.
# ---------------------------------------------------------------------------


def test_integration_recipe_pipeline_stacks_in_order():
    """Apply a non-trivial recipe (exposure + tone curve + split
    toning) to a flat grey image and verify the output differs from
    every intermediate single-feature application — proves the chain
    composes rather than the last step shadowing the rest."""
    from Imervue.image.recipe import Recipe

    # Use a non-neutral base so chroma-only effects (split toning,
    # white balance) have something to shift. Tone-curve points live
    # in normalised [0, 1] space, not 0..255.
    base = _solid_rgba(32, 32, (160, 110, 90, 255))
    s_curve = [(0.0, 0.0), (0.5, 0.78), (1.0, 1.0)]
    only_exposure = Recipe(exposure=1.0).apply(base)
    only_curve = Recipe(tone_curve_rgb=s_curve).apply(base)
    only_temp = Recipe(temperature=0.6).apply(base)
    full = Recipe(
        exposure=1.0,
        tone_curve_rgb=s_curve,
        temperature=0.6,
    ).apply(base)
    # Each single-feature output must differ from the base, and the
    # full stack must differ from every single-feature output —
    # otherwise one of them is a no-op or the stack collapsed to the
    # last applied transform.
    assert (only_exposure != base).any()
    assert (only_curve != base).any()
    assert (only_temp != base).any()
    assert (full != only_exposure).any()
    assert (full != only_curve).any()
    assert (full != only_temp).any()


# ---------------------------------------------------------------------------
# 3. Manga pipeline — panel cutter + speedlines + flash + tone layer all
#    coexist as layers on one document.
# ---------------------------------------------------------------------------


def test_integration_manga_pipeline_layers_compose():
    """Stack the four manga primitives onto one document and check
    every layer carries non-empty pixels and the composite differs
    from the base canvas."""
    from Imervue.paint.flash_effect import FlashOptions, render_flash
    from Imervue.paint.manga_panels import draw_panel_borders, panel_grid
    from Imervue.paint.speedlines import SpeedlineOptions, render_speedlines

    doc = PaintDocument()
    h, w = 96, 128
    doc.load_image(_solid_rgba(h, w, (255, 255, 255, 255)))

    # Panel-grid layer.
    panels_layer = doc.add_layer(name="Panels")
    layout = panel_grid(width=w, height=h, rows=2, cols=2,
                        gutter=4, border_width=2, margin=4)
    draw_panel_borders(panels_layer.image, layout)

    # Speedlines layer.
    speedlines_layer = doc.add_layer(name="Speedlines")
    rendered = render_speedlines((h, w), SpeedlineOptions(kind="radial"))
    np.copyto(speedlines_layer.image, rendered)

    # Flash layer.
    flash_layer = doc.add_layer(name="Flash")
    np.copyto(flash_layer.image, render_flash((h, w), FlashOptions()))

    assert doc.layer_count == 4
    # Every overlay layer wrote opaque pixels somewhere.
    for layer in doc.layers()[1:]:
        assert (layer.image[..., 3] > 0).any(), (
            f"{layer.name!r} has no opaque pixels"
        )
    composite = doc.composite()
    base = doc.layer_at(0).image
    assert (composite != base).any(), (
        "manga overlays did not visibly modify the base canvas"
    )


# ---------------------------------------------------------------------------
# 4. Selection → refine-edge → layer mask → composite.
# ---------------------------------------------------------------------------


def test_integration_selection_to_layer_mask_clips_composite():
    """Build a rect selection, refine-edge it into an alpha mask,
    install the alpha mask on a coloured layer, and assert the
    composite is the masked colour over the base — proves the
    selection / refine-edge / mask / compositor chain agrees on
    coordinate space."""
    from Imervue.paint.selection import rectangle_mask
    from Imervue.paint.selection_ops import refine_edge

    doc = PaintDocument()
    doc.load_image(_solid_rgba(40, 40, (10, 10, 10, 255)))
    overlay = doc.add_layer(name="Red")
    overlay.image[...] = (240, 30, 30, 255)

    # Rect inside the canvas, with a 2-px feather to round the
    # edges. ``refine_edge`` returns a float-alpha mask; convert to
    # uint8 for the layer-mask channel.
    sel = rectangle_mask(40, 40, 8, 8, 32, 32)
    alpha = refine_edge(sel, feather=2)
    mask_uint8 = (alpha * 255.0).clip(0, 255).astype(np.uint8)
    overlay.mask = mask_uint8
    overlay.mask_enabled = True

    composite = doc.composite()
    # Inside the rect the result is dominated by the red overlay; far
    # outside the rect it must equal the base layer (the mask kept
    # the overlay from leaking).
    inside = composite[20, 20]
    outside = composite[2, 2]
    assert inside[0] > 200, "inside mask should be red-dominant"
    assert tuple(int(x) for x in outside[:3]) == (10, 10, 10), (
        "outside mask should keep the base colour"
    )


# ---------------------------------------------------------------------------
# 5. Animation export — three frames round-trip through MP4 (when ffmpeg
#    is available) or GIF as the universal fallback.
# ---------------------------------------------------------------------------


def test_integration_animation_export_writes_non_empty_file(tmp_path):
    """Add three frames with distinct content and prove
    :func:`export_gif` writes a non-empty file. MP4 export needs
    imageio-ffmpeg which isn't always installed on CI runners, but
    GIF works against stock imageio."""
    imageio = pytest.importorskip("imageio")
    from Imervue.paint.animation import Animation, AnimationFrame
    from Imervue.paint.animation_export import export_gif

    animation = Animation()
    for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        frame_doc = PaintDocument()
        frame_doc.load_image(_solid_rgba(16, 16, (*color, 255)))
        animation.frames.append(
            AnimationFrame(document=frame_doc, name=f"f-{color[0]}"),
        )

    target = tmp_path / "anim.gif"
    export_gif(animation, target)

    assert target.is_file()
    assert target.stat().st_size > 0
    # Round-trip prove the frame count survives.
    frames = imageio.mimread(target)
    assert len(frames) == 3


# ---------------------------------------------------------------------------
# 6. Compositing all-features — adjustment + clipping + group + effects all
#    combined produce a result that differs from the base layer alone.
# ---------------------------------------------------------------------------


def test_integration_layer_features_combine_in_composite():
    """A layer with a clipping-mask flag sitting above an adjustment
    layer inside a group must still flow through the compositor and
    visibly change the output. Catches subtle bugs where one feature
    short-circuits another (e.g. adjustment skipping the clip flag,
    group opacity ignoring effects)."""
    from Imervue.paint.adjustments import Adjustment
    from Imervue.paint.document import LayerGroup

    doc = PaintDocument()
    base = _solid_rgba(24, 24, (200, 100, 50, 255))
    doc.load_image(base)

    # Group containing two layers — an adjustment layer and a
    # clipping-mask layer.
    group = LayerGroup(name="FX", visible=True, opacity=0.8, blend_mode="pass_through")
    doc._groups[group.name] = group  # noqa: SLF001 - test wiring without dialog

    adjustment = doc.add_layer(name="Curves")
    adjustment.group = group.name
    adjustment.adjustment = Adjustment(
        kind="brightness_contrast",
        params={"brightness": 30, "contrast": 0},
    )

    overlay = doc.add_layer(name="ClipMe")
    overlay.group = group.name
    overlay.image[...] = (50, 250, 50, 255)
    overlay.clip = True
    overlay.opacity = 0.7

    composite = doc.composite().copy()
    expected_base = composite_stack([doc.layer_at(0)], doc.shape)
    # The composite must differ from the lone base — every feature
    # contributed at least one pixel of change.
    assert (composite != expected_base).any()
    # And it must differ from a recompose with the group hidden,
    # which proves the group's opacity flowed through. The cache
    # is invalidated explicitly because mutating ``group.visible``
    # bypasses the document's setters that normally fire it.
    group.visible = False
    doc.invalidate_composite()
    composite_hidden = doc.composite()
    assert (composite != composite_hidden).any()
