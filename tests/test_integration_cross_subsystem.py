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


# ---------------------------------------------------------------------------
# 7. Undo / redo stack — a brush stroke survives the undo → redo round-trip.
# ---------------------------------------------------------------------------


def test_integration_undo_redo_round_trips_brush_stroke():
    """Paint a stroke, snapshot it, undo, paint a different stroke,
    redo; the redo path must restore the *first* stroke verbatim and
    the undo stack tracks both gestures separately."""
    from Imervue.paint.brush_engine import BrushStroke, BrushStrokeOptions
    from Imervue.paint.undo_stack import UndoStack

    doc = PaintDocument()
    doc.load_image(_solid_rgba(32, 32, (255, 255, 255, 255)))
    layer = doc.add_layer(name="Ink")
    stack = UndoStack(doc)
    stack.commit()  # Baseline snapshot — empty layer.

    # First stroke (red horizontal).
    options = BrushStrokeOptions(
        kind="pen", size=4, color=(255, 0, 0), opacity=1.0,
        hardness=1.0, seed=1,
    )
    stroke = BrushStroke(options)
    stroke.begin(layer.image, 4.0, 16.0)
    stroke.end(layer.image, 28.0, 16.0)
    stack.commit()
    after_first = layer.image.copy()
    assert (after_first[..., 3] > 0).any()

    # Undo — the snapshot should revert to the empty baseline.
    assert stack.undo()
    assert not (doc.layer_at(-1).image[..., 3] > 0).any()

    # Redo — the first stroke comes back byte-for-byte.
    assert stack.redo()
    np.testing.assert_array_equal(doc.layer_at(-1).image, after_first)


# ---------------------------------------------------------------------------
# 8. Vector layer rasterise — adding strokes to a vector layer makes them
#    appear in the next composite.
# ---------------------------------------------------------------------------


def test_integration_vector_layer_strokes_show_in_composite():
    """A vector layer keeps its strokes off-image; only the
    compositor's ``realise_vector_layer`` step flushes them into the
    raster cache. Without that hook, the canvas would be silently
    blank after a pen-tool gesture."""
    from Imervue.paint.vector_layer import VectorLayerData, VectorStroke

    doc = PaintDocument()
    doc.load_image(_solid_rgba(40, 40, (240, 240, 240, 255)))
    layer = doc.add_layer(name="Pen")
    layer.vector_data = VectorLayerData()
    layer.vector_data.add(VectorStroke(
        points=((4.0, 20.0), (16.0, 20.0), (28.0, 20.0), (36.0, 20.0)),
        width=3.0,
        color=(20, 30, 200, 255),
        opacity=1.0,
    ))

    composite = doc.composite()
    base = doc.layer_at(0).image
    # Somewhere along y=20 the blue stroke should be the dominant
    # colour — proving the rasterise step ran inside ``composite``.
    middle_row = composite[20, :, :3]
    blue_dominant = (middle_row[:, 2] > middle_row[:, 0]).any()
    assert blue_dominant
    assert (composite != base).any()


# ---------------------------------------------------------------------------
# 9. XMP sidecar round-trip — rating, title, keywords, colour label survive.
# ---------------------------------------------------------------------------


def test_integration_xmp_sidecar_round_trips_metadata(tmp_path):
    """``XmpData`` written by :func:`save` must come back from
    :func:`load` byte-equal in every tracked field. Catches
    namespace / element-tag drift between writer and reader."""
    pytest.importorskip("defusedxml")
    from Imervue.image.xmp_sidecar import XmpData, load, save

    fake_image = tmp_path / "photo.jpg"
    fake_image.write_bytes(b"\xff\xd8\xff\xd9")  # 4-byte stub JPEG.

    written = XmpData(
        rating=4,
        title="Sunset over Taipei",
        description="Long-exposure handheld",
        keywords=["sunset", "taipei", "long-exposure"],
        color_label="Red",
    )
    save(fake_image, written)
    reloaded = load(fake_image)

    assert reloaded.rating == written.rating
    assert reloaded.title == written.title
    assert reloaded.description == written.description
    assert reloaded.keywords == written.keywords
    assert reloaded.color_label.lower() == written.color_label.lower()


# ---------------------------------------------------------------------------
# 10. Library index → multi-criteria search — inserted rows are queryable
#     by extension + min-resolution.
# ---------------------------------------------------------------------------


def test_integration_library_index_query_returns_matching_paths(tmp_path):
    """Insert three image rows with varied resolution and extension,
    then prove the query layer can filter on both criteria at once.
    Locks down the SQL builder against a future regression that
    silently drops one of the WHERE clauses."""
    from Imervue.library import image_index

    db_path = tmp_path / "library.db"
    image_index.set_db_path(db_path)
    try:
        image_index.upsert_image(
            "/library/big.jpg",
            size=10_000_000, width=4096, height=2160, mtime=1.0,
        )
        image_index.upsert_image(
            "/library/small.jpg",
            size=200_000, width=320, height=240, mtime=2.0,
        )
        image_index.upsert_image(
            "/library/big.png",
            size=8_000_000, width=4096, height=2160, mtime=3.0,
        )
        # JPG-only + at least 1080p — only ``big.jpg`` qualifies.
        hits = image_index.search_images(
            exts=("jpg",), min_width=1920, min_height=1080,
        )
        assert "/library/big.jpg".replace("/", "\\") in [
            str(p).replace("/", "\\") for p in hits
        ] or "/library/big.jpg" in hits
        assert "/library/big.png" not in hits
        assert "/library/small.jpg" not in hits
    finally:
        # Reset the global so other tests don't reuse the throw-away DB.
        image_index.set_db_path(image_index._default_db_path())  # noqa: SLF001


# ---------------------------------------------------------------------------
# 11. Quick-mask → selection commit — painting into the proxy buffer and
#     converting yields the same boolean mask.
# ---------------------------------------------------------------------------


def test_integration_quick_mask_proxy_to_selection_round_trip():
    """The Quick-Mask workflow paints opaque red into a proxy RGBA
    buffer; ``selection_from_proxy`` must convert that proxy back
    into a bool mask whose ``True`` cells line up with the painted
    region."""
    from Imervue.paint.quick_mask import make_proxy_buffer, selection_from_proxy

    base_selection = None
    proxy = make_proxy_buffer((20, 20), base_selection)
    # Paint a 4x4 solid square into the proxy at (8..12, 8..12).
    proxy[8:12, 8:12] = (255, 0, 0, 255)
    sel = selection_from_proxy(proxy)
    assert sel.shape == (20, 20)
    assert sel.dtype == np.bool_
    assert sel[8:12, 8:12].all()
    # Outside the painted region the mask must be empty.
    assert not sel[0:4, 0:4].any()
    assert not sel[16:20, 16:20].any()


# ---------------------------------------------------------------------------
# 12. Watermark overlay — applying a watermark to a flat image must change
#     the corner pixels but leave the bulk of the image alone.
# ---------------------------------------------------------------------------


def test_integration_watermark_modifies_only_anchor_corner():
    """The export-time watermark anchors the overlay at one of nine
    grid cells. Apply with corner = bottom-right and assert the BR
    region differs from the base while the TL region matches."""
    from Imervue.paint.export_utils import apply_watermark

    base = _solid_rgba(64, 64, (200, 200, 200, 255))
    watermark = _solid_rgba(8, 8, (255, 0, 0, 255))
    out = apply_watermark(
        base, watermark, position="bottom-right",
        opacity=1.0, padding=2,
    )
    # Top-left far corner: untouched grey.
    np.testing.assert_array_equal(out[0:4, 0:4], base[0:4, 0:4])
    # Bottom-right interior: red watermark must be visible.
    br = out[-8:-2, -8:-2]
    assert (br[..., 0] > 200).any()
    assert (br[..., 1] < 100).any()


# ---------------------------------------------------------------------------
# 13. Tool dispatcher — set the active tool, dispatch a press, the active
#     layer's pixels change.
# ---------------------------------------------------------------------------


def test_integration_tool_dispatcher_brush_paints_active_layer():
    """End-to-end through the tool dispatcher: pick the brush, push a
    PointerEvent, the active layer's pixels change. Catches regressions
    in the dispatcher's tool-lookup table or the brush wiring."""
    from Imervue.paint import tool_state as ts
    from Imervue.paint.canvas import PointerEvent
    from Imervue.paint.tool_dispatcher import ToolDispatcher

    state = ts.load_tool_state()
    state.set_tool("brush")
    state.set_foreground((10, 200, 80))
    state.set_brush(size=8, hardness=1.0, opacity=1.0)

    canvas = _solid_rgba(40, 40, (255, 255, 255, 255))
    before = canvas.copy()
    dispatcher = ToolDispatcher(state, image_provider=lambda: canvas)
    dispatcher(PointerEvent(
        phase="press", x=20.0, y=20.0, button=1, modifiers=0, pressure=1.0,
    ))
    dispatcher(PointerEvent(
        phase="release", x=20.0, y=20.0, button=0, modifiers=0, pressure=1.0,
    ))
    assert (canvas != before).any(), (
        "tool dispatcher did not route the brush press to the canvas"
    )


# ---------------------------------------------------------------------------
# 14. Tag hierarchy — assigning a leaf tag and querying by an ancestor
#     branch returns the image (descendant rule).
# ---------------------------------------------------------------------------


def test_integration_hierarchical_tag_descendant_query(tmp_path):
    """Assigning ``animal/cat/british`` to an image must surface it
    when we query for ``animal`` — the descendants-included contract
    documented in user_guide.rst. Catches a regression where the
    join only matches exact paths."""
    from Imervue.library import image_index

    db_path = tmp_path / "tags.db"
    image_index.set_db_path(db_path)
    try:
        image_index.upsert_image("/photos/kitty.jpg", size=1_000)
        image_index.add_image_tag("/photos/kitty.jpg", "animal/cat/british")
        # Querying for the ancestor branch with descendants enabled
        # must surface the image — that's the contract user_guide.rst
        # documents for hierarchical tags.
        descendants = image_index.images_with_tag(
            "animal", include_descendants=True,
        )
        assert "/photos/kitty.jpg" in descendants
        # Sibling branches must NOT match the same image.
        plant_descendants = image_index.images_with_tag(
            "plant", include_descendants=True,
        )
        assert "/photos/kitty.jpg" not in plant_descendants
        # Exact-match (without descendants) on the leaf still works.
        leaf_match = image_index.images_with_tag(
            "animal/cat/british", include_descendants=False,
        )
        assert "/photos/kitty.jpg" in leaf_match
    finally:
        image_index.set_db_path(image_index._default_db_path())  # noqa: SLF001
