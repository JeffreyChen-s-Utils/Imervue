"""
Drag-out support — start a QDrag with file URIs from the tile grid so images
can be dropped into Explorer, Chrome, Discord, or any other drop target.

The drag payload is a standard ``text/uri-list`` + ``application/x-qt-windows-mime``
on Windows, set via ``QMimeData.setUrls``, which is what all the major native
apps understand.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMimeData, QUrl, Qt
from PySide6.QtGui import QDrag, QPixmap

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def try_start_drag_out(main_gui: GPUImageView, press_pos) -> bool:
    """Start a drag-out if the press is over a selected tile. Returns True when
    a drag was initiated so the caller should skip its rectangle-select path.
    """
    if not main_gui.tile_grid_mode:
        return False
    mx, my = press_pos.x(), press_pos.y()
    hit_path: str | None = None
    for x0, y0, x1, y1, path in main_gui.tile_rects:
        if x0 <= mx <= x1 and y0 <= my <= y1:
            hit_path = path
            break
    if hit_path is None:
        return False

    selected = set(main_gui.selected_tiles)
    if hit_path not in selected:
        # Only drag when the user has already flagged which tiles go.
        return False

    return _do_drag(main_gui, sorted(selected))


def _do_drag(main_gui: GPUImageView, paths: list[str]) -> bool:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths if Path(p).is_file()])
    if not mime.urls():
        return False
    drag = QDrag(main_gui)
    drag.setMimeData(mime)
    pixmap = _build_preview_pixmap(main_gui, paths[0])
    if pixmap is not None:
        drag.setPixmap(pixmap)
    drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction, Qt.DropAction.CopyAction)
    return True


def _build_preview_pixmap(_main_gui: GPUImageView, path: str) -> QPixmap | None:
    """Reuse the cached thumbnail if available; fall back to a plain rect."""
    from PIL import Image
    from PySide6.QtGui import QImage
    try:
        with Image.open(path) as src:
            src.thumbnail((96, 96), Image.Resampling.LANCZOS)
            im = src.convert("RGBA")
            data = im.tobytes("raw", "RGBA")
            qimg = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
            return QPixmap.fromImage(qimg.copy())
    except Exception:  # noqa: BLE001
        return None
