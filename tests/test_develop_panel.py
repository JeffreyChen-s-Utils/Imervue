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
    splitter.deleteLater()
    p.deleteLater()


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
# Commit semantics
# ======================================================================

class TestCommitSemantics:
    def test_no_commit_when_recipe_unchanged(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        p._commit_now()
        assert committed == []

    def test_rotate_commits_immediately(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda path, old, new: committed.append((path, old, new)))
        p._rotate(1)
        assert len(committed) == 1
        path, old, new = committed[0]
        assert path == str(sample_file)
        assert old.rotate_steps == 0
        assert new.rotate_steps == 1

    def test_rotate_four_times_commits_each(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        for _ in range(4):
            p._rotate(1)
        assert len(committed) == 4

    def test_flip_commits(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        p._flip_h()
        assert len(committed) == 1
        assert committed[0][2].flip_h is True

    def test_reset_commits(self, panel, sample_file):
        p, store = panel
        store.set_for_path(str(sample_file), Recipe(brightness=0.5))
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        p._reset()
        assert len(committed) == 1
        _path, old, new = committed[0]
        assert old.brightness == pytest.approx(0.5)
        assert new.is_identity()

    def test_reset_on_identity_is_noop(self, panel, sample_file):
        p, _ = panel
        p.bind_to_path(str(sample_file))
        committed = []
        p.recipe_committed.connect(lambda *args: committed.append(args))
        p._reset()  # already identity → no commit
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
