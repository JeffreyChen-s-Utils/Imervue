"""
Tests for annotation_dialog — helpers, undo commands, and canvas behavior
that is reachable without a real user interaction.

Importing this module pulls in PySide6, so these tests use the ``qapp``
fixture from conftest.py.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from PySide6.QtGui import QImage, QUndoStack

from Imervue.gui.annotation_dialog import (
    AnnotationCanvas, AnnotationDialog, _AddAnnotationCommand,
    _DeleteAnnotationCommand, _ModifyAnnotationCommand,
    _point_segment_distance, pil_to_qimage, qimage_to_pil,
)
from Imervue.gui.annotation_models import Annotation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_pil():
    arr = np.full((100, 200, 4), 255, dtype=np.uint8)
    return Image.fromarray(arr, "RGBA")


@pytest.fixture
def canvas(qapp, base_pil):
    stack = QUndoStack()
    c = AnnotationCanvas(base_pil, stack)
    # Force a fixed size so coordinate mapping is deterministic
    c.resize(400, 200)
    return c


# ---------------------------------------------------------------------------
# QImage <-> PIL helpers
# ---------------------------------------------------------------------------

class TestQImagePilHelpers:
    def test_pil_to_qimage_dimensions(self, qapp):
        img = Image.new("RGBA", (50, 30), (255, 0, 0, 255))
        q = pil_to_qimage(img)
        assert q.width() == 50
        assert q.height() == 30
        assert q.format() == QImage.Format.Format_RGBA8888

    def test_pil_to_qimage_promotes_rgb(self, qapp):
        img = Image.new("RGB", (10, 10), (0, 255, 0))
        q = pil_to_qimage(img)
        assert q.width() == 10
        # Sample center pixel — green channel should be 255
        color = q.pixelColor(5, 5)
        assert color.green() == 255

    def test_round_trip_pil_qt_pil(self, qapp):
        arr = np.zeros((20, 20, 4), dtype=np.uint8)
        arr[..., 2] = 200
        arr[..., 3] = 255
        original = Image.fromarray(arr, "RGBA")
        q = pil_to_qimage(original)
        back = qimage_to_pil(q)
        assert back.size == original.size
        assert np.array_equal(np.array(back), arr)

    def test_pil_to_qimage_owns_buffer(self, qapp):
        """The QImage must survive after the source numpy buffer is gone."""
        img = Image.new("RGBA", (8, 8), (10, 20, 30, 255))
        q = pil_to_qimage(img)
        del img  # gc the source — qimage should still be valid
        assert q.pixelColor(0, 0).red() == 10


# ---------------------------------------------------------------------------
# _resize_points static method
# ---------------------------------------------------------------------------

class TestResizePoints:
    def test_e_handle_extends_right(self):
        out = AnnotationCanvas._resize_points([(10, 10), (50, 50)], "e", 20, 0)
        assert out == [(10, 10), (70, 50)]

    def test_w_handle_extends_left(self):
        out = AnnotationCanvas._resize_points([(10, 10), (50, 50)], "w", -5, 0)
        assert out == [(5, 10), (50, 50)]

    def test_n_handle_extends_up(self):
        out = AnnotationCanvas._resize_points([(10, 10), (50, 50)], "n", 0, -7)
        assert out == [(10, 3), (50, 50)]

    def test_s_handle_extends_down(self):
        out = AnnotationCanvas._resize_points([(10, 10), (50, 50)], "s", 0, 12)
        assert out == [(10, 10), (50, 62)]

    def test_se_corner_moves_diagonally(self):
        out = AnnotationCanvas._resize_points([(10, 10), (50, 50)], "se", 10, 5)
        assert out == [(10, 10), (60, 55)]

    def test_nw_corner_moves_diagonally(self):
        out = AnnotationCanvas._resize_points([(10, 10), (50, 50)], "nw", -3, -4)
        assert out == [(7, 6), (50, 50)]

    def test_ne_corner_moves_horizontally_and_vertically(self):
        out = AnnotationCanvas._resize_points([(10, 10), (50, 50)], "ne", 4, -2)
        assert out == [(10, 8), (54, 50)]

    def test_sw_corner_moves_horizontally_and_vertically(self):
        out = AnnotationCanvas._resize_points([(10, 10), (50, 50)], "sw", -3, 6)
        assert out == [(7, 10), (50, 56)]

    def test_freehand_keeps_middle_points(self):
        orig = [(10, 10), (20, 15), (30, 20), (50, 50)]
        out = AnnotationCanvas._resize_points(orig, "se", 5, 5)
        # Middle points untouched, only endpoints adjusted
        assert out[1] == (20, 15)
        assert out[2] == (30, 20)
        assert out[-1] == (55, 55)

    def test_single_point_returns_unchanged(self):
        out = AnnotationCanvas._resize_points([(10, 10)], "e", 5, 5)
        assert out == [(10, 10)]


# ---------------------------------------------------------------------------
# Coordinate mapping
# ---------------------------------------------------------------------------

class TestCoordinateMapping:
    def test_screen_image_round_trip(self, canvas):
        # Pick an image-coord point, convert to screen, convert back
        for ix, iy in [(0, 0), (50, 50), (199, 99), (100, 50)]:
            sp = canvas._image_to_screen(ix, iy)
            back = canvas._screen_to_image(sp.x(), sp.y())
            assert back == (ix, iy)

    def test_image_centered_in_widget(self, canvas):
        # 200x100 base in 400x200 widget → scale 2.0, fits exactly horizontally
        rect = canvas._display_rect()
        assert rect.width() == pytest.approx(400.0)
        assert rect.height() == pytest.approx(200.0)

    def test_screen_to_image_handles_negative_input(self, canvas):
        # Clicking outside the displayed image (e.g. above-left of the
        # display rect) shouldn't crash — points become negative which is
        # fine; PIL clips at draw time.
        result = canvas._screen_to_image(-50, -10)
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)


# ---------------------------------------------------------------------------
# Undo commands
# ---------------------------------------------------------------------------

class TestUndoCommands:
    def test_add_command(self, canvas):
        ann = Annotation(kind="rect", points=[(10, 10), (50, 50)])
        cmd = _AddAnnotationCommand(canvas, ann)
        cmd.redo()
        assert ann in canvas._annotations
        assert canvas._selected_id == ann.id

        cmd.undo()
        assert ann not in canvas._annotations
        assert canvas._selected_id is None

    def test_add_command_via_undo_stack(self, canvas):
        ann = Annotation(kind="rect", points=[(0, 0), (10, 10)])
        canvas._undo_stack.push(_AddAnnotationCommand(canvas, ann))
        assert len(canvas._annotations) == 1

        canvas._undo_stack.undo()
        assert len(canvas._annotations) == 0

        canvas._undo_stack.redo()
        assert len(canvas._annotations) == 1

    def test_delete_command_preserves_position(self, canvas):
        a = Annotation(kind="rect", points=[(0, 0), (10, 10)])
        b = Annotation(kind="rect", points=[(20, 20), (30, 30)])
        c = Annotation(kind="rect", points=[(40, 40), (50, 50)])
        canvas._annotations = [a, b, c]

        cmd = _DeleteAnnotationCommand(canvas, b)
        cmd.redo()
        assert canvas._annotations == [a, c]

        cmd.undo()
        # b restored at its original index
        assert canvas._annotations[1].id == b.id

    def test_modify_command_old_new_points(self, canvas):
        ann = Annotation(kind="rect", points=[(10, 10), (50, 50)])
        canvas._annotations = [ann]

        cmd = _ModifyAnnotationCommand(
            canvas, ann.id, [(10, 10), (50, 50)], [(20, 20), (60, 60)]
        )
        cmd.redo()
        assert ann.points == [(20, 20), (60, 60)]

        cmd.undo()
        assert ann.points == [(10, 10), (50, 50)]

    def test_modify_command_no_op_when_id_missing(self, canvas):
        cmd = _ModifyAnnotationCommand(
            canvas, "nonexistent", [(0, 0)], [(1, 1)]
        )
        # Should not crash on a missing id
        cmd.redo()
        cmd.undo()


# ---------------------------------------------------------------------------
# Canvas public API
# ---------------------------------------------------------------------------

class TestCanvasAPI:
    def test_set_color_updates_selected_annotation(self, canvas):
        ann = Annotation(kind="rect", points=[(0, 0), (10, 10)],
                         color=(255, 0, 0, 255))
        canvas._annotations = [ann]
        canvas._selected_id = ann.id
        canvas.set_color((0, 255, 0, 255))
        assert ann.color == (0, 255, 0, 255)

    def test_set_color_no_selection_only_changes_default(self, canvas):
        ann = Annotation(kind="rect", points=[(0, 0), (10, 10)],
                         color=(255, 0, 0, 255))
        canvas._annotations = [ann]
        canvas.set_color((0, 0, 255, 255))
        assert ann.color == (255, 0, 0, 255)  # untouched
        assert canvas._color == (0, 0, 255, 255)

    def test_set_stroke_width_clamps_to_at_least_one(self, canvas):
        canvas.set_stroke_width(0)
        assert canvas._stroke_width == 1
        canvas.set_stroke_width(-5)
        assert canvas._stroke_width == 1

    def test_set_tool_clears_selection(self, canvas):
        ann = Annotation(kind="rect", points=[(0, 0), (10, 10)])
        canvas._annotations = [ann]
        canvas._selected_id = ann.id
        canvas.set_tool("rect")
        assert canvas._selected_id is None

    def test_set_annotations_clears_undo(self, canvas):
        canvas._undo_stack.push(
            _AddAnnotationCommand(
                canvas, Annotation(kind="rect", points=[(0, 0), (1, 1)])
            )
        )
        assert canvas._undo_stack.count() == 1

        canvas.set_annotations([
            Annotation(kind="ellipse", points=[(0, 0), (5, 5)]),
        ])
        assert canvas._undo_stack.count() == 0
        assert len(canvas._annotations) == 1

    def test_get_annotations_returns_copy(self, canvas):
        ann = Annotation(kind="rect", points=[(0, 0), (10, 10)])
        canvas._annotations = [ann]
        out = canvas.get_annotations()
        out.append(Annotation(kind="rect"))
        # Mutating the returned list must not affect the canvas
        assert len(canvas._annotations) == 1


# ---------------------------------------------------------------------------
# Hit testing
# ---------------------------------------------------------------------------

class TestHitTesting:
    def test_hit_inside_rect(self, canvas):
        ann = Annotation(kind="rect", points=[(50, 25), (150, 75)])
        canvas._annotations = [ann]
        # 200x100 image in 400x200 widget at scale 2.0, no offset
        # → image (100, 50) is screen (200, 100)
        sp = canvas._image_to_screen(100, 50)
        hit = canvas._hit_annotation(sp)
        assert hit is not None
        assert hit.id == ann.id

    def test_hit_misses_outside_rect(self, canvas):
        ann = Annotation(kind="rect", points=[(50, 25), (60, 30)])
        canvas._annotations = [ann]
        # Far away from the rect
        sp = canvas._image_to_screen(180, 90)
        hit = canvas._hit_annotation(sp)
        assert hit is None

    def test_topmost_annotation_wins(self, canvas):
        a = Annotation(kind="rect", points=[(0, 0), (100, 100)])
        b = Annotation(kind="rect", points=[(40, 40), (60, 60)])
        canvas._annotations = [a, b]
        sp = canvas._image_to_screen(50, 50)
        hit = canvas._hit_annotation(sp)
        # b is later in the list → drawn on top → should win the hit
        assert hit.id == b.id

    def test_diagonal_line_hit_only_near_line(self, canvas):
        ann = Annotation(
            kind="line", points=[(10, 10), (190, 90)], stroke_width=3,
        )
        canvas._annotations = [ann]
        # Point near the middle of the line — roughly on the segment
        sp_on = canvas._image_to_screen(100, 50)
        assert canvas._hit_annotation(sp_on) is ann
        # Point inside the bounding box but far from the line segment
        sp_off = canvas._image_to_screen(180, 15)
        assert canvas._hit_annotation(sp_off) is None

    def test_arrow_hit_uses_segment_distance(self, canvas):
        ann = Annotation(
            kind="arrow", points=[(0, 0), (200, 100)], stroke_width=3,
        )
        canvas._annotations = [ann]
        # On the diagonal
        sp_on = canvas._image_to_screen(100, 50)
        assert canvas._hit_annotation(sp_on) is ann
        # Far from the diagonal
        sp_off = canvas._image_to_screen(190, 5)
        assert canvas._hit_annotation(sp_off) is None

    def test_freehand_hit_on_path(self, canvas):
        ann = Annotation(
            kind="freehand",
            points=[(20, 20), (40, 30), (60, 40), (80, 50)],
            stroke_width=3,
        )
        canvas._annotations = [ann]
        # Near a middle segment
        sp_on = canvas._image_to_screen(50, 35)
        assert canvas._hit_annotation(sp_on) is ann
        # Far from every segment but still inside bounding box
        sp_off = canvas._image_to_screen(80, 20)
        assert canvas._hit_annotation(sp_off) is None


class TestPointSegmentDistance:
    def test_point_on_segment(self):
        d = _point_segment_distance(5, 5, (0, 0), (10, 10))
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_perpendicular_distance(self):
        d = _point_segment_distance(0, 5, (0, 0), (10, 0))
        assert d == pytest.approx(5.0)

    def test_past_endpoint_clamps_to_endpoint(self):
        # Point beyond segment end — distance is to the nearer endpoint
        d = _point_segment_distance(20, 0, (0, 0), (10, 0))
        assert d == pytest.approx(10.0)

    def test_degenerate_segment(self):
        d = _point_segment_distance(3, 4, (0, 0), (0, 0))
        assert d == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Dialog smoke test
# ---------------------------------------------------------------------------

class TestAnnotationDialogSmoke:
    def test_constructs_without_crash(self, qapp, base_pil):
        dlg = AnnotationDialog(base_pil, source_path="")
        try:
            assert dlg._canvas is not None
            # Toolbar built
            assert hasattr(dlg, "_tool_buttons")
            assert "select" in dlg._tool_buttons
        finally:
            dlg.deleteLater()

    def test_baked_image_with_no_annotations_matches_base(
        self, qapp, base_pil
    ):
        dlg = AnnotationDialog(base_pil, source_path="")
        try:
            baked = dlg._baked_image()
            assert baked.size == base_pil.size
            assert np.array_equal(np.array(baked), np.array(base_pil))
        finally:
            dlg.deleteLater()

    def test_baked_image_includes_annotation(self, qapp, base_pil):
        dlg = AnnotationDialog(base_pil, source_path="")
        try:
            ann = Annotation(
                kind="rect", points=[(20, 20), (60, 40)],
                color=(255, 0, 0, 255), filled=True,
            )
            dlg._canvas._annotations = [ann]
            baked = np.array(dlg._baked_image())
            # Pixel inside the rect should be red
            assert baked[30, 40, 0] == 255
            assert baked[30, 40, 1] == 0
        finally:
            dlg.deleteLater()


# ---------------------------------------------------------------------------
# Save behavior — atomic write, callback, format conversion
# ---------------------------------------------------------------------------

class TestDialogSaveBehavior:
    def test_write_png_round_trip(self, qapp, base_pil, tmp_path):
        dlg = AnnotationDialog(base_pil, source_path="")
        try:
            dlg._canvas._annotations = [
                Annotation(
                    kind="rect", points=[(10, 10), (40, 40)],
                    color=(0, 255, 0, 255), filled=True,
                )
            ]
            target = tmp_path / "out.png"
            dlg._write(str(target))

            assert target.exists()
            # Tmp file must have been removed (atomic replace cleanup)
            assert not (tmp_path / "out.png.tmp").exists()

            loaded = np.array(Image.open(target).convert("RGBA"))
            assert loaded[20, 20, 1] == 255
        finally:
            dlg.deleteLater()

    def test_write_jpeg_strips_alpha(self, qapp, base_pil, tmp_path):
        dlg = AnnotationDialog(base_pil, source_path="")
        try:
            target = tmp_path / "out.jpg"
            dlg._write(str(target))
            assert target.exists()
            loaded = Image.open(target)
            assert loaded.mode == "RGB"
            assert loaded.size == base_pil.size
        finally:
            dlg.deleteLater()

    def test_on_saved_called_when_saving_to_source(
        self, qapp, base_pil, tmp_path
    ):
        target = tmp_path / "src.png"
        base_pil.save(target)

        called: list = []
        dlg = AnnotationDialog(
            base_pil,
            source_path=str(target),
            on_saved=called.append,
        )
        try:
            dlg._write(str(target))
            assert called == [str(target)]
        finally:
            dlg.deleteLater()

    def test_on_saved_not_called_for_save_as_to_different_path(
        self, qapp, base_pil, tmp_path
    ):
        source = tmp_path / "src.png"
        other = tmp_path / "other.png"
        base_pil.save(source)

        called: list = []
        dlg = AnnotationDialog(
            base_pil,
            source_path=str(source),
            on_saved=called.append,
        )
        try:
            # Saving to a different path is "Save As" — viewer reload would
            # be wrong because the source file wasn't touched.
            dlg._write(str(other))
            assert called == []
            assert other.exists()
        finally:
            dlg.deleteLater()

    def test_save_project_round_trip(self, qapp, base_pil, tmp_path):
        dlg = AnnotationDialog(base_pil, source_path="")
        try:
            dlg._canvas._annotations = [
                Annotation(kind="rect", points=[(5, 5), (25, 25)]),
                Annotation(kind="text", points=[(50, 50)], text="hi"),
            ]
            project_path = tmp_path / "test.imervue_annot.json"

            from Imervue.gui.annotation_models import AnnotationProject
            base = dlg._canvas.get_base_pil()
            project = AnnotationProject(
                source_path="",
                source_size=(base.width, base.height),
                annotations=dlg._canvas.get_annotations(),
            )
            project.save(project_path)

            # Load it back into a fresh dialog and verify
            dlg2 = AnnotationDialog(base_pil, source_path="")
            try:
                loaded = AnnotationProject.load(project_path)
                dlg2._canvas.set_annotations(loaded.annotations)
                anns = dlg2._canvas.get_annotations()
                assert len(anns) == 2
                assert anns[0].kind == "rect"
                assert anns[1].text == "hi"
            finally:
                dlg2.deleteLater()
        finally:
            dlg.deleteLater()
