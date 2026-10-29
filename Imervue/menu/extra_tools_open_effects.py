"""Openers for the creative effects of the Develop submenu and the Retouch & Transform
and Multi-Image submenus of Extra Tools.

Each opener imports its dialog lazily, so building the menu loads none of them.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def _open_ai_upscale(ui: ImervueMainWindow):
    from Imervue.gui.ai_upscale_dialog import open_ai_upscale
    open_ai_upscale(ui.viewer)


def _open_posterize(ui: ImervueMainWindow) -> None:
    from Imervue.gui.posterize_dialog import open_posterize_dialog
    open_posterize_dialog(ui.viewer)


def _open_solarize(ui: ImervueMainWindow) -> None:
    from Imervue.gui.solarize_dialog import open_solarize
    open_solarize(ui.viewer)


def _open_glow(ui: ImervueMainWindow) -> None:
    from Imervue.gui.glow_dialog import open_glow
    open_glow(ui.viewer)


def _open_emboss(ui: ImervueMainWindow) -> None:
    from Imervue.gui.emboss_dialog import open_emboss
    open_emboss(ui.viewer)


def _open_polar(ui: ImervueMainWindow) -> None:
    from Imervue.gui.polar_dialog import open_polar
    open_polar(ui.viewer)


def _open_kaleidoscope(ui: ImervueMainWindow) -> None:
    from Imervue.gui.kaleidoscope_dialog import open_kaleidoscope
    open_kaleidoscope(ui.viewer)


def _open_frosted_glass(ui: ImervueMainWindow) -> None:
    from Imervue.gui.frosted_glass_dialog import open_frosted_glass
    open_frosted_glass(ui.viewer)


def _open_colormap(ui: ImervueMainWindow) -> None:
    from Imervue.gui.colormap_dialog import open_colormap
    open_colormap(ui.viewer)


def _open_distort(ui: ImervueMainWindow) -> None:
    from Imervue.gui.distort_dialog import open_distort
    open_distort(ui.viewer)


def _open_pixel_sort(ui: ImervueMainWindow) -> None:
    from Imervue.gui.pixel_sort_dialog import open_pixel_sort
    open_pixel_sort(ui.viewer)


def _open_anaglyph(ui: ImervueMainWindow) -> None:
    from Imervue.gui.anaglyph_dialog import open_anaglyph
    open_anaglyph(ui.viewer)


def _open_film_grain(ui: ImervueMainWindow) -> None:
    from Imervue.gui.film_grain_dialog import open_film_grain_dialog
    open_film_grain_dialog(ui.viewer)


def _open_lens_flare(ui: ImervueMainWindow) -> None:
    from Imervue.gui.lens_flare_dialog import open_lens_flare_dialog
    open_lens_flare_dialog(ui.viewer)


def _open_frequency_separation(ui: ImervueMainWindow) -> None:
    from Imervue.gui.frequency_separation_dialog import (
        open_frequency_separation_dialog,
    )
    open_frequency_separation_dialog(ui.viewer)


def _open_smart_crop(ui: ImervueMainWindow) -> None:
    from Imervue.gui.smart_crop_dialog import open_smart_crop_dialog
    open_smart_crop_dialog(ui.viewer)


def _open_portrait_retouch(ui: ImervueMainWindow) -> None:
    from Imervue.gui.portrait_retouch_dialog import open_portrait_retouch_dialog
    open_portrait_retouch_dialog(ui.viewer)


def _open_face_detection(ui: ImervueMainWindow):
    from Imervue.gui.face_detection_dialog import open_face_detection
    open_face_detection(ui.viewer)


def _open_lens_correction(ui: ImervueMainWindow):
    from Imervue.gui.lens_correction_dialog import open_lens_correction
    open_lens_correction(ui.viewer)


def _open_scale_bar(ui: ImervueMainWindow):
    from Imervue.gui.scale_bar_dialog import open_scale_bar
    open_scale_bar(ui.viewer)


def _open_healing_brush(ui: ImervueMainWindow):
    from Imervue.gui.healing_brush_dialog import open_healing_brush
    open_healing_brush(ui.viewer)


def _open_hdr_merge(ui: ImervueMainWindow):
    from Imervue.gui.hdr_merge_dialog import open_hdr_merge
    open_hdr_merge(ui.viewer)


def _open_panorama(ui: ImervueMainWindow):
    from Imervue.gui.panorama_dialog import open_panorama
    open_panorama(ui.viewer)


def _open_focus_stack(ui: ImervueMainWindow):
    from Imervue.gui.focus_stack_dialog import open_focus_stack
    open_focus_stack(ui.viewer)


def _open_stack_blend(ui: ImervueMainWindow):
    from Imervue.gui.stack_blend_dialog import open_stack_blend
    open_stack_blend(ui.viewer)


def _open_clone_stamp(ui: ImervueMainWindow):
    from Imervue.gui.clone_stamp_dialog import open_clone_stamp
    open_clone_stamp(ui.viewer)


def _open_crop_straighten(ui: ImervueMainWindow):
    from Imervue.gui.crop_straighten_dialog import open_crop_straighten
    open_crop_straighten(ui.viewer)


def _open_auto_straighten(ui: ImervueMainWindow):
    from Imervue.gui.auto_straighten_dialog import open_auto_straighten
    open_auto_straighten(ui.viewer)


def _open_noise_sharpen(ui: ImervueMainWindow):
    from Imervue.gui.noise_sharpen_dialog import open_noise_sharpen
    open_noise_sharpen(ui.viewer)


def _open_sky_replace(ui: ImervueMainWindow):
    from Imervue.gui.sky_replace_dialog import open_sky_replace
    open_sky_replace(ui.viewer)


def _open_photo_frame(ui: ImervueMainWindow):
    from Imervue.gui.photo_frame_dialog import open_photo_frame
    open_photo_frame(ui.viewer)


def _open_dither(ui: ImervueMainWindow):
    from Imervue.gui.dither_dialog import open_dither
    open_dither(ui.viewer)

