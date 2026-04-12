"""
Tests for annotation_models — data model + headless PIL bake.

These tests deliberately avoid importing annotation_dialog (which pulls in
PySide6) so they run in any environment, including CI containers without a
display server.
"""
import json

import numpy as np
import pytest
from PIL import Image

from Imervue.gui.annotation_models import (
    ALL_KINDS, Annotation, AnnotationProject, bake,
)


# ---------------------------------------------------------------------------
# Annotation dataclass
# ---------------------------------------------------------------------------

class TestAnnotationModel:
    def test_default_id_is_unique(self):
        a = Annotation(kind="rect")
        b = Annotation(kind="rect")
        assert a.id != b.id
        assert len(a.id) == 12

    def test_to_from_dict_round_trip(self):
        ann = Annotation(
            kind="arrow",
            points=[(10, 20), (100, 80)],
            color=(0, 128, 255, 200),
            stroke_width=5,
            text="hello",
            font_size=18,
            block_size=8,
            blur_radius=12,
        )
        restored = Annotation.from_dict(ann.to_dict())
        assert restored.kind == ann.kind
        assert restored.points == ann.points
        assert restored.color == ann.color
        assert restored.stroke_width == ann.stroke_width
        assert restored.text == ann.text
        assert restored.font_size == ann.font_size
        assert restored.block_size == ann.block_size
        assert restored.blur_radius == ann.blur_radius
        assert restored.id == ann.id

    def test_from_dict_supplies_id_when_missing(self):
        d = {"kind": "rect", "points": [[1, 2], [3, 4]]}
        a = Annotation.from_dict(d)
        assert a.id  # auto-generated
        assert a.points == [(1, 2), (3, 4)]

    def test_bounding_box_normalized(self):
        a = Annotation(kind="rect", points=[(50, 80), (10, 20)])
        assert a.bounding_box() == (10, 20, 50, 80)
        assert a.normalized_rect() == (10, 20, 40, 60)

    def test_bounding_box_empty(self):
        a = Annotation(kind="rect", points=[])
        assert a.bounding_box() == (0, 0, 0, 0)

    def test_all_kinds_has_eight_entries(self):
        # If a new kind is added, the bake() dispatch + tests need updating.
        assert len(ALL_KINDS) == 8


# ---------------------------------------------------------------------------
# AnnotationProject serialization
# ---------------------------------------------------------------------------

class TestAnnotationProject:
    def test_round_trip_in_memory(self):
        proj = AnnotationProject(
            source_path="C:/foo/bar.png",
            source_size=(640, 480),
            annotations=[
                Annotation(kind="rect", points=[(0, 0), (10, 10)]),
                Annotation(kind="text", points=[(5, 5)], text="hi"),
            ],
        )
        restored = AnnotationProject.from_dict(proj.to_dict())
        assert restored.version == 1
        assert restored.source_path == proj.source_path
        assert restored.source_size == proj.source_size
        assert len(restored.annotations) == 2
        assert restored.annotations[0].kind == "rect"
        assert restored.annotations[1].text == "hi"

    def test_save_load_disk(self, tmp_path):
        path = tmp_path / "proj.imervue_annot.json"
        proj = AnnotationProject(
            source_path=str(tmp_path / "src.png"),
            source_size=(100, 100),
            annotations=[Annotation(kind="ellipse", points=[(10, 10), (50, 60)])],
        )
        proj.save(path)
        assert path.exists()

        loaded = AnnotationProject.load(path)
        assert loaded.source_size == (100, 100)
        assert len(loaded.annotations) == 1
        assert loaded.annotations[0].kind == "ellipse"
        assert loaded.annotations[0].points == [(10, 10), (50, 60)]

    def test_loaded_json_has_version_field(self, tmp_path):
        path = tmp_path / "proj.json"
        AnnotationProject(annotations=[]).save(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert "annotations" in data
        assert "source_size" in data


# ---------------------------------------------------------------------------
# bake() — headless rendering
# ---------------------------------------------------------------------------

@pytest.fixture
def blank_image():
    """200x150 white RGBA image."""
    arr = np.full((150, 200, 4), 255, dtype=np.uint8)
    return Image.fromarray(arr, "RGBA")


class TestBake:
    def test_no_annotations_returns_equivalent_image(self, blank_image):
        out = bake(blank_image, [])
        assert out.size == blank_image.size
        assert out.mode == "RGBA"
        # Pixels unchanged
        assert np.array_equal(np.array(out), np.array(blank_image))

    def test_does_not_modify_input(self, blank_image):
        original = np.array(blank_image).copy()
        bake(
            blank_image,
            [Annotation(kind="rect", points=[(10, 10), (50, 50)],
                        color=(255, 0, 0, 255), filled=True)],
        )
        # Source untouched
        assert np.array_equal(np.array(blank_image), original)

    def test_filled_rect_changes_pixels_inside_box(self, blank_image):
        ann = Annotation(
            kind="rect",
            points=[(20, 20), (60, 60)],
            color=(255, 0, 0, 255),
            filled=True,
        )
        out = np.array(bake(blank_image, [ann]))
        # Center of the rect should be red
        cx, cy = 40, 40
        assert out[cy, cx, 0] == 255
        assert out[cy, cx, 1] == 0
        assert out[cy, cx, 2] == 0
        # A point well outside should still be white
        assert tuple(out[5, 5]) == (255, 255, 255, 255)

    def test_outline_rect_leaves_interior_unchanged(self, blank_image):
        ann = Annotation(
            kind="rect",
            points=[(20, 20), (80, 80)],
            color=(0, 255, 0, 255),
            stroke_width=2,
            filled=False,
        )
        out = np.array(bake(blank_image, [ann]))
        # Center should still be white
        assert tuple(out[50, 50]) == (255, 255, 255, 255)
        # Edge pixel should be green-ish
        assert out[20, 50, 1] > 0

    def test_mosaic_destroys_information(self):
        # Build a base with a sharp gradient so mosaic is observable
        arr = np.zeros((40, 40, 4), dtype=np.uint8)
        for x in range(40):
            arr[:, x, 0] = x * 6  # 0..234
        arr[:, :, 3] = 255
        base = Image.fromarray(arr, "RGBA")
        ann = Annotation(
            kind="mosaic",
            points=[(0, 0), (40, 40)],
            block_size=10,
        )
        out = np.array(bake(base, [ann]))
        # Within a single 10-px block, all red values should be equal
        block = out[5:10, 5:10, 0]
        assert np.all(block == block[0, 0])

    def test_blur_softens_edge(self):
        arr = np.zeros((40, 40, 4), dtype=np.uint8)
        arr[:, :20, 0] = 255  # left half red, right half black
        arr[:, :, 3] = 255
        base = Image.fromarray(arr, "RGBA")
        ann = Annotation(
            kind="blur",
            points=[(0, 0), (40, 40)],
            blur_radius=5,
        )
        out = np.array(bake(base, [ann]))
        # The pixel right at the edge boundary should be neither pure red
        # nor pure black after blurring.
        edge = out[20, 20, 0]
        assert 0 < edge < 255

    def test_text_annotation_no_crash_on_empty_text(self, blank_image):
        # Empty text should be a no-op, not a crash
        ann = Annotation(kind="text", points=[(10, 10)], text="")
        out = bake(blank_image, [ann])
        assert np.array_equal(np.array(out), np.array(blank_image))

    def test_arrow_requires_two_points(self, blank_image):
        # Single-point arrow is a degenerate case — must not crash
        ann = Annotation(kind="arrow", points=[(10, 10)])
        out = bake(blank_image, [ann])
        assert out.size == blank_image.size

    def test_freehand_under_two_points(self, blank_image):
        # Freehand with one point should be a no-op
        ann = Annotation(kind="freehand", points=[(10, 10)])
        out = bake(blank_image, [ann])
        assert np.array_equal(np.array(out), np.array(blank_image))

    def test_destructive_then_overlay_order(self):
        """Mosaic must run before overlay strokes — otherwise the stroke
        gets pixelated, which would be wrong."""
        arr = np.full((40, 40, 4), 255, dtype=np.uint8)
        base = Image.fromarray(arr, "RGBA")
        annotations = [
            # Note: declared in stroke-then-mosaic order. bake() must still
            # apply the mosaic first so the stroke survives intact.
            Annotation(kind="rect", points=[(10, 10), (30, 30)],
                       color=(0, 0, 255, 255), stroke_width=2, filled=False),
            Annotation(kind="mosaic", points=[(0, 0), (40, 40)], block_size=4),
        ]
        out = np.array(bake(base, annotations))
        # Edge of the rect should still show blue — proves the stroke
        # was drawn after mosaic.
        edge_blue = out[10, 20, 2]
        assert edge_blue > 100

    def test_input_grayscale_is_promoted_to_rgba(self):
        gray = Image.fromarray(np.full((20, 20), 128, dtype=np.uint8), mode="L")
        out = bake(gray, [])
        assert out.mode == "RGBA"
        assert out.size == (20, 20)

    def test_mosaic_block_larger_than_region_does_not_crash(self, blank_image):
        # User picks block_size larger than the rect — degenerate but
        # PIL must still produce a valid output.
        ann = Annotation(
            kind="mosaic",
            points=[(10, 10), (15, 15)],
            block_size=100,
        )
        out = bake(blank_image, [ann])
        assert out.size == blank_image.size

    def test_mosaic_outside_image_clipped(self, blank_image):
        # Annotation extends past the image bounds — must clamp, not crash
        ann = Annotation(
            kind="mosaic",
            points=[(150, 100), (500, 500)],
            block_size=10,
        )
        out = bake(blank_image, [ann])
        assert out.size == blank_image.size

    def test_blur_zero_size_region_is_noop(self, blank_image):
        # Zero-area mosaic/blur should be skipped silently
        ann = Annotation(
            kind="blur",
            points=[(50, 50), (50, 50)],
            blur_radius=5,
        )
        out = bake(blank_image, [ann])
        assert np.array_equal(np.array(out), np.array(blank_image))

    def test_filled_ellipse_marks_center(self, blank_image):
        ann = Annotation(
            kind="ellipse",
            points=[(20, 20), (80, 80)],
            color=(0, 0, 255, 255),
            filled=True,
        )
        out = np.array(bake(blank_image, [ann]))
        # Center of the ellipse should be blue
        assert out[50, 50, 2] == 255
        assert out[50, 50, 0] == 0

    def test_arrow_draws_line_and_head(self, blank_image):
        ann = Annotation(
            kind="arrow",
            points=[(10, 50), (180, 50)],
            color=(255, 0, 0, 255),
            stroke_width=4,
        )
        out = np.array(bake(blank_image, [ann]))
        # Some pixel along the arrow should be red
        assert (out[48:53, 100, 0] == 255).any()
        # The tip area should have red pixels
        assert (out[45:55, 175:181, 0] == 255).any()

    def test_arrow_zero_length_does_not_crash(self, blank_image):
        ann = Annotation(kind="arrow", points=[(50, 50), (50, 50)])
        out = bake(blank_image, [ann])
        assert out.size == blank_image.size

    def test_multiple_annotations_layer_correctly(self, blank_image):
        # Two filled rects — second should win in the overlap region
        red = Annotation(
            kind="rect", points=[(10, 10), (60, 60)],
            color=(255, 0, 0, 255), filled=True,
        )
        green = Annotation(
            kind="rect", points=[(40, 40), (90, 90)],
            color=(0, 255, 0, 255), filled=True,
        )
        out = np.array(bake(blank_image, [red, green]))
        # Inside both: green wins (drawn after red)
        assert out[50, 50, 1] == 255
        assert out[50, 50, 0] == 0
        # Inside red only
        assert out[20, 20, 0] == 255
        # Inside green only
        assert out[80, 80, 1] == 255

    def test_freehand_with_many_points_renders(self, blank_image):
        pts = [(10 + i * 2, 10 + i) for i in range(40)]
        ann = Annotation(
            kind="freehand", points=pts,
            color=(255, 0, 255, 255), stroke_width=3,
        )
        out = np.array(bake(blank_image, [ann]))
        # Some pixel along the path should be magenta-ish
        assert (out[..., 0] == 255).any()
        assert (out[..., 2] == 255).any()


# ---------------------------------------------------------------------------
# Project loading edge cases
# ---------------------------------------------------------------------------

class TestProjectLoadEdgeCases:
    def test_load_missing_optional_fields(self, tmp_path):
        path = tmp_path / "minimal.json"
        path.write_text('{"annotations": []}', encoding="utf-8")
        proj = AnnotationProject.load(path)
        assert proj.version == 1
        assert proj.annotations == []
        assert proj.source_path == ""

    def test_load_unknown_extra_fields_ignored(self, tmp_path):
        # Forward-compat: unknown fields shouldn't crash the loader
        path = tmp_path / "extras.json"
        path.write_text(
            '{"version": 1, "annotations": [], "future_field": "ignored"}',
            encoding="utf-8",
        )
        proj = AnnotationProject.load(path)
        assert proj.annotations == []

    def test_annotation_from_dict_with_legacy_minimal(self):
        d = {"kind": "rect"}
        a = Annotation.from_dict(d)
        assert a.kind == "rect"
        assert a.points == []
        assert a.color == (255, 0, 0, 255)  # default
        assert a.stroke_width == 3
