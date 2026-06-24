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
    _add_action(sub, lang, "deflicker_title", "Deflicker (Time-lapse)",
                lambda: _open_deflicker(ui))
    _add_action(sub, lang, "binarize_title", "Document Binarize",
                lambda: _open_binarize(ui))
    _add_action(sub, lang, "otsu_title", "Otsu Threshold",
                lambda: _open_otsu(ui))
    _add_action(sub, lang, "animedit_title", "Edit Animation (GIF)",
                lambda: _open_animation_edit(ui))
    _add_action(sub, lang, "optimize_title", "Optimize to Target Size",
                lambda: _open_optimize(ui))
    _add_action(sub, lang, "meme_title", "Meme Caption",
                lambda: _open_meme(ui))
    _add_action(sub, lang, "stego_title", "Steganography",
                lambda: _open_steganography(ui))


def _build_library_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("library_submenu", "Library & Metadata"))
    _add_action(sub, lang, "library_search_title", "Library Search",
                lambda: _open_library_search(ui))
    _add_action(sub, lang, "smart_albums_title", "Smart Albums",
                lambda: _open_smart_albums(ui))
    _add_action(sub, lang, "similar_search_title", "Find Similar Images",
                lambda: _open_similar_search(ui))
    _add_action(sub, lang, "semantic_search_title", "Semantic Search (text)",
                lambda: _open_semantic_search(ui))
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
    _add_action(sub, lang, "inspector_title", "Scopes & Inspector",
                lambda: _open_image_inspector(ui))
    _add_action(sub, lang, "tiny_planet_title", "Tiny Planet (360°)",
                lambda: _open_tiny_planet(ui))
    _add_action(sub, lang, "stats_title", "Image Statistics",
                lambda: _open_image_statistics(ui))
    _add_action(sub, lang, "quality_title", "Quality Report",
                lambda: _open_quality_report(ui))
    _add_action(sub, lang, "testchart_title", "Test Chart",
                lambda: _open_test_charts(ui))
    _build_cvd_submenu(sub, ui, lang)


def _build_cvd_submenu(parent_menu, ui: ImervueMainWindow, lang: dict) -> None:
    """Colour-vision-deficiency simulation overlay — preview the
    current image as a viewer with protanopia / deuteranopia /
    tritanopia / achromatopsia would see it. Non-destructive; the
    source file and recipe stay untouched."""
    cvd_menu = parent_menu.addMenu(lang.get("cvd_view_title", "Color blindness preview"))
    _add_action(cvd_menu, lang, "cvd_view_off", "Off",
                lambda: _set_cvd_mode(ui, None))
    for kind, fallback in (
        ("protanopia", "Protanopia (red-blind)"),
        ("deuteranopia", "Deuteranopia (green-blind)"),
        ("tritanopia", "Tritanopia (blue-blind)"),
        ("achromatopsia", "Achromatopsia (greyscale)"),
    ):
        _add_action(cvd_menu, lang, f"cvd_view_{kind}", fallback,
                    lambda _kind=kind: _set_cvd_mode(ui, _kind))


def _set_cvd_mode(ui: ImervueMainWindow, mode: str | None) -> None:
    viewer = getattr(ui, "viewer", None)
    if viewer is None or not hasattr(viewer, "set_cvd_view_mode"):
        return
    viewer.set_cvd_view_mode(mode)


def _build_workflow_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("workflow_submenu", "Workflow"))
    _add_action(sub, lang, "culling_title", "Culling",
                lambda: _open_culling(ui))
    _add_action(sub, lang, "staging_tray_title", "Staging Tray",
                lambda: _open_staging_tray(ui))
    _add_action(sub, lang, "reference_panel_title", "Reference Panel",
                lambda: _open_reference_panel(ui))
    _add_action(sub, lang, "vcopies_title", "Virtual Copies",
                lambda: _open_virtual_copies(ui))
    _add_action(sub, lang, "dual_pane_title", "Dual-Pane File Manager",
                lambda: _open_dual_pane(ui))
    _add_action(sub, lang, "macro_title", "Macros",
                lambda: _open_macro_manager(ui))
    _add_action(sub, lang, "watch_folder_title", "Watched Folder",
                lambda: _open_watch_folder(ui))


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
    _add_action(sub, lang, "collage_title", "Collage",
                lambda: _open_collage(ui))
    _add_action(sub, lang, "idsheet_title", "ID Photo Sheet",
                lambda: _open_id_photo_sheet(ui))


def _build_develop_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("develop_submenu", "Develop (Non-Destructive)"))
    _add_action(sub, lang, "before_after_title", "Before / After Compare",
                lambda: _open_before_after(ui))
    _add_action(sub, lang, "develop_presets_title", "Develop Presets…",
                lambda: _open_develop_presets(ui))
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
    _add_action(sub, lang, "levels_title", "Levels",
                lambda: _open_levels(ui))
    _add_action(sub, lang, "channel_mixer_title", "Channel Mixer",
                lambda: _open_channel_mixer(ui))
    _add_action(sub, lang, "gradient_map_title", "Gradient Map",
                lambda: _open_gradient_map(ui))
    _add_action(sub, lang, "auto_balance_title", "Auto Color Balance",
                lambda: _open_auto_balance(ui))
    _add_action(sub, lang, "local_contrast_title", "Clarity / Dehaze",
                lambda: _open_local_contrast(ui))
    _add_action(sub, lang, "hsl_title", "HSL / Color Mixer",
                lambda: _open_hsl_mixer(ui))
    _add_action(sub, lang, "clahe_title", "CLAHE (Local Equalize)",
                lambda: _open_clahe(ui))
    _add_action(sub, lang, "flatten_title", "Flatten Background",
                lambda: _open_flatten_field(ui))
    _add_action(sub, lang, "frame_title", "Frame & Caption",
                lambda: _open_photo_frame(ui))
    _add_action(sub, lang, "dither_title", "Ordered Dither",
                lambda: _open_dither(ui))
    _add_action(sub, lang, "colormap_title", "Color Map",
                lambda: _open_colormap(ui))
    _add_action(sub, lang, "distort_title", "Distort (Swirl/Pinch/Ripple)",
                lambda: _open_distort(ui))
    _add_action(sub, lang, "pixelsort_title", "Pixel Sort",
                lambda: _open_pixel_sort(ui))
    _add_action(sub, lang, "film_grain_title", "Film Grain",
                lambda: _open_film_grain(ui))
    _add_action(sub, lang, "lens_flare_title", "Lens Flare",
                lambda: _open_lens_flare(ui))
    _add_action(sub, lang, "posterize_title", "Threshold / Posterize",
                lambda: _open_posterize(ui))
    _add_action(sub, lang, "solarize_title", "Solarize",
                lambda: _open_solarize(ui))
    _add_action(sub, lang, "glow_title", "Diffuse Glow",
                lambda: _open_glow(ui))
    _add_action(sub, lang, "graduated_density_title", "Graduated Density",
                lambda: _open_graduated_density(ui))
    _add_action(sub, lang, "velvia_title", "Velvia",
                lambda: _open_velvia(ui))
    _add_action(sub, lang, "emboss_title", "Emboss",
                lambda: _open_emboss(ui))
    _add_action(sub, lang, "defringe_title", "Defringe",
                lambda: _open_defringe(ui))
    _add_action(sub, lang, "film_negative_title", "Film Negative",
                lambda: _open_film_negative(ui))
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
    _add_action(sub, lang, "frequency_sep_title", "Frequency Separation",
                lambda: _open_frequency_separation(ui))
    _add_action(sub, lang, "smart_crop_title", "Smart Crop",
                lambda: _open_smart_crop(ui))
    _add_action(sub, lang, "portrait_retouch_title", "Portrait Auto-Retouch",
                lambda: _open_portrait_retouch(ui))
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
    _add_action(sub, lang, "scalebar_title", "Scale Bar",
                lambda: _open_scale_bar(ui))


def _build_multi_image_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = menu.addMenu(lang.get("multi_image_submenu", "Multi-Image"))
    _add_action(sub, lang, "hdr_title", "HDR Merge",
                lambda: _open_hdr_merge(ui))
    _add_action(sub, lang, "pano_title", "Panorama Stitch",
                lambda: _open_panorama(ui))
    _add_action(sub, lang, "fstack_title", "Focus Stacking",
                lambda: _open_focus_stack(ui))
    _add_action(sub, lang, "stack_blend_title", "Image Stack (Mean/Median/Max/Min)",
                lambda: _open_stack_blend(ui))
    _add_action(sub, lang, "anaglyph_title", "Anaglyph 3D",
                lambda: _open_anaglyph(ui))


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


def _open_before_after(ui: ImervueMainWindow):
    from Imervue.gui.before_after_dialog import open_before_after_dialog
    open_before_after_dialog(ui.viewer)


def _open_semantic_search(ui: ImervueMainWindow):
    from Imervue.gui.semantic_search_dialog import open_semantic_search_dialog
    open_semantic_search_dialog(ui.viewer)


def _open_develop_presets(ui: ImervueMainWindow):
    from Imervue.gui.develop_presets_dialog import open_develop_presets_dialog
    open_develop_presets_dialog(ui.viewer)


def _open_tone_curve(ui: ImervueMainWindow):
    from Imervue.gui.tone_curve_dialog import open_tone_curve
    open_tone_curve(ui.viewer)


def _open_lut(ui: ImervueMainWindow):
    from Imervue.gui.lut_dialog import open_lut
    open_lut(ui.viewer)


def _open_posterize(ui: ImervueMainWindow) -> None:
    from Imervue.gui.posterize_dialog import open_posterize_dialog
    open_posterize_dialog(ui.viewer)


def _open_solarize(ui: ImervueMainWindow) -> None:
    from Imervue.gui.solarize_dialog import open_solarize
    open_solarize(ui.viewer)


def _open_glow(ui: ImervueMainWindow) -> None:
    from Imervue.gui.glow_dialog import open_glow
    open_glow(ui.viewer)


def _open_graduated_density(ui: ImervueMainWindow) -> None:
    from Imervue.gui.graduated_density_dialog import open_graduated_density
    open_graduated_density(ui.viewer)


def _open_velvia(ui: ImervueMainWindow) -> None:
    from Imervue.gui.velvia_dialog import open_velvia
    open_velvia(ui.viewer)


def _open_emboss(ui: ImervueMainWindow) -> None:
    from Imervue.gui.emboss_dialog import open_emboss
    open_emboss(ui.viewer)


def _open_defringe(ui: ImervueMainWindow) -> None:
    from Imervue.gui.defringe_dialog import open_defringe
    open_defringe(ui.viewer)


def _open_film_negative(ui: ImervueMainWindow) -> None:
    from Imervue.gui.film_negative_dialog import open_film_negative
    open_film_negative(ui.viewer)


def _open_levels(ui: ImervueMainWindow) -> None:
    from Imervue.gui.levels_dialog import open_levels_dialog
    open_levels_dialog(ui.viewer)


def _open_channel_mixer(ui: ImervueMainWindow) -> None:
    from Imervue.gui.channel_mixer_dialog import open_channel_mixer_dialog
    open_channel_mixer_dialog(ui.viewer)


def _open_gradient_map(ui: ImervueMainWindow) -> None:
    from Imervue.gui.gradient_map_dialog import open_gradient_map_dialog
    open_gradient_map_dialog(ui.viewer)


def _open_auto_balance(ui: ImervueMainWindow) -> None:
    from Imervue.gui.auto_color_balance_dialog import open_auto_color_balance_dialog
    open_auto_color_balance_dialog(ui.viewer)


def _open_local_contrast(ui: ImervueMainWindow) -> None:
    from Imervue.gui.local_contrast_dialog import open_local_contrast
    open_local_contrast(ui.viewer)


def _open_hsl_mixer(ui: ImervueMainWindow) -> None:
    from Imervue.gui.hsl_mixer_dialog import open_hsl_mixer
    open_hsl_mixer(ui.viewer)


def _open_clahe(ui: ImervueMainWindow) -> None:
    from Imervue.gui.clahe_dialog import open_clahe
    open_clahe(ui.viewer)


def _open_flatten_field(ui: ImervueMainWindow) -> None:
    from Imervue.gui.flatten_field_dialog import open_flatten_field
    open_flatten_field(ui.viewer)


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


def _open_test_charts(ui: ImervueMainWindow) -> None:
    from Imervue.gui.test_charts_dialog import open_test_charts
    open_test_charts(ui.viewer)


def _open_quality_report(ui: ImervueMainWindow) -> None:
    from Imervue.gui.quality_report_dialog import open_quality_report
    open_quality_report(ui.viewer)


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


def _open_image_statistics(ui: ImervueMainWindow) -> None:
    from Imervue.gui.image_statistics_dialog import open_image_statistics
    open_image_statistics(ui.viewer)


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


def _open_deflicker(ui: ImervueMainWindow) -> None:
    from Imervue.gui.deflicker_dialog import open_deflicker_dialog
    open_deflicker_dialog(ui.viewer)


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


def _open_collage(ui: ImervueMainWindow):
    from Imervue.gui.collage_dialog import open_collage
    open_collage(ui.viewer)


def _open_id_photo_sheet(ui: ImervueMainWindow):
    from Imervue.gui.id_photo_sheet_dialog import open_id_photo_sheet
    open_id_photo_sheet(ui.viewer)


def _open_photo_frame(ui: ImervueMainWindow):
    from Imervue.gui.photo_frame_dialog import open_photo_frame
    open_photo_frame(ui.viewer)


def _open_dither(ui: ImervueMainWindow):
    from Imervue.gui.dither_dialog import open_dither
    open_dither(ui.viewer)
