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

    # XMP sidecar 匯入 / 匯出（Lightroom / Capture One 相容）
    xmp_action = menu.addAction(lang.get("xmp_title", "XMP Sidecars"))
    xmp_action.triggered.connect(lambda: _open_xmp_sidecar(ui))

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

    # 巨集管理（錄製 / 重播）
    macros_action = menu.addAction(lang.get("macro_title", "Macros"))
    macros_action.triggered.connect(lambda: _open_macro_manager(ui))

    # Contact sheet PDF
    contact_action = menu.addAction(
        lang.get("contact_sheet_title", "Contact Sheet PDF"))
    contact_action.triggered.connect(lambda: _open_contact_sheet(ui))

    # Web gallery HTML
    web_gallery_action = menu.addAction(
        lang.get("web_gallery_title", "Web Gallery"))
    web_gallery_action.triggered.connect(lambda: _open_web_gallery(ui))

    # Slideshow MP4
    slideshow_action = menu.addAction(
        lang.get("slideshow_mp4_title", "Slideshow Video"))
    slideshow_action.triggered.connect(lambda: _open_slideshow_mp4(ui))

    menu.addSeparator()

    # 時間軸檢視 (Google Photos 樣式)
    timeline_menu = menu.addMenu(lang.get("timeline_title", "Timeline View"))
    for gran_key, fallback in (
        ("day", "By day"), ("month", "By month"), ("year", "By year"),
    ):
        a = timeline_menu.addAction(lang.get(f"timeline_by_{gran_key}", fallback))
        a.triggered.connect(lambda checked, g=gran_key: _open_timeline(ui, g))

    # 行事曆檢視（依拍攝日期）
    calendar_action = menu.addAction(
        lang.get("calendar_title", "Calendar View"))
    calendar_action.triggered.connect(lambda: _open_calendar_view(ui))

    # 地圖檢視（GPS）
    map_action = menu.addAction(lang.get("map_title", "Map View"))
    map_action.triggered.connect(lambda: _open_map_view(ui))

    menu.addSeparator()

    # --- Non-destructive develop editors (per-image) ---
    tone_action = menu.addAction(lang.get("tone_curve_title", "Tone Curve"))
    tone_action.triggered.connect(lambda: _open_tone_curve(ui))

    lut_action = menu.addAction(lang.get("lut_title", "Apply .cube LUT"))
    lut_action.triggered.connect(lambda: _open_lut(ui))

    vcopies_action = menu.addAction(
        lang.get("vcopies_title", "Virtual Copies"))
    vcopies_action.triggered.connect(lambda: _open_virtual_copies(ui))

    face_action = menu.addAction(lang.get("face_title", "Face Detection"))
    face_action.triggered.connect(lambda: _open_face_detection(ui))

    menu.addSeparator()

    # --- Destructive transforms (output a new file) ---
    lens_action = menu.addAction(
        lang.get("lens_title", "Lens Correction"))
    lens_action.triggered.connect(lambda: _open_lens_correction(ui))

    heal_action = menu.addAction(lang.get("heal_title", "Healing Brush"))
    heal_action.triggered.connect(lambda: _open_healing_brush(ui))

    hdr_action = menu.addAction(lang.get("hdr_title", "HDR Merge"))
    hdr_action.triggered.connect(lambda: _open_hdr_merge(ui))

    pano_action = menu.addAction(lang.get("pano_title", "Panorama Stitch"))
    pano_action.triggered.connect(lambda: _open_panorama(ui))

    fstack_action = menu.addAction(
        lang.get("fstack_title", "Focus Stacking"))
    fstack_action.triggered.connect(lambda: _open_focus_stack(ui))


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
