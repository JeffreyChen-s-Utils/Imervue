"""Tests for Imervue.gui.develop_panel.DevelopPanel.

We construct the panel with a stub main_gui that satisfies the minimum
attribute surface the panel touches: ``main_window`` (any QObject-ish
parent) and ``reload_current_image_with_recipe`` which the undo command
path would normally call.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QSplitter

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import RecipeStore


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def main_window(qapp):
    mw = QMainWindow()
    yield mw
    mw.close()


@pytest.fixture
def panel(main_window, monkeypatch, tmp_path):
    """DevelopPanel bound to a temporary RecipeStore.

    We monkeypatch the module-level ``recipe_store`` singleton so panel
    writes go to a tmp file and don't pollute the user's real store.
    """
    from Imervue.gui import develop_panel as develop_panel_mod

    isolated = RecipeStore(store_path=tmp_path / "recipes.json")
    monkeypatch.setattr(develop_panel_mod, "recipe_store", isolated)

    stub_gui = MagicMock()
    stub_gui.main_window = main_window
    stub_gui.reload_current_image_with_recipe = MagicMock()

    from Imervue.gui.develop_panel import DevelopPanel
    p = DevelopPanel(stub_gui)

    # Build the left/right panels into a temporary splitter so widgets exist
    splitter = QSplitter(Qt.Orientation.Horizontal)
    p.build_left_panel(splitter)
    p.build_right_panel(splitter)

    # Start with no image bound (controls disabled)
    p.bind_to_path(None)

    # Shrink the debounce interval so tests don't need to wait
    p._debounce.setInterval(0)
    yield p, isolated
    # The panel wires Qt signals into the MagicMock ``stub_gui``;
    # if we leave those connected when the next test constructs
    # a fresh MagicMock, Python's GC can fire DURING ``Mock.__init__``
    # and try to call into the now-dead stub via the still-live
    # signal connection — an "access violation" in the C++ side.
    # Tear the connections down explicitly, then drain queued
    # ``DeferredDelete`` events so the QObject C++ sides are gone
    # before the next test runs.
    from PySide6.QtCore import QCoreApplication, QEvent
    splitter.setParent(None)
    splitter.deleteLater()
    p.setParent(None)
    p.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "img.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 500)
    from Imervue.image.recipe import clear_identity_cache
    clear_identity_cache()
    return p


# ======================================================================
# Construction + initial state
# ======================================================================

class TestPanelConstruction:
    def test_panel_is_disabled_when_no_path(self, panel):
        p, _ = panel
        assert not p._exposure.isEnabled()
        assert not p._brightness.isEnabled()

    def test_bind_to_none_clears_state(self, panel):
        p, _ = panel
        p.bind_to_path(None)
        assert p._path is None
        assert p.current_recipe().is_identity()

    def test_bind_to_path_enables_controls(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        assert p._exposure.isEnabled()
        assert p._brightness.isEnabled()

    def test_bind_loads_existing_recipe(self, panel, sample_file):
        p, store = panel
        store.set_for_path(str(sample_file), Recipe(brightness=0.5, contrast=-0.2))
        p.bind_to_path(str(sample_file))
        assert p.current_recipe().brightness == pytest.approx(0.5)
        assert p.current_recipe().contrast == pytest.approx(-0.2)

    def test_bind_reflects_recipe_in_sliders(self, panel, sample_file):
        p, store = panel
        store.set_for_path(str(sample_file), Recipe(brightness=0.5))
        p.bind_to_path(str(sample_file))
        # brightness slider: -100..100 mapped to -1..1
        assert p._brightness.value() == 50


# ======================================================================
# Slider → recipe mapping
# ======================================================================

class TestSliderMapping:
    def test_brightness_slider_sets_recipe(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        p._brightness.setValue(30)
        assert p._current.brightness == pytest.approx(0.3)

    def test_exposure_slider_sets_recipe(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        p._exposure.setValue(150)  # 1.5 stops
        assert p._current.exposure == pytest.approx(1.5)

    def test_all_zero_sliders_is_identity(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        p._brightness.setValue(0)
        p._contrast.setValue(0)
        p._saturation.setValue(0)
        p._exposure.setValue(0)
        assert p._current.is_identity()

    def test_suppress_signals_blocks_commit(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        # Bind triggers a sync that must NOT emit
        p.bind_to_path(str(sample_file))
        assert committed == []


# ======================================================================
# Preview semantics (no commit until save)
# ======================================================================

class TestPreviewSemantics:
    """Slider/rotate/flip changes are preview-only — they update
    ``_current`` but never emit ``recipe_committed``."""

    def test_slider_does_not_commit(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        p._brightness.setValue(50)
        assert committed == []
        assert p._current.brightness == pytest.approx(0.5)

    def test_rotate_does_not_commit(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        p._rotate(1)
        assert committed == []
        assert p._current.rotate_steps == 1

    def test_flip_does_not_commit(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        p._flip_h()
        assert committed == []
        assert p._current.flip_h is True

    def test_reset_clears_recipe(self, panel, sample_file):
        p, store = panel
        store.set_for_path(str(sample_file), Recipe(brightness=0.5))
        p.bind_to_path(str(sample_file))
        p._reset()
        assert p._current.is_identity()

    def test_reset_on_identity_is_noop(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        p._reset()  # already identity
        assert committed == []


# ======================================================================
# Label refresh
# ======================================================================

class TestLabels:
    def test_labels_refresh_on_slider_move(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        p._brightness.setValue(50)
        assert "+50" in p._brightness_label.text()

    def test_exposure_label_shows_decimals(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        p._exposure.setValue(125)
        assert "1.25" in p._exposure_label.text() or "+1.25" in p._exposure_label.text()

    def test_negative_brightness_shows_minus(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        p._brightness.setValue(-40)
        assert "-40" in p._brightness_label.text()


# ======================================================================
# Canvas ↔ recipe integration
# ======================================================================

@pytest.fixture
def real_image(tmp_path):
    """A real 100x80 white PNG for canvas tests."""
    import numpy as np
    from PIL import Image

    arr = np.full((80, 100, 4), 200, dtype=np.uint8)
    img = Image.fromarray(arr, "RGBA")
    path = tmp_path / "real.png"
    img.save(str(path), format="PNG")
    from Imervue.image.recipe import clear_identity_cache
    clear_identity_cache()
    return path


class TestCanvasRecipeSync:
    """Verify that develop slider changes are reflected on the canvas image."""

    def test_canvas_created_with_recipe_applied(self, panel, real_image):
        """When binding with a non-identity recipe, the canvas base should
        differ from the raw file pixels."""
        p, store = panel
        store.set_for_path(str(real_image), Recipe(brightness=0.8))
        p.bind_to_path(str(real_image))
        assert p._canvas is not None
        import numpy as np
        from PIL import Image
        raw = Image.open(str(real_image)).convert("RGBA")
        raw_arr = np.array(raw)
        canvas_arr = np.array(p._canvas.get_base_pil())
        # Brightness 0.8 should make pixels brighter — arrays must differ
        assert not np.array_equal(raw_arr, canvas_arr)

    def test_refresh_updates_canvas_on_recipe_change(self, panel, real_image):
        """Calling bind_to_path again (same path, new recipe) must update
        the canvas base image."""
        p, store = panel
        p.bind_to_path(str(real_image))
        import numpy as np
        before = np.array(p._canvas.get_base_pil()).copy()
        store.set_for_path(str(real_image), Recipe(brightness=0.5))
        p._current = Recipe(brightness=0.5)
        p._committed = Recipe(brightness=0.5)
        p._refresh_canvas_base()
        after = np.array(p._canvas.get_base_pil())
        assert not np.array_equal(before, after)

    def test_identity_recipe_shows_raw_pixels(self, panel, real_image):
        """With an identity recipe, the canvas base should match the raw file."""
        p, _ = panel
        p.bind_to_path(str(real_image))
        import numpy as np
        from PIL import Image
        raw = Image.open(str(real_image)).convert("RGBA")
        raw_arr = np.array(raw)
        canvas_arr = np.array(p._canvas.get_base_pil())
        assert np.array_equal(raw_arr, canvas_arr)

    def test_geometry_change_clears_annotations(self, panel, real_image):
        """Rotation changes dimensions — annotations must be cleared."""
        p, _ = panel
        p.bind_to_path(str(real_image))
        assert p._canvas is not None
        # Add a dummy annotation
        from Imervue.gui.annotation_models import Annotation
        ann = Annotation(kind="rect", points=[(10, 10), (50, 50)])
        p._canvas.set_annotations([ann])
        assert len(p._canvas.get_annotations()) == 1
        # Simulate a 90° rotation recipe refresh
        p._current = Recipe(rotate_steps=1)
        p._refresh_canvas_base()
        # Image is now 80x100 (was 100x80) → annotations cleared
        assert len(p._canvas.get_annotations()) == 0


# ======================================================================
# recipe_committed wiring — debounced commit writes back + notifies
# ======================================================================

def _connect_store_writer(panel_obj, store):
    """Wire ``recipe_committed`` to a handler that mirrors production.

    The real consumer (``EditRecipeCommand`` via ``_on_recipe_committed``)
    writes the *new* recipe to the store. We replicate just that effect so the
    test can assert the round-trip without standing up a full viewer.
    """
    emitted: list[tuple] = []

    def _handler(path, old_recipe, new_recipe):
        emitted.append((path, old_recipe, new_recipe))
        store.set_for_path(path, new_recipe)

    panel_obj.recipe_committed.connect(_handler)
    return emitted


class TestRecipeCommitted:
    """The debounce timer firing finalises the edit: write-back + signal."""

    def test_debounced_commit_emits_and_writes_store(self, panel, sample_file):
        p, store = panel
        p.bind_to_path(str(sample_file))
        emitted = _connect_store_writer(p, store)

        p._brightness.setValue(50)
        # Slider only schedules a preview — nothing committed yet.
        assert emitted == []

        # Fire the debounce as the timer would.
        p._preview_debounced()

        assert len(emitted) == 1
        path, old_recipe, new_recipe = emitted[0]
        assert path == str(sample_file)
        assert old_recipe.brightness == pytest.approx(0.0)
        assert new_recipe.brightness == pytest.approx(0.5)
        # The store now holds the committed recipe.
        assert store.get_for_path(str(sample_file)).brightness == pytest.approx(0.5)

    def test_commit_payload_is_defensive_copy(self, panel, sample_file):
        p, store = panel
        p.bind_to_path(str(sample_file))
        emitted = _connect_store_writer(p, store)

        p._brightness.setValue(50)
        p._preview_debounced()
        _, _, new_recipe = emitted[0]

        # Mutating the panel's working recipe must not corrupt the payload.
        p._current.brightness = 0.9
        assert new_recipe.brightness == pytest.approx(0.5)

    def test_commit_is_noop_when_unchanged(self, panel, sample_file):
        p, store = panel
        p.bind_to_path(str(sample_file))
        emitted = _connect_store_writer(p, store)

        # No slider moved → committed == current → no emission.
        p._preview_debounced()
        assert emitted == []

    def test_second_commit_uses_prior_as_old(self, panel, sample_file):
        p, store = panel
        p.bind_to_path(str(sample_file))
        emitted = _connect_store_writer(p, store)

        p._brightness.setValue(50)
        p._preview_debounced()
        p._brightness.setValue(20)
        p._preview_debounced()

        assert len(emitted) == 2
        _, old_recipe, new_recipe = emitted[1]
        assert old_recipe.brightness == pytest.approx(0.5)
        assert new_recipe.brightness == pytest.approx(0.2)

    def test_commit_noop_without_path(self, panel):
        p, store = panel
        p.bind_to_path(None)
        emitted = _connect_store_writer(p, store)
        p._current = Recipe(brightness=0.5)
        p._preview_debounced()
        assert emitted == []

    def test_reset_commits_back_to_identity(self, panel, sample_file):
        p, store = panel
        store.set_for_path(str(sample_file), Recipe(brightness=0.5))
        p.bind_to_path(str(sample_file))
        emitted = _connect_store_writer(p, store)

        p._reset()

        assert len(emitted) == 1
        _, old_recipe, new_recipe = emitted[0]
        assert old_recipe.brightness == pytest.approx(0.5)
        assert new_recipe.is_identity()
        # Identity recipe drops the entry from the store.
        assert store.get_for_path(str(sample_file)) is None


# ======================================================================
# Destructive save paths — crop + annotation atomic write
# ======================================================================

class TestCropSave:
    """``_apply_crop`` writes the cropped image atomically and resets state."""

    def test_apply_crop_writes_file_and_cleans_tmp(self, panel, real_image):
        from PIL import Image

        p, store = panel
        p.bind_to_path(str(real_image))
        # Select a 40x30 crop region.
        p._canvas._crop_rect = (10, 5, 40, 30)

        p._apply_crop()

        saved = Image.open(str(real_image))
        assert saved.size == (40, 30)
        # The atomic .tmp sibling must be gone.
        assert not (real_image.parent / (real_image.name + ".tmp")).exists()
        # Recipe is reset because the edit is now baked into the pixels.
        assert p._current.is_identity()

    def test_apply_crop_jpeg_converts_rgba_to_rgb(self, panel, tmp_path):
        from PIL import Image

        from Imervue.image.recipe import clear_identity_cache

        # A .jpg source is loaded into the canvas as RGBA, so the crop save
        # must take the RGBA->RGB branch before re-encoding as JPEG.
        rgb = Image.new("RGB", (60, 50), (120, 30, 200))
        jpg_path = tmp_path / "shot.jpg"
        rgb.save(str(jpg_path), format="JPEG")
        clear_identity_cache()

        p, _ = panel
        p.bind_to_path(str(jpg_path))
        assert p._canvas.get_base_pil().mode == "RGBA"
        p._canvas._crop_rect = (0, 0, 30, 20)

        p._apply_crop()

        saved = Image.open(str(jpg_path))
        assert saved.mode == "RGB"
        assert saved.size == (30, 20)

    def test_apply_crop_rolls_back_on_write_failure(self, panel, real_image, monkeypatch):
        p, _ = panel
        p.bind_to_path(str(real_image))
        # A non-identity recipe so we can prove it is NOT reset on failure.
        p._current = Recipe(brightness=0.4)
        p._canvas._crop_rect = (0, 0, 40, 30)

        import Imervue.gui.develop_panel as mod

        def _boom(_src, _dst):
            raise OSError("disk full")

        monkeypatch.setattr(mod.os, "replace", _boom)

        p._apply_crop()

        # No leftover .tmp, and the recipe survived (no reset on failure).
        assert not (real_image.parent / (real_image.name + ".tmp")).exists()
        assert p._current.brightness == pytest.approx(0.4)

    def test_apply_crop_ignores_tiny_region(self, panel, real_image):
        from PIL import Image

        p, _ = panel
        p.bind_to_path(str(real_image))
        original_size = Image.open(str(real_image)).size
        p._canvas._crop_rect = (0, 0, 1, 1)  # below the 2px minimum

        p._apply_crop()

        # File untouched.
        assert Image.open(str(real_image)).size == original_size


class TestAnnotationSave:
    """``_save_annotation`` bakes overlays and writes back atomically."""

    def test_save_annotation_writes_and_cleans_tmp(self, panel, real_image):
        from PIL import Image

        from Imervue.gui.annotation_models import Annotation

        p, _ = panel
        p.bind_to_path(str(real_image))
        p._canvas.set_annotations(
            [Annotation(kind="rect", points=[(5, 5), (40, 30)])]
        )

        p._save_annotation()

        # File still opens and the .tmp sibling is cleaned up.
        assert Image.open(str(real_image)).size == (100, 80)
        assert not (real_image.parent / (real_image.name + ".tmp")).exists()
        assert p._current.is_identity()

    def test_save_annotation_jpeg_converts_rgba_to_rgb(self, panel, tmp_path):
        from PIL import Image

        from Imervue.gui.annotation_models import Annotation
        from Imervue.image.recipe import clear_identity_cache

        rgb = Image.new("RGB", (60, 50), (10, 220, 40))
        jpg_path = tmp_path / "ann.jpg"
        rgb.save(str(jpg_path), format="JPEG")
        clear_identity_cache()

        p, _ = panel
        p.bind_to_path(str(jpg_path))
        # bake() returns RGBA, so the save path must convert before JPEG encode.
        p._canvas.set_annotations(
            [Annotation(kind="rect", points=[(5, 5), (30, 25)])]
        )

        p._save_annotation()

        saved = Image.open(str(jpg_path))
        assert saved.mode == "RGB"

    def test_save_annotation_rolls_back_on_write_failure(self, panel, real_image, monkeypatch):
        from Imervue.gui.annotation_models import Annotation

        p, _ = panel
        p.bind_to_path(str(real_image))
        p._current = Recipe(brightness=0.3)
        p._canvas.set_annotations(
            [Annotation(kind="rect", points=[(5, 5), (40, 30)])]
        )

        import Imervue.gui.develop_panel as mod

        def _boom(_src, _dst):
            raise OSError("permission denied")

        monkeypatch.setattr(mod.os, "replace", _boom)

        p._save_annotation()

        assert not (real_image.parent / (real_image.name + ".tmp")).exists()
        # Recipe untouched because the save never completed.
        assert p._current.brightness == pytest.approx(0.3)
