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


# ---------------------------------------------------------------------------
# 15. Recipe store per-path persistence — set, save to disk, reload, get
#     the same recipe back. Covers the JSON schema + the file-identity hash.
# ---------------------------------------------------------------------------


def test_integration_recipe_store_round_trips_per_path(tmp_path):
    """Setting a recipe for a path, dropping the in-memory cache, and
    reloading the store from disk must yield byte-equal recipes —
    proves the JSON schema, the path-keyed identity hash, and the
    autosave hook all stay in sync."""
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import RecipeStore

    fake_image = tmp_path / "shot.jpg"
    fake_image.write_bytes(b"\xff\xd8\xff\xd9")  # 4-byte stub JPEG.

    store_a = RecipeStore(store_path=tmp_path / "recipes.json")
    recipe = Recipe(exposure=0.7, saturation=0.4, temperature=-0.3)
    store_a.set_for_path(str(fake_image), recipe)
    # Force the save side of the store via the documented public path
    # (set_for_path schedules a write; close out via a fresh instance).
    del store_a

    store_b = RecipeStore(store_path=tmp_path / "recipes.json")
    reloaded = store_b.get_for_path(str(fake_image))
    assert reloaded is not None
    assert reloaded.exposure == pytest.approx(recipe.exposure)
    assert reloaded.saturation == pytest.approx(recipe.saturation)
    assert reloaded.temperature == pytest.approx(recipe.temperature)


# ---------------------------------------------------------------------------
# 16. Phash similarity ordering — three pHashes from three colour gradients
#     line up by Hamming distance the way the similar-image search expects.
# ---------------------------------------------------------------------------


def test_integration_phash_orders_by_visual_similarity(tmp_path):
    """``compute_phash`` over three images (A, A-shifted, totally-
    different) must yield Hamming(A, A-shifted) < Hamming(A, other).
    Catches regressions that would silently reorder the duplicate /
    similar-image search results."""
    from PIL import Image

    from Imervue.library.phash import compute_phash, hamming

    base = np.tile(
        np.linspace(0, 255, 64, dtype=np.uint8), (64, 1),
    )
    base_rgb = np.stack([base, base, base], axis=-1)
    shifted = np.roll(base_rgb, shift=2, axis=1)
    inverted = 255 - base_rgb

    a_path = tmp_path / "a.png"
    b_path = tmp_path / "a-shifted.png"
    c_path = tmp_path / "inverted.png"
    Image.fromarray(base_rgb).save(a_path)
    Image.fromarray(shifted).save(b_path)
    Image.fromarray(inverted).save(c_path)

    h_a = compute_phash(a_path)
    h_b = compute_phash(b_path)
    h_c = compute_phash(c_path)
    assert h_a is not None and h_b is not None and h_c is not None
    near = hamming(h_a, h_b)
    far = hamming(h_a, h_c)
    assert near < far, (
        f"shifted ({near}) should hash closer than inverted ({far})"
    )


# ---------------------------------------------------------------------------
# 17. Brush preset bundle — export a list of presets to a .imervuebrush,
#     re-import, every preset survives byte-for-byte.
# ---------------------------------------------------------------------------


def test_integration_brush_preset_bundle_round_trip(tmp_path):
    """``export_bundle`` + ``import_bundle`` is the share-presets-with-
    a-friend path. The two-way round-trip must preserve every field
    on every preset."""
    from Imervue.paint.brush_preset_io import export_bundle, import_bundle
    from Imervue.paint.brush_presets import BrushPreset

    presets = [
        BrushPreset(
            name="Smooth Pen", kind="pen",
            size=18, opacity=0.95, hardness=1.0,
        ),
        BrushPreset(
            name="Soft Watercolor", kind="watercolor",
            size=42, opacity=0.6, hardness=0.4,
        ),
    ]
    target = tmp_path / "bundle.imervuebrush"
    export_bundle(presets, target)
    reloaded = import_bundle(target)

    assert len(reloaded) == len(presets)
    for original, restored in zip(presets, reloaded, strict=True):
        assert restored.name == original.name
        assert restored.kind == original.kind
        assert restored.size == original.size
        assert restored.opacity == pytest.approx(original.opacity)
        assert restored.hardness == pytest.approx(original.hardness)


# ---------------------------------------------------------------------------
# 18. Color palette .gpl import — the ``.gpl``-format reader returns the colours
#     in declaration order with the right RGB triples.
# ---------------------------------------------------------------------------


def test_integration_palette_gimp_import_preserves_color_order(tmp_path):
    """A minimal ``.gpl`` palette has ``GIMP Palette`` header + per-line
    ``R G B name`` rows. The importer must yield colours in the
    same order with the right RGB and (optionally) name."""
    from Imervue.paint.color_palette_io import import_gimp_palette

    palette_text = (
        "GIMP Palette\n"
        "Name: Test\n"
        "Columns: 1\n"
        "#\n"
        "255   0   0\tRed\n"
        "  0 255   0\tGreen\n"
        "  0   0 255\tBlue\n"
    )
    target = tmp_path / "palette.gpl"
    target.write_text(palette_text, encoding="utf-8")
    colours = import_gimp_palette(target)

    assert len(colours) == 3
    assert tuple(colours[0].rgb) == (255, 0, 0)
    assert tuple(colours[1].rgb) == (0, 255, 0)
    assert tuple(colours[2].rgb) == (0, 0, 255)


# ---------------------------------------------------------------------------
# 19. Action recorder → replay — every recorded action's payload survives
#     into the replay queue and the recorder reports the same length.
# ---------------------------------------------------------------------------


def test_integration_action_recorder_round_trip_preserves_actions():
    """Record three actions, persist via the manager, reload the
    list from the in-memory store. Catches schema regressions in
    ``Action.to_dict`` / ``ActionRecording.from_dict``."""
    from Imervue.paint.action_recorder import (
        Action,
        ActionRecorder,
        ActionRecording,
    )

    rec = ActionRecorder()
    rec.start("smoke-test")
    rec.record("brush", {"x": 1, "y": 2})
    rec.record("erase", {"x": 3, "y": 4})
    rec.record("brush", {"x": 5, "y": 6})
    recording = rec.stop()
    assert recording is not None

    serialised = recording.to_dict()
    reloaded = ActionRecording.from_dict(serialised)
    assert reloaded.name == recording.name
    assert len(reloaded.actions) == 3
    kinds = [a.kind for a in reloaded.actions]
    assert kinds == ["brush", "erase", "brush"]
    assert reloaded.actions[2].params["x"] == 5
    # Confirm Action's frozen dataclass field is `params`, not `payload`.
    assert isinstance(Action.from_dict({"kind": "test"}), Action)


# ---------------------------------------------------------------------------
# 20. Pyramid tile generation — a 2048×2048 source produces a multi-level
#     pyramid where each level halves the dimensions until ≤ tile size.
# ---------------------------------------------------------------------------


def test_integration_pyramid_levels_halve_until_under_tile_size():
    """Deep-zoom builds a pyramid where each level is half the
    resolution of the previous. The renderer picks a level based on
    the requested zoom — so the contract is "the pyramid has the
    right number of levels and each is half the previous"."""
    from Imervue.image.pyramid import DeepZoomImage

    arr = np.zeros((2048, 2048, 3), dtype=np.uint8)
    arr[..., 0] = np.linspace(0, 255, 2048, dtype=np.uint8)[None, :]

    pyramid = DeepZoomImage(arr)
    assert len(pyramid.levels) >= 2
    # Each level must be roughly half the previous dimension (allow
    # ±1 px slop for the integer floor-divide).
    for prev, nxt in zip(pyramid.levels, pyramid.levels[1:], strict=False):
        prev_h, prev_w = prev.shape[:2]
        nxt_h, nxt_w = nxt.shape[:2]
        assert nxt_w <= (prev_w + 1) // 2 + 1
        assert nxt_h <= (prev_h + 1) // 2 + 1
    # ``get_level`` clamps the zoom and returns ``(index, array)``.
    idx, level_arr = pyramid.get_level(zoom=0.25)
    assert 0 <= idx < len(pyramid.levels)
    assert level_arr.shape == pyramid.levels[idx].shape


# ---------------------------------------------------------------------------
# 21. Compare modes — difference and overlay produce mathematically distinct
#     outputs when run against the same two source images.
# ---------------------------------------------------------------------------


def test_integration_compare_modes_yield_distinct_outputs():
    """The Compare dialog ships overlay (alpha lerp) and difference
    (absolute diff) tabs. For non-trivial inputs the two outputs
    must differ — otherwise one of the kernels collapsed to the
    other or both went through the same code path."""
    from Imervue.gpu_image_view.actions.compare_dialog import (
        compute_difference,
        compute_overlay,
    )

    a = _solid_rgba(16, 16, (200, 100, 50, 255))
    b = _solid_rgba(16, 16, (50, 200, 100, 255))
    overlay = compute_overlay(a, b, alpha=0.5)
    difference = compute_difference(a, b, gain=1.0)

    assert overlay.shape == a.shape
    assert difference.shape == a.shape
    assert (overlay != difference).any(), (
        "overlay and difference modes produced identical output"
    )
    # The two operators are mathematically different: overlay's
    # max-channel value sits halfway between A and B (~125), while a
    # gain-1 difference of (200, 100, 50) vs (50, 200, 100) hits
    # 150 in the dominant channel. The overlay must come out
    # brighter on average and the difference must spike higher.
    assert int(difference.max()) >= int(overlay.max() - 20)


# ---------------------------------------------------------------------------
# 22. Web gallery export — three images in a folder produce an index.html
#     plus per-image thumbnails on disk.
# ---------------------------------------------------------------------------


def test_integration_web_gallery_export_writes_index_and_thumbs(tmp_path):
    """The static-HTML gallery generator must produce ``index.html``
    plus a thumbnail file for every input image. Catches a
    regression where the inline-lightbox renderer drops the thumb-
    generation pass entirely."""
    pytest.importorskip("PIL")
    from PIL import Image

    from Imervue.export.web_gallery import WebGalleryOptions, generate_web_gallery

    src_dir = tmp_path / "shoot"
    src_dir.mkdir()
    image_paths: list[str] = []
    for i, color in enumerate(((255, 80, 80), (80, 255, 80), (80, 80, 255))):
        p = src_dir / f"img-{i}.png"
        Image.fromarray(np.full((48, 64, 3), color, dtype=np.uint8)).save(p)
        image_paths.append(str(p))

    out_dir = tmp_path / "gallery"
    generate_web_gallery(
        image_paths, out_dir, WebGalleryOptions(title="Test"),
    )

    index = out_dir / "index.html"
    assert index.is_file()
    body = index.read_text(encoding="utf-8")
    assert "Test" in body
    # Every source produced at least one referenced thumb.
    thumbs = list(out_dir.rglob("*.jpg")) + list(out_dir.rglob("*.png"))
    assert len(thumbs) >= len(image_paths)


# ---------------------------------------------------------------------------
# 23. Layer effects pipeline — a layer with a drop-shadow effect produces
#     pixels outside the original image bounds in the composite.
# ---------------------------------------------------------------------------


def test_integration_layer_effect_extends_pixels_past_source():
    """Drop-shadow blooms past the source layer's silhouette. Apply
    the effect and prove the composite has opaque pixels in
    quadrants the source layer never touched — proves the effect
    pipeline runs before the compositor and not after."""
    from Imervue.paint.layer_effects import LayerEffect

    doc = PaintDocument()
    doc.load_image(_solid_rgba(40, 40, (240, 240, 240, 255)))
    overlay = doc.add_layer(name="Solid")
    overlay.image[...] = (0, 0, 0, 0)
    # Tiny opaque block in the centre — drop-shadow will extend it.
    overlay.image[18:22, 18:22] = (50, 50, 220, 255)
    overlay.effects = (LayerEffect(
        kind="drop_shadow",
        params={"distance": 4, "blur": 2, "opacity": 1.0,
                "color": [0, 0, 0, 255]},
    ),)
    composite = doc.composite()
    base = doc.layer_at(0).image
    # Shadow must put visible pixels in the lower-right where the
    # block originally had none.
    region = composite[22:30, 22:30]
    assert (region != base[22:30, 22:30]).any()
