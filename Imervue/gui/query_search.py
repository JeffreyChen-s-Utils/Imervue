"""Query-search entry point — prompt for a query string and filter the grid.

Thin Qt wrapper over :func:`Imervue.library.search_query.parse_query` and
``smart_album.apply_to_paths`` (the same filtering the Smart Albums dialog uses).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QInputDialog

from Imervue.library import smart_album
from Imervue.library.search_query import parse_query
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def open_query_search(main_gui: GPUImageView) -> None:  # pragma: no cover - Qt UI
    lang = language_wrapper.language_word_dict
    text, ok = QInputDialog.getText(
        main_gui,
        lang.get("query_search_title", "Search by Query"),
        lang.get("query_search_prompt",
                 "e.g. kw:beach rating:>=4 type:video place:Paris"),
    )
    if not ok or not text.strip():
        return
    base = getattr(main_gui, "_unfiltered_images", None) or list(main_gui.model.images)
    filtered = smart_album.apply_to_paths(base, parse_query(text))
    toast = getattr(main_gui.main_window, "toast", None)
    if not filtered:
        if toast is not None:
            toast.info(lang.get("query_search_none", "No images match the query"))
        return
    main_gui._unfiltered_images = list(base)
    main_gui.clear_tile_grid()
    main_gui.load_tile_grid_async(filtered)
    if toast is not None:
        toast.success(lang.get("query_search_done", "{n} match").format(n=len(filtered)))
