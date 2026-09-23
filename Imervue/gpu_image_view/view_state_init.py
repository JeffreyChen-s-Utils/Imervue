"""State initialisers for :class:`GPUImageView`, called once from its constructor.

Each sets one group of instance attributes (tile grid, deep zoom, browsing,
interaction, display) on the view it is given; none touches GL, so they run
before a context exists.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QUndoStack

from Imervue.gpu_image_view.images.image_model import ImageModel
from Imervue.gpu_image_view.tile_focus import NO_FOCUS
from Imervue.gpu_image_view.tile_layout import DEFAULT_THUMBNAIL_SIZE, resolve_thumbnail_size

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def init_grid_state(view: GPUImageView) -> None:
    """Undo stacks and tile-grid layout, selection-cursor and upload state."""
    # ===== Undo =====
    view.undo_stack = []  # legacy delete undo
    view.undo_manager = QUndoStack(view)

    # ===== Tile Grid =====
    view.tile_grid_mode = False
    view.selected_image_path = None
    view.tile_rects = []  # 用來存每個 tile 的 rectangle
    view.grid_offset_x = 0
    view.grid_offset_y = 0
    view.tile_scale = 1.0
    # Effective per-tile draw scale = tile_scale / devicePixelRatio,
    # recomputed each ``paint_tile_grid`` so thumbnails keep a consistent
    # physical size across monitors with different display scaling.
    view._tile_draw_scale = 1.0
    # Set when the thumbnail size changes while in deep zoom, so the grid
    # is rebuilt at the new size when the user exits back to the wall.
    view._tile_size_dirty = False
    # Keyboard focus cursor — index into ``model.images`` of the tile
    # highlighted for arrow-key navigation. NO_FOCUS (-1) means nothing is
    # focused yet, so the highlight only shows once the user starts
    # keyboard-browsing and never bothers mouse-only users.
    view.focused_tile_index = NO_FOCUS
    # The amber ring draws only while this is True — set by arrow-key
    # navigation, cleared by mouse clicks and by (re)entering the wall,
    # so the ring never greets the user uninvited.
    view.focus_ring_visible = False
    view.tile_textures = {}
    view.tile_cache = {}  # path -> img_data
    view.tile_errors: dict[str, str] = {}
    view._tile_error_toasted: set[str] = set()
    view._tile_retry_counts: dict[str, int] = {}
    view.offline_paths: set[str] = set()
    # 檔案存在檢查全部走背景掃描（tile_loader.OfflineScanWorker），
    # paint 路徑只查 offline_paths 這個 set，不做任何檔案系統 I/O。
    view._offline_scan_inflight = False
    from Imervue.gpu_image_view.tile_loader import OFFLINE_SWEEP_INTERVAL_MS
    view._offline_sweep_timer = QTimer(view)
    view._offline_sweep_timer.setInterval(OFFLINE_SWEEP_INTERVAL_MS)
    view._offline_sweep_timer.timeout.connect(view._tick_offline_sweep)
    # path -> monotonic arrival time, for the thumbnail fade-in animation.
    view._tile_load_times: dict[str, float] = {}
    # path -> (size, mtime_ns, suffix), used to migrate tile cache on rename.
    view._tile_file_signatures: dict[str, tuple[int, int, str]] = {}
    # Async PBO streaming uploader; allocated in initializeGL once a
    # GL context exists. Stays None (synchronous fallback) until then.
    view._tile_uploader = None


def init_deep_zoom_state(view: GPUImageView) -> None:
    """Deep-zoom image, load tracking and view-fitting state."""
    # ===== DeepZoom =====
    view.zoom = 1.0
    view.dz_offset_x = 0
    view.dz_offset_y = 0
    view.last_pos = None
    view.tile_manager = None
    view.deep_zoom = None
    # Path of the image whose full pyramid is loading in the background.
    # While set (and ``deep_zoom`` is still None) the overlay shows a
    # low-res preview + "Loading…" pill instead of a blank frame.
    view._deep_zoom_loading: str | None = None
    # Path of the image currently shown (or targeted) in deep zoom — the
    # image whose view ``zoom`` / offsets are live. Used to save the view
    # under the right key when navigating away (see ``save_view_state``).
    view._deep_zoom_path: str | None = None
    view._deep_zoom_error: tuple[str, str] | None = None
    view._deep_zoom_request_id = 0
    view._deep_zoom_retry_counts: dict[str, int] = {}
    view._saved_tile_state = None
    # True while the user is click-dragging inside the deep-zoom minimap
    # to pan the viewport.
    view._minimap_dragging = False
    # When True, the user has zoomed / panned manually so the
    # canvas should not auto-fit on resize. Cleared on every
    # fresh image load via :meth:`_fit_to_window`.
    view._user_locked_view = False
    # Snapshot (taken before the per-load save) of whether the image being
    # loaded had a genuinely remembered view, so a fresh entry always fits.
    view._loading_was_remembered = False
    # Base dims the remembered zoom was saved against — a mismatch on load
    # (rotate/crop changed the geometry) forces a refit.
    view._loading_remembered_dims = None
    # Whether the remembered view being loaded was a deliberate zoom-in
    # (kept) or a whole-image fit (re-fit to the current canvas).
    view._loading_was_locked = False
    # Most-recent ``resizeGL`` size — same role as the paint
    # canvas's ``_last_resize_size``. Used by ``_fit_to_window``
    # so the initial centre uses the GL-reported logical size
    # rather than ``view.width()`` / ``height()`` which can lag
    # the actual layout for the first frame or two.
    view._last_resize_size: tuple[int, int] = (0, 0)
    # Retires a screen-settle watch when a newer screen change starts.
    view._screen_settle_generation = 0


def init_browse_state(view: GPUImageView) -> None:
    """Image switching, filtered list, thumbnail density, filmstrip and fade state."""
    # ===== 圖片切換控制 =====
    view.model = ImageModel()
    view.model.images = []  # 所有圖片路徑
    view.current_index = 0
    view.on_filename_changed = None
    # Fired with the edited full-resolution base-level array once a deep-zoom
    # image is on screen. The multi-monitor mirror uses it to show the same
    # edited result the main viewer shows (not the raw file on disk).
    view.on_deep_zoom_displayed = None
    view.deep_zoom_tile_size = 512
    view._slideshow_opacity = 1.0

    # ===== 篩選前完整圖片列表 =====
    view._unfiltered_images: list[str] = []

    # ===== 縮圖排列密度 =====
    # 0 (compact) / 8 (standard) / 16 (relaxed) — 縮圖間額外 padding 像素
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    view.tile_padding = int(user_setting_dict.get("tile_padding", 8))
    # Persisted thumbnail size — survives restarts (validated against the
    # known sizes so a corrupt value can't break the grid).
    view.thumbnail_size = resolve_thumbnail_size(
        user_setting_dict.get("thumbnail_size", DEFAULT_THUMBNAIL_SIZE),
    )

    # ===== 底部縮圖膠卷（deep-zoom filmstrip）=====
    # 在單張檢視時於畫面底部顯示鄰近縮圖，點選即可跳圖。可由設定關閉。
    view._filmstrip_enabled = bool(
        user_setting_dict.get("filmstrip_enabled", True),
    )
    # path -> QPixmap，膠卷與低解析載入預覽共用；換資料夾時清空。
    view._filmstrip_thumb_cache: dict = {}
    # 已排程但尚未完成的膠卷縮圖載入路徑，避免每幀重複丟 worker。
    # 膠卷與載入預覽的縮圖只來自 tile_cache；某些進入單張檢視的路徑
    # （直接開檔、單張檢視時的資料夾刷新）不會經過 tile wall 載入，
    # tile_cache 因此是空的，於是改在繪製時按需補載入到這裡去重。
    view._filmstrip_pending: set[str] = set()

    # ===== 切換淡入轉場 =====
    # 顯示新的單張圖時讓它淡入，連續翻圖更順。可由設定關閉。
    view._transition_enabled = bool(
        user_setting_dict.get("image_transition_enabled", True),
    )
    from Imervue.gpu_image_view.view_animator import ImageFadeController
    view._image_fade = ImageFadeController(view)


def init_interaction_state(view: GPUImageView) -> None:
    """Hover preview, history, grid selection, mouse, rubber-band zoom and smooth navigation."""
    # ===== Hover 預覽 =====
    # Lazy-init 避免在沒有 QApplication 時匯入失敗
    view._hover_controller = None
    view._hover_last_path: str | None = None
    view._hover_tile_path: str | None = None
    view._timeline_grouping_enabled = True
    view._quick_meta_hud: tuple[str, float] | None = None

    # ===== 瀏覽歷史 =====
    # 每次進入 deep zoom 的圖片會被 push 到 history controller。
    # 前進/後退移動指標，不重寫 stack（除非使用者跳到新圖則 truncate）。
    from Imervue.gpu_image_view.history_controller import HistoryController
    view._history = HistoryController(view)

    # ===== Tile Grid 選取模式 =====
    view.tile_selection_mode = False  # 是否在選取模式
    view.selected_tiles = set()  # 已選取的 tile path
    view.long_press_threshold = 500  # 長按進入選取模式的毫秒
    view._press_timer = None
    view._drag_selecting = False  # 是否正在拖曳框選
    view._drag_start_pos = None
    view._drag_end_pos = None

    # ===== Mouse =====
    view._middle_dragging = False
    view.press_pos = None

    # ===== 框選放大（deep-zoom rubber-band zoom）=====
    # 深縮放時左鍵拖一個方框 → 放大到該區域填滿畫面。
    view._zoom_band_active = False
    view._zoom_band_start = None
    view._zoom_band_end = None

    # ===== 平滑導覽：緩動縮放 + 慣性平移 =====
    # 會改變操作手感，預設關閉；user_setting 開啟後生效。
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    view._smooth_nav_enabled = bool(
        user_setting_dict.get("smooth_navigation_enabled", False),
    )
    from Imervue.gpu_image_view.view_animator import (
        PanMomentumController,
        ZoomEaseController,
    )
    view._zoom_ease = ZoomEaseController(view)
    view._pan_momentum = PanMomentumController(view)
    view._last_pan_velocity = (0.0, 0.0)


def init_display_state(view: GPUImageView) -> None:
    """VRAM budget, histogram, OSD / HUD / loupe / reading-mode toggles and animation."""
    # ===== VRAM 管理 =====
    # 保守預設 1.5 GB。initializeGL() 會嘗試用 NVX/ATI 擴充詢問 GPU 實際 VRAM，
    # 抓到的話會覆寫成實體 VRAM 的 ~40%，在顯卡強的機器上可大幅放寬 tile cache。
    view._vram_usage = 0  # 目前 tile grid 紋理佔用 bytes
    view._vram_limit = int(1.5 * 1024 * 1024 * 1024)  # 1.5 GB fallback
    view._vram_limit_default = view._vram_limit
    view._tile_tex_sizes: dict[str, int] = {}  # path → texture bytes

    # ===== 直方圖 =====
    view._show_histogram = False
    view._histogram_cache: tuple | None = None  # (path, Histogram, ClipStats)

    # ===== OSD (On-Screen Display) =====
    # F3 — 切換右上角顯示檔名 / 尺寸 / 格式 / 檔案大小
    view._show_osd = False
    # Ctrl+F3 — Debug HUD：VRAM、tile cache、執行緒池等技術資訊
    view._show_debug_hud = False
    # 目前滑鼠在圖片上的像素座標（update_status 用，paint_pixel_view 用）
    view._hover_image_xy: tuple[int, int] | None = None
    # OSD 的 EXIF 行快取：(path, lines)，避免每幀重讀檔案
    view._exif_osd_cache: tuple | None = None
    # Shift+P — 像素檢視模式：zoom >= 4x 時顯示像素網格 + RGB 值
    view._pixel_view = False
    # L — 放大鏡 loupe：跟著游標顯示局部放大，挑片/對焦確認用
    view._loupe_enabled = False
    # Shift+滾輪 在 loupe 開啟時調整放大倍率（見 overlay_painter）。
    from Imervue.gpu_image_view.hud_geometry import LOUPE_MAGNIFICATION
    view._loupe_magnification = LOUPE_MAGNIFICATION
    # W — 閱讀模式：fit 寬度 + 垂直捲動，捲到底自動接下一張（webtoon/長圖）
    view._reading_mode = False

    # ===== 動畫播放 =====
    view._animation: object | None = None  # AnimationPlayer instance

    # ===== Minimap =====
    view._minimap_tex = None  # GL texture id
    view._minimap_dzi = None  # 對應的 DeepZoomImage，用來偵測是否需要重建

    # 原本 deep zoom 模式下 5 秒不動就會自動藏起 menu/status/tree/exif — 使用者
    # 反映會擋到檢視流程，移除此行為。保留 mouseTracking 讓 cursor 位置更新
    # 等其他仰賴 mouse move 事件的功能繼續運作。
    view.setMouseTracking(True)

    # ===== Focus ======
    view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    view.setFocus()

    # ===== Drag & Drop =====
    view.setAcceptDrops(True)

    # ===== 觸控板手勢 =====
    # Pinch → deep zoom 縮放；Swipe 左右 → 切換圖片
    view.grabGesture(Qt.GestureType.PinchGesture)
    view.grabGesture(Qt.GestureType.SwipeGesture)
