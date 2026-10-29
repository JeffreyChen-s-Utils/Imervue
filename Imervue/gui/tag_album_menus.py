"""Right-click "Tags" / "Albums" submenus for one image or a batch selection.

Each checkable entry toggles the image in that tag or album, "+ New …" asks
for a name, creates it and adds the image(s), and every change is announced
with a toast when the main window has one. ``tag_album_dialog`` re-exports the
three ``build_*`` functions the right-click menus import.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QInputDialog, QMenu

from Imervue.gui.tag_album_logic import (
    ALBUM_CREATE, ALBUM_CREATE_FALLBACK, ALBUM_CREATE_PROMPT, ALBUM_NAME_FALLBACK,
    TAG_CREATE, TAG_CREATE_FALLBACK, TAG_CREATE_PROMPT, TAG_NAME_FALLBACK, entered_name,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.tags import (
    add_tag, add_to_album, create_album, create_tag, get_all_albums, get_all_tags,
    get_tags_for_image, remove_from_album, remove_tag,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def build_tag_submenu(main_gui: GPUImageView, path: str, parent_menu: QMenu):
    """Build 'Add to Tag' submenu for right-click context menu."""
    lang = language_wrapper.language_word_dict
    tag_menu = parent_menu.addMenu(lang.get("tag_menu_title", "Tags"))

    tags = get_all_tags()
    current_tags = get_tags_for_image(path)

    for tag_name in sorted(tags.keys()):
        action = tag_menu.addAction(tag_name)
        action.setCheckable(True)
        action.setChecked(tag_name in current_tags)
        action.triggered.connect(
            lambda checked, t=tag_name: _toggle_tag(main_gui, t, path)
        )

    if tags:
        tag_menu.addSeparator()

    new_action = tag_menu.addAction(lang.get("tag_create_and_add", "+ New Tag..."))
    new_action.triggered.connect(lambda: _create_and_add_tag(main_gui, path))


def build_album_submenu(main_gui: GPUImageView, path: str, parent_menu: QMenu):
    """Build 'Add to Album' submenu for right-click context menu."""
    lang = language_wrapper.language_word_dict
    album_menu = parent_menu.addMenu(lang.get("album_menu_title", "Albums"))

    albums = get_all_albums()

    for album_name in sorted(albums.keys()):
        in_album = path in albums[album_name]
        action = album_menu.addAction(album_name)
        action.setCheckable(True)
        action.setChecked(in_album)
        action.triggered.connect(
            lambda checked, a=album_name: _toggle_album(main_gui, a, path)
        )

    if albums:
        album_menu.addSeparator()

    new_action = album_menu.addAction(lang.get("album_create_and_add", "+ New Album..."))
    new_action.triggered.connect(lambda: _create_and_add_album(main_gui, path))


def build_batch_tag_album_submenu(main_gui: GPUImageView, paths: list[str], parent_menu: QMenu):
    """Build tag/album submenu for batch selected images."""
    lang = language_wrapper.language_word_dict

    # Batch add to tag
    tag_menu = parent_menu.addMenu(lang.get("batch_tag_title", "Add to Tag"))
    tags = get_all_tags()
    for tag_name in sorted(tags.keys()):
        action = tag_menu.addAction(tag_name)
        action.triggered.connect(
            lambda checked, t=tag_name: _batch_add_tag(main_gui, t, paths)
        )
    if tags:
        tag_menu.addSeparator()
    new_action = tag_menu.addAction(lang.get("tag_create_and_add", "+ New Tag..."))
    new_action.triggered.connect(lambda: _batch_create_and_add_tag(main_gui, paths))

    # Batch add to album
    album_menu = parent_menu.addMenu(lang.get("batch_album_title", "Add to Album"))
    albums = get_all_albums()
    for album_name in sorted(albums.keys()):
        action = album_menu.addAction(album_name)
        action.triggered.connect(
            lambda checked, a=album_name: _batch_add_album(main_gui, a, paths)
        )
    if albums:
        album_menu.addSeparator()
    new_action = album_menu.addAction(lang.get("album_create_and_add", "+ New Album..."))
    new_action.triggered.connect(lambda: _batch_create_and_add_album(main_gui, paths))


def _ask_tag_name(main_gui: GPUImageView) -> str | None:
    lang = language_wrapper.language_word_dict
    return entered_name(*QInputDialog.getText(
        main_gui, lang.get(TAG_CREATE, TAG_CREATE_FALLBACK),
        lang.get(TAG_CREATE_PROMPT, TAG_NAME_FALLBACK)))


def _ask_album_name(main_gui: GPUImageView) -> str | None:
    lang = language_wrapper.language_word_dict
    return entered_name(*QInputDialog.getText(
        main_gui, lang.get(ALBUM_CREATE, ALBUM_CREATE_FALLBACK),
        lang.get(ALBUM_CREATE_PROMPT, ALBUM_NAME_FALLBACK)))


def _toggle_tag(main_gui: GPUImageView, tag_name: str, path: str):
    if path in get_all_tags().get(tag_name, []):
        remove_tag(tag_name, path)
        _toast(main_gui, f"Removed from '{tag_name}'")
    else:
        add_tag(tag_name, path)
        _toast(main_gui, f"Tagged '{tag_name}'")


def _create_and_add_tag(main_gui: GPUImageView, path: str):
    name = _ask_tag_name(main_gui)
    if name:
        create_tag(name)
        add_tag(name, path)
        _toast(main_gui, f"Tagged '{name}'")


def _toggle_album(main_gui: GPUImageView, album_name: str, path: str):
    if path in get_all_albums().get(album_name, []):
        remove_from_album(album_name, path)
        _toast(main_gui, f"Removed from '{album_name}'")
    else:
        add_to_album(album_name, path)
        _toast(main_gui, f"Added to '{album_name}'")


def _create_and_add_album(main_gui: GPUImageView, path: str):
    name = _ask_album_name(main_gui)
    if name:
        create_album(name)
        add_to_album(name, path)
        _toast(main_gui, f"Added to '{name}'")


def _batch_add_tag(main_gui: GPUImageView, tag_name: str, paths: list[str]):
    count = sum(1 for p in paths if add_tag(tag_name, p))
    _toast(main_gui, f"Tagged {count} image(s) as '{tag_name}'")


def _batch_create_and_add_tag(main_gui: GPUImageView, paths: list[str]):
    name = _ask_tag_name(main_gui)
    if name:
        create_tag(name)
        _batch_add_tag(main_gui, name, paths)


def _batch_add_album(main_gui: GPUImageView, album_name: str, paths: list[str]):
    count = sum(1 for p in paths if add_to_album(album_name, p))
    _toast(main_gui, f"Added {count} image(s) to '{album_name}'")


def _batch_create_and_add_album(main_gui: GPUImageView, paths: list[str]):
    name = _ask_album_name(main_gui)
    if name:
        create_album(name)
        _batch_add_album(main_gui, name, paths)


def _toast(main_gui: GPUImageView, msg: str):
    if hasattr(main_gui.main_window, "toast"):
        main_gui.main_window.toast.info(msg)
