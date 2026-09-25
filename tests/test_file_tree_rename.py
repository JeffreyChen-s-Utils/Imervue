"""Renaming and duplicating in the folder tree: a file's saved data and sidecars follow it."""
from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def rename(qapp, monkeypatch):
    """Rename *path* through the tree's F2 action, answering the prompt with *new_name*."""
    from PySide6.QtWidgets import QInputDialog

    from Imervue.gui import file_tree_view as mod
    toasts: list[str] = []
    tree = SimpleNamespace(
        _main_window=SimpleNamespace(toast=SimpleNamespace(
            warning=toasts.append, error=toasts.append, success=toasts.append)),
        _refresh_tree=lambda: None,
    )

    def run(path, new_name):
        monkeypatch.setattr(QInputDialog, "getText",
                            staticmethod(lambda *_a, **_k: (new_name, True)))
        mod._FileTreeView._rename_path(tree, str(path))  # noqa: SLF001
        return toasts

    return run


def test_a_renamed_file_keeps_its_rating_and_sidecar(rename, tmp_path):
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    photo = tmp_path / "IMG.JPG"
    photo.write_text("jpg", encoding="utf-8")
    (tmp_path / "IMG.JPG.xmp").write_text("darktable", encoding="utf-8")
    user_setting_dict["image_ratings"] = {str(photo): 3}
    assert rename(photo, "harbour.JPG") == ["Renamed to harbour.JPG"]
    assert user_setting_dict["image_ratings"] == {str(tmp_path / "harbour.JPG"): 3}
    assert (tmp_path / "harbour.JPG.xmp").read_text(encoding="utf-8") == "darktable"


def test_a_renamed_folder_keeps_the_data_of_every_photo_inside(rename, tmp_path):
    """Renaming a folder orphaned every rating, tag and library note under it."""
    from Imervue.library import image_index
    from Imervue.user_settings.tags import get_tags_for_image
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    photo = tmp_path / "shoot" / "a.jpg"
    photo.parent.mkdir()
    photo.write_text("a", encoding="utf-8")
    user_setting_dict["image_tags"] = {"sea": [str(photo)]}
    image_index.set_note(str(photo), "print")
    rename(tmp_path / "shoot", "2024 harbour")
    moved = str(tmp_path / "2024 harbour" / "a.jpg")
    assert get_tags_for_image(moved) == ["sea"]
    assert image_index.get_note(moved) == "print"


def test_a_duplicate_gets_copies_of_the_sidecars(qapp, tmp_path):
    from Imervue.gui import file_tree_view as mod
    photo = tmp_path / "IMG.JPG"
    photo.write_text("jpg", encoding="utf-8")
    (tmp_path / "IMG.xmp").write_text("edits", encoding="utf-8")
    (tmp_path / "IMG.JPG.annotations.json").write_text("notes", encoding="utf-8")
    toasts: list[str] = []
    tree = SimpleNamespace(
        _main_window=SimpleNamespace(toast=SimpleNamespace(
            error=toasts.append, success=toasts.append)),
        _refresh_tree=lambda: None,
    )
    mod._FileTreeView._duplicate_file(tree, str(photo))  # noqa: SLF001
    assert toasts == ["Duplicated to IMG (copy).JPG"]
    assert (tmp_path / "IMG (copy).xmp").read_text(encoding="utf-8") == "edits"
    assert (tmp_path / "IMG (copy).JPG.annotations.json").read_text(encoding="utf-8") == "notes"
    assert (tmp_path / "IMG.xmp").exists()
