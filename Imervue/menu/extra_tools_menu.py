from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.multi_language.language_wrapper import language_wrapper


def build_extra_tools_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict
    menu = ui.menuBar().addMenu(lang.get("extra_tools_menu", "Extra Tools"))

    _build_batch_submenu(menu, ui, lang)
    _build_library_submenu(menu, ui, lang)
    _build_views_submenu(menu, ui, lang)
    _build_workflow_submenu(menu, ui, lang)
    _build_export_submenu(menu, ui, lang)
    _build_develop_submenu(menu, ui, lang)
    _build_retouch_submenu(menu, ui, lang)
    _build_multi_image_submenu(menu, ui, lang)


def _add_action(submenu, lang: dict, key: str, fallback: str, callback) -> None:
    action = submenu.addAction(lang.get(key, fallback))
    action.triggered.connect(callback)


# --- Submenus ---------------------------------------------------------------

def _build_batch_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("batch_submenu", "Batch"))
    _add_action(sub, lang, "batch_convert_title", "Batch Format Conversion",
                lambda: _open_batch_convert(ui))
    _add_action(sub, lang, "exif_strip_title", "Batch EXIF Strip",
                lambda: _open_exif_strip(ui))
    _add_action(sub, lang, "sanitize_title", "Image Sanitizer",
                lambda: _open_image_sanitize(ui))
    _add_action(sub, lang, "organizer_title", "Image Organizer",
                lambda: _open_image_organizer(ui))
    _add_action(sub, lang, "token_rename_title", "Token Batch Rename",
                lambda: _open_token_rename(ui))


def _build_library_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("library_submenu", "Library & Metadata"))
    _add_action(sub, lang, "library_search_title", "Library Search",
                lambda: _open_library_search(ui))
    _add_action(sub, lang, "smart_albums_title", "Smart Albums",
                lambda: _open_smart_albums(ui))
    _add_action(sub, lang, "similar_search_title", "Find Similar Images",
                lambda: _open_similar_search(ui))
    _add_action(sub, lang, "duplicate_title", "Find Duplicate Images",
                lambda: _open_duplicate_detection(ui))
    _add_action(sub, lang, "auto_tag_title", "Auto-Tag Images",
                lambda: _open_auto_tag(ui))
    _add_action(sub, lang, "htags_title", "Hierarchical Tags",
                lambda: _open_hierarchical_tags(ui))
    sub.addSeparator()
    _add_action(sub, lang, "metadata_export_title", "Export Metadata (CSV / JSON)",
                lambda: _open_metadata_export(ui))
    _add_action(sub, lang, "xmp_title", "XMP Sidecars",
                lambda: _open_xmp_sidecar(ui))
    _add_action(sub, lang, "geotag_title", "GPS Geotag",
                lambda: _open_gps_geotag(ui))


def _build_views_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("views_submenu", "Views"))
    timeline_menu = sub.addMenu(lang.get("timeline_title", "Timeline View"))
    for gran_key, fallback in (
        ("day", "By day"), ("month", "By month"), ("year", "By year"),
    ):
        action = timeline_menu.addAction(lang.get(f"timeline_by_{gran_key}", fallback))
        action.triggered.connect(lambda checked, g=gran_key: _open_timeline(ui, g))
    _add_action(sub, lang, "calendar_title", "Calendar View",
                lambda: _open_calendar_view(ui))
    _add_action(sub, lang, "map_title", "Map View",
                lambda: _open_map_view(ui))


def _build_workflow_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("workflow_submenu", "Workflow"))
    _add_action(sub, lang, "culling_title", "Culling",
                lambda: _open_culling(ui))
    _add_action(sub, lang, "staging_tray_title", "Staging Tray",
                lambda: _open_staging_tray(ui))
    _add_action(sub, lang, "vcopies_title", "Virtual Copies",
                lambda: _open_virtual_copies(ui))
    _add_action(sub, lang, "dual_pane_title", "Dual-Pane File Manager",
                lambda: _open_dual_pane(ui))
    _add_action(sub, lang, "macro_title", "Macros",
                lambda: _open_macro_manager(ui))


def _build_export_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("export_submenu", "Export"))
    _add_action(sub, lang, "contact_sheet_title", "Contact Sheet PDF",
                lambda: _open_contact_sheet(ui))
    _add_action(sub, lang, "web_gallery_title", "Web Gallery",
                lambda: _open_web_gallery(ui))
    _add_action(sub, lang, "slideshow_mp4_title", "Slideshow Video",
                lambda: _open_slideshow_mp4(ui))
    _add_action(sub, lang, "print_title", "Print Layout",
                lambda: _open_print_layout(ui))


def _build_develop_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("develop_submenu", "Develop (Non-Destructive)"))
    _add_action(sub, lang, "tone_curve_title", "Tone Curve",
                lambda: _open_tone_curve(ui))
    _add_action(sub, lang, "lut_title", "Apply .cube LUT",
                lambda: _open_lut(ui))
    _add_action(sub, lang, "split_title", "Split Toning",
                lambda: _open_split_toning(ui))
    _add_action(sub, lang, "masks_title", "Local Adjustment Masks",
                lambda: _open_masks(ui))
    _add_action(sub, lang, "layers_title", "Layers",
                lambda: _open_layers(ui))
    _add_action(sub, lang, "posterize_title", "Threshold / Posterize",
                lambda: _open_posterize(ui))
    _add_action(sub, lang, "proof_title", "Soft Proof",
                lambda: _open_soft_proof(ui))


def _build_retouch_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("retouch_submenu", "Retouch & Transform"))
    _add_action(sub, lang, "upscale_title", "AI Image Upscale",
                lambda: _open_ai_upscale(ui))
    _add_action(sub, lang, "nr_title", "Noise Reduction / Sharpening",
                lambda: _open_noise_sharpen(ui))
    _add_action(sub, lang, "heal_title", "Healing Brush",
                lambda: _open_healing_brush(ui))
    _add_action(sub, lang, "stamp_title", "Clone Stamp",
                lambda: _open_clone_stamp(ui))
    _add_action(sub, lang, "face_title", "Face Detection",
                lambda: _open_face_detection(ui))
    _add_action(sub, lang, "sky_title", "Sky / Background",
                lambda: _open_sky_replace(ui))
    sub.addSeparator()
    _add_action(sub, lang, "crop_title", "Crop / Straighten",
                lambda: _open_crop_straighten(ui))
    _add_action(sub, lang, "autostr_title", "Auto-Straighten",
                lambda: _open_auto_straighten(ui))
    _add_action(sub, lang, "lens_title", "Lens Correction",
                lambda: _open_lens_correction(ui))


def _build_multi_image_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("multi_image_submenu", "Multi-Image"))
    _add_action(sub, lang, "hdr_title", "HDR Merge",
                lambda: _open_hdr_merge(ui))
    _add_action(sub, lang, "pano_title", "Panorama Stitch",
                lambda: _open_panorama(ui))
    _add_action(sub, lang, "fstack_title", "Focus Stacking",
                lambda: _open_focus_stack(ui))


# --- Dialog openers ---------------------------------------------------------

def _open_batch_convert(ui: ImervueMainWindow):
    from Imervue.gui.batch_convert_dialog import open_batch_convert
    open_batch_convert(ui.viewer)


def _open_ai_upscale(ui: ImervueMainWindow):
    from Imervue.gui.ai_upscale_dialog import open_ai_upscale
    open_ai_upscale(ui.viewer)


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


def _open_culling(ui: ImervueMainWindow):
    from Imervue.gui.culling_dialog import open_culling
    open_culling(ui)


def _open_staging_tray(ui: ImervueMainWindow):
    from Imervue.gui.staging_tray_dialog import open_staging_tray
    open_staging_tray(ui)


def _open_dual_pane(ui: ImervueMainWindow):
    from Imervue.gui.dual_pane_dialog import open_dual_pane
    open_dual_pane(ui)


def _open_timeline(ui: ImervueMainWindow, granularity: str):
    from Imervue.gui.timeline_view import open_timeline
    open_timeline(ui, granularity)


def _open_macro_manager(ui: ImervueMainWindow):
    from Imervue.gui.macro_manager_dialog import open_macro_manager_dialog
    open_macro_manager_dialog(ui)


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


def _open_tone_curve(ui: ImervueMainWindow):
    from Imervue.gui.tone_curve_dialog import open_tone_curve
    open_tone_curve(ui.viewer)


def _open_lut(ui: ImervueMainWindow):
    from Imervue.gui.lut_dialog import open_lut
    open_lut(ui.viewer)


def _open_posterize(ui: ImervueMainWindow) -> None:
    from Imervue.gui.posterize_dialog import open_posterize_dialog
    open_posterize_dialog(ui.viewer)


def _open_layers(ui: ImervueMainWindow) -> None:
    from Imervue.gui.layers_dialog import open_layers_dialog
    from Imervue.image.recipe import Recipe
    from Imervue.image.recipe_store import recipe_store
    viewer = ui.viewer
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    path = images[idx]
    recipe = recipe_store.get_for_path(path) or Recipe()
    new_layers = open_layers_dialog(recipe, parent=ui)
    if new_layers is None:
        return
    new_recipe = Recipe(
        **{f.name: getattr(recipe, f.name) for f in recipe.__dataclass_fields__.values()}
    )
    new_recipe.extra = dict(recipe.extra)
    new_recipe.extra["layers"] = new_layers
    recipe_store.set_for_path(path, new_recipe)
    hook = getattr(viewer, "reload_current_image_with_recipe", None)
    if callable(hook):
        hook(path)


def _open_virtual_copies(ui: ImervueMainWindow):
    from Imervue.gui.virtual_copies_dialog import open_virtual_copies
    open_virtual_copies(ui.viewer)


def _open_face_detection(ui: ImervueMainWindow):
    from Imervue.gui.face_detection_dialog import open_face_detection
    open_face_detection(ui.viewer)


def _open_lens_correction(ui: ImervueMainWindow):
    from Imervue.gui.lens_correction_dialog import open_lens_correction
    open_lens_correction(ui.viewer)


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


def _open_masks(ui: ImervueMainWindow):
    from Imervue.gui.masks_dialog import open_masks
    open_masks(ui.viewer)


def _open_split_toning(ui: ImervueMainWindow):
    from Imervue.gui.split_toning_dialog import open_split_toning
    open_split_toning(ui.viewer)


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


def _open_soft_proof(ui: ImervueMainWindow):
    from Imervue.gui.soft_proof_dialog import open_soft_proof
    open_soft_proof(ui.viewer)


def _open_gps_geotag(ui: ImervueMainWindow):
    from Imervue.gui.gps_geotag_dialog import open_gps_geotag
    open_gps_geotag(ui.viewer)


def _open_print_layout(ui: ImervueMainWindow):
    from Imervue.gui.print_layout_dialog import open_print_layout
    open_print_layout(ui)
