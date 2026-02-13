from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

def switch_to_next_image(main_gui: GPUImageView) -> None:
    images = main_gui.model.images

    if not images:
        return

    if main_gui.current_index < len(images) - 1:
        main_gui.current_index += 1
        main_gui.load_deep_zoom_image(images[main_gui.current_index])

    main_gui.update()



def switch_to_previous_image(main_gui: GPUImageView) -> None:
    images = main_gui.model.images

    if not images:
        return

    if main_gui.current_index > 0:
        main_gui.current_index -= 1
        main_gui.load_deep_zoom_image(images[main_gui.current_index])

    main_gui.update()


def select_tiles_in_rect(start_pos, end_pos, main_gui: GPUImageView):
    if start_pos is None or end_pos is None:
        return

    x0, y0 = start_pos.x(), start_pos.y()
    x1, y1 = end_pos.x(), end_pos.y()
    rect = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

    for tx0, ty0, tx1, ty1, path in main_gui.tile_rects:
        tile_rect = QRectF(tx0, ty0, tx1 - tx0, ty1 - ty0)
        if rect.intersects(tile_rect):
            main_gui.selected_tiles.add(path)
