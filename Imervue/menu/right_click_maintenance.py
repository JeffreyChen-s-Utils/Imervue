"""Run library maintenance and ordered staging-tray operations."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu
from Imervue.multi_language.language_wrapper import language_wrapper
import os
from Imervue.gpu_image_view.actions.select import selected_in_view_order
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _maintenance_action(main_gui: GPUImageView, menu: QMenu):
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("maintenance_menu", "Library Maintenance…"))
    action.triggered.connect(lambda: _library_maintenance(main_gui))


def _library_maintenance(main_gui: GPUImageView) -> None:
    from Imervue.library import image_index
    from Imervue.library.maintenance import run_maintenance

    folders = image_index.list_library_roots()
    if not folders:
        images = main_gui.model.images
        folders = [os.path.dirname(images[0])] if images else []
    if not folders:
        return
    lang = language_wrapper.language_word_dict
    toast = getattr(main_gui.main_window, "toast", None)
    result = run_maintenance(folders)
    if result["missing"]:
        from Imervue.gui.dialog_rows import confirm

        question = lang.get("maintenance_prune_q", "Remove {n} missing file(s) from the index?")
        question = question.format(n=result["missing"])
        if confirm(main_gui, lang.get("maintenance_menu", "Library Maintenance…"), question):
            run_maintenance(folders, prune=True)
            if toast is not None:
                toast.success(
                    lang.get("maintenance_pruned", "Pruned {n} missing").format(n=result["missing"])
                )
            return
    if toast is not None:
        toast.info(
            lang.get("maintenance_summary", "{missing} missing, {new} new").format(
                missing=result["missing"], new=result["new"]
            )
        )


def _staging_tray_actions(main_gui: GPUImageView, menu: QMenu) -> None:
    if not main_gui.model.images:
        return
    lang = language_wrapper.language_word_dict
    tray_menu = menu.addMenu(lang.get("staging_tray_title", "Staging Tray"))
    add_action = tray_menu.addAction(
        lang.get("staging_tray_add_selected", "Add selected tiles"),
    )
    add_action.triggered.connect(lambda: _add_to_staging_tray(main_gui))
    open_action = tray_menu.addAction(
        lang.get("staging_tray_open", "Open Staging Tray"),
    )
    open_action.triggered.connect(lambda: _open_staging_tray(main_gui))


def _add_to_staging_tray(main_gui: GPUImageView) -> None:
    from Imervue.library import staging_tray

    paths = selected_in_view_order(main_gui)
    if not paths and main_gui.deep_zoom and main_gui.model.images:
        paths = [main_gui.model.images[main_gui.current_index]]
    if not paths:
        return
    staging_tray.add_many(paths)
    if hasattr(main_gui.main_window, "toast"):
        lang = language_wrapper.language_word_dict
        main_gui.main_window.toast.success(
            lang.get("staging_tray_added", "Added {n} item(s) to tray").format(
                n=len(paths),
            ),
        )


def _open_staging_tray(main_gui: GPUImageView) -> None:
    from Imervue.gui.staging_tray_dialog import open_staging_tray

    open_staging_tray(main_gui.main_window)
