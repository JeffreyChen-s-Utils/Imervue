"""Contract: the complete Extra Tools menu tree and where each entry leads.

Pins, in English, every submenu (title, object name), separator and action
(label, enabled state, shortcut, checkability) in build order, and for each action
the lazily imported dialog module, the opener it calls and whether that opener is
handed the main window or its viewer. Dialog imports are intercepted, so no dialog
is constructed and the lazy import stays observable.
"""
from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest

from Imervue.menu import extra_tools_menu
from Imervue.multi_language.english import english_word_dict
from Imervue.multi_language.language_wrapper import language_wrapper

_DIALOG_PREFIX = "Imervue.gui."
_LAYERS = ("Imervue.gui.layers_dialog", "open_layers_dialog")


class _FakeDialogModule:
    """Stands in for a lazily imported dialog module and records each opener call."""

    def __init__(self, name: str, log: list, returns: dict) -> None:
        self._name, self._log, self._returns = name, log, returns

    def __getattr__(self, attr: str):
        key = (self._name, attr)

        def _call(*args, **kwargs):
            self._log.append((*key, args, kwargs))
            return self._returns.get(key)
        return _call


@pytest.fixture
def dialog_calls(monkeypatch):
    """Intercept ``from Imervue.gui.<module> import <opener>``; yield (log, returns)."""
    log: list = []
    returns: dict = {}
    real_import = builtins.__import__

    def _import(name, globals_=None, locals_=None, fromlist=(), level=0):
        if level == 0 and fromlist and name.startswith(_DIALOG_PREFIX):
            return _FakeDialogModule(name, log, returns)
        return real_import(name, globals_, locals_, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", _import)
    return log, returns


@pytest.fixture
def english(monkeypatch):
    monkeypatch.setattr(language_wrapper, "language_word_dict", english_word_dict)


def _walk(menu, path=()):
    for action in menu.actions():
        if action.isSeparator():
            yield path, action, "---"
        elif action.menu() is not None:
            yield path, action, action.menu()
            yield from _walk(action.menu(), (*path, action.menu().title()))
        else:
            yield path, action, None


def _viewer(cvd_log: list, images=(), index=-1):
    return SimpleNamespace(
        set_cvd_view_mode=cvd_log.append,
        model=SimpleNamespace(images=list(images)), current_index=index,
    )


def _target(window, log: list, cvd_log: list, before: int):
    """Describe what one triggered action did."""
    calls = log[before:]
    if cvd_log:
        return ("cvd", cvd_log.pop())
    if not calls:
        return ("no-call",)
    assert len(calls) == 1, calls
    module, func, args, kwargs = calls[0]
    assert kwargs == {}
    kinds = tuple(
        "ui" if a is window else "viewer" if a is window.viewer else a for a in args
    )
    return (module.removeprefix(_DIALOG_PREFIX), func, *kinds)


def _snapshot(window, log: list, cvd_log: list) -> list[tuple]:
    from PySide6.QtWidgets import QMenu
    top = window.findChild(QMenu, extra_tools_menu.EXTRA_TOOLS_OBJECT_NAME)
    rows: list[tuple] = [("menu", top.title(), top.objectName())]
    for path, action, kind in _walk(top):
        where = " > ".join(path)
        assert action.isEnabled()
        assert not action.isCheckable()
        assert action.shortcut().isEmpty()
        if kind == "---":
            rows.append((where, "---"))
        elif kind is not None:
            rows.append((where, "menu", kind.title(), kind.objectName()))
        else:
            before = len(log)
            action.trigger()
            rows.append((where, action.text(), *_target(window, log, cvd_log, before)))
    return rows


_V, _U = "viewer", "ui"

EXPECTED_TREE = [
    ('menu', 'Extra Tools', 'extra_tools'),
    ('', 'menu', 'Batch', 'extra_tools.batch_submenu'),
    ('Batch', 'Batch Format Conversion', 'batch_convert_dialog', 'open_batch_convert', _V),
    ('Batch', 'Batch EXIF Strip', 'exif_strip_dialog', 'open_exif_strip', _V),
    ('Batch', 'Image Sanitizer', 'image_sanitize_dialog', 'open_image_sanitize', _V),
    ('Batch', 'Image Organizer', 'image_organizer_dialog', 'open_image_organizer', _V),
    ('Batch', 'Token Batch Rename', 'token_rename_dialog', 'open_token_rename', _U),
    ('Batch', 'Deflicker (Time-lapse)', 'deflicker_dialog', 'open_deflicker_dialog', _V),
    ('Batch', 'Document Binarize', 'binarize_dialog', 'open_binarize', _V),
    ('Batch', 'Otsu Threshold', 'otsu_dialog', 'open_otsu', _V),
    ('Batch', 'Edit Animation', 'animation_edit_dialog', 'open_animation_edit', _V),
    ('Batch', 'Optimize to Target Size', 'optimize_dialog', 'open_optimize', _V),
    ('Batch', 'Meme Caption', 'meme_dialog', 'open_meme', _V),
    ('Batch', 'Steganography', 'steganography_dialog', 'open_steganography', _V),
    ('', 'menu', 'Library & Metadata', 'extra_tools.library_submenu'),
    ('Library & Metadata', 'Library Search', 'library_search_dialog', 'open_library_search', _U),
    ('Library & Metadata', 'Smart Albums', 'smart_albums_dialog', 'open_smart_albums', _U),
    ('Library & Metadata',
     'Find Similar Images', 'similar_search_dialog', 'open_similar_search', _U),
    ('Library & Metadata',
     'Semantic Search', 'semantic_search_dialog', 'open_semantic_search_dialog', _V),
    ('Library & Metadata',
     'Find Duplicate Images', 'duplicate_detection_dialog', 'open_duplicate_detection', _V),
    ('Library & Metadata', 'Auto-Tag Images', 'auto_tag_dialog', 'open_auto_tag', _U),
    ('Library & Metadata',
     'Hierarchical Tags', 'hierarchical_tags_dialog', 'open_hierarchical_tags', _U),
    ('Library & Metadata', '---'),
    ('Library & Metadata',
     'Export Metadata (CSV / JSON)', 'metadata_export_dialog', 'open_metadata_export', _U),
    ('Library & Metadata', 'XMP Sidecars', 'xmp_sidecar_dialog', 'open_xmp_sidecar', _U),
    ('Library & Metadata', 'GPS Geotag', 'gps_geotag_dialog', 'open_gps_geotag', _V),
    ('Library & Metadata', 'Geotag from GPX Track', 'gpx_geotag_dialog', 'open_gpx_geotag', _U),
    ('Library & Metadata', 'Edit Capture Time', 'capture_time_dialog', 'open_capture_time', _U),
    ('Library & Metadata',
     'Metadata Template', 'metadata_template_dialog', 'open_metadata_template', _U),
    ('Library & Metadata',
     'Thumbnail Cache', 'cache_maintenance_dialog', 'open_cache_maintenance', _U),
    ('', 'menu', 'Views', 'extra_tools.views_submenu'),
    ('Views', 'menu', 'Timeline View', ''),
    ('Views > Timeline View', 'By day', 'timeline_view', 'open_timeline', _U, 'day'),
    ('Views > Timeline View', 'By month', 'timeline_view', 'open_timeline', _U, 'month'),
    ('Views > Timeline View', 'By year', 'timeline_view', 'open_timeline', _U, 'year'),
    ('Views', 'Calendar View', 'calendar_view_dialog', 'open_calendar_view', _U),
    ('Views', 'Map View', 'map_view_dialog', 'open_map_view', _U),
    ('Views', 'Scopes & Inspector', 'image_inspector_dialog', 'open_image_inspector', _V),
    ('Views', 'Tiny Planet (360°)', 'tiny_planet_dialog', 'open_tiny_planet', _V),
    ('Views', 'Image Statistics', 'image_statistics_dialog', 'open_image_statistics', _V),
    ('Views', 'Quality Report', 'quality_report_dialog', 'open_quality_report', _V),
    ('Views', 'Test Chart', 'test_charts_dialog', 'open_test_charts', _V),
    ('Views', 'menu', 'Color blindness preview', ''),
    ('Views > Color blindness preview', 'Off', 'cvd', None),
    ('Views > Color blindness preview', 'Protanopia (red-blind)', 'cvd', 'protanopia'),
    ('Views > Color blindness preview', 'Deuteranopia (green-blind)', 'cvd', 'deuteranopia'),
    ('Views > Color blindness preview', 'Tritanopia (blue-blind)', 'cvd', 'tritanopia'),
    ('Views > Color blindness preview', 'Achromatopsia (greyscale)', 'cvd', 'achromatopsia'),
    ('', 'menu', 'Workflow', 'extra_tools.workflow_submenu'),
    ('Workflow', 'Background Jobs', 'background_jobs', 'open_background_jobs', _U),
    ('Workflow', 'Photo Workflow', 'photo_workflow_dialog', 'open_photo_workflow', _U),
    ('Workflow', 'Culling', 'culling_dialog', 'open_culling', _U),
    ('Workflow', 'Staging Tray', 'staging_tray_dialog', 'open_staging_tray', _U),
    ('Workflow', 'Reference Panel', 'reference_panel_dialog', 'open_reference_panel', _U),
    ('Workflow', 'Virtual Copies', 'virtual_copies_dialog', 'open_virtual_copies', _V),
    ('Workflow', 'Dual-Pane File Manager', 'dual_pane_dialog', 'open_dual_pane', _U),
    ('Workflow', 'Macros', 'macro_manager_dialog', 'open_macro_manager_dialog', _U),
    ('Workflow', 'Watched Folder', 'watch_folder_dialog', 'open_watch_folder', _V),
    ('', 'menu', 'Export', 'extra_tools.export_submenu'),
    ('Export', 'Contact Sheet PDF', 'contact_sheet_dialog', 'open_contact_sheet_dialog', _U),
    ('Export', 'Web Gallery', 'web_gallery_dialog', 'open_web_gallery_dialog', _U),
    ('Export', 'Slideshow Video', 'slideshow_mp4_dialog', 'open_slideshow_mp4_dialog', _U),
    ('Export', 'Print Layout', 'print_layout_dialog', 'open_print_layout', _U),
    ('Export', 'Collage', 'collage_dialog', 'open_collage', _V),
    ('Export', 'ID Photo Sheet', 'id_photo_sheet_dialog', 'open_id_photo_sheet', _V),
    ('', 'menu', 'Develop (Non-Destructive)', 'extra_tools.develop_submenu'),
    ('Develop (Non-Destructive)',
     'Before / After Compare', 'before_after_dialog', 'open_before_after_dialog', _V),
    ('Develop (Non-Destructive)',
     'Develop Presets…', 'develop_presets_dialog', 'open_develop_presets_dialog', _V),
    ('Develop (Non-Destructive)', 'Tone Curve', 'tone_curve_dialog', 'open_tone_curve', _V),
    ('Develop (Non-Destructive)', 'Apply .cube LUT', 'lut_dialog', 'open_lut', _V),
    ('Develop (Non-Destructive)', 'Split Toning', 'split_toning_dialog', 'open_split_toning', _V),
    ('Develop (Non-Destructive)', 'Local Adjustment Masks', 'masks_dialog', 'open_masks', _V),
    ('Develop (Non-Destructive)', 'Layers', 'no-call'),
    ('Develop (Non-Destructive)', 'Levels', 'levels_dialog', 'open_levels_dialog', _V),
    ('Develop (Non-Destructive)',
     'Channel Mixer', 'channel_mixer_dialog', 'open_channel_mixer_dialog', _V),
    ('Develop (Non-Destructive)',
     'Gradient Map', 'gradient_map_dialog', 'open_gradient_map_dialog', _V),
    ('Develop (Non-Destructive)',
     'Auto Color Balance', 'auto_color_balance_dialog', 'open_auto_color_balance_dialog', _V),
    ('Develop (Non-Destructive)',
     'Clarity / Dehaze', 'local_contrast_dialog', 'open_local_contrast', _V),
    ('Develop (Non-Destructive)', 'HSL / Color Mixer', 'hsl_mixer_dialog', 'open_hsl_mixer', _V),
    ('Develop (Non-Destructive)', 'CLAHE (Local Equalize)', 'clahe_dialog', 'open_clahe', _V),
    ('Develop (Non-Destructive)',
     'Flatten Background', 'flatten_field_dialog', 'open_flatten_field', _V),
    ('Develop (Non-Destructive)', 'Frame & Caption', 'photo_frame_dialog', 'open_photo_frame', _V),
    ('Develop (Non-Destructive)', 'Ordered Dither', 'dither_dialog', 'open_dither', _V),
    ('Develop (Non-Destructive)', 'Color Map', 'colormap_dialog', 'open_colormap', _V),
    ('Develop (Non-Destructive)', 'Distort', 'distort_dialog', 'open_distort', _V),
    ('Develop (Non-Destructive)', 'Polar Coordinates', 'polar_dialog', 'open_polar', _V),
    ('Develop (Non-Destructive)', 'Kaleidoscope', 'kaleidoscope_dialog', 'open_kaleidoscope', _V),
    ('Develop (Non-Destructive)',
     'Frosted Glass', 'frosted_glass_dialog', 'open_frosted_glass', _V),
    ('Develop (Non-Destructive)', 'Pixel Sort', 'pixel_sort_dialog', 'open_pixel_sort', _V),
    ('Develop (Non-Destructive)', 'Film Grain', 'film_grain_dialog', 'open_film_grain_dialog', _V),
    ('Develop (Non-Destructive)', 'Lens Flare', 'lens_flare_dialog', 'open_lens_flare_dialog', _V),
    ('Develop (Non-Destructive)',
     'Threshold / Posterize', 'posterize_dialog', 'open_posterize_dialog', _V),
    ('Develop (Non-Destructive)', 'Solarize', 'solarize_dialog', 'open_solarize', _V),
    ('Develop (Non-Destructive)', 'Diffuse Glow', 'glow_dialog', 'open_glow', _V),
    ('Develop (Non-Destructive)',
     'Graduated Density', 'graduated_density_dialog', 'open_graduated_density', _V),
    ('Develop (Non-Destructive)', 'Velvia', 'velvia_dialog', 'open_velvia', _V),
    ('Develop (Non-Destructive)', 'Emboss', 'emboss_dialog', 'open_emboss', _V),
    ('Develop (Non-Destructive)', 'Defringe', 'defringe_dialog', 'open_defringe', _V),
    ('Develop (Non-Destructive)',
     'Film Negative', 'film_negative_dialog', 'open_film_negative', _V),
    ('Develop (Non-Destructive)',
     'Filmic Tone Map', 'filmic_tonemap_dialog', 'open_filmic_tonemap', _V),
    ('Develop (Non-Destructive)',
     'Tone Equalizer', 'tone_equalizer_dialog', 'open_tone_equalizer', _V),
    ('Develop (Non-Destructive)',
     'Detail Equalizer', 'detail_equalizer_dialog', 'open_detail_equalizer', _V),
    ('Develop (Non-Destructive)', 'Soft Proof', 'soft_proof_dialog', 'open_soft_proof', _V),
    ('', 'menu', 'Retouch & Transform', 'extra_tools.retouch_submenu'),
    ('Retouch & Transform', 'AI Image Upscale', 'ai_upscale_dialog', 'open_ai_upscale', _V),
    ('Retouch & Transform',
     'Noise Reduction / Sharpening', 'noise_sharpen_dialog', 'open_noise_sharpen', _V),
    ('Retouch & Transform', 'Healing Brush', 'healing_brush_dialog', 'open_healing_brush', _V),
    ('Retouch & Transform', 'Clone Stamp', 'clone_stamp_dialog', 'open_clone_stamp', _V),
    ('Retouch & Transform',
     'Frequency Separation', 'frequency_separation_dialog', 'open_frequency_separation_dialog', _V),
    ('Retouch & Transform', 'Smart Crop', 'smart_crop_dialog', 'open_smart_crop_dialog', _V),
    ('Retouch & Transform',
     'Portrait Auto-Retouch', 'portrait_retouch_dialog', 'open_portrait_retouch_dialog', _V),
    ('Retouch & Transform', 'Face Detection', 'face_detection_dialog', 'open_face_detection', _V),
    ('Retouch & Transform', 'Sky / Background', 'sky_replace_dialog', 'open_sky_replace', _V),
    ('Retouch & Transform', '---'),
    ('Retouch & Transform',
     'Crop / Straighten', 'crop_straighten_dialog', 'open_crop_straighten', _V),
    ('Retouch & Transform',
     'Auto-Straighten', 'auto_straighten_dialog', 'open_auto_straighten', _V),
    ('Retouch & Transform',
     'Lens Correction', 'lens_correction_dialog', 'open_lens_correction', _V),
    ('Retouch & Transform', 'Scale Bar', 'scale_bar_dialog', 'open_scale_bar', _V),
    ('', 'menu', 'Multi-Image', 'extra_tools.multi_image_submenu'),
    ('Multi-Image', 'HDR Merge', 'hdr_merge_dialog', 'open_hdr_merge', _V),
    ('Multi-Image', 'Panorama Stitch', 'panorama_dialog', 'open_panorama', _V),
    ('Multi-Image', 'Focus Stacking', 'focus_stack_dialog', 'open_focus_stack', _V),
    ('Multi-Image', 'Image Stack', 'stack_blend_dialog', 'open_stack_blend', _V),
    ('Multi-Image', 'Anaglyph 3D', 'anaglyph_dialog', 'open_anaglyph', _V),
]


def _build(window_viewer):
    from PySide6.QtWidgets import QMainWindow
    window = QMainWindow()
    window.viewer = window_viewer
    extra_tools_menu.build_extra_tools_menu(window)
    return window


def test_menu_tree_order_labels_and_targets(qapp, english, dialog_calls):
    log, _returns = dialog_calls
    cvd_log: list = []
    window = _build(_viewer(cvd_log))
    try:
        assert _snapshot(window, log, cvd_log) == EXPECTED_TREE
    finally:
        window.deleteLater()


def test_dialog_modules_are_imported_only_when_triggered(qapp, english, dialog_calls):
    log, _returns = dialog_calls
    window = _build(_viewer([]))
    try:
        assert log == []
    finally:
        window.deleteLater()


def _find_action(window, text):
    from PySide6.QtWidgets import QMenu
    top = window.findChild(QMenu, extra_tools_menu.EXTRA_TOOLS_OBJECT_NAME)
    return next(a for _p, a, k in _walk(top) if k is None and a.text() == text)


class _RecipeStoreSpy:
    def __init__(self, existing=None):
        self.existing = existing
        self.saved: list = []

    def get_for_path(self, path):
        return self.existing

    def set_for_path(self, path, recipe):
        self.saved.append((path, recipe))


@pytest.fixture
def recipe_spy(monkeypatch):
    from Imervue.image.recipe_store import recipe_store
    spy = _RecipeStoreSpy()
    monkeypatch.setattr(recipe_store, "get_for_path", spy.get_for_path)
    monkeypatch.setattr(recipe_store, "set_for_path", spy.set_for_path)
    return spy


@pytest.mark.parametrize("index", [-1, 1])
def test_layers_needs_a_current_image(qapp, english, dialog_calls, recipe_spy, index):
    log, _returns = dialog_calls
    window = _build(_viewer([], images=["a.png"], index=index))
    try:
        _find_action(window, "Layers").trigger()
        assert log == []
        assert recipe_spy.saved == []
    finally:
        window.deleteLater()


def test_layers_cancel_keeps_the_recipe(qapp, english, dialog_calls, recipe_spy):
    from Imervue.image.recipe import Recipe
    log, _returns = dialog_calls
    recipe_spy.existing = Recipe()
    window = _build(_viewer([], images=["a.png"], index=0))
    try:
        _find_action(window, "Layers").trigger()
        assert log == [(*_LAYERS, (recipe_spy.existing,), {"parent": window})]
        assert recipe_spy.saved == []
    finally:
        window.deleteLater()


def test_layers_result_is_stored_on_a_copy_and_reloaded(qapp, english, dialog_calls, recipe_spy):
    from Imervue.image.recipe import Recipe
    log, returns = dialog_calls
    returns[_LAYERS] = [{"name": "L1"}]
    original = Recipe(exposure=0.5)
    original.extra = {"keep": 1}
    recipe_spy.existing = original
    reloaded: list = []
    viewer = _viewer([], images=["a.png", "b.png"], index=1)
    viewer.reload_current_image_with_recipe = reloaded.append
    window = _build(viewer)
    try:
        _find_action(window, "Layers").trigger()
        assert len(log) == 1
        [(path, stored)] = recipe_spy.saved
        assert path == "b.png"
        assert stored is not original
        assert stored.exposure == pytest.approx(0.5)
        assert stored.extra == {"keep": 1, "layers": [{"name": "L1"}]}
        assert original.extra == {"keep": 1}
        assert reloaded == ["b.png"]
    finally:
        window.deleteLater()


def test_layers_without_a_stored_recipe_or_reload_hook(qapp, english, dialog_calls, recipe_spy):
    from Imervue.image.recipe import Recipe
    log, returns = dialog_calls
    returns[_LAYERS] = []
    window = _build(_viewer([], images=["a.png"], index=0))
    try:
        _find_action(window, "Layers").trigger()
        [(_m, _f, (passed,), _kw)] = log
        assert passed == Recipe()
        [(path, stored)] = recipe_spy.saved
        assert (path, stored.extra) == ("a.png", {"layers": []})
    finally:
        window.deleteLater()


def test_cvd_mode_is_ignored_without_a_capable_viewer(qapp, english, dialog_calls):
    for viewer in (None, SimpleNamespace()):
        window = _build(viewer)
        try:
            _find_action(window, "Protanopia (red-blind)").trigger()
        finally:
            window.deleteLater()
