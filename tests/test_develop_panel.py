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
    splitter.addWidget(p.build_left_panel())
    splitter.addWidget(p.build_right_panel())

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

    def test_geometry_change_clears_annotations(self, panel, real_image, pump_until):
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
        pump_until(lambda: p._preview.is_idle)
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

class TestDecodedSourceCache:
    """The decoded source image is cached by path so repeated previews for
    the same image skip the disk read + decode."""

    @staticmethod
    def _spy_image_open(monkeypatch):
        """Wrap ``Image.open`` in the develop_panel module with a call counter.

        Returns a list whose length equals the number of decode calls.
        """
        import Imervue.gui.develop_panel as mod

        calls: list[str] = []
        real_open = mod.Image.open

        def _counting_open(path, *args, **kwargs):
            calls.append(str(path))
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(mod.Image, "open", _counting_open)
        return calls

    def test_repeated_preview_decodes_once(self, panel, real_image, monkeypatch):
        p, _ = panel
        calls = self._spy_image_open(monkeypatch)
        p.bind_to_path(str(real_image))
        decodes_after_bind = len(calls)
        # bind decodes once to build the canvas.
        assert decodes_after_bind == 1

        # Several preview refreshes on the same path must reuse the cache.
        p._current = Recipe(brightness=0.2)
        p._refresh_canvas_base()
        p._current = Recipe(brightness=0.4)
        p._refresh_canvas_base()
        p._current = Recipe(brightness=0.6)
        p._refresh_canvas_base()

        assert len(calls) == decodes_after_bind  # no extra decodes

    def test_switching_path_redecodes(self, panel, real_image, tmp_path, monkeypatch):
        from PIL import Image as PILImage

        from Imervue.image.recipe import clear_identity_cache

        # A second distinct image.
        other = tmp_path / "other.png"
        PILImage.new("RGBA", (40, 30), (10, 20, 30, 255)).save(str(other), "PNG")
        clear_identity_cache()

        p, _ = panel
        calls = self._spy_image_open(monkeypatch)
        p.bind_to_path(str(real_image))
        assert len(calls) == 1
        assert calls[-1] == str(real_image)

        # Binding to a different path invalidates the cache and re-decodes.
        p.bind_to_path(str(other))
        assert len(calls) == 2
        assert calls[-1] == str(other)

    def test_bind_to_none_invalidates_cache(self, panel, real_image, monkeypatch):
        p, _ = panel
        p.bind_to_path(str(real_image))
        assert p._decoded_source is not None

        p.bind_to_path(None)
        assert p._decoded_source is None
        assert p._decoded_source_key is None

        # Re-binding must decode again (cache was cleared).
        calls = self._spy_image_open(monkeypatch)
        p.bind_to_path(str(real_image))
        assert len(calls) == 1

    def test_cached_output_matches_uncached(self, panel, real_image):
        """A cached re-render produces byte-identical output to a fresh load."""
        import numpy as np
        from PIL import Image as PILImage

        p, _ = panel
        p.bind_to_path(str(real_image))
        recipe = Recipe(brightness=0.5, contrast=0.2)
        p._current = recipe

        # Render via the (now-cached) panel path.
        cached = np.array(p._load_image_with_recipe(str(real_image)))

        # Render the same recipe independently, bypassing the cache entirely.
        raw = PILImage.open(str(real_image)).convert("RGBA")
        expected = np.array(PILImage.fromarray(recipe.apply(np.array(raw)), "RGBA"))

        assert np.array_equal(cached, expected)

    def test_failed_decode_clears_cache(self, panel, real_image, monkeypatch):
        import Imervue.gui.develop_panel as mod

        p, _ = panel
        p.bind_to_path(str(real_image))
        assert p._decoded_source is not None

        def _boom(_path, *_a, **_k):
            raise OSError("cannot read")

        monkeypatch.setattr(mod.Image, "open", _boom)
        result = p._load_image_with_recipe(str(real_image) + "x")
        assert result is None
        assert p._decoded_source is None
        assert p._decoded_source_key is None


class TestExifOrientedSource:
    """The Modify tab decodes its own source; it must agree with the viewer."""

    @staticmethod
    def _portrait(tmp_path):
        from PIL import Image
        exif = Image.Exif()
        exif[0x0112] = 6
        path = tmp_path / "portrait.jpg"
        Image.new("RGB", (40, 20)).save(path, exif=exif)
        return str(path)

    def test_tagged_photo_is_decoded_upright(self, panel, tmp_path):
        p, _ = panel
        p._current = Recipe()
        assert p._decode_source(self._portrait(tmp_path)).size == (20, 40)

    def test_raw_source_is_the_developed_image(self, panel, tmp_path, monkeypatch):
        """Pillow alone decoded a RAW's small embedded preview for the Modify tab."""
        import numpy as np

        from Imervue.gpu_image_view.images import image_loader
        monkeypatch.setattr(image_loader, "_load_raw",
                            lambda _p, thumbnail: np.zeros((30, 45, 3), dtype=np.uint8))
        p, _ = panel
        p._current = Recipe()
        assert p._decode_source(str(tmp_path / "shot.nef")).size == (45, 30)

    def test_legacy_geometry_recipe_decodes_the_stored_orientation(self, panel, tmp_path):
        p, _ = panel
        path = self._portrait(tmp_path)
        p._current = Recipe.from_dict({"crop": [0, 0, 10, 10]})
        assert p._decode_source(path).size == (40, 20)
        p._current = Recipe()   # same path, other base: the cache must not answer
        assert p._decode_source(path).size == (20, 40)


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

    def test_apply_crop_refuses_to_overwrite_a_raw(self, panel, tmp_path, monkeypatch):
        """With the full RAW now in Modify, a crop would have written PNG bytes into the .cr2."""
        import numpy as np

        from Imervue.gpu_image_view.images import image_loader
        monkeypatch.setattr(image_loader, "_load_raw",
                            lambda _p, thumbnail: np.zeros((40, 60, 3), dtype=np.uint8))
        raw = tmp_path / "shot.cr2"
        raw.write_bytes(b"RAW-DATA-THAT-MUST-SURVIVE")
        p, _ = panel
        shown = []
        from types import SimpleNamespace
        monkeypatch.setattr(p._main_gui.main_window, "toast",
                            SimpleNamespace(info=shown.append), raising=False)
        p.bind_to_path(str(raw))
        p._canvas._crop_rect = (0, 0, 30, 20)
        p._apply_crop()
        assert raw.read_bytes() == b"RAW-DATA-THAT-MUST-SURVIVE"
        assert shown and "overwritten" in shown[0]

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

        import Imervue.system.atomic_write as mod_save

        def _boom(_src, _dst):
            raise OSError("disk full")

        monkeypatch.setattr(mod_save.os, "replace", _boom)

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

        import Imervue.system.atomic_write as mod_save

        def _boom(_src, _dst):
            raise OSError("permission denied")

        monkeypatch.setattr(mod_save.os, "replace", _boom)

        p._save_annotation()

        assert not (real_image.parent / (real_image.name + ".tmp")).exists()
        # Recipe untouched because the save never completed.
        assert p._current.brightness == pytest.approx(0.3)

    def test_save_annotation_on_a_raw_saves_a_copy_instead(self, panel, tmp_path, monkeypatch):
        """With no in-place check it wrote PNG bytes into the .cr2."""
        import numpy as np
        from PIL import Image
        from PySide6.QtWidgets import QFileDialog

        from Imervue.gpu_image_view.images import image_loader
        from Imervue.gui.annotation_models import Annotation
        monkeypatch.setattr(image_loader, "_load_raw",
                            lambda _p, thumbnail: np.zeros((40, 60, 3), dtype=np.uint8))
        raw = tmp_path / "shot.cr2"
        raw.write_bytes(b"RAW-DATA-THAT-MUST-SURVIVE")
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            staticmethod(lambda *_a, **_k: (str(tmp_path / "shot_notes"), "")))
        p, _ = panel
        p.bind_to_path(str(raw))
        p._current = Recipe(brightness=0.2)
        p._canvas.set_annotations([Annotation(kind="rect", points=[(5, 5), (30, 25)])])

        p._save_annotation()

        assert raw.read_bytes() == b"RAW-DATA-THAT-MUST-SURVIVE"
        with Image.open(tmp_path / "shot_notes.png") as copy:   # an unwritable name gets .png
            assert copy.size == (60, 40)
        assert p._current.brightness == pytest.approx(0.2)       # the source's edit stays

    def test_cancelled_copy_writes_nothing(self, panel, tmp_path, monkeypatch):
        from PIL import Image
        from PySide6.QtWidgets import QFileDialog
        anim = tmp_path / "anim.gif"
        frames = [Image.new("RGB", (8, 4), c) for c in ((255, 0, 0), (0, 255, 0))]
        frames[0].save(anim, save_all=True, append_images=frames[1:])
        before = anim.read_bytes()
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            staticmethod(lambda *_a, **_k: ("", "")))
        p, _ = panel
        p.bind_to_path(str(anim))
        p._save_annotation()
        assert anim.read_bytes() == before
        assert [f.name for f in tmp_path.iterdir()] == ["anim.gif"]


class TestSavesKeepMetadata:
    """Crop and annotation saves re-encoded the file and dropped its EXIF."""

    @staticmethod
    def _photo(tmp_path, orientation=1):
        from PIL import Image
        exif = Image.Exif()
        exif[0x010F] = "Canon"
        exif[0x0112] = orientation
        exif.get_ifd(0x8769)[0x9003] = "2020:01:02 03:04:05"
        exif.get_ifd(0x8825)[1] = "N"
        path = tmp_path / "photo.jpg"
        Image.new("RGB", (60, 40), (90, 140, 200)).save(path, quality=92, exif=exif)
        return path

    @staticmethod
    def _assert_kept(path):
        from PIL import Image
        with Image.open(path) as img:
            exif = img.getexif()
            assert exif[0x010F] == "Canon"
            assert exif.get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"
            assert exif.get_ifd(0x8825)[1] == "N"
            assert 0x0112 not in exif           # the saved pixels are upright
            return img.size

    def test_crop_keeps_exif_and_drops_the_orientation(self, panel, tmp_path):
        from Imervue.image.recipe import clear_identity_cache
        path = self._photo(tmp_path, orientation=6)     # shown 40x60
        clear_identity_cache()
        p, _ = panel
        p.bind_to_path(str(path))
        p._canvas._crop_rect = (0, 0, 30, 50)
        p._apply_crop()
        assert self._assert_kept(path) == (30, 50)

    def test_annotation_save_keeps_exif(self, panel, tmp_path):
        from Imervue.gui.annotation_models import Annotation
        from Imervue.image.recipe import clear_identity_cache
        path = self._photo(tmp_path)
        clear_identity_cache()
        p, _ = panel
        p.bind_to_path(str(path))
        p._canvas.set_annotations([Annotation(kind="rect", points=[(5, 5), (30, 25)])])
        p._save_annotation()
        assert self._assert_kept(path) == (60, 40)


def test_navigate_image_delegates_to_on_navigate(panel, monkeypatch):
    """The public wrapper forwards the direction to the private handler."""
    p, _ = panel
    calls = []
    monkeypatch.setattr(p, "_on_navigate_image", calls.append)
    p.navigate_image(1)
    p.navigate_image(-1)
    assert calls == [1, -1]


def test_active_tool_survives_image_switch(panel, real_image):
    """A fresh canvas (image switch) keeps the active tool, so mosaic/blur/etc.
    stay usable instead of silently reverting to select."""
    p, _ = panel
    p.bind_to_path(str(real_image))
    p._set_tool("mosaic")
    assert p._canvas.current_tool() == "mosaic"
    # Re-creating the canvas is exactly what an image switch does.
    p._create_canvas(str(real_image))
    assert p._canvas.current_tool() == "mosaic"


def _spy_toasts(monkeypatch):
    """Record every (text, level) shown via the canvas ToastWidget."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "Imervue.gui.toast.ToastWidget.show_message",
        lambda self, text, level="info", duration_ms=2500: calls.append((text, level)),
    )
    return calls


def test_save_shows_success_toast(panel, real_image, monkeypatch):
    p, _ = panel
    calls = _spy_toasts(monkeypatch)
    p.bind_to_path(str(real_image))
    p._save_annotation()
    assert any(level == "success" for _text, level in calls)


def test_save_failure_shows_warning_toast(panel, real_image, monkeypatch):
    p, _ = panel
    calls = _spy_toasts(monkeypatch)
    p.bind_to_path(str(real_image))

    import Imervue.system.atomic_write as mod

    def _boom(_src, _dst):
        raise OSError("disk full")

    monkeypatch.setattr(mod.os, "replace", _boom)
    p._save_annotation()
    assert any(level == "warning" for _text, level in calls)
    assert not any(level == "success" for _text, level in calls)


def test_toast_is_noop_without_a_canvas(panel, monkeypatch):
    p, _ = panel
    calls = _spy_toasts(monkeypatch)
    p.bind_to_path(None)          # no canvas
    p._toast("hi", "info")
    assert calls == []


class TestCanvasContextMenu:
    def test_rebind_target_after_delete(self):
        from Imervue.gui.develop_panel import _rebind_target_after_delete
        assert _rebind_target_after_delete(["a", "b", "c"], 1) == "b"
        assert _rebind_target_after_delete(["a"], 0) == "a"

    def test_rebind_target_none_when_empty_or_out_of_range(self):
        from Imervue.gui.develop_panel import _rebind_target_after_delete
        assert _rebind_target_after_delete([], 0) is None
        assert _rebind_target_after_delete(["a", "b"], 5) is None
        assert _rebind_target_after_delete(["a", "b"], -1) is None

    def test_menu_has_save_navigate_and_delete(self, panel, real_image):
        p, _ = panel
        p.bind_to_path(str(real_image))
        menu = p._build_canvas_menu()
        texts = [a.text() for a in menu.actions() if a.text()]
        assert len(texts) == 4          # save, previous, next, delete
        menu.setParent(None)
        menu.deleteLater()

    def test_show_menu_is_noop_without_a_bound_image(self, panel):
        p, _ = panel
        p.bind_to_path(None)
        p._show_canvas_menu(None)       # must not raise / exec


class TestCanvasHost:
    """The canvas sits in the centre of the Modify tab, between its docks."""

    @pytest.fixture
    def sample_file(self, tmp_path):
        from PIL import Image
        path = tmp_path / "real.png"
        Image.new("RGB", (12, 8), "red").save(path)
        return path

    @staticmethod
    def _host(panel):
        from Imervue.gui.main_window_docks import CanvasHost
        host = CanvasHost("nothing open")
        panel._main_gui.main_window._modify_canvas_host = host  # noqa: SLF001
        return host

    def test_binding_an_image_shows_its_canvas_in_the_host(self, panel, sample_file):
        p, _ = panel
        host = self._host(p)
        assert host.shows_hint()
        p.bind_to_path(str(sample_file))
        assert host.currentWidget() is p.canvas()
        assert not host.shows_hint()

    def test_unbinding_shows_the_hint_again(self, panel, sample_file):
        p, _ = panel
        host = self._host(p)
        p.bind_to_path(str(sample_file))
        p.bind_to_path(None)
        assert p.canvas() is None
        assert host.shows_hint()
        assert host.count() == 1

    def test_a_second_image_replaces_the_first_canvas(self, panel, sample_file, tmp_path):
        from PIL import Image
        other = tmp_path / "other.png"
        Image.new("RGB", (8, 8), "green").save(other)
        p, _ = panel
        host = self._host(p)
        p.bind_to_path(str(sample_file))
        first = p.canvas()
        p.bind_to_path(str(other))
        assert p.canvas() is not first
        assert host.currentWidget() is p.canvas()
        assert host.count() == 2          # the hint and the one live canvas

    def test_a_window_without_a_host_still_gets_a_canvas(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        assert p.canvas() is not None


class TestToolStripSizing:
    """Strip buttons are sized from their labels, so none is cut at any UI scale."""

    def test_every_button_has_one_size_that_fits_its_label(self, panel):
        p, _ = panel
        buttons = list(p._tool_buttons.values())  # noqa: SLF001
        sizes = {(b.width(), b.height()) for b in buttons}
        assert len(sizes) == 1
        for button in buttons:
            hint = button.sizeHint()
            assert button.width() >= hint.width()
            assert button.height() >= hint.height()

    def test_buttons_are_no_smaller_than_the_designed_size(self, panel):
        p, _ = panel
        button = p._tool_buttons["select"]  # noqa: SLF001
        assert button.width() >= p._TOOL_BTN_SIZE.width()  # noqa: SLF001
        assert button.height() >= p._TOOL_BTN_SIZE.height()  # noqa: SLF001

    def test_a_larger_ui_scale_enlarges_the_buttons(self, qapp):
        from PySide6.QtWidgets import QToolButton

        from Imervue.gui.develop_panel import DevelopPanel
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        base = DevelopPanel._size_tool_buttons([QToolButton()])  # noqa: SLF001
        user_setting_dict["ui_scale_percent"] = 200
        doubled = DevelopPanel._size_tool_buttons([QToolButton()])  # noqa: SLF001
        assert doubled.width() == 2 * base.width()
        assert doubled.height() == 2 * base.height()

    def test_the_strip_is_wide_enough_for_its_buttons(self, qapp):
        from unittest.mock import MagicMock

        from Imervue.gui.develop_panel import DevelopPanel
        p = DevelopPanel(MagicMock())
        strip = p.build_left_panel()
        try:
            assert strip.minimumWidth() > p._tool_buttons["select"].width()  # noqa: SLF001
        finally:
            strip.deleteLater()
            p.deleteLater()

    def test_the_adjustment_panel_is_never_narrower_than_its_controls(self, qapp):
        from unittest.mock import MagicMock

        from Imervue.gui.develop_panel import DevelopPanel
        p = DevelopPanel(MagicMock())
        scroll = p.build_right_panel()
        try:
            assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            assert scroll.minimumWidth() > scroll.widget().minimumSizeHint().width()
        finally:
            scroll.deleteLater()
            p.deleteLater()


class TestDrawingPropertyPairs:
    """Stroke width and opacity sliders stay in step with their spin boxes."""

    def test_defaults_and_layout(self, panel):
        p, _ = panel
        assert (p._width_slider.value(), p._width_spin.value()) == (3, 3)
        assert (p._opacity_slider.value(), p._opacity_spin.value()) == (100, 100)
        assert p._opacity_spin.suffix() == " %"
        assert p._width_spin.maximumWidth() == 60

    def test_width_slider_updates_spin_without_a_canvas(self, panel):
        p, _ = panel
        p._canvas = None
        p._width_slider.setValue(9)
        assert p._width_spin.value() == 9

    def test_width_spin_sets_the_canvas_stroke(self, panel):
        p, _ = panel
        canvas = MagicMock()
        p._canvas = canvas
        try:
            p._width_spin.setValue(17)
            assert p._width_slider.value() == 17
            canvas.set_stroke_width.assert_called_once_with(17)
        finally:
            p._canvas = None

    def test_opacity_slider_sets_the_canvas_opacity(self, panel):
        p, _ = panel
        canvas = MagicMock()
        p._canvas = canvas
        try:
            p._opacity_slider.setValue(35)
            assert p._opacity_spin.value() == 35
            canvas.set_brush_opacity.assert_called_once_with(35)
        finally:
            p._canvas = None

    def test_pairs_are_part_of_the_interactive_widgets(self, panel):
        p, _ = panel
        for widget in (p._width_slider, p._width_spin, p._opacity_slider, p._opacity_spin):
            assert widget in p._interactive_widgets



@pytest.fixture
def viewer_stack(panel, monkeypatch):
    """The viewer's recipe undo stack attached as in the main window; commands write to the test store."""
    from PySide6.QtGui import QUndoStack

    from Imervue.gpu_image_view.actions import recipe_commands
    p, store = panel
    monkeypatch.setattr(recipe_commands, "recipe_store", store)
    stack = QUndoStack()
    p.use_undo_stack(stack)
    p.recipe_committed.connect(lambda path, old, new: stack.push(
        recipe_commands.EditRecipeCommand(p._main_gui, path, old, new)))  # noqa: SLF001
    yield p, store, stack
    stack.deleteLater()


def test_undo_and_redo_step_through_the_slider_edits(viewer_stack, sample_file):
    """The buttons drove a stack no edit was ever pushed to: they did nothing."""
    p, store, _stack = viewer_stack
    p.bind_to_path(str(sample_file))
    p._exposure.setValue(50)  # noqa: SLF001
    p._btn_undo.click()  # noqa: SLF001 - also commits the edit still in its debounce
    assert store.get_for_path(str(sample_file)) is None   # back to no recipe at all
    assert p._exposure.value() == 0  # noqa: SLF001
    p._btn_redo.click()  # noqa: SLF001
    assert store.get_for_path(str(sample_file)).exposure == pytest.approx(0.5)
    assert p._exposure.value() == 50  # noqa: SLF001


def test_another_pictures_edit_on_top_is_left_alone(viewer_stack, sample_file, tmp_path):
    from Imervue.gpu_image_view.actions.recipe_commands import EditRecipeCommand
    from Imervue.image.recipe import Recipe
    p, store, stack = viewer_stack
    other_file = tmp_path / "other.png"
    other_file.write_bytes(sample_file.read_bytes())
    other = str(other_file)
    stack.push(EditRecipeCommand(p._main_gui, other, Recipe(), Recipe(exposure=1.0)))  # noqa: SLF001
    p.bind_to_path(str(sample_file))
    p._btn_undo.click()  # noqa: SLF001
    assert stack.index() == 1
    assert store.get_for_path(other).exposure == pytest.approx(1.0)
