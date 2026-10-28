"""Run metadata, culling, orientation and dated-import batches with count reporting."""

from __future__ import annotations

from Imervue.multi_language.language_wrapper import language_wrapper
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _tag_by_location(main_gui: GPUImageView) -> None:
    from Imervue.image.geo_keywords import tag_paths_by_location

    count = tag_paths_by_location(list(main_gui.selected_tiles))
    _report_count(
        main_gui,
        count,
        "batch_geo_keywords_done",
        "Tagged {n} photo(s) by location",
        "batch_geo_keywords_none",
        "No geotagged images found",
    )


def _index_keywords(main_gui: GPUImageView) -> None:
    from Imervue.library.keyword_index import import_keywords_to_index

    count = import_keywords_to_index(list(main_gui.selected_tiles))
    _report_count(
        main_gui,
        count,
        "batch_index_keywords_done",
        "Indexed keywords from {n} photo(s)",
        "batch_index_keywords_none",
        "No keywords found to index",
    )


def _auto_cull_blurry(main_gui: GPUImageView) -> None:
    from Imervue.library.auto_cull import auto_cull_blurry

    count = auto_cull_blurry(list(main_gui.selected_tiles))
    main_gui.update()
    _report_count(
        main_gui,
        count,
        "batch_auto_cull_done",
        "Flagged {n} blurry photo(s) as reject",
        "batch_auto_cull_none",
        "No blurry photos found",
    )


def _auto_cull_low_quality(main_gui: GPUImageView) -> None:
    from Imervue.library.quality_cull import auto_cull_low_quality

    count = auto_cull_low_quality(list(main_gui.selected_tiles))
    main_gui.update()
    _report_count(
        main_gui,
        count,
        "batch_quality_cull_done",
        "Flagged {n} low-quality photo(s) as reject",
        "batch_quality_cull_none",
        "No images to cull",
    )


def _auto_orient(main_gui: GPUImageView) -> None:
    """Write an upright PNG copy (``<stem>_oriented.png``, then ``_1``…) of each selected image."""
    from Imervue.gui._apply_save import output_path
    from Imervue.gui.export_source import recipe_base_image
    from Imervue.image.read_errors import IMAGE_READ_ERRORS

    paths = list(main_gui.selected_tiles)
    lang = language_wrapper.language_word_dict
    toast = getattr(main_gui.main_window, "toast", None)
    count = 0
    for path in paths:
        try:
            # The viewer's decode: upright, sRGB (the copy has no ICC), full-size RAW.
            image = recipe_base_image(path, None)
            # A free name: an earlier copy may have been retouched since, and
            # p.jpg and p.png in one selection both want p_oriented.png.
            image.save(output_path(path, "oriented"))
        except IMAGE_READ_ERRORS:
            logging.getLogger("Imervue.right_click_menu").warning(
                "Auto-orient failed for %s", path, exc_info=True
            )
            continue
        count += 1
    if toast is None:
        return
    if count:
        toast.success(lang.get("batch_auto_orient_done", "Oriented {n} photo(s)").format(n=count))
    else:
        toast.info(lang.get("batch_auto_orient_none", "No images to orient"))


def _import_by_date(main_gui: GPUImageView) -> None:
    from PySide6.QtWidgets import QFileDialog
    from Imervue.library.date_import import import_by_date

    paths = list(main_gui.selected_tiles)
    if not paths:
        return
    lang = language_wrapper.language_word_dict
    out_dir = QFileDialog.getExistingDirectory(
        main_gui, lang.get("date_import_menu", "Import to Dated Folders…")
    )
    if not out_dir:
        return
    count = import_by_date(paths, out_dir)
    toast = getattr(main_gui.main_window, "toast", None)
    if toast is None:
        return
    if count:
        toast.success(lang.get("date_import_done", "Imported {n} file(s) by date").format(n=count))
    else:
        toast.info(lang.get("date_import_none", "No files to import"))


def _report_count(main_gui, count, success_key, success_text, empty_key, empty_text):
    """Report a completed batch count after its operation-specific side effects."""
    if not hasattr(main_gui.main_window, "toast"):
        return
    lang = language_wrapper.language_word_dict
    if count:
        main_gui.main_window.toast.success(lang.get(success_key, success_text).format(n=count))
    else:
        main_gui.main_window.toast.info(lang.get(empty_key, empty_text))
