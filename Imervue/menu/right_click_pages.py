"""Split and combine multipage documents with read-error reporting."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QMenu
from Imervue.multi_language.language_wrapper import language_wrapper
import logging
from Imervue.gpu_image_view.actions.select import selected_in_view_order
from Imervue.menu.right_click_current import _current_image_path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _split_pages_action(main_gui: GPUImageView, menu: QMenu):
    if not main_gui.deep_zoom:
        return
    lang = language_wrapper.language_word_dict
    action = menu.addAction(lang.get("multipage_split", "Split Pages…"))
    action.triggered.connect(lambda: _split_multipage(main_gui))


def _split_multipage(main_gui: GPUImageView) -> None:
    from PySide6.QtWidgets import QFileDialog
    from PIL import Image
    from Imervue.image.multipage import page_count, split_multipage
    from Imervue.image.read_errors import IMAGE_READ_ERRORS

    path = _current_image_path(main_gui)
    if not path:
        return
    lang = language_wrapper.language_word_dict
    toast = getattr(main_gui.main_window, "toast", None)
    try:
        with Image.open(path) as img:
            frames = page_count(img)
    except IMAGE_READ_ERRORS:
        frames = 1
    if frames <= 1:
        if toast is not None:
            toast.info(lang.get("multipage_split_none", "Not a multi-page file"))
        return
    out_dir = QFileDialog.getExistingDirectory(
        main_gui, lang.get("multipage_split", "Split Pages…")
    )
    if not out_dir:
        return
    saved = split_multipage(path, out_dir)
    if toast is not None:
        toast.success(lang.get("multipage_split_done", "Split into {n} pages").format(n=len(saved)))


def _combine_multipage(main_gui: GPUImageView) -> None:
    from PySide6.QtWidgets import QFileDialog
    from Imervue.image.multipage import combine_to_multipage
    from Imervue.image.read_errors import IMAGE_READ_ERRORS

    paths = selected_in_view_order(main_gui)  # page order
    if not paths:
        return
    lang = language_wrapper.language_word_dict
    dest, _ = QFileDialog.getSaveFileName(
        main_gui,
        lang.get("multipage_combine", "Combine to PDF / TIFF…"),
        "",
        "PDF (*.pdf);;TIFF (*.tiff)",
    )
    if not dest:
        return
    toast = getattr(main_gui.main_window, "toast", None)
    try:
        result = combine_to_multipage(paths, dest)
    except IMAGE_READ_ERRORS as exc:  # a page that can't be decoded, or a failed save
        logging.getLogger("Imervue.right_click_menu").warning(
            "Combining %d pages into %s failed", len(paths), dest, exc_info=True
        )
        if toast is not None:
            toast.error(str(exc))
        return
    if toast is not None:
        toast.success(
            lang.get("multipage_combine_done", "Combined {n} pages → {name}").format(
                n=result["pages"], name=Path(dest).name
            )
        )
