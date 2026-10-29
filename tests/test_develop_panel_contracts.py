"""Contracts of the Modify develop panel that the module split must keep.

Pins the tool selection, drawing-property handlers, crop / save reloads,
navigation, deletion, slider handlers and commit guard of
:class:`~Imervue.gui.develop_panel.DevelopPanel`, and that the module-level
``recipe_store`` patched on ``develop_panel`` still reaches every writer.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QColorDialog, QWidget

from Imervue.image.recipe import Recipe
from tests import test_develop_panel as shared

main_window = shared.main_window
panel = shared.panel
real_image = shared.real_image
sample_file = shared.sample_file
pytestmark = pytest.mark.gui


@pytest.fixture
def opened(monkeypatch):
    """Record every viewer reload the panel asks ``open_path`` for."""
    from Imervue.gpu_image_view.images import image_loader
    calls: list[str] = []
    monkeypatch.setattr(image_loader, "open_path",
                        lambda main_gui, path: calls.append(path))
    return calls


class _Canvas:
    """Records the drawing-state setters the panel forwards to a canvas."""

    def __init__(self):
        self.calls: list[tuple] = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, *args))


def test_panel_class_keeps_its_import_path_and_qt_base():
    from Imervue.gui import develop_panel
    assert develop_panel.DevelopPanel.__module__ == "Imervue.gui.develop_panel"
    mro = develop_panel.DevelopPanel.__mro__
    # Every mixin precedes the Qt base so its methods win over QWidget's.
    assert all(not issubclass(cls, QWidget) for cls in mro[1:mro.index(QWidget)])
    for name in ("_rebind_target_after_delete", "recipe_store", "logger"):
        assert hasattr(develop_panel, name)


class TestToolSelection:
    def test_current_tool_defaults_to_select_when_nothing_is_checked(self, panel):
        p, _ = panel
        for btn in p._tool_buttons.values():
            btn.setChecked(False)
        assert p._current_tool() == "select"

    def test_current_brush_defaults_to_pen_when_nothing_is_checked(self, panel):
        p, _ = panel
        for btn in p._brush_buttons.values():
            btn.setChecked(False)
        assert p._current_brush() == "pen"

    def test_drawing_tool_opens_the_annotation_properties(self, panel):
        p, _ = panel
        p._property_tabs.setCurrentIndex(0)
        p._set_tool("rect")
        assert p._property_tabs.currentIndex() == 1
        assert p._current_tool() == "rect"
        assert [k for k, b in p._tool_buttons.items() if b.isChecked()] == ["rect"]

    @pytest.mark.parametrize("tool", ["select", "crop"])
    def test_select_and_crop_keep_the_current_property_page(self, panel, tool):
        p, _ = panel
        p._property_tabs.setCurrentIndex(0)
        p._set_tool(tool)
        assert p._property_tabs.currentIndex() == 0

    def test_crop_tool_shows_the_crop_controls_and_sets_the_ratio(self, panel, real_image):
        p, _ = panel
        p.bind_to_path(str(real_image))
        p._crop_ratio_combo.setCurrentIndex(1)       # 1 : 1
        p._set_tool("crop")
        assert p._crop_widget.isVisibleTo(p._crop_widget.parentWidget())
        assert p._canvas.current_tool() == "crop"
        p._set_tool("select")
        assert not p._crop_widget.isVisibleTo(p._crop_widget.parentWidget())

    def test_ratio_change_reaches_the_canvas(self, panel, monkeypatch):
        p, _ = panel
        canvas = _Canvas()
        p._canvas = canvas
        p._crop_ratio_combo.setCurrentIndex(2)       # 4 : 3 (signal fires the handler)
        p._on_crop_ratio_changed(2)
        assert ("set_crop_ratio", 4, 3) in canvas.calls
        p._canvas = None
        p._on_crop_ratio_changed(0)                  # no canvas: no error

    def test_cancel_crop_clears_it_and_returns_to_select(self, panel, real_image):
        p, _ = panel
        p.bind_to_path(str(real_image))
        p._set_tool("crop")
        p._canvas._crop_rect = (1, 1, 20, 20)
        p._cancel_crop()
        assert p._canvas.get_crop_rect() is None
        assert p._current_tool() == "select"

    def test_cancel_crop_without_a_canvas_still_selects(self, panel):
        p, _ = panel
        p._set_tool("crop")
        p._cancel_crop()
        assert p._current_tool() == "select"


class TestDrawingProperties:
    def test_picked_colour_updates_state_button_and_canvas(self, panel, monkeypatch):
        p, _ = panel
        canvas = _Canvas()
        p._canvas = canvas
        monkeypatch.setattr(QColorDialog, "getColor",
                            lambda *_a, **_k: QColor(10, 20, 30, 40))
        p._pick_color()
        assert p._draw_color == (10, 20, 30, 40)
        assert "rgba(10,20,30,40)" in p._color_btn.styleSheet()
        assert "#fff" in p._color_btn.styleSheet()
        assert ("set_color", (10, 20, 30, 40)) in canvas.calls
        p._canvas = None

    def test_cancelled_colour_dialog_changes_nothing(self, panel, monkeypatch):
        p, _ = panel
        monkeypatch.setattr(QColorDialog, "getColor", lambda *_a, **_k: QColor())
        p._pick_color()
        assert p._draw_color == (255, 0, 0, 255)

    def test_bright_colour_gets_dark_text(self, panel):
        p, _ = panel
        p._draw_color = (200, 200, 200, 255)
        p._update_color_button_style()
        assert "#000" in p._color_btn.styleSheet()

    def test_brush_and_font_handlers_forward_to_the_canvas(self, panel):
        p, _ = panel
        canvas = _Canvas()
        p._canvas = canvas
        p._on_brush_selected("marker")
        p._on_font_changed(QFont("Arial"))
        p._on_font_size_changed(31)
        assert ("set_brush_type", "marker") in canvas.calls
        assert ("set_font_family", "Arial") in canvas.calls
        assert ("set_font_size", 31) in canvas.calls
        p._canvas = None
        p._on_brush_selected("pen")
        p._on_font_changed(QFont("Arial"))
        p._on_font_size_changed(12)


class TestOrientationAndSliders:
    def test_orientation_needs_a_bound_image(self, panel):
        p, _ = panel
        p._rotate(1)
        p._flip_h()
        p._flip_v()
        p._reset()
        assert p._current.is_identity()

    def test_rotate_wraps_and_flips_toggle(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        p._rotate(-1)
        assert p._current.rotate_steps == 3
        p._flip_h()
        p._flip_v()
        assert p._current.flip_h and p._current.flip_v
        p._flip_h()
        assert not p._current.flip_h

    def test_advanced_handler_writes_its_field_unless_suppressed(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        handler = p._make_advanced_handler("vibrance")
        handler(35)
        assert p._current.vibrance == pytest.approx(0.35)
        assert "+35" in p._adv_labels["vibrance"].text()
        p._suppress_signals = True
        handler(-50)
        p._suppress_signals = False
        assert p._current.vibrance == pytest.approx(0.35)

    @pytest.mark.parametrize("handler, field", [
        ("_on_exposure", "exposure"), ("_on_brightness", "brightness"),
        ("_on_contrast", "contrast"), ("_on_saturation", "saturation"),
    ])
    def test_basic_handlers_respect_suppression(self, panel, sample_file, handler, field):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        getattr(p, handler)(25)
        assert getattr(p._current, field) == pytest.approx(0.25)
        p._suppress_signals = True
        getattr(p, handler)(-60)
        p._suppress_signals = False
        assert getattr(p._current, field) == pytest.approx(0.25)

    def test_set_enabled_toggles_every_interactive_widget(self, panel):
        p, _ = panel
        p._set_enabled(True)
        assert all(w.isEnabled() for w in p._interactive_widgets)
        p._set_enabled(False)
        assert not any(w.isEnabled() for w in p._interactive_widgets)


class TestCommitGuard:
    def test_commit_in_flight_does_not_emit_again(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        emitted = []
        p.recipe_committed.connect(lambda *a: emitted.append(a))
        p._current.exposure = 0.3
        p._committing = True
        p._commit_recipe()
        p._committing = False
        assert emitted == []
        p._commit_recipe()
        assert len(emitted) == 1
        assert emitted[0][0] == str(sample_file)

    def test_step_edit_without_a_bound_image_is_a_noop(self, panel):
        p, _ = panel
        p.step_edit(True)
        p.step_edit(False)
        assert p._current.is_identity()


class TestOverwriteReloads:
    """Crop and save bake the recipe into the file, reset it and reload the viewer."""

    def test_crop_resets_the_patched_store_and_reloads(self, panel, real_image, opened):
        p, store = panel
        store.set_for_path(str(real_image), Recipe(brightness=0.2))
        p.bind_to_path(str(real_image))
        p._canvas._crop_rect = (0, 0, 50, 40)
        p._apply_crop()
        assert store.get_for_path(str(real_image)) in (None, Recipe())
        assert p._committed.is_identity() and p._current.is_identity()
        assert opened == [str(real_image)]
        p._main_gui._clear_deep_zoom.assert_called_once_with()
        assert p._canvas_source_path == str(real_image)
        assert p._canvas.get_crop_rect() is None

    def test_crop_without_a_region_writes_nothing(self, panel, real_image, opened):
        p, _ = panel
        p.bind_to_path(str(real_image))
        before = real_image.read_bytes()
        p._apply_crop()
        assert real_image.read_bytes() == before
        assert opened == []

    def test_crop_without_a_canvas_is_a_noop(self, panel, opened):
        p, _ = panel
        p._apply_crop()
        p._save_annotation()
        assert opened == []

    def test_viewer_reload_failure_is_logged_not_raised(self, panel, real_image,
                                                        monkeypatch, caplog):
        from Imervue.gpu_image_view.images import image_loader

        def _boom(main_gui, path):
            raise RuntimeError("viewer gone")

        monkeypatch.setattr(image_loader, "open_path", _boom)
        p, _ = panel
        p.bind_to_path(str(real_image))
        p._canvas._crop_rect = (0, 0, 50, 40)
        with caplog.at_level("ERROR", logger="Imervue.develop_panel"):
            p._apply_crop()
        assert "Viewer reload after crop failed" in caplog.text
        caplog.clear()
        with caplog.at_level("ERROR", logger="Imervue.develop_panel"):
            p._save_annotation()
        assert "Viewer reload after annotation save failed" in caplog.text

    def test_save_resets_the_patched_store_and_reloads(self, panel, real_image, opened):
        p, store = panel
        store.set_for_path(str(real_image), Recipe(contrast=0.3))
        p.bind_to_path(str(real_image))
        p._save_annotation()
        assert store.get_for_path(str(real_image)) in (None, Recipe())
        assert p._current.is_identity()
        assert opened == [str(real_image)]

    def test_cannot_overwrite_warning_needs_a_window_toast(self, panel, monkeypatch):
        p, _ = panel
        monkeypatch.setattr(p, "_main_gui", SimpleNamespace(main_window=None))
        p._warn_cannot_overwrite()                    # no toast: silently skipped


class TestNavigationAndDelete:
    def test_navigation_direction_picks_next_or_previous(self, panel, real_image, monkeypatch):
        from Imervue.gpu_image_view.actions import select
        p, _ = panel
        moves = []
        monkeypatch.setattr(select, "switch_to_next_image",
                            lambda main_gui: moves.append("next"))
        monkeypatch.setattr(select, "switch_to_previous_image",
                            lambda main_gui: moves.append("prev"))
        p._main_gui.model.images = [str(real_image)]
        p._main_gui.current_index = 0
        p._on_navigate_image(1)
        p._on_navigate_image(-1)
        p._on_navigate_image(0)
        assert moves == ["next", "prev", "prev"]
        assert p._path == str(real_image)
        p._main_gui.current_index = 4
        p._on_navigate_image(1)
        assert p._path is None

    def test_delete_rebinds_to_the_next_survivor(self, panel, real_image, tmp_path, monkeypatch):
        from Imervue.gpu_image_view.actions import delete
        p, _ = panel
        other = tmp_path / "other.png"
        other.write_bytes(real_image.read_bytes())
        viewer = p._main_gui
        viewer.model.images = [str(real_image), str(other)]
        viewer.current_index = 0

        def _delete(v):
            v.model.images = [str(other)]

        monkeypatch.setattr(delete, "delete_current_image", _delete)
        p.bind_to_path(str(real_image))
        p._delete_current_image()
        assert p._path == str(other)
        viewer.makeCurrent.assert_called()
        viewer.doneCurrent.assert_called()

    def test_delete_out_of_range_does_nothing(self, panel, real_image, monkeypatch):
        from Imervue.gpu_image_view.actions import delete
        p, _ = panel
        monkeypatch.setattr(delete, "delete_current_image",
                            lambda _v: pytest.fail("must not delete"))
        p._main_gui.model.images = []
        p._main_gui.current_index = 0
        p.bind_to_path(str(real_image))
        p._delete_current_image()
        assert p._path == str(real_image)
