from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def compute_visible_range(main_gui: GPUImageView):
    if not main_gui.tile_grid_mode:
        return 0, 0

    base_tile = main_gui.thumbnail_size or 256
    scaled_tile = base_tile * main_gui.tile_scale
    cols = max(1, math.ceil(main_gui.width() / scaled_tile))

    row_height = scaled_tile

    visible_top = -main_gui.grid_offset_y
    visible_bottom = visible_top + main_gui.height()

    first_row = max(0, int(visible_top // row_height))
    last_row = int(visible_bottom // row_height) + 1

    # 加 buffer
    buffer_rows = 2
    first_row = max(0, first_row - buffer_rows)
    last_row += buffer_rows

    start_index = first_row * cols
    end_index = (last_row + 1) * cols

    return start_index, min(end_index, len(main_gui.model.images))
