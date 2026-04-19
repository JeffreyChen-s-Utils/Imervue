from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.multi_language.language_wrapper import language_wrapper


def build_extra_tools_menu(ui: ImervueMainWindow):
    lang = language_wrapper.language_word_dict
    menu = ui.menuBar().addMenu(lang.get("extra_tools_menu", "Extra Tools"))

    # 批次格式轉換
    convert_action = menu.addAction(
        lang.get("batch_convert_title", "Batch Format Conversion"))
    convert_action.triggered.connect(lambda: _open_batch_convert(ui))

    # AI 圖片放大
    upscale_action = menu.addAction(
        lang.get("upscale_title", "AI Image Upscale"))
    upscale_action.triggered.connect(lambda: _open_ai_upscale(ui))

    # 重複圖片偵測
    dup_action = menu.addAction(
        lang.get("duplicate_title", "Find Duplicate Images"))
    dup_action.triggered.connect(lambda: _open_duplicate_detection(ui))

    # 圖片整理工具
    organizer_action = menu.addAction(
        lang.get("organizer_title", "Image Organizer"))
    organizer_action.triggered.connect(lambda: _open_image_organizer(ui))

    # EXIF 批次清除
    strip_action = menu.addAction(
        lang.get("exif_strip_title", "Batch EXIF Strip"))
    strip_action.triggered.connect(lambda: _open_exif_strip(ui))

    # 圖片淨化重繪
    sanitize_action = menu.addAction(
        lang.get("sanitize_title", "Image Sanitizer"))
    sanitize_action.triggered.connect(lambda: _open_image_sanitize(ui))

    menu.addSeparator()

    # 全域圖片資料庫搜尋
    lib_action = menu.addAction(
        lang.get("library_search_title", "Library Search"))
    lib_action.triggered.connect(lambda: _open_library_search(ui))

    # 智慧相簿
    smart_action = menu.addAction(
        lang.get("smart_albums_title", "Smart Albums"))
    smart_action.triggered.connect(lambda: _open_smart_albums(ui))

    # 相似圖片搜尋
    similar_action = menu.addAction(
        lang.get("similar_search_title", "Find Similar Images"))
    similar_action.triggered.connect(lambda: _open_similar_search(ui))

    # 自動標記
    auto_tag_action = menu.addAction(
        lang.get("auto_tag_title", "Auto-Tag Images"))
    auto_tag_action.triggered.connect(lambda: _open_auto_tag(ui))

    # 階層式標籤
    htags_action = menu.addAction(
        lang.get("htags_title", "Hierarchical Tags"))
    htags_action.triggered.connect(lambda: _open_hierarchical_tags(ui))

    # Token 批次重新命名
    rename_action = menu.addAction(
        lang.get("token_rename_title", "Token Batch Rename"))
    rename_action.triggered.connect(lambda: _open_token_rename(ui))

    # 中繼資料匯出 (CSV / JSON)
    meta_action = menu.addAction(
        lang.get("metadata_export_title", "Export Metadata (CSV / JSON)"))
    meta_action.triggered.connect(lambda: _open_metadata_export(ui))

    # 分揀 (Pick / Reject)
    cull_action = menu.addAction(
        lang.get("culling_title", "Culling"))
    cull_action.triggered.connect(lambda: _open_culling(ui))

    # 暫存籃
    tray_action = menu.addAction(
        lang.get("staging_tray_title", "Staging Tray"))
    tray_action.triggered.connect(lambda: _open_staging_tray(ui))

    # 雙窗格檔案管理
    dual_pane_action = menu.addAction(
        lang.get("dual_pane_title", "Dual-Pane File Manager"))
    dual_pane_action.triggered.connect(lambda: _open_dual_pane(ui))

    menu.addSeparator()

    # 時間軸檢視 (Google Photos 樣式)
    timeline_menu = menu.addMenu(lang.get("timeline_title", "Timeline View"))
    for gran_key, fallback in (
        ("day", "By day"), ("month", "By month"), ("year", "By year"),
    ):
        a = timeline_menu.addAction(lang.get(f"timeline_by_{gran_key}", fallback))
        a.triggered.connect(lambda checked, g=gran_key: _open_timeline(ui, g))


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
