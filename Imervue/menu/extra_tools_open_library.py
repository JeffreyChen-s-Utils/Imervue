"""Openers for the Extra Tools Batch and Library & Metadata submenus.

Each opener imports its dialog lazily, so building the menu loads none of them.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def _open_batch_convert(ui: ImervueMainWindow):
    from Imervue.gui.batch_convert_dialog import open_batch_convert
    open_batch_convert(ui.viewer)


def _open_duplicate_detection(ui: ImervueMainWindow):
    from Imervue.gui.duplicate_detection_dialog import open_duplicate_detection
    open_duplicate_detection(ui.viewer)


def _open_image_organizer(ui: ImervueMainWindow):
    from Imervue.gui.image_organizer_dialog import open_image_organizer
    open_image_organizer(ui.viewer)


def _open_exif_strip(ui: ImervueMainWindow):
    from Imervue.gui.exif_strip_dialog import open_exif_strip
    open_exif_strip(ui.viewer)


def _open_image_sanitize(ui: ImervueMainWindow):
    from Imervue.gui.image_sanitize_dialog import open_image_sanitize
    open_image_sanitize(ui.viewer)


def _open_library_search(ui: ImervueMainWindow):
    from Imervue.gui.library_search_dialog import open_library_search
    open_library_search(ui)


def _open_smart_albums(ui: ImervueMainWindow):
    from Imervue.gui.smart_albums_dialog import open_smart_albums
    open_smart_albums(ui)


def _open_similar_search(ui: ImervueMainWindow):
    from Imervue.gui.similar_search_dialog import open_similar_search
    open_similar_search(ui)


def _open_auto_tag(ui: ImervueMainWindow):
    from Imervue.gui.auto_tag_dialog import open_auto_tag
    open_auto_tag(ui)


def _open_hierarchical_tags(ui: ImervueMainWindow):
    from Imervue.gui.hierarchical_tags_dialog import open_hierarchical_tags
    open_hierarchical_tags(ui)


def _open_token_rename(ui: ImervueMainWindow):
    from Imervue.gui.token_rename_dialog import open_token_rename
    open_token_rename(ui)


def _open_metadata_export(ui: ImervueMainWindow):
    from Imervue.gui.metadata_export_dialog import open_metadata_export
    open_metadata_export(ui)


def _open_xmp_sidecar(ui: ImervueMainWindow):
    from Imervue.gui.xmp_sidecar_dialog import open_xmp_sidecar
    open_xmp_sidecar(ui)


def _open_semantic_search(ui: ImervueMainWindow):
    from Imervue.gui.semantic_search_dialog import open_semantic_search_dialog
    open_semantic_search_dialog(ui.viewer)


def _open_binarize(ui: ImervueMainWindow) -> None:
    from Imervue.gui.binarize_dialog import open_binarize
    open_binarize(ui.viewer)


def _open_otsu(ui: ImervueMainWindow) -> None:
    from Imervue.gui.otsu_dialog import open_otsu
    open_otsu(ui.viewer)


def _open_animation_edit(ui: ImervueMainWindow) -> None:
    from Imervue.gui.animation_edit_dialog import open_animation_edit
    open_animation_edit(ui.viewer)


def _open_optimize(ui: ImervueMainWindow) -> None:
    from Imervue.gui.optimize_dialog import open_optimize
    open_optimize(ui.viewer)


def _open_meme(ui: ImervueMainWindow) -> None:
    from Imervue.gui.meme_dialog import open_meme
    open_meme(ui.viewer)


def _open_steganography(ui: ImervueMainWindow) -> None:
    from Imervue.gui.steganography_dialog import open_steganography
    open_steganography(ui.viewer)


def _open_deflicker(ui: ImervueMainWindow) -> None:
    from Imervue.gui.deflicker_dialog import open_deflicker_dialog
    open_deflicker_dialog(ui.viewer)


def _open_gps_geotag(ui: ImervueMainWindow):
    from Imervue.gui.gps_geotag_dialog import open_gps_geotag
    open_gps_geotag(ui.viewer)


def _open_gpx_geotag(ui: ImervueMainWindow):
    from Imervue.gui.gpx_geotag_dialog import open_gpx_geotag
    open_gpx_geotag(ui)


def _open_capture_time(ui: ImervueMainWindow):
    from Imervue.gui.capture_time_dialog import open_capture_time
    open_capture_time(ui)


def _open_metadata_template(ui: ImervueMainWindow):
    from Imervue.gui.metadata_template_dialog import open_metadata_template
    open_metadata_template(ui)


def _open_cache_maintenance(ui: ImervueMainWindow):
    from Imervue.gui.cache_maintenance_dialog import open_cache_maintenance
    open_cache_maintenance(ui)

