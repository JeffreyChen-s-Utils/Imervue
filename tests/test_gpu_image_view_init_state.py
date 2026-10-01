"""Characterisation test for ``GPUImageView``'s constructed state.

Pins every instance attribute the constructor creates: its name and type, the
value of simple ones (flags, numbers, strings, ``None``, empty containers), and
each ``QTimer``'s interval and single-shot flag. Generated from the view before
its state initialisers moved to ``view_state_init.py``, so moving code cannot
drop, rename or re-default a field.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer

from _qt_skip import pytestmark  # noqa: E402,F401
from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_EXPECTED = {'_animation': ('NoneType', None),
 '_browse': ('BrowseFeatures',),
 '_deep_zoom_error': ('NoneType', None),
 '_deep_zoom_loading': ('NoneType', None),
 '_deep_zoom_path': ('NoneType', None),
 '_deep_zoom_renderer': ('DeepZoomRenderer',),
 '_deep_zoom_request_id': ('int', 0),
 '_deep_zoom_retry_counts': ('dict', 'empty'),
 '_drag_end_pos': ('NoneType', None),
 '_drag_selecting': ('bool', False),
 '_drag_start_pos': ('NoneType', None),
 '_exif_osd_cache': ('NoneType', None),
 '_filmstrip_enabled': ('bool', True),
 '_filmstrip_pending': ('set', 'empty'),
 '_filmstrip_thumb_cache': ('dict', 'empty'),
 '_folder_scan_active': ('bool', False),
 '_histogram_cache': ('NoneType', None),
 '_history': ('HistoryController',),
 '_hover_controller': ('NoneType', None),
 '_hover_image_xy': ('NoneType', None),
 '_hover_last_path': ('NoneType', None),
 '_hover_tile_path': ('NoneType', None),
 '_image_fade': ('ImageFadeController',),
 '_input': ('InputController',),
 '_key_dispatch': ('KeyActionDispatcher',),
 '_key_input': ('KeyInputHandler',),
 '_last_pan_velocity': ('tuple',),
 '_last_resize_size': ('tuple',),
 '_load_generation': ('int', 0),
 '_loading_remembered_dims': ('NoneType', None),
 '_loading_was_locked': ('bool', False),
 '_loading_was_remembered': ('bool', False),
 '_loupe_enabled': ('bool', False),
 '_loupe_magnification': ('int', 4),
 '_middle_dragging': ('bool', False),
 '_minimap_dragging': ('bool', False),
 '_minimap_dzi': ('NoneType', None),
 '_minimap_tex': ('NoneType', None),
 '_offline_scan_inflight': ('bool', False),
 '_offline_sweep_timer': ('QTimer', 4000, False),
 '_overlay': ('OverlayPainter',),
 '_pan_momentum': ('PanMomentumController',),
 '_pixel_view': ('bool', False),
 '_prefetch': ('PrefetchScheduler',),
 '_press_timer': ('NoneType', None),
 '_progress_coalescer': ('SignalCoalescer',),
 '_quick_meta_hud': ('NoneType', None),
 '_reading_mode': ('bool', False),
 '_saved_tile_state': ('NoneType', None),
 '_screen_settle_generation': ('int', 0),
 '_show_debug_hud': ('bool', False),
 '_show_histogram': ('bool', False),
 '_show_osd': ('bool', False),
 '_shown_file_watch': ('ShownFileWatch',),
 '_slideshow_opacity': ('float', 1.0),
 '_smooth_nav_enabled': ('bool', False),
 '_tile_draw_scale': ('float', 1.0),
 '_tile_error_toasted': ('set', 'empty'),
 '_tile_file_signatures': ('dict', 'empty'),
 '_tile_load_times': ('dict', 'empty'),
 '_tile_renderer': ('TileGridRenderer',),
 '_tile_retry_counts': ('dict', 'empty'),
 '_tile_size_dirty': ('bool', False),
 '_tile_tex_sizes': ('dict', 'empty'),
 '_tile_uploader': ('NoneType', None),
 '_timeline_grouping_enabled': ('bool', True),
 '_transition_enabled': ('bool', True),
 '_unfiltered_images': ('list', 'empty'),
 '_user_locked_view': ('bool', False),
 '_view_memory': ('dict', 'empty'),
 '_vram_limit': ('int', 1610612736),
 '_vram_limit_default': ('int', 1610612736),
 '_vram_usage': ('int', 0),
 '_zoom_band_active': ('bool', False),
 '_zoom_band_end': ('NoneType', None),
 '_zoom_band_start': ('NoneType', None),
 '_zoom_ease': ('ZoomEaseController',),
 'aboutToCompose': ('SignalInstance',),
 'aboutToResize': ('SignalInstance',),
 'active_deep_zoom_preview_worker': ('NoneType', None),
 'active_deep_zoom_worker': ('NoneType', None),
 'active_tile_workers': ('set', 'empty'),
 'current_index': ('int', 0),
 'customContextMenuRequested': ('SignalInstance',),
 'deep_zoom': ('NoneType', None),
 'deep_zoom_tile_size': ('int', 512),
 'deepzoom_pool': ('QThreadPool',),
 'destroyed': ('SignalInstance',),
 'dz_offset_x': ('int', 0),
 'dz_offset_y': ('int', 0),
 'focus_ring_visible': ('bool', False),
 'focused_tile_index': ('int', -1),
 'frameSwapped': ('SignalInstance',),
 'grid_mutex': ('QMutex',),
 'grid_offset_x': ('int', 0),
 'grid_offset_y': ('int', 0),
 'last_pos': ('NoneType', None),
 'long_press_threshold': ('int', 500),
 'main_window': ('SimpleNamespace',),
 'model': ('ImageModel',),
 'objectNameChanged': ('SignalInstance',),
 'offline_paths': ('set', 'empty'),
 'on_deep_zoom_displayed': ('NoneType', None),
 'on_filename_changed': ('NoneType', None),
 'prefetch_pool': ('QThreadPool',),
 'press_pos': ('NoneType', None),
 'renderer': ('GLRenderer',),
 'resized': ('SignalInstance',),
 'selected_image_path': ('NoneType', None),
 'selected_tiles': ('set', 'empty'),
 'thread_pool': ('QThreadPool',),
 'thumbnail_pool': ('QThreadPool',),
 'thumbnail_size': ('int', 512),
 'tile_cache': ('dict', 'empty'),
 'tile_errors': ('dict', 'empty'),
 'tile_grid_mode': ('bool', False),
 'tile_manager': ('NoneType', None),
 'tile_padding': ('int', 8),
 'tile_rects': ('list', 'empty'),
 'tile_scale': ('float', 1.0),
 'tile_selection_mode': ('bool', False),
 'tile_textures': ('dict', 'empty'),
 'undo_manager': ('QUndoStack',),
 'undo_stack': ('list', 'empty'),
 'windowIconChanged': ('SignalInstance',),
 'windowIconTextChanged': ('SignalInstance',),
 'windowTitleChanged': ('SignalInstance',),
 'zoom': ('float', 1.0)}


def _describe(value):
    if isinstance(value, QTimer):
        return ("QTimer", value.interval(), value.isSingleShot())
    if value is None or isinstance(value, (bool, int, float, str)):
        return (type(value).__name__, value)
    if isinstance(value, (list, dict, set, tuple)) and not value:
        return (type(value).__name__, "empty")
    return (type(value).__name__,)


@pytest.fixture
def view(qapp):
    widget = GPUImageView(SimpleNamespace())
    yield widget
    widget.deleteLater()


def test_constructed_attributes_are_unchanged(view):
    actual = {k: _describe(v) for k, v in sorted(vars(view).items()) if k != "__METAOBJECT__"}
    assert sorted(actual) == sorted(_EXPECTED)
    for name, expected in _EXPECTED.items():
        assert actual[name] == expected, name
