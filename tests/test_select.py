"""Selection order: every order-sensitive action gets the selection in view order.

``selected_tiles`` is a set, so ``list(selected_tiles)`` came out in hash
order and a slideshow, contact sheet, web gallery, GIF, collage or numbered
rename built from a multi-selection was shuffled.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Imervue.gpu_image_view.actions.select import selected_in_view_order, selection_or_all

# Enough names that hash order differs from list order.
_IMAGES = [f"C:/shots/img_{i:02d}.png" for i in range(24)]
_PICKED = _IMAGES[3::2]


def _viewer(selected, images=_IMAGES):
    return SimpleNamespace(selected_tiles=set(selected), model=SimpleNamespace(images=list(images)),
                           main_window=None)


def test_hash_order_really_differs():
    assert list(set(_PICKED)) != _PICKED  # otherwise the tests below prove nothing


def test_selection_follows_view_order():
    assert selected_in_view_order(_viewer(_PICKED)) == _PICKED


def test_selected_paths_missing_from_the_model_follow_sorted():
    viewer = _viewer(["C:/z.png", _IMAGES[5], "C:/a.png", _IMAGES[1]])
    assert selected_in_view_order(viewer) == [_IMAGES[1], _IMAGES[5], "C:/a.png", "C:/z.png"]


def test_non_string_entries_and_empty_selection():
    assert selected_in_view_order(_viewer([])) == []
    assert selected_in_view_order(_viewer([_IMAGES[2], 7, None])) == [_IMAGES[2]]
    assert selected_in_view_order(SimpleNamespace()) == []


def test_selection_or_all():
    assert selection_or_all(None) == []
    assert selection_or_all(_viewer([])) == _IMAGES
    assert selection_or_all(_viewer(_PICKED)) == _PICKED
    assert selection_or_all(SimpleNamespace(selected_tiles=set())) == []


@pytest.mark.parametrize("module, opener, dialog", [
    ("Imervue.gpu_image_view.actions.batch_ops", "open_batch_rename", "BatchRenameDialog"),
    ("Imervue.gpu_image_view.actions.batch_ops", "open_batch_move", "BatchMoveDialog"),
    ("Imervue.gui.gif_video_dialog", "open_gif_video_dialog", "GifVideoDialog"),
])
def test_selection_openers_pass_view_order(monkeypatch, module, opener, dialog):
    import importlib
    mod = importlib.import_module(module)
    received = []

    class _Fake:
        def __init__(self, _gui, paths):
            received.append(paths)

        def exec(self):
            return 0

    monkeypatch.setattr(mod, dialog, _Fake)
    getattr(mod, opener)(_viewer(_PICKED))
    assert received == [_PICKED]


@pytest.mark.parametrize("module, opener, dialog, arg", [
    ("Imervue.gui.token_rename_dialog", "open_token_rename", "TokenRenameDialog", "ui"),
    ("Imervue.gui.collage_dialog", "open_collage", "CollageDialog", "viewer"),
])
@pytest.mark.parametrize("picked, expected", [(_PICKED, _PICKED), ([], _IMAGES)])
def test_selection_or_all_openers_pass_view_order(monkeypatch, module, opener, dialog, arg,
                                                   picked, expected):
    import importlib
    mod = importlib.import_module(module)
    received = []

    class _Fake:
        def __init__(self, _owner, paths):
            received.append(paths)

        def exec(self):
            return 0

    monkeypatch.setattr(mod, dialog, _Fake)
    viewer = _viewer(picked)
    getattr(mod, opener)(SimpleNamespace(viewer=viewer) if arg == "ui" else viewer)
    assert received == [expected]


@pytest.mark.parametrize("module, cls", [
    ("Imervue.gui.slideshow_mp4_dialog", "SlideshowMp4Dialog"),
    ("Imervue.gui.contact_sheet_dialog", "ContactSheetDialog"),
    ("Imervue.gui.web_gallery_dialog", "WebGalleryDialog"),
])
def test_export_dialogs_use_view_order(qapp, module, cls):
    import importlib
    dialog = getattr(importlib.import_module(module), cls)(None)
    try:
        dialog.ui = SimpleNamespace(viewer=_viewer(_PICKED))
        assert dialog._resolve_images() == _PICKED  # noqa: SLF001
        dialog.ui = SimpleNamespace(viewer=_viewer([]))
        assert dialog._resolve_images() == _IMAGES  # noqa: SLF001
        dialog.ui = None
        assert dialog._resolve_images() == []  # noqa: SLF001
    finally:
        dialog.deleteLater()


def test_combine_multipage_pages_follow_view_order(monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from Imervue.image import multipage
    from Imervue.menu import right_click_menu as rcm
    received = []
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_k: ("C:/out.pdf", ""))
    monkeypatch.setattr(multipage, "combine_to_multipage",
                        lambda paths, dest: received.append(paths) or {"pages": len(paths)})
    rcm._combine_multipage(_viewer(_PICKED))  # noqa: SLF001
    assert received == [_PICKED]


def test_staging_tray_adds_in_view_order(monkeypatch):
    from Imervue.library import staging_tray
    from Imervue.menu import right_click_menu as rcm
    received = []
    monkeypatch.setattr(staging_tray, "add_many", received.append)
    rcm._add_to_staging_tray(_viewer(_PICKED))  # noqa: SLF001
    assert received == [_PICKED]


def _viewer_in(folder):
    return SimpleNamespace(model=SimpleNamespace(images=[str(folder / "a.png")]))


def test_sibling_folders_follow_the_trees_natural_order(tmp_path):
    """Next folder went Day 1, Day 10, Day 11, Day 2 while the tree showed Day 1, Day 2."""
    from Imervue.gpu_image_view.actions.select import _sibling_folders
    for name in ("Day 10", "Day 2", "Day 1"):
        (tmp_path / name).mkdir()
    assert [p.name for p in _sibling_folders(_viewer_in(tmp_path / "Day 1"))] == ["Day 1", "Day 2", "Day 10"]


def test_sibling_folders_leave_out_hidden_ones_but_keep_the_current(tmp_path):
    from Imervue.gpu_image_view.actions.select import _sibling_folders
    for name in ("a", ".git", ".stash", "b"):
        (tmp_path / name).mkdir()
    assert [p.name for p in _sibling_folders(_viewer_in(tmp_path / "a"))] == ["a", "b"]
    assert [p.name for p in _sibling_folders(_viewer_in(tmp_path / ".stash"))] == [".stash", "a", "b"]


def test_sibling_folders_of_an_empty_view_are_none():
    from Imervue.gpu_image_view.actions.select import _sibling_folders
    assert _sibling_folders(SimpleNamespace(model=SimpleNamespace(images=[]))) == []
