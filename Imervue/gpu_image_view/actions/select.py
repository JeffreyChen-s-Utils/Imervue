from __future__ import annotations

from typing import TYPE_CHECKING

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
