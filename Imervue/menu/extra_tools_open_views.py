"""Openers for the Extra Tools Views, Workflow and Export submenus.

Each opener imports its dialog lazily, so building the menu loads none of them.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


def _open_culling(ui: ImervueMainWindow):
    from Imervue.gui.culling_dialog import open_culling
    open_culling(ui)


def _open_staging_tray(ui: ImervueMainWindow):
    from Imervue.gui.staging_tray_dialog import open_staging_tray
    open_staging_tray(ui)


def _open_reference_panel(ui: ImervueMainWindow):
    from Imervue.gui.reference_panel_dialog import open_reference_panel
    open_reference_panel(ui)


def _open_dual_pane(ui: ImervueMainWindow):
    from Imervue.gui.dual_pane_dialog import open_dual_pane
    open_dual_pane(ui)


def _open_timeline(ui: ImervueMainWindow, granularity: str):
    from Imervue.gui.timeline_view import open_timeline
    open_timeline(ui, granularity)


def _open_macro_manager(ui: ImervueMainWindow):
    from Imervue.gui.macro_manager_dialog import open_macro_manager_dialog
    open_macro_manager_dialog(ui)


def _open_watch_folder(ui: ImervueMainWindow):
    from Imervue.gui.watch_folder_dialog import open_watch_folder
    open_watch_folder(ui.viewer)


def _open_contact_sheet(ui: ImervueMainWindow):
    from Imervue.gui.contact_sheet_dialog import open_contact_sheet_dialog
    open_contact_sheet_dialog(ui)


def _open_web_gallery(ui: ImervueMainWindow):
    from Imervue.gui.web_gallery_dialog import open_web_gallery_dialog
    open_web_gallery_dialog(ui)


def _open_slideshow_mp4(ui: ImervueMainWindow):
    from Imervue.gui.slideshow_mp4_dialog import open_slideshow_mp4_dialog
    open_slideshow_mp4_dialog(ui)


def _open_calendar_view(ui: ImervueMainWindow):
    from Imervue.gui.calendar_view_dialog import open_calendar_view
    open_calendar_view(ui)


def _open_map_view(ui: ImervueMainWindow):
    from Imervue.gui.map_view_dialog import open_map_view
    open_map_view(ui)


def _open_image_inspector(ui: ImervueMainWindow):
    from Imervue.gui.image_inspector_dialog import open_image_inspector
    open_image_inspector(ui.viewer)


def _open_tiny_planet(ui: ImervueMainWindow):
    from Imervue.gui.tiny_planet_dialog import open_tiny_planet
    open_tiny_planet(ui.viewer)


def _open_test_charts(ui: ImervueMainWindow) -> None:
    from Imervue.gui.test_charts_dialog import open_test_charts
    open_test_charts(ui.viewer)


def _open_quality_report(ui: ImervueMainWindow) -> None:
    from Imervue.gui.quality_report_dialog import open_quality_report
    open_quality_report(ui.viewer)


def _open_image_statistics(ui: ImervueMainWindow) -> None:
    from Imervue.gui.image_statistics_dialog import open_image_statistics
    open_image_statistics(ui.viewer)


def _open_virtual_copies(ui: ImervueMainWindow):
    from Imervue.gui.virtual_copies_dialog import open_virtual_copies
    open_virtual_copies(ui.viewer)


def _open_print_layout(ui: ImervueMainWindow):
    from Imervue.gui.print_layout_dialog import open_print_layout
    open_print_layout(ui)


def _open_collage(ui: ImervueMainWindow):
    from Imervue.gui.collage_dialog import open_collage
    open_collage(ui.viewer)


def _open_id_photo_sheet(ui: ImervueMainWindow):
    from Imervue.gui.id_photo_sheet_dialog import open_id_photo_sheet
    open_id_photo_sheet(ui.viewer)

