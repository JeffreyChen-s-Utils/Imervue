"""The Material dock lists the user's own materials, and Edit > Save Selection as Material… adds one.

Nothing read the user's material folder or the captured brush tips, so only
the built-in procedural materials showed and a captured tip was gone after a
restart (``progress.md`` #50); ``paint/save_region_as_material.py`` was never
reachable either.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from Imervue.paint import material_library
from Imervue.paint.brush_tip_capture import USER_BRUSH_TIP_DIR_NAME
from Imervue.paint.edit_menu import commit_save_material
from Imervue.paint.material_library import (
    USER_MATERIALS_DIR_NAME,
    default_material_index,
    material_dock_index,
    user_material_index,
)


@pytest.fixture
def app_root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(material_library, "app_dir", lambda: tmp_path)
    return tmp_path


def _png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (4, 4), (10, 20, 30, 255)).save(path)


def test_the_library_folder_and_captured_tips_are_listed(app_root):
    _png(app_root / USER_MATERIALS_DIR_NAME / "tone" / "dots.png")
    _png(app_root / USER_MATERIALS_DIR_NAME / "paper.png")
    _png(app_root / USER_BRUSH_TIP_DIR_NAME / "leaf.png")
    entries = {e.name: e.category for e in user_material_index().entries}
    assert entries == {"dots": "tone", "paper": "texture", "leaf": "brush_tip"}


def test_without_user_folders_nothing_is_listed_or_created(app_root):
    assert user_material_index().entries == []
    assert list(app_root.iterdir()) == []


def test_the_dock_lists_user_materials_before_the_built_in_ones(app_root):
    _png(app_root / USER_MATERIALS_DIR_NAME / "pattern" / "bricks.png")
    names = [e.name for e in material_dock_index().entries]
    assert names[0] == "bricks"
    assert names[1:] == [e.name for e in default_material_index().entries]


# --- Edit > Save Selection as Material… ----------------------------------------

class _Dock:
    def __init__(self):
        self._index = SimpleNamespace(entries=[])
        self.refreshed = 0

    def index(self):
        return self._index

    def _refresh_grid(self):
        self.refreshed += 1


def _workspace(selection, picture):
    document = SimpleNamespace(selection=lambda: selection, composite=lambda: picture)
    return SimpleNamespace(canvas=lambda: SimpleNamespace(document=lambda: document),
                           _material_dock=_Dock())


def _picture() -> np.ndarray:
    picture = np.zeros((12, 12, 4), np.uint8)
    picture[...] = (200, 100, 50, 255)
    return picture


def test_the_selection_is_saved_cropped_with_the_rest_transparent(tmp_path):
    selection = np.zeros((12, 12), bool)
    selection[2:6, 3:8] = True
    selection[2, 3] = False                    # a notch: inside the box, outside the selection
    workspace = _workspace(selection, _picture())
    saved = commit_save_material(workspace, "brick", "pattern", library_root=tmp_path)
    assert Path(saved) == (tmp_path / "pattern" / "brick.png").resolve()
    pixels = np.asarray(Image.open(saved).convert("RGBA"))
    assert pixels.shape == (4, 5, 4)
    assert pixels[0, 0, 3] == 0 and pixels[1, 1, 3] == 255
    assert tuple(pixels[1, 1, :3]) == (200, 100, 50)


def test_the_saved_material_shows_in_the_dock_at_once(tmp_path):
    selection = np.ones((12, 12), bool)
    workspace = _workspace(selection, _picture())
    commit_save_material(workspace, "wall", "texture", library_root=tmp_path)
    dock = workspace._material_dock
    assert [e.name for e in dock.index().entries] == ["wall"]
    assert dock.refreshed == 1


def test_the_picture_itself_is_left_alone(tmp_path):
    picture = _picture()
    selection = np.zeros((12, 12), bool)
    selection[0:2, 0:2] = True
    commit_save_material(_workspace(selection, picture), "x", "texture", library_root=tmp_path)
    assert (picture[..., 3] == 255).all()


@pytest.mark.parametrize("selection", [None, np.zeros((12, 12), bool)])
def test_without_a_selection_nothing_is_saved(tmp_path, selection):
    workspace = _workspace(selection, _picture())
    assert commit_save_material(workspace, "x", "texture", library_root=tmp_path) is None
    assert list(tmp_path.iterdir()) == []
    assert workspace._material_dock.refreshed == 0


def test_a_name_with_no_usable_characters_saves_nothing(tmp_path):
    workspace = _workspace(np.ones((12, 12), bool), _picture())
    assert commit_save_material(workspace, "///", "texture", library_root=tmp_path) is None
    assert workspace._material_dock.refreshed == 0


def test_by_default_it_saves_into_the_user_library(app_root):
    workspace = _workspace(np.ones((12, 12), bool), _picture())
    saved = commit_save_material(workspace, "mine", "tone")
    assert Path(saved).parent == (app_root / USER_MATERIALS_DIR_NAME / "tone").resolve()
    assert [e.name for e in user_material_index().entries] == ["mine"]
