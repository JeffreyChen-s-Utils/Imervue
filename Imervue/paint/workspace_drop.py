"""Drag-and-drop file open for the Paint workspace.

Split out of :mod:`paint_workspace` to keep the coordinator small.
:class:`FileDropMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace` ahead of
``QMainWindow`` so its Qt drag / drop overrides are the ones Qt dispatches.
"""
from __future__ import annotations

import logging

from Imervue.image.formats import JPEG_EXTENSIONS
from Imervue.image.read_errors import IMAGE_READ_ERRORS

logger = logging.getLogger("Imervue.paint.workspace")


class FileDropMixin:
    """Accept file-URL drops and open each supported file.

    Expects the host to provide ``_canvas``, ``_tab_dirty``, ``new_tab``,
    ``load_image`` and (optionally) ``_file_menu_bridge``.
    """

    SUPPORTED_DROP_EXTS = tuple(sorted(
        {".imervue", ".psd", ".png", ".tif", ".tiff", ".bmp", ".webp"} | JPEG_EXTENSIONS))

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Accept file URL drops the workspace knows how to open."""
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        for url in mime.urls():
            if url.isLocalFile() and self._is_supported_drop(url.toLocalFile()):
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        # Mirror dragEnter — Qt requires both for a clean drop visual.
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        """Open every supported file the user dropped.

        PSDs route through the file-menu bridge so the open feeds the
        recent-files list. Plain raster files are loaded into the active
        canvas via load_image — same path as the existing File ▸ Open
        flow for non-PSDs.
        """
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        opened_any = False
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if not self._is_supported_drop(path):
                continue
            self._open_dropped_path(path)
            opened_any = True
        if opened_any:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _is_supported_drop(self, path: str) -> bool:
        lowered = path.lower()
        return any(lowered.endswith(ext) for ext in self.SUPPORTED_DROP_EXTS)

    def _open_dropped_path(self, path: str) -> None:
        if path.lower().endswith(".imervue"):
            self._file_menu_bridge.open_document_at(path)
            return
        if path.lower().endswith(".psd"):
            bridge = getattr(self, "_file_menu_bridge", None)
            if bridge is not None and hasattr(bridge, "open_psd_at"):
                bridge.open_psd_at(path)
                return
        # Plain raster: load via Pillow, push into the active canvas.
        try:
            from Imervue.gpu_image_view.images.image_loader import decode_image_file
            rgba = decode_image_file(path)   # RAW developed, sRGB, upright, like the viewer
            # Route through the wrapper (not self._canvas.load_image) so the layer
            # dock is rebound to the new document; the bare canvas call left the
            # dock showing / mutating the replaced document.
            if self._tab_dirty.get(self._canvas, False):
                self.new_tab(width=1, height=1)
            self.load_image(rgba, source_path=path)
            from Imervue.paint import recent_files
            recent_files.add(path)
            bridge = getattr(self, "_file_menu_bridge", None)
            if bridge is not None and hasattr(bridge, "refresh_recent_menu"):
                bridge.refresh_recent_menu()
        except IMAGE_READ_ERRORS as exc:
            logger.warning("dropped file %r could not be opened: %s", path, exc)
