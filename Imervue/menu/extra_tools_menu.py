from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.menu.extra_tools_open_library import (  # dialog openers wired below
    _open_animation_edit,
    _open_auto_tag,
    _open_batch_convert,
    _open_binarize,
    _open_cache_maintenance,
    _open_capture_time,
    _open_deflicker,
    _open_duplicate_detection,
    _open_exif_strip,
    _open_gps_geotag,
    _open_gpx_geotag,
    _open_hierarchical_tags,
    _open_image_organizer,
    _open_image_sanitize,
    _open_library_search,
    _open_meme,
    _open_metadata_export,
    _open_metadata_template,
    _open_optimize,
    _open_otsu,
    _open_semantic_search,
    _open_similar_search,
    _open_smart_albums,
    _open_steganography,
    _open_token_rename,
    _open_xmp_sidecar,
)
from Imervue.menu.extra_tools_open_views import (  # dialog openers wired below
    _open_calendar_view,
    _open_collage,
    _open_contact_sheet,
    _open_culling,
    _open_dual_pane,
    _open_id_photo_sheet,
    _open_image_inspector,
    _open_image_statistics,
    _open_macro_manager,
    _open_map_view,
    _open_print_layout,
    _open_quality_report,
    _open_reference_panel,
    _open_slideshow_mp4,
    _open_staging_tray,
    _open_test_charts,
    _open_timeline,
    _open_tiny_planet,
    _open_virtual_copies,
    _open_watch_folder,
    _open_web_gallery,
)
from Imervue.menu.extra_tools_open_develop import (  # dialog openers wired below
    _open_auto_balance,
    _open_before_after,
    _open_channel_mixer,
    _open_clahe,
    _open_defringe,
    _open_detail_equalizer,
    _open_develop_presets,
    _open_film_negative,
    _open_filmic_tonemap,
    _open_flatten_field,
    _open_gradient_map,
    _open_graduated_density,
    _open_hsl_mixer,
    _open_layers,
    _open_levels,
    _open_local_contrast,
    _open_lut,
    _open_masks,
    _open_soft_proof,
    _open_split_toning,
    _open_tone_curve,
    _open_tone_equalizer,
    _open_velvia,
)
from Imervue.menu.extra_tools_open_effects import (  # dialog openers wired below
    _open_ai_upscale,
    _open_anaglyph,
    _open_auto_straighten,
    _open_clone_stamp,
    _open_colormap,
    _open_crop_straighten,
    _open_distort,
    _open_dither,
    _open_emboss,
    _open_face_detection,
    _open_film_grain,
    _open_focus_stack,
    _open_frequency_separation,
    _open_frosted_glass,
    _open_glow,
    _open_hdr_merge,
    _open_healing_brush,
    _open_kaleidoscope,
    _open_lens_correction,
    _open_lens_flare,
    _open_noise_sharpen,
    _open_panorama,
    _open_photo_frame,
    _open_pixel_sort,
    _open_polar,
    _open_portrait_retouch,
    _open_posterize,
    _open_scale_bar,
    _open_sky_replace,
    _open_smart_crop,
    _open_solarize,
    _open_stack_blend,
)
from Imervue.multi_language.language_wrapper import language_wrapper

# Plugins place their entries with ``main_window.findChild(QMenu, name)`` using
# these object names, so they are a contract with Imervue_Plugins
# (architecture.md section 6): add new ones freely, never rename or drop one.
EXTRA_TOOLS_OBJECT_NAME = "extra_tools"


def submenu_object_name(key: str) -> str:
    """Return the Qt object name of the Extra Tools submenu titled by ``key``."""
    return f"{EXTRA_TOOLS_OBJECT_NAME}.{key}"


def build_extra_tools_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict
    menu = ui.menuBar().addMenu(lang.get("extra_tools_menu", "Extra Tools"))
    menu.setObjectName(EXTRA_TOOLS_OBJECT_NAME)

    _build_batch_submenu(menu, ui, lang)
    _build_library_submenu(menu, ui, lang)
    _build_views_submenu(menu, ui, lang)
    _build_workflow_submenu(menu, ui, lang)
    _build_export_submenu(menu, ui, lang)
    _build_develop_submenu(menu, ui, lang)
    _build_retouch_submenu(menu, ui, lang)
    _build_multi_image_submenu(menu, ui, lang)


def _add_submenu(menu, lang: dict, key: str, fallback: str):
    """Add the submenu titled ``lang[key]`` and give it a stable object name."""
    sub = menu.addMenu(lang.get(key, fallback))
    sub.setObjectName(submenu_object_name(key))
    return sub


def _add_action(submenu, lang: dict, key: str, fallback: str, callback) -> None:
    action = submenu.addAction(lang.get(key, fallback))
    action.triggered.connect(callback)


# --- Submenus ---------------------------------------------------------------

def _build_batch_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = _add_submenu(menu, lang, "batch_submenu", "Batch")
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
    sub = _add_submenu(menu, lang, "library_submenu", "Library & Metadata")
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
    _add_action(sub, lang, "gpx_title", "Geotag from GPX Track",
                lambda: _open_gpx_geotag(ui))
    _add_action(sub, lang, "capture_time_title", "Edit Capture Time",
                lambda: _open_capture_time(ui))
    _add_action(sub, lang, "metadata_template_title", "Metadata Template",
                lambda: _open_metadata_template(ui))
    _add_action(sub, lang, "cache_maintenance_title", "Thumbnail Cache",
                lambda: _open_cache_maintenance(ui))


def _build_views_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = _add_submenu(menu, lang, "views_submenu", "Views")
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
                    lambda checked=False, _kind=kind: _set_cvd_mode(ui, _kind))


def _set_cvd_mode(ui: ImervueMainWindow, mode: str | None) -> None:
    viewer = getattr(ui, "viewer", None)
    if viewer is None or not hasattr(viewer, "set_cvd_view_mode"):
        return
    viewer.set_cvd_view_mode(mode)


def _build_workflow_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = _add_submenu(menu, lang, "workflow_submenu", "Workflow")
    from Imervue.gui.background_jobs import open_background_jobs
    _add_action(sub, lang, "background_jobs", "Background Jobs",
                lambda: open_background_jobs(ui))
    from Imervue.gui.photo_workflow_dialog import open_photo_workflow
    _add_action(sub, lang, "photo_workflow", "Photo Workflow",
                lambda: open_photo_workflow(ui))
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
    sub = _add_submenu(menu, lang, "export_submenu", "Export")
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
    sub = _add_submenu(menu, lang, "develop_submenu", "Develop (Non-Destructive)")
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
    _add_action(sub, lang, "polar_title", "Polar Coordinates",
                lambda: _open_polar(ui))
    _add_action(sub, lang, "kaleidoscope_title", "Kaleidoscope",
                lambda: _open_kaleidoscope(ui))
    _add_action(sub, lang, "frosted_title", "Frosted Glass",
                lambda: _open_frosted_glass(ui))
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
    _add_action(sub, lang, "filmic_title", "Filmic Tone Map",
                lambda: _open_filmic_tonemap(ui))
    _add_action(sub, lang, "tone_eq_title", "Tone Equalizer",
                lambda: _open_tone_equalizer(ui))
    _add_action(sub, lang, "detail_eq_title", "Detail Equalizer",
                lambda: _open_detail_equalizer(ui))
    _add_action(sub, lang, "proof_title", "Soft Proof",
                lambda: _open_soft_proof(ui))


def _build_retouch_submenu(menu, ui: ImervueMainWindow, lang: dict) -> None:
    sub = _add_submenu(menu, lang, "retouch_submenu", "Retouch & Transform")
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
    sub = _add_submenu(menu, lang, "multi_image_submenu", "Multi-Image")
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

