# Imervue 架構全覽 (architecture_explore)

> 產出日期：2026-08-03（全樹掃描）· 最後同步：2026-09-26 · 對應 commit `4346a3e` · 分支 `dev` · 版本 `1.0.90`
>
> 本文件是一次「全樹掃描」的結果：以 AST 逐檔擷取模組 docstring、類別與公開函式，
> 再交叉比對實際程式碼撰寫而成。散文用繁體中文，模組名 / 路徑 / 型別一律保留英文。

---

## 目錄

1. [一句話定位](#1-一句話定位)
2. [規模統計](#2-規模統計)
3. [執行入口與啟動流程](#3-執行入口與啟動流程)
4. [頂層結構：一個主視窗、五個分頁](#4-頂層結構一個主視窗五個分頁)
5. [分層與依賴規則](#5-分層與依賴規則)
6. [套件逐一說明](#6-套件逐一說明)
   - [6.1 `Imervue/`（根層）](#61-imervue根層)
   - [6.2 `Imervue/system/`](#62-imervuesystem)
   - [6.3 `Imervue/user_settings/`](#63-imervueuser_settings)
   - [6.4 `Imervue/multi_language/`](#64-imervuemulti_language)
   - [6.5 `Imervue/sessions/`](#65-imervuesessions)
   - [6.6 `Imervue/macros/`](#66-imervuemacros)
   - [6.7 `Imervue/external/`](#67-imervueexternal)
   - [6.8 `Imervue/export/`](#68-imervueexport)
   - [6.9 `Imervue/image/`](#69-imervueimage純運算核心)
   - [6.10 `Imervue/gpu_image_view/`](#610-imervuegpu_image_view)
   - [6.11 `Imervue/library/`](#611-imervuelibrary)
   - [6.12 `Imervue/gui/`](#612-imervuegui)
   - [6.13 `Imervue/menu/`](#613-imervuemenu)
   - [6.14 `Imervue/paint/`](#614-imervuepaint)
   - [6.15 `Imervue/puppet/`](#615-imervuepuppet)
   - [6.16 `Imervue/desktop_pet/`](#616-imervuedesktop_pet)
   - [6.17 `Imervue/plugin/`](#617-imervueplugin)
   - [6.18 `Imervue/mcp_server/`](#618-imervuemcp_server)
7. [`plugins/` 外掛實作](#7-plugins-外掛實作)
8. [`tests/` 測試體系](#8-tests-測試體系)
9. [建置、封裝與 CI](#9-建置封裝與-ci)
10. [跨切面模式（重要）](#10-跨切面模式重要)
11. [持久化檔案一覽](#11-持久化檔案一覽)
12. [架構注意事項與已知陷阱](#12-架構注意事項與已知陷阱)

---

## 1. 一句話定位

Imervue = **Image + Immerse + View**。以 PySide6 + OpenGL 打造的桌面應用，同時是：

| 身分 | 對應分頁 | 核心套件 |
| --- | --- | --- |
| GPU 加速的圖片瀏覽器 / 相片庫 | Tab 0 `Imervue` | `gpu_image_view/`、`library/` |
| 非破壞性顯影（Lightroom 式 recipe） | Tab 1 `Modify` | `image/recipe*.py`、`gui/develop_panel.py` |
| 全功能點陣繪圖 / 漫畫工作區 | Tab 2 `Paint` | `paint/` |
| 2D 骨架人偶動畫（Live2D Cubism 相容） | Tab 3 `Puppet` | `puppet/` |
| 桌面寵物懸浮視窗 | Tab 4 `Desktop Pet` | `desktop_pet/` |

另有兩條**非 GUI** 的對外介面：`Imervue/cli.py`（headless 批次 CLI）與
`Imervue/mcp_server/`（Model Context Protocol server，把 56 個影像工具暴露給 LLM 代理）。

**必要相依只有 11 個套件**：PySide6、qt-material、Pillow、PyOpenGL(+accelerate)、numpy、
rawpy、imageio(+ffmpeg)、defusedxml、watchdog。所有重量級 / ML 相依都被推到 `plugins/`。

---

## 2. 規模統計

| 區域 | 檔案數 | 行數 |
| --- | ---: | ---: |
| `tests/` | 889 | 148,198 |
| `Imervue/paint/`（含 `docks/`、`tools/`） | 190 | 46,140 |
| `Imervue/gui/` | 167 | 33,295 |
| `Imervue/puppet/` | 57 | 15,296 |
| `Imervue/image/` | 128 | 15,355 |
| `Imervue/gpu_image_view/`（含 `actions/`、`images/`） | 69 | 13,237 |
| `Imervue/multi_language/` | 8 | 14,154 |
| `Imervue/desktop_pet/` | 34 | 8,261 |
| `Imervue/mcp_server/` | 16 | 4,666 |
| `Imervue/library/` | 32 | 4,266 |
| `Imervue/menu/` | 11 | 3,594 |
| `Imervue/` 根層 | 5 | 1,576 |
| `Imervue/plugin/` | 10 | 2,246 |
| `Imervue/system/` | 32 | 3,152 |
| `Imervue/export/` | 9 | 1,082 |
| `Imervue/user_settings/` | 10 | 1,155 |
| `Imervue/sessions/` + `macros/` + `external/` | 9 | 935 |
| `plugins/`（17 個外掛） | 64 | 14,365 |
| **總計** | **1,740** | **330,973** |

其中 `Imervue/` 套件本身 787 檔 / 168,410 行。

測試碼與產品碼比約 **0.71 : 1**（123k vs 173k），這是專案開發規範中「無測試即未完成」規則的直接體現。

> 數字以 `CLAUDE.md`「Architecture Map」章節裡的指令重新產生，不要手改。

---

## 3. 執行入口與啟動流程

進入點：`Imervue/__main__.py`（`py -m Imervue`）。

```
py -m Imervue [--debug] [--software_opengl] [file]
   │
   ├─ 1. 凍結環境偵測 → 關閉 OpenGL_accelerate（Nuitka 打包後 Cython 擴充會壞）
   ├─ 2. Windows：強制 UTF-8 I/O（避免 CJK 顯示成 ?）
   ├─ 3. main()：setup_logging() + install_exception_logging()（在 import PySide6 之前，
   │      所以連啟動期的例外也會進 imervue.log）→ configure_pillow()（Pillow 像素上限依記憶體放寬、中途截斷的檔案讀到截斷處）
   ├─ 3b. _set_windows_app_user_model_id() → 工作列圖示身分
   ├─ 4. QApplication + setQuitOnLastWindowClosed(False)
   ├─ 5. read_user_setting()  ← 必須在任何 widget 之前
   │      load_and_apply_theme(app)       (system/themes.py)
   │      load_and_apply_from_settings(app) (system/ui_scale.py)
   ├─ 6. ImervueMainWindow(debug=…)
   │      └─ 內部：還原視窗幾何 → 建 5 個分頁 → create_menu()
   │                → _init_plugin_system_example() 載入外掛
   │                → QTimer(800ms) 顯示 What's New / 首次導覽
   └─ 7. 命令列帶檔案 → QTimer(100ms) open_path(viewer, path)
```

**其他入口**

| 入口 | 檔案 | 用途 |
| --- | --- | --- |
| `py -m Imervue.cli …` | `Imervue/cli.py` | headless 批次：resize / watermark / info / convert，只用純 NumPy+Pillow 路徑，完全不起 Qt；直接執行時先 `configure_pillow()` |
| `py -m Imervue.mcp_server` | `Imervue/mcp_server/__main__.py` | stdio JSON-RPC 2.0 MCP server（啟動前 `configure_pillow()`） |
| `exe/start_Imervue.py` | — | PyInstaller / auto-py-to-exe 的啟動 shim |

---

## 4. 頂層結構：一個主視窗、五個分頁

`ImervueMainWindow(QMainWindow)`（`Imervue/Imervue_main_window.py`，924 行）是唯一的協調者；篩選列、遺失檔、資料夾監看、分頁、螢幕、檢視模式、狀態列、瀏覽模式各由 `Imervue/gui/main_window_*.py` 的 mixin 提供。
中央是一個 `QTabWidget`：

```
ImervueMainWindow
├── QTabWidget (self._main_tabs)
│   ├── Tab 0  "Imervue"       ← QSplitter
│   │      ├── 左：_FileTreeView  (FileTreeSortProxy → FolderThumbnailModel)
│   │      │        + tree_search (QLineEdit)
│   │      └── 右：QVBoxLayout
│   │             ├── QTabBar          ← 瀏覽器式圖片分頁（每頁 = 一張 deep-zoom 圖）
│   │             ├── BreadcrumbBar    ← 可點擊路徑列
│   │             ├── filter row       ← 檔名 / tag / rating / date 過濾
│   │             ├── filename_label
│   │             └── QSplitter
│   │                    ├── QStackedWidget   0=GPUImageView 1=ImageListView 2=DualImageView
│   │                    └── ExifSidebar
│   ├── Tab 1  "Modify"        ← QSplitter：左工具列 | AnnotationCanvas | 右顯影滑桿
│   ├── Tab 2  "Paint"         ← PaintWorkspace
│   ├── Tab 3  "Puppet"        ← PuppetWorkspace (QMainWindow-in-tab)
│   └── Tab 4  "Desktop Pet"   ← PetWorkspace（控制面板；角色在另一個 top-level PetWindow）
├── QStatusBar  ← 訊息 + 色標籤 chip + index/解析度/大小/縮放/游標 + MemoryPressureIndicator + 進度條
├── QDockWidget "Image load issues"  ← ImageIssuePanel
└── 系統匣 PetTrayIcon（平台支援時）
```

**主視窗自己負責的職責**（其餘全部委派）：

- 分頁切換路由（`_on_main_tab_changed`）、Modify/Paint 分頁的左右鍵改為換圖（`eventFilter`）
- 瀏覽模式切換 grid / list / dual、Theater mode（隱藏所有 chrome）、多螢幕鏡像視窗
- 檔名 / 標籤 / 星等 / 日期過濾列，以及「檔案不見了」的批次修復（自動比對同名、移除、換根目錄）
- 資料夾監控去抖（`QFileSystemWatcher` 500ms + watchdog 遞迴監看）
- 視窗幾何存還原、**跨螢幕自適應**（`moveEvent` 300ms 去抖 → 重新 fit 圖片）
- 每資料夾的 view session 存還原、瀏覽器式圖片分頁狀態機
- 關閉時：`commit_pending_deletions()` → 外掛 unload → 存設定

---

## 5. 分層與依賴規則

專案有一條貫穿全樹的硬規則：**純運算與 Qt 外殼必須分開**。

```
┌──────────────────────────────────────────────────────────┐
│ menu/            選單建構 → 呼叫 gui/ 對話框               │
├──────────────────────────────────────────────────────────┤
│ gui/             Qt 對話框外殼（滑桿、預覽、背景 worker）  │
│ gpu_image_view/  OpenGL widget + 協作者                    │
│ paint/ puppet/ desktop_pet/  各自的工作區                  │
├──────────────────────────────────────────────────────────┤
│ image/  library/  export/    純邏輯：NumPy / Pillow / sqlite│
│                              無 Qt import，可在 worker 執行 │
├──────────────────────────────────────────────────────────┤
│ system/  user_settings/  multi_language/  plugin/          │
│                              基礎設施                       │
└──────────────────────────────────────────────────────────┘
```

具體表現：

- `gui/xxx_dialog.py` 幾乎都只是外殼，數學在 `image/xxx.py`。docstring 會明寫
  「Pure math in :mod:`Imervue.image.xxx`; this is the Qt shell」。
- 從 Qt 類別抽出的純函式（`vram_budget.py`、`layers.py`、`tile_layout.py`、`edge_snap.py`…）
  可以不開 GL context、不建 widget 就直接單元測試。
- `gpu_image_view.py`（1,758 行）本身只留 GL 生命週期與 Qt 事件轉發，
  其餘全部委派給約 40 個 collaborator 模組。

---

## 6. 套件逐一說明

### 6.1 `Imervue/`（根層）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `__main__.py` | 130 | `main()`：先設定 logging 與 excepthook，再 import Qt；CLI 參數解析、凍結環境修補、QApplication 建立、主視窗啟動 |
| `Imervue_main_window.py` | 706 | `ImervueMainWindow`：5 分頁協調者（建構、分頁切換、Paint 綁定、記憶體壓力、拖放、關閉）；其餘職責來自 `gui/main_window_*.py` 的九個 mixin |
| `cli.py` | 595 | headless 批次 CLI（resize / watermark / info / convert…），只走純 NumPy+Pillow 路徑；輸入一律經 `shown.open_shown` / `load_shown_rgba`（RAW 經 libraw 顯像、其餘轉 sRGB 並轉正），`info` 經 `dimensions.probe_image`，資料夾收 `RASTER_EXTENSIONS`，沿用副檔名的輸出遇到 RAW 改寫 PNG；讀不到的檔案記為錯誤、其餘照跑 |
| `integration_guide.py` | 145 | 外掛系統初始化：建立 `PluginManager`、dispatch 主分頁 hook、把外掛語言掛進語言選單（按 object name 找選單） |

### 6.2 `Imervue/system/`

作業系統與應用程式層級的基礎設施。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `app_paths.py` | 109 | 凍結環境安全的路徑解析（icon / plugins / 設定檔），PyInstaller & Nuitka 都適用 |
| `clipboard_monitor.py` | 136 | ShareX 式剪貼簿監聽：PrintScreen 截圖 → 自動開啟註解視窗 |
| `error_report.py` | 177 | 一鍵支援包產生器（日誌 + 環境資訊打包） |
| `file_association.py` | 252 | 跨平台檔案關聯「用 Imervue 開啟」註冊 / 取消；副檔名即 `formats.STILL_IMAGE_EXTENSIONS`（排序），MIME 用 freedesktop shared-mime-info 的名稱 |
| `file_tree_watcher.py` | 171 | watchdog 遞迴監看樹根，跨執行緒 signal 回 UI 觸發 model refresh |
| `qimage_convert.py` | 33 | `pil_to_qimage()` / `qimage_to_pil()`：經 RGBA8888 並複製緩衝區的雙向轉換（標註與剪貼簿共用） |
| `log_setup.py` | 83 | 集中式 logging 設定：`setup_logging()`（可重複呼叫；`app_dir()` 不可寫時退到使用者目錄；凍結時不掛 stderr handler）與 `install_exception_logging()` |
| `macos_bundle.py` | 74 | macOS `.app` Info.plist 文件型別關聯；每種相機 RAW 對到 `public.camera-raw-image` |
| `onboarding.py` | 81 | 首次啟動導覽步驟註冊表 |
| `release_notes.py` | 111 | What's-New 對話框的版本說明資料 |
| `theme_color_math.py` | 91 | WCAG 對比度數學，供主題撰寫與無障礙稽核 |
| `themes.py` | 175 | 內建配色主題 |
| `best_effort.py` | 29 | `best_effort(step)`：不中斷呼叫端地執行一段收尾步驟，失敗時以 warning 帶 traceback 記錄（取代無聲的 `suppress(Exception)`） |
| `qt_translations.py` | 60 | `install_qt_translations(app, language)`：依介面語言載入 PySide6 附帶的 `qtbase_<locale>.qm`，讓 Qt 內建字串（確定 / 取消、是 / 否、檔案對話框、分頁關閉提示）跟著翻譯；英文或外掛語言不裝 |
| `qt_timers.py` | 27 | `call_later(ms, owner, fn)`：延遲呼叫，`owner`（QObject）先被銷毀就由 Qt 取消；取代 `QTimer.singleShot(ms, lambda: …)` 與 `singleShot(ms, obj.method)`，兩者在物件刪除後都照樣執行 |
| `file_manager.py` | 59 | `reveal_in_file_manager(path, select=)`：用 OS 的檔案總管開啟路徑（Windows `explorer`，命令列由 `explorer_command` 組成、路徑一律加引號，因為 Explorer 以逗號與 `=` 分隔參數；macOS `open [-R]`、Linux `xdg-open`），檔案總管啟動不了時丟 `OSError`；`reveal_or_warn` 包一層、失敗記警告，給沒有更好處理方式的選單動作用（檔案樹、右鍵選單、清單檢視、外掛選單） |
| `wallpaper.py` | 161 | `set_desktop_wallpaper(path)`：設為桌布（Windows `SystemParametersInfoW`、macOS 以 argv 傳路徑給 `osascript`、GNOME `gsettings` 同時設亮／暗色）；JPEG／PNG／BMP 以外的格式與帶 EXIF 方向的照片先經 `wallpaper_file` 存成檢視器所見的 JPEG 副本（轉正、sRGB、透明處鋪黑，放在 `%LOCALAPPDATA%/Imervue/wallpaper`，檔名隨來源的大小與修改時間變、只留最新一份；做不出副本時交原檔），因為 Windows 拿到解不開的檔案會回報成功卻把桌面變黑；失敗只記錄；右鍵選單在 `QThreadPool` 裡呼叫 |
| `local_origin.py` | 28 | `is_allowed_origin(origin)`：分辨瀏覽器裡的他站網頁與本機用戶端，桌寵 webhook 與 puppet VTS API 共用，擋掉跨站請求 |
| `trash_ops.py` | 327 | **背景批次刪除**：`send2trash` 單次呼叫成本 ~0.27s，因此所有刪除必須走這裡，禁止 per-file 迴圈；刪除後各檔的 sidecar 同路處理（不計進結果）；`recycle_bin_holds`：Windows 上只有固定磁碟才交給 shell（記憶卡、USB 隨身碟、網路磁碟會被直接永久刪除），其餘留在原處算失敗；`purge_batch` 裡這類「送回收筒」的項目改為直接刪除（使用者已確認永久刪除）；`delete_outright(paths)`：確認後直接刪，資料夾連內容一起（`_unlink_chunk` 仍只刪檔案，culling 不會清空資料夾） |
| `file_transfer.py` | 244 | `transfer_into(sources, dest_dir, *, move)`：搬移／複製進資料夾一律走這裡；以 `batch_move_planner` 規劃不重複的檔名（依檔案系統大小寫規則），寫入前再確認目標不存在，絕不覆蓋（Move/Copy 對話框、雙窗格、staging tray 共用）；`carry_along(pairs, *, move)`：檔案搬移／改名／複製後帶走 sidecar（`IMG.xmp`、`IMG.JPG.xmp`、`IMG.JPG.annotations.json`；RAW+JPEG 共用的 `IMG.xmp` 改用複製），搬移時再呼叫 `follow_saved_data`；`carry_sidecars`：只搬 sidecar，worker 執行緒可用；`follow_saved_data(files, folders, *, keep_existing)`：設定（`path_metadata`）與圖庫（`image_index.move_paths`）的每路徑資料改指新路徑，資料夾展開成其下每個檔；`sidecars_of(path)`：只屬於這個檔的 sidecar（刪除時一起帶走）；`is_same_file(a, b)`：兩個路徑是否指同一個檔（Windows 只改大小寫的改名不算衝突） |
| `batch_rename.py` | 157 | `rename_files(pairs)`：一批改名，目標可以是批次內另一個檔目前的名稱（重新編號、互換）：依相依順序改，循環先借同資料夾的暫時名稱，失敗時放回原名；不覆蓋批次外的檔；sidecar 隨每次改名走，存的資料（評分、標籤、備註…）整批一次 `follow_saved_data`（Batch Rename、Token Batch Rename 共用） |
| `atomic_write.py` | 33 | `replace_atomically(path, write)`：寫到 `.tmp` 兄弟檔再 `os.replace`，失敗時原檔完整、暫存檔刪除；所有覆寫使用者既有檔的存檔（EXIF 改寫、旋轉、套用裁切、PSD／puppet／paint 文件、`save_image` 的匯出與轉檔、Paint 匯出預設）都走它；`write_text_atomically(path, text)` 是文字版（XMP／註解 sidecar、素材庫索引、工作階段檔、桌寵腳本、註解專案） |
| `unreadable_guard.py` | 63 | `UnreadableFileGuard`：存檔在啟動時讀不到（JSON 壞掉、被其他程式占用）就 `note_unreadable`；每次存檔前 `clear_to_save`，第一次覆寫前先另存 `<檔名>.unreadable-<日期>-<時間>`，存不了副本就回 False、不覆寫（`user_setting_dict`、`recipe_store` 使用） |
| `free_names.py` | 33 | `free_names(directory, stems, ext)`：資料夾裡還沒被占用的檔名（`photo_clahe.png`，被占用就 `_1`、`_2`…；一組檔案共用一個編號；依檔案系統的大小寫規則比對，列不出內容的資料夾視為空的），寫新檔在使用者檔案旁邊的工具都經由它挑名（`_apply_save.output_path(s)`、Export 與 GIF／影片對話框的預設檔名、多頁拆分、EXIF 清除的副本；右鍵「依 EXIF 自動旋轉」經 `output_path`） |
| `hidden_files.py` | 37 | `is_hidden(entry)`：資料夾列舉要跳過的檔案，名稱以點開頭（macOS 在記憶卡與網路磁碟上寫的 `._photo.jpg`、`.Trashes`、`.Spotlight-V100`）或帶 Windows 隱藏屬性（檔案總管與資料夾樹也不顯示，`$RECYCLE.BIN`）；`DirEntry` 用列舉時已讀到的屬性，路徑則多一次 `stat`；讀不到的檔案不算隱藏 |
| `image_listing.py` | 61 | `list_images(folder, extensions, *, recursive=False, should_stop=None)`：批次工具、CLI 的資料夾參數、圖庫掃描、監看資料夾、樹狀圖示共用的資料夾列舉（依副檔名、自然排序、跳過隱藏檔，遞迴時不進隱藏資料夾，遞迴時每個資料夾前問 `should_stop`，讀不了的資料夾只列出讀到的部分）；Batch Convert、EXIF 清除、影像整理、影像淨化、AI 放大、重複偵測、`cli.iter_image_paths`、`maintenance.scan_image_files`、`watch_folder.scan_images`、`folder_preview_path`、MCP 的 `list_images`／`find_similar`／`collection_stats`／smart album、resource 清單（`tools_read._folder_images`、`resources.list_resources`）都用它 |
| `natural_sort.py` | 29 | `natural_key(name)`：和檔案總管一樣的自然排序鍵（`img2` 在 `img10` 之前，不分大小寫，全形數字也算數字；相等時依小寫、原名定序）；檢視器的名稱排序（縮圖格、上下張、資料夾快取）、`sort_menu`、網頁相簿與各批次對話框的清單都用它，和檔案樹的 numeric `QCollator` 一致 |
| `pillow_setup.py` | 25 | `configure_pillow()`：GUI（`__main__.main`）、直接執行的 CLI、MCP server 啟動時套用的 Pillow 設定：`raise_pixel_limit()` 加上 `ImageFile.LOAD_TRUNCATED_IMAGES`，中途截斷的 JPEG／PNG／TIFF／GIF／BMP（下載或複製中斷、從故障記憶卡救回）像瀏覽器一樣讀到截斷處，不再整張打不開；整個行程生效，測試不經過這裡，所以測試裡仍是 Pillow 預設 |
| `pixel_limit.py` | 87 | `raise_pixel_limit()`：把 Pillow 的 `MAX_IMAGE_PIXELS` 依實體記憶體放寬（`total_memory_bytes()`；拒絕點落在解碼需要全部記憶體處，16 GB 約 13 億像素，不低於 Pillow 預設），由 `pillow_setup.configure_pillow()` 呼叫；`decode_slot(pixels)`：超過 Pillow 預設的巨圖一次只解一張（`image_loader` 的點陣解碼與縮圖使用），避免縮圖 worker 同時解多張全景圖耗盡記憶體 |
| `ui_scale.py` | 61 | 應用程式全域 UI 縮放係數（必須在任何 widget 佈局前套用） |
| `watch_folder.py` | 138 | 監控資料夾自動化：新檔案進來自動套用動作；預設收檢視器能開的每種靜態格式（連線拍攝的 RAW 也算）；經 `list_images` 列舉，Mac 複製進來的 `._` 檔不觸發動作 |

### 6.3 `Imervue/user_settings/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `user_setting_dict.py` | 363 | **全域設定字典**。多帳號（profile）容器、v1→v2 自動遷移、去抖非同步存檔、atomic JSON writer（`.tmp` + `os.replace`）；啟動時讀不到的設定檔交給 `UnreadableFileGuard` 看守（所有寫設定檔的路徑都走 `_save_settings`）；`unreadable_settings_file()` 給啟動時的警告用 |
| `bookmark.py` | 90 | 跨資料夾書籤 / 收藏集合 |
| `code_replacements.py` | 69 | 片語展開（caption、keyword 用的縮寫） |
| `color_labels.py` | 120 | 每圖色標籤（紅/黃/綠/藍/紫），與五星評分獨立 |
| `metadata_template.py` | 72 | IPTC/XMP 欄位範本（stationery pad） |
| `path_metadata.py` | 137 | 設定裡以圖片路徑為鍵的資料（評分、色標籤、標題、描述、收藏、書籤、staging tray、參考圖釘選、最近圖片、標籤與相簿成員）跟著改名／搬移的檔案走：`move_path_metadata(mapping, *, keep_existing)` 同時改鍵（`a→b` 與 `b→c` 並存也只搬一次），新路徑上前一個檔案留下的資料清掉；`folder_moves` 把資料夾搬移展開成其下每個路徑；`stored_paths` |
| `recent_image.py` | 65 | 最近資料夾 / 圖片追蹤，上限由設定控制 |
| `tag_validator.py` | 106 | 標籤 / 相簿集合的完整性檢查與清理 |
| `tags.py` | 133 | 自訂標籤與虛擬相簿管理 |

### 6.4 `Imervue/multi_language/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `language_wrapper.py` | 86 | 單例 `language_wrapper`。內建 5 語言；`register_language()` 供外掛新增語言，`merge_translations()` 供外掛補鍵（不覆寫既有鍵） |
| `english.py` | 2,805 | 英文字典（**正規來源**，其他語言以它為鍵集基準） |
| `traditional_chinese.py` | 2,770 | 繁體中文 |
| `chinese.py` | 2,771 | 簡體中文 |
| `japanese.py` | 2,784 | 日文 |
| `korean.py` | 2,782 | 韓文 |
| `translation_validation.py` | 156 | 字典進入 `LanguageWrapper` 前的驗證（缺鍵 / 型別） |

> 第 6 個語言（西班牙文）以 `plugins/spanish_translation/` 形式提供，示範外掛語言註冊流程。

### 6.5 `Imervue/sessions/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `session_manager.py` | 249 | Session / Workspace 存檔與還原（開啟的資料夾、圖片、視圖狀態） |
| `session_migration.py` | 133 | `.imervue-session.json` 的驗證、版本遷移與合併 |
| `folder_session.py` | 38 | 每資料夾視圖 session 的純函式助手 |

### 6.6 `Imervue/macros/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `macro_manager.py` | 299 | 巨集錄製 / 重播：把一批動作套用到選取集 |
| `macro_step_validator.py` | 111 | 錄下來的巨集步驟驗證與整理 |

### 6.7 `Imervue/external/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `editors.py` | 103 | 外部編輯器啟動器。設定存在 `user_setting_dict["external_editors"]`，以非阻塞 `subprocess.Popen` 啟動 |

### 6.8 `Imervue/export/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `contact_sheet.py` | 189 | 索引表 PDF 產生器，用 `QPdfWriter`+`QPainter`（不需 reportlab）；格子影像經 `decode_image` |
| `contact_sheet_layouts.py` | 55 | 具名版面預設（紙張 / 格線 / 邊界 / 說明文字） |
| `web_gallery.py` | 262 | 靜態 HTML 相簿產生器，輸出自足資料夾（無外部 JS/CSS 相依）；縮圖經 `decode_image`（轉正、sRGB、RAW 可讀） |
| `gallery_sort.py` | 76 | 匯出前的排序 / 過濾 / 分組（依名稱、時間、大小、副檔名、資料夾、拍攝日） |
| `slideshow_mp4.py` | 140 | 幻燈片 MP4 產生器（imageio + ffmpeg） |
| `slideshow_effects.py` | 101 | 純 NumPy 轉場效果（fade、dissolve、wipe…），逐幀決定性 |
| `cheat_sheet.py` | 237 | 可列印的快捷鍵速查表 PDF，隨當前語言產生 |
| `pdf_output.py` | 21 | `begin_pdf_painter`：在 `QPdfWriter` 上開啟 `QPainter`，目標無法寫入時丟 `OSError`（`QPdfWriter` 本身不丟例外，只讓 `begin` 回傳 `False`） |

### 6.9 `Imervue/image/`（純運算核心）

128 個模組、15,355 行，**只有 `info.py` import Qt**（用 `QMessageBox` 顯示圖片資訊對話框），其餘都可在 worker
執行緒直接呼叫，也是 `cli.py`、`mcp_server/`、`plugins/` 共用的演算法庫。

#### 非破壞性顯影核心（最重要的三個檔）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `recipe.py` | 664 | **`Recipe` dataclass**：一張圖的完整非破壞性編輯描述。`apply()` 是固定順序的管線：幾何(旋轉/翻轉/裁切) → 曝光 → 亮度對比 → vibrance → 飽和度，再依 `extra` 套用 split toning / levels / channel mixer / gradient map / threshold+posterize / lens flare / film grain / layer stack / masks / LUT。另提供 `to_dict`/`from_dict` 往返、`recipe_hash`、`is_identity`、`exif_oriented` / `base_is_oriented()`（舊存檔缺這個鍵、又帶幾何時，仍套在未轉正的像素上），以及 `file_identity()`（md5(前、中、後各 4KB \| 檔案大小)，避免 mtime 改變就失效；只看前 4KB 時，同尺寸的未壓縮掃描檔會共用一個 identity）與 `file_identities()`（連同舊版只含前 4KB 的 identity，供遷移）；`turned_with_file(recipe, clockwise, size)`：檔案轉 90° 後的 recipe（翻轉互換、裁切框隨之旋轉；帶位置的 extra 不轉） |
| `recipe_store.py` | 477 | 單一 JSON 檔支撐的記憶體 recipe 索引。以路徑為主的 API（`get_for_path`/`set_for_path`），並支援 **virtual copies**（同一張圖的具名 recipe 變體）；`rekey(old, new, transform)` 把 recipe 與虛擬副本搬到新 identity（不能全部轉換就不動），`identity_for(path)` 查詢前先把存在舊版 identity 下的 recipe 搬到新 identity（每個檔案只搬一次）；`carry_recipe(path, change, transform)` 在改寫檔案（EXIF、無損旋轉）後讓 recipe 跟著檔案；讀不到的 store 檔由 `UnreadableFileGuard` 看守，解不開的單筆原樣寫回 |
| `recipe_adjustments.py` | 124 | `Recipe.apply` 用到的逐通道色調調整 |
| `recipe_diff.py` | 63 | 兩個 recipe 的 diff 與選擇性合併 |
| `develop_presets.py` | 102 | 具名顯影預設與批次 recipe 同步 |

#### 色調 / 顏色

`curves.py`(245) 曲線 · `tone_curve.py`(152) flag-based 曲線 · `levels.py`(95) 黑白場+gamma ·
`channel_mixer.py`(129) 3×3 矩陣 · `hsl_mixer.py`(109) 分頻 HSL · `split_toning.py`(67) ·
`gradient_map.py`(169) · `gradient_perceptual.py`(144) OkLab/OkLCH 感知混色 ·
`colormap.py`(63) 科學色階 · `lut.py`(258) Adobe `.cube` 讀取與套用（含 Resolve 的 `LUT_*_INPUT_RANGE`、BOM）·
`auto_color_balance.py`(190) 四種自動白平衡 · `posterize.py`(130) · `solarize.py`(51) ·
`velvia.py`(65) 亮度加權飽和 · `film_negative.py`(67) 負片轉正 · `filmic_tonemap.py`(94) ·
`tone_equalizer.py`(80) 分區曝光 · `soft_proof.py`(65) ICC 軟打樣 + 色域外標示

#### 局部對比 / 細節 / 銳利化 / 降噪

`local_contrast.py`(100) clarity+texture · `clahe.py`(106) · `detail_equalizer.py`(75) 分尺度對比 ·
`denoise.py`(83) · `dehaze.py`(84) 暗通道先驗 · `defringe.py`(85) 邊緣色散 ·
`frequency_separation.py`(124) 高低頻分離 · `focus_peaking.py`(63) · `sharpness.py`(53) ·
`flatten_field.py`(97) 去漸層（光害/暗角）

#### 幾何 / 變形

`geometry.py`(150) 裁切+校正+透視 · `crop_geometry.py`(75) 純裁切幾何+三分線 ·
`auto_straighten.py`(92) Hough 水平線偵測 · `lens_correction.py`(150) 畸變/暗角/色差 ·
`distort.py`(65) swirl/pinch/ripple · `polar.py`(68) 極座標 · `kaleidoscope.py`(66) ·
`equirectangular.py`(77) 360° tiny planet · `resample.py`(43) 共用反向映射重採樣 ·
`orientation.py`(123) EXIF orientation：`QUARTER_TURN_CODES`、`exif_orientation`、`transpose_for`（轉完會清掉結果上的 EXIF / XMP 轉向標籤，避免再轉一次）與 `strip_xmp_orientation`

#### 藝術效果 / 疊加

`film_grain.py`(146) · `lens_flare.py`(165) · `glow.py`(70) Orton bloom · `emboss.py`(85) ·
`frosted_glass.py`(49) · `dither.py`(56) Bayer · `pixel_sort.py`(58) · `graduated_density.py`(103) ND 漸層 ·
`false_color.py`(56) 曝光分區上色 · `meme.py`(100) · `photo_frame.py`(67) 相框/拍立得/說明文字 ·
`watermark.py`(137) · `scale_bar.py`(71) 比例尺 · `test_charts.py`(75) 校正圖表產生

#### 多影像合成

`hdr_merge.py`(117) · `panorama.py`(84)（包 OpenCV `Stitcher`） · `focus_stack.py`(122) ·
`stack_blend.py`(120) 統計堆疊 · `collage.py`(64) · `anaglyph.py`(79) 紅藍 3D ·
`deflicker.py`(108) 縮時去閃 · `id_photo_sheet.py`(72) 證件照拼版 · `print_layout.py`(118) 列印拼版 PDF（reportlab；影像經 `decode_image`） ·
`multipage.py`(116) 多頁 PDF/TIFF 合併與拆分（`page_count`：頁數是影格數，但 PSD 的影格是同一張圖的圖層、相機 JPEG 的 MPF 預覽（Pillow 開成 MPO）不是一頁，都算 1 頁，只有 MPF 標成立體／多角度／全景的才有多頁；`in_place_save.frame_count` 也照這個算，右鍵「拆分頁面」也用它；合併時每頁經檢視器的 `decode_image` 轉正、轉 sRGB，以 `replace_atomically` 寫入；拆出的頁面經 `free_names` 一組挑名，不蓋掉上次拆出的頁面）

#### 遮罩 / 修補 / 圖層

`masks.py`(296) 筆刷/放射/線性遮罩 · `layers.py`(258) 疊加圖層合成 · `healing.py`(103) OpenCV inpaint ·
`clone_stamp.py`(137) · `inpaint.py`(54) 無模型擴散修補 · `segmentation.py`(130) 天空/前景/背景遮罩 ·
`saliency.py`(170) 啟發式顯著性 + 三分法裁切建議

#### 二值化 / 文件

`binarize.py`(49) Sauvola · `otsu.py`(59) · `steganography.py`(75) LSB 隱寫 ·
`ela.py`(53) 錯誤層級分析 · `copy_move.py`(84) 複製貼上偽造偵測

#### I/O、格式與快取

`raw_loader.py`(218) 省記憶體 RAW 載入；`raw_dimensions()` 只讀標頭取成像尺寸；`develop_raw(path, *, thumbnail)` 顯像成 8-bit RGB（嵌入預覽經 `upright_preview` 依 libraw `flip` 轉正，沒有可用預覽就半尺寸顯像；縮圖 worker 也用它），`LibRawError` 轉 `OSError`，不依賴 Qt（MCP 伺服器也用） · `in_place_save.py`(285) `can_rewrite_in_place(path)` / `in_place_format(path)` / `frame_count(path)`：能否把編輯後的像素寫回原檔（RAW、HEIC、JXL、SVG、多影格一律否）；旋轉、Modify 套用裁切、註解儲存都先問它；`carried_save_kwargs(source, fmt, path)` 把原檔的描述性 EXIF（`descriptive_exif`，白名單、不帶轉向與 TIFF 版面標籤）/ ICC / DPI / XMP / PNG 文字 / 壓縮設定（`webp_is_lossless`）轉成重存參數；`save_over_source(path, edited)` 把編輯後（已轉正、sRGB）的影像原子寫回原檔並帶回這些 metadata（不帶 ICC 與轉向），Modify 套用裁切／儲存註解、註解編輯器的 Save 與 AI 放大的覆寫都走它；`save_edited_copy(source, edited, target)` 寫新檔時也帶回來源的描述性 EXIF 與 DPI（同格式則全套）；`descriptive_exif(..., keep_location=False)` 另外去掉 GPS IFD 與 XMP，`keep_maker_note=False`（匯出與換格式的副本）去掉 MakerNote；`can_rewrite_exif` / `rewrite_exif(path, update)`：只換 EXIF 區塊（JPEG 走 `jpeg_exif`、WebP 走 `webp_exif`）並原子寫回，GPS 地理標記與 EXIF 編輯器共用 · `export_metadata.py`(84) 匯出的 metadata 政策：`export_save_options(source, policy)` 依「全部／位置以外（預設）／無」回傳 `{"exif": bytes}`，不帶轉向與像素尺寸 · `jpeg_orientation.py`(65) `set_jpeg_orientation(data, code)`：只改 JPEG 的 EXIF 轉向值（有標籤就原地改 2 bytes，沒有才重組 EXIF 或新增 APP1 段），像素與其他 metadata 不動 · `webp_exif.py`(105) `update_webp_exif(data, update)`：換掉 WebP 的 `EXIF` chunk（簡單格式先升級成帶 `VP8X` 的延伸格式、畫布與 alpha 旗標取自位元串流），影像資料位元組不變 · `jpeg_exif.py`(169) 只靠 Pillow 改 JPEG 的 EXIF：`header_segments` / `exif_segment` / `replace_exif_segment` 換掉 APP1 段、`serialize_exif(exif, original)` 補回 `Image.Exif.tobytes` 會丟的 IFD1 縮圖、`update_jpeg_exif(data, update)` 一次做完（像素位元組不變） · `exif_types.py`(121) `restore_types(payload, original)`：把 Pillow `Exif.tobytes` 猜錯的項目型別（UNDEFINED 被寫成 BYTE、非負 SRATIONAL 被寫成 RATIONAL）依 EXIF 規格表或原檔改回，只換同元素大小的型別，值與位移不動；`jpeg_exif`、`export_metadata`、`in_place_save` 序列化 EXIF 都經過它 · `exif_fields.py`(153) EXIF 編輯器的純邏輯：`EDITABLE_FIELDS`、`read_fields` / `apply_fields`（UTF-8 文字標籤、依區塊位元組序的 UNICODE UserComment，空白即移除）、`can_edit`（JPEG、WebP）、`save_fields`（經 `in_place_save.rewrite_exif` 原子寫回） · `dimensions.py`(47) `image_dimensions(path)`：讀檔頭取像素尺寸的共用入口（RAW 走 libraw，Pillow 會回報內嵌預覽的尺寸）；`probe_image(path)` 另回報格式與模式（RAW 為副檔名與 `RGB`），CLI `info` 用它 · `heif_support.py`(60) HEIC / HEIF 經選用的 pillow-heif（1.x 起不處理 AVIF）· `avif_support.py`(18) AVIF 由 Pillow 內建外掛讀寫，`avif_available()` 回報這個 Pillow 有沒有 libavif · `jxl_support.py`(50) ·
`formats.py`(86) 能開的副檔名唯一來源：`JPEG_EXTENSIONS`（`.jpg`／`.jpeg`／`.jpe`／`.jfif`／`.jif`，類型篩選、影像整理、各批次工具與 Paint 的 JPEG 判斷都用它）、`PILLOW_EXTRA_EXTENSIONS`（ICO、TGA、DDS、QOI、JPEG 2000、Netpbm、PCX、PSD 的合併圖：Pillow 自己讀得了，只供檢視，原地存檔不認得它們）、`RAW_EXTENSIONS`（LibRaw 讀得了的 23 種相機 RAW；RAW+JPEG 堆疊也用它）、`STILL_IMAGE_EXTENSIONS`（媒體庫）、`VIEWER_EXTENSIONS`（再加影片；檢視器、檔案樹、拖放、開啟對話框）、`RASTER_EXTENSIONS`（去掉要 Qt 的 SVG；CLI 與 MCP）、`ensure_pillow_opener(ext)` ·
`save_formats.py`(106) 輸出格式中繼資料與 `save_image`（寫到路徑一律原子替換）；HEIC、JXL 依選用套件，AVIF 依 Pillow 有無 libavif 決定是否提供· `optimize.py`(73) 目標檔案大小編碼 ·
`export_presets.py`(94) 匯出預設包 · `video_frames.py`(231) 影片解碼原語（瀏覽器與外掛共用） ·
`pyramid.py`(38) `DeepZoomImage` 金字塔 · `tile_manager.py`(94) 圖磚 LRU 快取與淘汰 ·
`thumbnail_disk_cache.py`(242) 縮圖磁碟快取（鍵含 `_KEY_VERSION`，快取像素的意義改變時遞增；相機 RAW 另用 `_RAW_KEY_VERSION`，只讓 RAW 的項目失效） · `folder_index.py`(64) 每資料夾圖片清單快取（只用於依解析度排序：其他排序直接以 `scandir` 掃描，比逐檔確認快取的路徑還在快得多） ·
`read_errors.py`(15) `IMAGE_READ_ERRORS`：Pillow 讀圖失敗會丟的例外（`OSError`、`ValueError`、`SyntaxError`（損壞的 WebP EXIF）、`DecompressionBombError`）

#### 中繼資料

`xmp_sidecar.py`(598) XMP sidecar 讀寫（跨編輯器互通）；`load` 沒有 sidecar 時讀檔案內嵌的 XMP 封包（JPEG／PNG／WebP／TIFF）再以 EXIF `Rating`／`RatingPercent` 補評分（`load_embedded`，經 `metadata_sync.percent_to_rating`）；找 `foo.xmp`（Adobe），只有 `foo.jpg.xmp`（darktable／digiKam）時讀寫它；`label_color` 把 Lightroom（`Red`）與 Bridge（`Select`）的標籤對到 Imervue 顏色，匯出照 Lightroom 寫法並保留同色的既有用字；`xmp:Rating` -1（Lightroom／Bridge／darktable 的拒絕）與圖庫的挑片 reject 雙向對應；`save` 合併進既有檔：只換評分／標籤／標題／描述／關鍵字／作者，其他編輯器寫的內容（RAW 顯影設定等）與命名空間前綴保留，無法解析的檔丟 `UnreadableSidecarError`（`OSError`）不覆寫 · `metadata_sync.py`(76) XMP↔EXIF 評分調和 ·
`raw_exif.py`(278) Pillow 打不開的 RAW 容器的 EXIF：CR3 的 `CMT1`／`CMT2`／`CMT4` 盒、RW2／RWL／ORF（換掉魔術數字後由 Pillow seek 讀取，RW2 去掉 Panasonic 私有標籤但保留 ISO）、RAF 內嵌 JPEG 的 APP1；只 seek 到中繼資料 · `gps.py`(84) EXIF GPS 擷取 · `gps_geotag.py`(84) 寫入（JPEG / WebP 經 `in_place_save.rewrite_exif`，不需 piexif） · `reverse_geocode.py`(151) 離線逆地理編碼 ·
`geo_keywords.py`(52) 地點寫進 XMP 關鍵字 · `face_detection.py`(148) 人臉偵測與人物標籤（Haar，需 OpenCV 4；缺時丟 `FaceDetectorUnavailableError`；cascade XML 由 Python 讀入後從記憶體載入，OpenCV 裝在非 ASCII 路徑下也能用） ·
`annotations.py`(269) JSON sidecar 註解 · `shown.py`(76) `as_shown(img, code=None)`：檢視器看到的樣子（先依內嵌描述檔轉 sRGB、再依 EXIF 轉正）；`open_shown(path)` 不靠 Qt 解整個檔案（相機 RAW 經 `develop_raw` 顯像，其餘先註冊 HEIC / JXL opener），`load_shown_rgb(path)` / `load_shown_rgba(path)` 建在它上面（16 位元與浮點灰階先縮放）；`as_shown_8bit(img, code=None, mode="RGBA")` 是送到螢幕的 8 位元版本，16 位元與浮點灰階先經 `to_eight_bit` 縮放、不讓 `convert` 截斷成全白（清單檢視、懸停預覽、比較、拖出、重複偵測、影像檢查、時間軸、圖層疊加、參考圖、CLIP 用它），`as_shown` 本身保留位元深度（EXIF 清除的副本仍是 16 位元）；預覽、工具輸入、匯出、Modify、註解、合成、OCR、CLIP、MCP、Paint 的姿勢圖／素材／參考圖都走它 · `high_bit_depth.py`(67) `to_eight_bit(img)`：16 位元灰階（`I;16` 各位元組序）依 0..65535 縮成 8 位元，32 位元整數在 16 位元內時同樣縮放、否則最小到最大拉伸，浮點在 0..1 內對應黑到白、否則拉伸，NaN 與無限大顯示黑色；其他模式原樣傳回（Pillow 的 `convert` 對這些模式是截斷，16 位元灰階掃描幾乎全白） · `color_profile.py`(86) `to_srgb(img)`：內嵌 ICC（Display P3、Adobe RGB、CMYK）轉 sRGB；灰階（`L`／`LA`）的灰階描述檔（Dot Gain 20%、Gray Gamma 1.8）先算成 256 階曲線（`_grey_curve`）再套到灰階值，結果仍是灰階；無描述檔、sRGB 或描述檔與模式不符時原樣回傳，transform 與曲線依描述檔快取 · `exif_merge.py`(86) `read_exif(path)`（任何格式的 EXIF，子 IFD 在檔案開著時讀好，RAW 容器經 `raw_exif`；GPS、拍攝時間、Token 重新命名、中繼資料匯出都用它）、`merged_exif(img 或 Exif)`、`get_exif_data(path)`（以標籤名稱回傳、HEIC／JXL 先註冊 opener；不依賴 Qt，MCP、圖庫、面板共用）：IFD0 + Exif 子 IFD、GPS 巢狀，與 Pillow 的 `_getexif()` 同形狀但每種格式都有 · `info.py`(171) 圖片資訊組裝與對話框；EXIF 由 `exif_merge.get_exif_data` 讀，HEIC / JXL 也讀得到

#### 分析 / 品質

`histogram.py`(103) · `statistics.py`(65) 逐通道統計 + CSV · `scopes.py`(66) 波形/RGB parade ·
`quality_metrics.py`(88) 無參考品質 · `quality_score.py`(62) 篩選用技術評分 ·
`perceptual_hash.py`(157) pHash 與近似重複分組（`upright`：先依 EXIF 轉正再雜湊，未帶標籤者雜湊值不變；`grey_levels`：16 位元與浮點灰階先經 `to_eight_bit` 縮放再轉 8 位元灰階，dHash、aHash 與圖庫的 pHash 共用）

#### 其他

`browser_state.py`(400) 共用瀏覽狀態（過濾規格、中繼資料索引、遺失檔案偵測與重定位）·
`batch_move_planner.py`(114) 無碰撞批次搬移規劃 · `animation_edit.py`(95) GIF/APNG 反轉/回力鏢/速度 ·
`caption.py`(91) 本地視覺 LLM 產生 alt-text · `ocr.py`(159) Tesseract · `portrait_retouch.py`(177) ·
`speech_*`／`text_*` 相關在 `paint/`

### 6.10 `Imervue/gpu_image_view/`

OpenGL 檢視器。`GPUImageView(QOpenGLWidget)`（1,758 行）只保留 GL 生命週期與 Qt 事件覆寫，
其餘拆成約 40 個協作者。有兩種顯示狀態：**tile wall**（縮圖牆）與 **deep zoom**（單張深縮放）。

#### 檢視器主體與渲染

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `gpu_image_view.py` | 767 | 主 widget：GL 初始化、`paintGL`、tile grid、鍵盤與拖放事件；deep-zoom 載入、視圖適配、預取／記憶體、滑鼠來自下面四個 mixin；`run_shortcut_action(action)` 讓別的元件以按鍵的方式執行快捷鍵動作 |
| `view_state_init.py` | 278 | 建構子呼叫的狀態初始化函式（tile grid、deep zoom、瀏覽、互動、顯示），只設定屬性、不碰 GL |
| `deep_zoom_loading.py` | 299 | `DeepZoomLoadingMixin`：開一張圖的狀態機（預覽解碼→完整解碼、套 recipe、過期結果丟棄、失敗重試一次、首幀通知） |
| `shown_file_watch.py` | 87 | `ShownFileWatch`：deep zoom 顯示中那張圖的檔案監看；`load_deep_zoom_image` 每次載入時 `follow` 並記下大小與修改時間，之後每 `POLL_MS`（500 ms）用 `os.stat` 量一次，變了之後又連續一次沒變（寫完了）才經 `_reload_rewritten_image` 重新載入並重解縮圖；外部編輯器就地覆寫、寫副本再改名蓋過去、保留原修改時間的存檔都看得到。刻意不用 `QFileSystemWatcher` 監看檔案：在 Windows 上它讓其他程式改名蓋過去的存檔約一成被拒絕存取（實測 600 次 54 次），資料夾監看與 `os.stat` 都不會 |
| `view_fitting.py` | 304 | `ViewFittingMixin`：fit window/width/height、新圖初始視圖、版面／換螢幕／載入後的 settle 重算（`settle_poll`） |
| `prefetch_memory.py` | 123 | `PrefetchMemoryMixin`：相鄰圖預取與 RSS 超限時釋放快取與材質 |
| `view_mouse.py` | 148 | `ViewMouseMixin`：滾輪縮放（含放大鏡倍率、格線與閱讀模式捲動）、按壓／拖曳／放開、雙擊切換 |
| `gl_renderer.py` | 349 | 現代 OpenGL 渲染器（VBO + GLSL），shader 編譯失敗時退回 immediate mode |
| `tile_grid_renderer.py` | 279 | 縮圖牆 GL 繪製 |
| `deep_zoom_renderer.py` | 277 | Deep-zoom 圖磚 + minimap GL 繪製 |
| `overlay_painter.py` | 885 | 所有 `QPainter` 疊層：OSD、HUD、直方圖、filmstrip、letterbox（文字與幾何在 `osd_text.py`、`hud_geometry.py`，圖磚徽章在 `tile_badges.py`） |
| `tile_badges.py` | 93 | 圖磚徽章繪製：色彩標籤條、收藏、書籤、星等、堆疊數、日期、影片播放圓鈕（純 `QPainter`，不需 GL） |
| `texture_upload.py` | 162 | 統一 RGBA 材質上傳（含 RGB→RGBA padding） |
| `pbo_uploader.py` | 243 | Pixel-Buffer-Object 串流上傳，避免 GUI 執行緒卡在驅動 staging copy |
| `gl_context.py` | 54 | 判斷在 `paintGL` 之外釋放材質時是否需要先 make-current |

#### 視圖數學（純函式，可無 GL 測試）

`viewport_math.py`(51) 螢幕↔影像座標 · `view_nav.py`(133) · `fit_view.py`(234) fit window/width/height ·
`view_state.py`(116) 每圖縮放記憶 + 隨機跳圖 · `view_animator.py`(206) 緩動（淡入、縮放、慣性平移）·
`minimap.py`(108) · `tile_layout.py`(115) 格線佈局 · `tile_focus.py`(113) 鍵盤焦點游標 ·
`filmstrip.py`(105) 底部縮圖帶佈局 · `video_badge.py`(57) ▶ 播放徽章幾何 ·
`osd_text.py`(118) OSD／Debug HUD 的文字（檔案大小、EXIF 行）· `hud_geometry.py`(71) hover HUD 與放大鏡的擺放與取樣範圍 ·
`screen_fit`(在 `gui/`) 與 `settle_poll`(在 `gui/`) 配合處理跨螢幕重排

#### 輸入與動作路由

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `input_controller.py` | 429 | 滑鼠 / 滾輪 / 手勢：滾輪縮放、minimap 點擊導航、圖磚框選、中鍵平移 |
| `key_input_handler.py` | 289 | 鍵盤事件路由（F8 HUD、F1-F5 色標籤、Esc、方向鍵） |
| `key_action_dispatcher.py` | 356 | 把 shortcut_manager 解析出的**動作名稱**表格化派送到檢視器操作 |
| `browse_features.py` | 195 | Deep-zoom 瀏覽行為：filmstrip 導航、閱讀模式捲動、平移夾限 |
| `history_controller.py` | 119 | Alt+←/→ 瀏覽歷史堆疊 |
| `drop_handler.py` | 75 | 拖放檔案/資料夾開啟 |
| `clipboard_paste.py` | 109 | 剪貼簿貼上圖片並插入模型 |
| `hover_preview_binding.py` | 55 | 縮圖懸停預覽彈窗綁定 |
| `cull_actions.py` | 119 | 色標籤與 pick/reject 挑片狀態套用；`resolve_cull_targets` 決定按鍵作用的照片：多選的格子 → deep zoom 的圖 → 方向鍵焦點（焦點框顯示時）→ 滑鼠下的格子，評分與我的最愛也用它；`apply_color_label`／`apply_cull_state` 可用 `targets=` 指定照片（清單檢視的選取列） |
| `status_info.py` | 76 | 狀態列欄位組裝 |

#### 資源管理與效能

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `tile_loader.py` | 603 | 縮圖牆非同步載入：距離感知優先權、grid mutex 下收集結果、進度合併；每 4 秒的背景 stat 掃描（`scan_folder_paths`）標出消失的檔案，也找出縮圖解碼後被其他程式改寫（大小或修改時間變了）的檔案，重解它的縮圖（`refresh_rewritten_tile`：新縮圖到之前照畫舊的，到了換掉舊材質；filmstrip 與預取也丟掉）；改寫、消失、復原的路徑整批交給 `refetch_list_rows`，清單檢視的列一起更新 |
| `tile_textures.py` | 138 | 圖磚 GPU 材質配置與 VRAM 預算淘汰 |
| `tile_wall_loading.py` | 99 | 牆面 loading 狀態與轉圈幾何（大資料夾/網路磁碟不再空白） |
| `prefetch_scheduler.py` | 176 | Deep-zoom 鄰居預載排程、取消過期 worker、淘汰快取 |
| `deep_zoom_priority.py` | 40 | 圖磚渲染優先權 |
| `vram_budget.py` | 67 | 純函式：使用者覆寫值 + 夾限策略 |
| `vram_detect.py` | 104 | 廠商 GL 探測實際 VRAM（`glGetIntegerv`） |
| `memory_pressure.py` | 246 | 狀態列記憶體壓力指示器（綠/黃/紅 + 百分比，點擊清快取） |
| `worker_pools.py` | 110 | 執行緒池分池策略：縮圖爆量不再和 deep-zoom worker 搶資源 |
| `signal_coalescer.py` | 92 | 次幀 signal 合併，避免 N 個縮圖回呼各觸發一次進度更新 |
| `cvd_view_mode.py` | 98 | 色覺障礙模擬（view-time 模組級開關，載入時套用） |

#### `gpu_image_view/images/` — 載入層

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `image_loader.py` | 527 | **核心載入路徑**：`decode_image_file()`（解碼成檢視器看到的 RGBA，不套 recipe 與檢視模擬；Modify 與 Paint 用它當底圖）、`decode_image(path, *, max_edge=None)`（同一份解碼成 Pillow 影像，全不透明轉 RGB，可縮到長邊；輸出與預覽共用）、`load_image_file()`（RAW/SVG/HEIF/JXL/一般點陣 → RGBA，可套 recipe）、`LoadDeepZoomWorker`（背景建金字塔）、`FolderScanWorker`（分批掃描大資料夾；兩種掃描都經 `_is_listed` 跳過隱藏檔，直接開啟的隱藏檔仍加進清單；依解析度或拍攝日期這類要逐檔讀標頭的排序（`_HEADER_SORTS`）走 `folder_index` 快取）、`open_path()` 對外入口；點陣圖（大圖與縮圖）先經 `to_eight_bit` 把 16 位元與浮點灰階縮成 8 位元、再轉 sRGB，並依 EXIF Orientation 轉正（舊 recipe 帶幾何時例外，見 `Recipe.base_is_oriented`）；能開的副檔名取自 `image/formats.py` |
| `load_thumbnail_worker.py` | 149 | 單張縮圖解碼 `QRunnable`（點陣圖交給 `image_loader._load_raster_thumbnail`／`_load_raster`，和檢視器同一條解碼：EXIF 轉正、sRGB、16 位元灰階縮放、巨圖一次一張的 `decode_slot`；RAW 取 `raw_loader.develop_raw(thumbnail=True)` 的轉正預覽） |
| `image_model.py` | 24 | `ImageModel`：目前資料夾的圖片路徑清單 |
| `prefetch.py` | 178 | 預載視窗大小與方向追蹤（`NavigationDirectionTracker`） |

#### `gpu_image_view/actions/` — 檢視器動作

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `delete.py` | 227 | **軟刪除 / 復原**：先隱藏不落地，`commit_pending_deletions()` 在關閉時一次送 `trash_ops`，回傳留在原處的檔案 |
| `select.py` | 239 | 上下張切換（含 wrap-around toast）、跳到上/下一個有圖的兄弟資料夾（和資料夾樹同一個順序：自然排序、略過隱藏資料夾）、框選圖磚；`selected_in_view_order` / `selection_or_all` 依瀏覽順序回傳選取（`selected_tiles` 是 set） |
| `batch_ops.py` | 289 | 批次重新命名（經 `batch_rename.rename_files`）/ 移動 / 複製（經 `file_transfer.transfer_into`，不覆蓋）/ 旋轉（逐檔走 `lossless_rotate`） |
| `compare_dialog.py` | 584 | 圖片比對：並排(2/4)、疊加(alpha)、差異(gain-boost) |
| `slideshow.py` | 211 | 幻燈片播放控制器 + 對話框 |
| `animation_player.py` | 341 | GIF / APNG / Animated WebP 播放器；只有 `_ANIMATED_FORMATS`（GIF、PNG、WebP、AVIF、JXL）會播放，多頁 TIFF（`_PAGED_FORMATS`）是 `paged`：不播放、用逐格鍵翻頁、OSD 顯示「第 2/5 頁」（`anim_indicator_text`），其他 Pillow 回報多格的檔案（相機 JPEG 的 MPF 預覽被開成 MPO、PSD 的圖層）不當動畫；APNG 的預設影像（Pillow 的第 0 格、`default_image`）不播放，逐格與串流都從第 1 格起算（`_first`），載入後先把第一格放上畫面；每格和靜態圖一樣經 `to_eight_bit` 與 `to_srgb`；解碼後超過 `_DECODED_FRAMES_BUDGET`（512 MB）就改為串流：留住檔案位元組（BytesIO，不鎖檔），播到哪格才解哪格，只快取最後一格 |
| `search_dialog.py` | 280 | 檔名即時搜尋 |
| `goto_dialog.py` | 102 | Ctrl+G 跳至第 N 張 |
| `keyboard_actions.py` | 323 | 鍵盤快捷動作實作（Ctrl+C 複製檢視器顯示的金字塔底層，沒有時才解碼檔案；評分 `rate_current_image` 與我的最愛 `toggle_favorite` 作用在 `resolve_cull_targets` 的照片上，全都已是那個狀態時清除；兩者都可用 `targets=` 指定照片） |
| `lossless_rotate.py` | 115 | 90° 旋轉檔案：JPEG 只改 EXIF 轉向標籤（`jpeg_orientation`，不需 piexif、其餘位元組不變）；其他格式從檢視器看到的影像轉後原子重存，以 `in_place_save.carried_save_kwargs` 帶回 metadata 與壓縮設定；RAW、多影格等無法完整寫回的檔案拒絕處理；經 `recipe_store.carry_recipe` 讓 Modify recipe 跟著轉（`recipe.turned_with_file`） |
| `drag_out.py` | 75 | 從圖磚拖出檔案 URI 到 Explorer / Chrome / Discord |
| `undo_commands.py` | 82 | `RotateCommand` / `RatingCommand` / `FavoriteCommand` |
| `recipe_commands.py` | 60 | `EditRecipeCommand`：顯影編輯的 undo/redo（存新舊 recipe dict） |
| `undo_coalescer.py` | 61 | 把滑桿拖曳產生的密集編輯合併成單一 undo 步驟 |

### 6.11 `Imervue/library/`

SQLite 支撐的跨資料夾相片庫索引與整理演算法（純邏輯，無 Qt）。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `image_index.py` | 735 | **核心 SQLite 索引**：跨資料夾中繼資料、註記、階層標籤、smart album、pHash、挑片旗標；`move_paths(mapping, *, keep_existing)` 在一個交易內把 images／notes／culling／image_tags 的路徑改到新位置（檔案改名、搬移、重新連結時），`stored_paths()` 列出所有表的路徑 |
| `scanner.py` | 167 | 背景掃描器，走訪 library roots 填索引（走訪沿用 `maintenance.scan_image_files`，HEIC / JXL 先註冊解碼器） |
| `maintenance.py` | 46 | 索引與檔案系統對帳；`scan_image_files()` 經 `list_images(recursive=True)` 收 `formats.STILL_IMAGE_EXTENSIONS`，跳過隱藏檔與隱藏資料夾（磁碟根目錄的 `$RECYCLE.BIN`、Mac 的 `.Trashes`），也是掃描器的走訪 |
| `smart_album.py` | 361 | Smart Albums：保存查詢並重新套用 |
| `search_query.py` | 219 | 自由文字查詢 → Smart Album 規則 |
| `album_io.py` | 74 | Smart Album 匯出 / 匯入為可攜 JSON |
| `clip_search.py` | 382 | CLIP 語意搜尋（「找出符合這句話的照片」） |
| `auto_tag.py` | 133 | 啟發式內容分類 + 選用 CLIP ONNX |
| `phash.py` | 85 | 64-bit DCT pHash（轉正後經 `perceptual_hash.grey_levels` 取灰階） |
| `bloom_filter.py` | 150 | 純 Python bloom filter，快速判斷「看過這個指紋沒」 |
| `dedupe_resolver.py` | 60 | 從一組重複中挑出該保留的那張 |
| `stacks.py` | 89 | RAW + JPEG 配對堆疊 |
| `events.py` | 89 | 依拍攝時間間隔把照片分成「事件」 |
| `calendar_index.py` | 158 | 依拍攝日分桶，供 Calendar View；`capture_datetime()` 是讀拍攝時間的共用入口（Exif 子 IFD → IFD0 → 修改時間），整理工具、時間軸、圖片淨化都走它 |
| `capture_time.py` | 49 | 批次位移 EXIF 時間戳 |
| `date_import.py` | 101 | 依拍攝日匯入到日期資料夾 |
| `gpx_geotag.py` | 113 | GPX 軌跡對時取得座標 |
| `auto_cull.py` | 61 | 依銳利度自動剔除模糊（每張經檢視器的 `decode_image` 讀成最長邊 512 px：RAW 走內嵌預覽、HEIC 可讀、已轉正；讀不了的跳過） |
| `quality_cull.py` | 58 | 依綜合技術品質剔除（每張經檢視器的 `decode_image` 讀成最長邊 512 px：RAW 走內嵌預覽、HEIC 可讀、已轉正；讀不了的跳過） |
| `group_cull.py` | 95 | 每組保留最佳一張 |
| `face_clustering.py` | 78 | 人臉特徵分群 → People Albums |
| `keyword_index.py` | 63 | XMP sidecar 關鍵字匯入索引；`lr:hierarchicalSubject`（`A\|B\|C`）轉成標籤路徑 `A/B/C`（`tag_paths`），只重複其層級的零散關鍵字不另加 |
| `keyword_vocabulary.py` | 163 | 受控詞彙展開（Photo Mechanic 式） |
| `keyword_vocabulary_store.py` | 44 | 詞彙的設定檔儲存 |
| `tag_relations.py` | 49 | 標籤共現 → 相關標籤建議 |
| `metadata_audit.py` | 40 | 找出中繼資料不完整的圖片 |
| `metadata_export.py` | 133 | 中繼資料 CSV / JSON 匯出（EXIF 欄位經 `exif_merge` 讀子 IFD，有理數輸出為數字） |
| `collection_stats.py` | 81 | 集合的評分/收藏/色標籤/挑片統計 |
| `reference_pins.py` | 95 | 釘選參考圖籃子 |
| `staging_tray.py` | 98 | 跨資料夾選取籃 |
| `token_rename.py` | 201 | Token 式批次改名；預覽時批次內其他檔目前的名稱不算衝突，實際改名交給 `batch_rename.rename_files` |

### 6.12 `Imervue/gui/`

167 個檔、33,295 行 —— 全部是 Qt 前端。多數對話框只是外殼，數學在 `image/`。

#### 主視窗組件（非對話框）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `develop_panel.py` | 911 | **Modify 分頁面板**：`build_left_panel()` 工具列、內嵌 `AnnotationCanvas`、recipe 預覽與提交。發出 `recipe_committed` signal；右側面板與 splitter 尺寸來自下面兩個 mixin |
| `develop_right_panel.py` | 327 | `DevelopRightPanelMixin`：Modify 右側屬性面板（裁切、繪圖屬性、標註存檔、顯影滑桿、recipe 重設／復原），每段一個 `_build_*` 方法 |
| `modify_splitter.py` | 131 | `ModifySplitterMixin` + 純函式 `canvas_splitter_sizes()` / `splitter_is_alive()`：把剩餘寬度給中央畫布，並在換螢幕時以 `settle_poll` 持續重算 |
| `annotation_canvas.py` | 845 | 註解畫布 widget + `QUndoCommand`（新增／刪除／修改），工具狀態、座標換算、選取與拖曳、文字編輯、鍵盤；繪製、裁切、馬賽克／模糊來自下面三個 mixin |
| `annotation_drawing.py` | 417 | `AnnotationDrawingMixin`：各種標註與九種筆刷的 QPainter 繪製、選取控點、裁切遮罩；`HANDLE_SIZE` |
| `annotation_crop.py` | 172 | `AnnotationCropMixin`：裁切工具的比例、控點命中與拖曳；`handle_cursor()` |
| `annotation_destructive.py` | 250 | `AnnotationDestructiveMixin` + `_BakeDestructiveCommand`：馬賽克／模糊的強度對話框、即時預覽與烘焙進底圖 |
| `annotation_dialog.py` | 805 | macOS Preview 式標註對話框（編輯器版面、工具、快捷鍵、狀態列） |
| `annotation_file_actions.py` | 202 | `AnnotationFileActionsMixin`：標註的存檔／另存（`.tmp` 原子寫入；寫回原檔時經 `save_over_source` 保留 metadata）；模組層 `ask_save_as_path`（無法寫出的副檔名補 `.png`）/ `write_annotated` 也供 Modify 分頁在 RAW／HEIC／多影格上改存副本、複製到剪貼簿、存／讀 `.imervue_annot.json` 專案 |
| `dialog_rows.py` | 135 | 批次／資料夾／單張工具對話框共用的列與路徑挑選：`save_path_into()` / `open_path_into()`（檔案對話框選到的路徑寫入輸入框；`save_path_into` 也回傳它，取消時回傳 None）、`may_replace()`（目標已存在又不是存檔對話框確認過的，經 `ask_to_replace()` 問要不要取代，預設不取代）、`confirm(parent, title, text)`（刪除、清空、覆寫前的是／否確認，預設「否」；Qt 自己會把「是」設成預設，所有 `QMessageBox.question` 都要指定預設按鈕，`test_questions_default_to_no` 守著）、`image_save_filter()`（PNG / JPEG / TIFF 存檔篩選）；`path_browse_row()`（路徑輸入框＋瀏覽…）、`folder_picker_row()`（再加前置標籤）、`quality_slider()`（「品質：N」標籤＋0–100 滑桿）、`action_button_row()`（靠右按鈕列）；檔案對話框與顯示切換由呼叫端負責 |
| `file_filters.py` | 38 | 檔案對話框篩選字串：`name_filter(label, exts)`、`translated_filter(key, default, exts)`、`image_filter(exts)`（標籤走語言字典，副檔名樣式留在程式）；`viewer_filter()` 直接取 `formats.VIEWER_EXTENSIONS`，開啟圖片與重新定位遺失檔案的對話框因此列出檢視器能開的全部格式 |
| `slider_spin.py` | 75 | `make_slider_spin()` / `link_slider_spin()`：滑桿與數字框雙向同步（訊號阻斷、每次編輯只回報一次）；取代各面板手寫的 `blockSignals` 配對 |
| `main_window_filter.py` | 262 | `MainWindowFilterMixin`：檢視器上方的篩選列（檔名／副檔名／標籤／日期／評分）、套用並盡量保住目前圖片、狀態存回 |
| `main_window_missing.py` | 160 | `MainWindowMissingMixin`：遺失檔批次處理（依檔名自動配對、移除、整個根目錄搬移）與每路徑中繼資料的遷移 |
| `main_window_folders.py` | 307 | `MainWindowFoldersMixin`：監看目前資料夾、重整清單時保住 deep-zoom 圖、資料夾消失時的復原、每資料夾工作階段存取 |
| `main_window_tabs.py` | 219 | `MainWindowTabsMixin`：資料夾分頁的開關、移動、循環、右鍵選單，讓分頁、檔案樹與檢視器指向同一路徑 |
| `main_window_screens.py` | 205 | `MainWindowScreensMixin`：視窗幾何存回（落在仍存在的螢幕上）、跨不同縮放比例螢幕時重算、移動／縮放後重新適配 |
| `main_window_views.py` | 124 | `MainWindowViewsMixin`：雙視窗、多螢幕視窗、劇院模式 |
| `main_window_status.py` | 94 | `MainWindowStatusMixin`：狀態列訊息、掃描進度條、圖片資訊標籤 |
| `main_window_layout.py` | 296 | `MainWindowLayoutMixin`：主視窗建構子呼叫的 `_build_*`（檔案樹、檢視器欄、圖片分頁列、視圖堆疊、工作區分頁、狀態列） |
| `main_window_browse.py` | 139 | `MainWindowBrowseMixin`：縮圖牆／清單切換、清單啟動、從 deep zoom 返回、縮圖尺寸與間距；`refetch_list_rows` 把磁碟上變了的路徑轉給清單檢視；`delete_list_selection` 走縮圖牆的 `delete_selected_tiles`（可復原、之後整批進回收筒），`undo_from_list` 執行檢視器的 undo 後重建清單；`mark_list_selection` 把選取列交給評分、最愛、挑片、色彩標籤的同一組函式（`targets=`） |
| `annotation_models.py` | 603 | 註解資料模型 + **無 Qt 的 PIL 渲染路徑**（可在 worker / 測試中使用）；`jitter_seed()` 給噴槍／炭筆／蠟筆穩定的亂數種子（CRC32，不受行程的 str hash 隨機化影響） |
| `file_tree_view.py` | 929 | `_FileTreeView`：左側檔案樹，含快捷鍵與右鍵選單、重名處理 |
| `file_tree_sort.py` | 149 | `FileTreeSortProxy`：`QFileSystemModel` 沒有的「建立日期」等具名排序鍵 |
| `folder_thumbnail_model.py` | 173 | `QFileSystemModel` 子類，用資料夾第一張圖當樹狀圖示（`folder_preview_path` 經 `list_images`：自然排序、跳過 `._` 等隱藏檔，和縮圖牆的第一張一致；取代不穩定的 Windows shell 縮圖） |
| `image_list_view.py` | 719 | 清單檢視（`QTableView`，縮圖牆的替代）；名稱自然排序，使用者點選的排序欄在 `set_paths` 重建後照樣套用（沒點過時維持檢視器的順序、不顯示箭頭）；點星等欄依點到的星（`star_at`）評分；`refetch(paths)` 讓外部改寫、刪除或復原的列重新讀取（舊縮圖留到新的到為止，讀取中途檔案變了就丟掉那次結果重讀）；Delete／Undo 與評分、我的最愛、挑片、色彩標籤（F1–F5）照「快捷鍵設定」解讀（`_handle_edit_key`），刪除、復原、標記選取列都交給主視窗 |
| `dual_image_view.py` | 196 | 雙圖檢視：Split / Manga / Manga RTL 三種模式 |
| `exif_sidebar.py` | 438 | 可收合的 EXIF 側邊欄（含星等元件） |
| `breadcrumb_bar.py` | 147 | 麵包屑路徑列 |
| `timeline_view.py` | 362 | 時間軸檢視（年/月/日分組） |
| `toast.py` | 96 | Toast / snackbar 通知 |
| `settings_notice.py` | 40 | `warn_if_settings_unreadable(parent)`：啟動時設定檔讀不到，就用非阻塞 `QMessageBox` 說明已改用預設值、副本會存在哪、怎麼取回（主視窗啟動後 800 ms 呼叫） |
| `trash_failure_notice.py` | 59 | `offer_permanent_delete(parent, paths)`：提交刪除後送不進回收筒、留在原處的檔案，列出來問使用者要不要永久刪除（預設保留；確定就 `delete_outright`，資料夾連內容、檔案連 sidecar 一起刪）；關閉時與 File 選單的立即提交都會呼叫 |
| `hover_preview.py` | 192 | 縮圖懸停放大彈窗（預覽依 EXIF 轉正，標題列顯示圖片本身尺寸） |
| `image_issue_panel.py` | 142 | 圖片載入問題面板（dock） |
| `multi_monitor_window.py` | 276 | 多螢幕鏡像視窗 |
| `command_palette.py` | 160 | Ctrl+Shift+P，走訪 `menuBar()` 展平所有 `QAction` 的模糊搜尋啟動器（經 `menu_tree`） |
| `menu_tree.py` | 59 | 不經 `QAction.menu()` 走訪選單樹（`submenu_index` / `iter_menu_actions`），見 §10.10 |
| `modify_actions_widget.py` | 203 | 共用的 Modify 動作按鈕組（選單與右鍵共用） |
| `main_tab_nav.py` | 47 | Modify/Paint 分頁左右鍵的純路由決策 |
| `screen_fit.py` | 62 | 換螢幕時主視窗自適應的純幾何 |
| `settle_poll.py` | 58 | **有界重試**：視窗還在 settle 時反覆重跑佈局步驟（解決 `singleShot(0)` 跨不了 OS 視窗變更的問題）；`owner=` 讓鏈隨物件銷毀而停 |
| `workspace_manager.py` | 154 | 具名工作區預設（幾何 + 佈局快照） |
| `query_search.py` | 41 | 查詢字串輸入 → 過濾縮圖牆 |
| `_apply_save.py` | 174 | **共用的「載入 → 套用 → 另存副本」骨架**（`EffectWorker(QThread)`），約 30 個單圖工具對話框共用；`load_rgba()` 回傳檢視器看到的陣列（RAW 全尺寸顯像、sRGB、依 EXIF 轉正）；`output_path(s)` 給出原圖旁不存在的檔名（`photo_clahe.png` → `_1` …，一組共用編號，由 `system/free_names` 挑名），工具再跑一次不會蓋掉上次結果（外掛也 import，見 architecture.md §6） |

#### 顯影 / 調色對話框（多為 `_apply_save` 外殼）

`tone_curve_dialog.py`(288) · `levels_dialog.py`(169) · `channel_mixer_dialog.py`(148) ·
`hsl_mixer_dialog.py`(130) · `split_toning_dialog.py`(114) · `gradient_map_dialog.py`(165) ·
`colormap_dialog.py`(91) · `lut_dialog.py`(110) · `posterize_dialog.py`(157) ·
`solarize_dialog.py`(139) · `velvia_dialog.py`(84) · `film_negative_dialog.py`(81) ·
`filmic_tonemap_dialog.py`(106) · `tone_equalizer_dialog.py`(96) · `detail_equalizer_dialog.py`(91) ·
`auto_color_balance_dialog.py`(199) · `local_contrast_dialog.py`(120) · `clahe_dialog.py`(100) ·
`defringe_dialog.py`(95) · `graduated_density_dialog.py`(95) · `soft_proof_dialog.py`(128) ·
`develop_presets_dialog.py`(166) · `virtual_copies_dialog.py`(159) · `before_after_dialog.py`(174) 分割滑桿對照 ·
`layers_dialog.py`(449) 疊加圖層堆疊管理 · `masks_dialog.py`(223) 局部調整遮罩

#### 效果 / 濾鏡對話框

`glow_dialog.py`(158) · `emboss_dialog.py`(96) · `film_grain_dialog.py`(135) · `lens_flare_dialog.py`(134) ·
`frosted_glass_dialog.py`(85) · `dither_dialog.py`(91) · `distort_dialog.py`(101) · `polar_dialog.py`(80) ·
`kaleidoscope_dialog.py`(81) · `pixel_sort_dialog.py`(106) · `meme_dialog.py`(94) ·
`photo_frame_dialog.py`(107) · `scale_bar_dialog.py`(106) · `anaglyph_dialog.py`(111) ·
`frequency_separation_dialog.py`(143) 輸出兩個圖層檔 · `binarize_dialog.py`(100) · `otsu_dialog.py`(89) ·
`flatten_field_dialog.py`(95) · `test_charts_dialog.py`(101) · `steganography_dialog.py`(125)

#### 幾何 / 修補 / 多圖

`crop_straighten_dialog.py`(211) · `auto_straighten_dialog.py`(189) · `lens_correction_dialog.py`(157) ·
`smart_crop_dialog.py`(126) 顯著性裁切建議 · `tiny_planet_dialog.py`(113) ·
`clone_stamp_dialog.py`(209) · `healing_brush_dialog.py`(245) · `sky_replace_dialog.py`(143) ·
`portrait_retouch_dialog.py`(162) · `noise_sharpen_dialog.py`(156) · `face_detection_dialog.py`(236) ·
`hdr_merge_dialog.py`(151) · `panorama_dialog.py`(162) · `focus_stack_dialog.py`(150) ·
`stack_blend_dialog.py`(170) · `collage_dialog.py`(87) · `deflicker_dialog.py`(237) 縮時去閃（檢視器解碼；輸出到 `deflickered/`，可寫回的格式沿用並帶 EXIF，RAW 存 PNG） ·
`id_photo_sheet_dialog.py`(106) · `print_layout_dialog.py`(168)

#### 批次 / 匯出 / 管理

`batch_convert_dialog.py`(403) 批次格式轉換（經 `upright_image` 解碼、帶回全部 EXIF；「刪除原檔」只把單影格點陣靜態圖一次送進資源回收筒） · `batch_export_dialog.py`(395) · `export_dialog.py`(256) 單張匯出（預設檔名經 `free_names` 挑還沒被占用的；目標就是原圖本身時另外詢問，其他既有檔案經 `dialog_rows.may_replace`，預設不取代） · `export_source.py`(49) `recipe_base_image()`（recipe 套用的底圖：轉正，舊幾何 recipe 例外；智慧裁切、人臉偵測在它上面算座標）、`upright_image()`（`image_loader.decode_image` 的別名入口；AI 放大與批次轉換共用） · `shown_qimage.py`(33) `shown_qimage(path, *, max_edge)`：檢視器解碼成 QImage，讀不到回傳空 QImage（比較、雙圖、多螢幕、資料夾縮圖取代 `QPixmap(path)`）、`open_export_source()`：兩個匯出共用的來源（經 `decode_image_file`：RAW 全尺寸、SVG 點陣化、sRGB、依 EXIF 轉正，再套 recipe；輸出不帶 ICC 與轉向標籤，所以都烘進像素）· `export_metadata_combo.py`(44) `metadata_row()`：兩個匯出對話框共用的「Metadata」下拉（全部／位置以外／無），選擇記在 user settings `export_metadata` ·
`optimize_dialog.py`(111) 目標檔案大小 · `gif_video_dialog.py`(399) 多張圖做 GIF／MP4（預設輸出經 `free_names` 挑沒被占用的 `output.gif`；既有檔案經 `dialog_rows.may_replace` 詢問） · `contact_sheet_dialog.py`(187) ·
`web_gallery_dialog.py`(150) · `slideshow_mp4_dialog.py`(175) · `image_organizer_dialog.py`(533) ·
`duplicate_detection_dialog.py`(542) 檔案雜湊 + pHash · `image_sanitize_dialog.py`(744) 淨化重繪（剝除所有隱藏資料）·
`exif_strip_dialog.py`(309) EXIF 批次清除（覆寫原檔走 `replace_atomically`；另存的 `_clean` 副本經 `free_names` 挑名） · `token_rename_dialog.py`(124) · `culling_dialog.py`(253) 挑片 ·
`ai_upscale_dialog.py`(721) Real-ESRGAN via ONNX（模型自 HuggingFace 下載）

#### 相片庫 / 中繼資料 / 搜尋

`library_search_dialog.py`(227) · `smart_albums_dialog.py`(298) · `semantic_search_dialog.py`(177) ·
`similar_search_dialog.py`(104) · `advanced_filter_dialog.py`(286) · `tag_album_dialog.py`(523) ·
`tag_filter_dialog.py`(165) · `hierarchical_tags_dialog.py`(190) · `auto_tag_dialog.py`(172) ·
`keyword_editor_dialog.py`(217) · `keyword_vocabulary_dialog.py`(70) · `exif_editor.py`(139) EXIF 編輯對話框（外殼；讀寫在 `image/exif_fields`，不支援的格式顯示說明） ·
`gps_geotag_dialog.py`(90) · `map_view_dialog.py`(180) OSM 底圖 · `calendar_view_dialog.py`(108) ·
`events_dialog.py`(50) · `metadata_export_dialog.py`(94) · `xmp_sidecar_dialog.py`(126) ·
`bookmark_dialog.py`(345) · `staging_tray_dialog.py`(180) · `reference_panel_dialog.py`(298) ·
`image_statistics_dialog.py`(90) · `quality_report_dialog.py`(61) · `image_inspector_dialog.py`(84) 波形/parade/false colour/focus peaking ·
`ocr_dialog.py`(118)

#### 設定 / 系統

`preferences_dialog.py`(268) · `shortcut_settings_dialog.py`(407) · `profiles_dialog.py`(206) 多帳號 ·
`workspace_dialog.py`(231) · `external_editors_settings.py`(151) · `recycle_bin_dialog.py`(365) 軟刪除回收桶 ·
`cache_maintenance_dialog.py`(53) · `watch_folder_dialog.py`(111) · `macro_manager_dialog.py`(334) ·
`dual_pane_dialog.py`(167) 雙窗格檔案管理 · `onboarding_dialog.py`(135) 首次導覽 · `whats_new_dialog.py`(143)

### 6.13 `Imervue/menu/`

選單建構層 —— 只負責組 `QAction` 與呼叫對應對話框，不含業務邏輯。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `extra_tools_menu.py` | 828 | **最大的選單**：Batch / Library / Views / CVD / Workflow / Export / Develop / Retouch / Multi-image 九個子選單，約 100 個 `_open_*` 進入點。子選單帶 `extra_tools.<key>` object name（`submenu_object_name`），外掛靠它 `findChild` 放入口，是對 Imervue_Plugins 的契約 |
| `right_click_menu.py` | 874 | 檢視器右鍵選單：在檔案總管顯示、複製路徑、遺失檔案重定位、重試載入、OCR、批次動作、staging tray、桌布、比較、書籤、標籤… |
| `file_menu.py` | 524 | 開啟資料夾/圖片、新視窗、檔案關聯註冊、剪貼簿貼上、書籤、標籤相簿、快捷鍵設定、偏好設定、回收桶、多帳號、Session、工作區、外部編輯器 |
| `tip_menu.py` | 290 | 操作說明選單 + 快捷鍵速查對話框 |
| `filter_menu.py` | 281 | Filter 選單：依副檔名 / 色彩標籤 / 星等 / 標籤 / 相簿 / 分揀狀態過濾，多標籤與進階過濾，RAW+JPEG 堆疊，清除篩選 |
| `plugin_menu.py` | 333 | 外掛管理：檢視已載入、下載、啟用/停用、開啟資料夾；記錄外掛加進選單的入口（`dispatch_plugin_menus`），重新載入前先移除（`remove_plugin_menu_entries`） |
| `recent_menu.py` | 192 | 最近資料夾 / 最近圖片子選單（teardown-safe，會自動剔除不存在路徑） |
| `sort_menu.py` | 185 | 依名稱 / 修改日期 / 建立日期 / 拍攝日期（`library.calendar_index.capture_datetime`：EXIF 拍攝時間，沒有就用修改時間；同一秒的連拍依檔名）/ 大小 / 解析度排序 |
| `language_menu.py` | 58 | 語言切換（提示重新啟動）；選單 object name `language_menu` |
| `modify_menu.py` | 29 | Deep-Zoom 專用的「修改」選單動作 |

### 6.14 `Imervue/paint/`

190 個檔、46,140 行 —— 全樹最大的子系統，是一個完整的點陣繪圖 + 漫畫製作工作區。

#### 核心文件模型與畫布

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `document.py` | 895 | `PaintDocument`：圖層堆疊 + 選取範圍 + 作用中圖層（幾何、合併、群組操作來自下面三個 mixin；`Layer` / `LayerGroup` 等由 `layer_model` re-export，見 `__all__`） |
| `document_geometry.py` | 214 | `DocumentGeometryMixin`：裁切（矩形／選取／非透明）、翻轉、90/180° 旋轉、縮放、自由變形，圖層、遮罩與已存選取一起改 |
| `document_merge.py` | 201 | `DocumentMergeMixin`：依色塊拆分作用中圖層、向下合併、合併可見、平面化 |
| `document_groups.py` | 136 | `DocumentGroupsMixin`：圖層群組的建立／刪除／改名、成員與群組屬性 |
| `canvas.py` | 856 | `PaintCanvas`：GPU 加速的中央繪圖表面——文件與選取、GL 生命週期與 `paintGL`、材質上傳；疊加繪製、輸入、視圖變換來自下面三個 mixin，`PointerEvent` 等由 `__all__` re-export |
| `canvas_overlays.py` | 538 | `PaintCanvasOverlaysMixin`：棋盤背景（`build_checker_pattern`）、行進螞蟻選取框、工具預覽、多邊形預覽、出血線、洋蔥皮、尺寸 HUD、拖放高亮、像素格線 VBO |
| `canvas_input.py` | 356 | `PaintCanvasInputMixin`：滑鼠／繪圖板事件轉成 `PointerEvent` 交給工具、平移、滾輪縮放、鋼筆 Enter/Esc、拖放開檔 |
| `canvas_view.py` | 187 | `PaintCanvasViewMixin` + `ZOOM_MIN`/`ZOOM_MAX`、`clamp_zoom()`、`wrap_rotation()`：縮放、繞中心旋轉、適配、螢幕↔影像座標 |
| `pointer_event.py` | 35 | `PointerEvent`（工具收到的指標快照）與 `ToolDispatcher` 型別；不依賴 Qt widget |
| `compositing.py` | 438 | 純 NumPy 圖層合成 |
| `layer_model.py` | 116 | 圖層與圖層群組資料模型 |
| `layer_ops.py` | 171 | 向下合併 / 合併可見 / 平面化的純函式 |
| `document_io.py` | 450 | 原生 `.imervue` NPZ bundle 存讀 |
| `psd_io.py` | 873 | Photoshop `.psd` 匯入 / 匯出（互通子集） |
| `undo_stack.py` | 192 | 每文件的 undo / redo |
| `damage.py` | 151 | 破損矩形記帳，供部分材質上傳；另有 `(x, y, w, h)` 元組版的 `union_rects()` / `from_rect()` 給修飾工具累積筆畫用 |
| `blend_modes.py` | 63 | 共用 RGB 混色模式數學 |
| `blend_if.py` | 333 | Blend-If：依亮度範圍決定逐像素可見度 |

#### 筆刷引擎

`brush_engine.py`(650) 純 NumPy 光柵化 · `gpu_brush.py`(681) OpenGL FBO+GLSL 加速 ·
`brush_dynamics.py`(150) · `brush_random.py`(143) 散佈/色彩抖動/傾斜旋轉 · `brush_cursor.py`(515) 筆跡游標預覽 ·
`brush_presets.py`(349) · `default_brush_presets.py`(164) · `brush_preset_io.py`(240) 含外部格式匯入 ·
`brush_preset_dialog.py`(264) · `brush_kind_preview.py`(89) · `brush_tip_capture.py`(137) 從選區擷取筆尖 ·
`custom_brush.py`(97) · `pressure_curve.py`(146) + `pressure_curve_dialog.py`(255) 筆壓曲線 ·
`stabilizer.py`(84) 筆畫穩定器 · `catmull_rom_spline.py`(80) 平滑重採樣 · `symmetry.py`(85) 對稱繪製 ·
`smudge.py`(120) 塗抹/混色筆 · `blur.py`(74) · `dodge_burn.py`(100) · `sponge.py`(68) ·
`watercolor.py`(182) 濕畫法模擬 · `stamp_tool.py`(151) + `stroke_along_path.py`(99)

#### 選取 / 變形

`selection.py`(295) · `selection_ops.py`(325) 選區精修 · `selection_transform.py`(202) 仿射變換 ·
`marquee.py`(93) 選區邊界線段 · `quick_mask.py`(219) 快速遮罩 · `magnetic_lasso.py`(118) 磁性套索 ·
`stroke_selection.py`(140) 描邊選區 · `transform_handles.py`(270) · `perspective_warp.py`(202) 四角透視 ·
`mesh_warp.py`(295) 控制網格雙線性變形 · `liquify.py`(262) + `liquify_dialog.py`(288) 液化 ·
`crop.py`(93) + `crop_tool.py`(90) · `canvas_transforms.py`(76) · `image_resize.py`(149)

#### 填色 / 形狀 / 向量 / 文字

`fill.py`(372) 洪水填色 · `auto_region_fill.py`(253) 一次填滿所有封閉區 · `auto_base_color.py`(245) 線稿自動平塗 ·
`divide_layer.py`(158) 依顏色拆圖層 · `pattern_fill.py`(130) · `gradient.py`(168) + `gradient_editor.py`(282) +
`gradient_map_presets.py`(88) · `shape_engine.py`(265) + `shape_tool.py`(310) ·
`bezier_path.py`(217) + `pen_commit.py`(106) 鋼筆工具 · `polyline_offset.py`(75) 平行曲線 ·
`vector_layer.py`(311) 非破壞性向量線條 · `binary_layer.py`(139) 1-bit 墨線圖層 ·
`image_trace.py`(220) 遮罩 → 輪廓向量化 · `line_cleanup.py`(168) Chaikin 平滑 + 補小縫 ·
`text_render.py`(225) · `text_tool.py`(209) · `rich_text.py`(584) 逐字樣式 · `text_on_path.py`(173) ·
`text_on_selection.py`(92)

#### 顏色

`color_math.py`(83) · `color_wheel.py`(262) + `color_wheel_widget.py`(204) · `color_palette.py`(168) +
`color_palette_io.py`(303) 外部調色盤格式 · `color_sampler.py`(174) 取樣點 · `swatch_panel.py`(245) ·
`palette_extract.py`(168) median-cut 抽色 · `match_color.py`(96) · `match_palette.py`(108) ·
`color_management.py`(181) ICC · `color_blindness.py`(118) CVD 模擬 · `auto_correct.py`(79) ·
`adjustments.py`(739) 純 NumPy 非破壞性調整種類與套用管線 · `histogram.py`(128) + `histogram_dock.py`(141)

#### 漫畫 / 網點

`manga_menu.py`(578) · `manga_effects.py`(347) 速度線 + 網點 · `manga_panels.py`(262) 分鏡版面 ·
`halftone.py`(357) 網點引擎 · `speedlines.py`(210) · `speech_bubble.py`(204) + `speech_bubbles.py`(487) 對話框氣泡 ·
`comic_stamps.py`(266) + `stamp_dock.py`(88) · `comic_formats.py`(161) · `flash_effect.py`(132) 爆炸效果 ·
`frame_splitter.py`(137) · `bleed_guides.py`(154) 裁切/出血/安全線 · `page_templates.py`(266) ·
`page_numbering.py`(156) · `page_dock.py`(348) 頁面瀏覽 · `paint_project.py`(147) 多頁專案 +
`paint_project_io.py`(114) + `paint_project_export.py`(130) · `new_project_dialog.py`(105)

#### 動畫

`animation.py`(478) 時間軸 + 洋蔥皮 · `animation_timeline.py`(198) 純 NumPy 模型 ·
`animation_dock.py`(289) 幀條 + 播放控制 · `animation_export.py`(165) · `timelapse.py`(126) 縮時匯出

#### 素材 / 參考 / 姿勢

`material_library.py`(301) · `material_procedural.py`(221) 程序化材質 · `material_drop.py`(121) ·
`save_region_as_material.py`(107) · `reference_dock.py`(258) Paint 參考圖 dock（經 `decode_image_file` 以檢視器的樣子顯示：轉正、sRGB、RAW 顯像） + `reference_panel.py`(283) ·
`pose_skeleton.py`(210) + `pose_dock.py`(185) + `pose_drop.py`(128) 2D 火柴人姿勢參考

#### 輔助線 / 檢視

`rulers.py`(492) 繪圖輔助尺 · `smart_guides.py`(168) 智慧吸附 · `snap_guides.py`(124) ·
`visual_guides.py`(262) 像素格線 · `view_transform.py`(146) 平移/縮放/旋轉 · `multi_view.py`(246) 同文件第二視窗 ·
`size_hud.py`(138) + `size_hud_bridge.py`(63) 筆刷大小 HUD · `welcome_overlay.py`(222) ·
`layer_thumbnail.py`(183) · `layer_effects.py`(341) 陰影/外光暈/描邊

#### 工作區骨架與選單

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `paint_workspace.py` | 756 | 頂層 `PaintWorkspace` widget |
| `tool_dispatcher.py` | 448 | 把 `PointerEvent` 路由到作用中工具的處理器；工具本體都在 `tools/`，在這裡 re-export（`__all__`） |
| `tool_state.py` | 896 | **無 Qt** 的工具狀態模型 |
| `tool_bar.py` | 414 | 工具列：按鈕只在提示顯示按鍵，工具按鍵由 `tools_menu.py`（`tool_shortcut`）獨佔 |
| `workspace_tabs.py` | 327 | 多文件分頁 |
| `workspace_docks.py` | 418 | dock 建構與佈局持久化 |
| `workspace_content.py` | 433 | 文件內容命令 |
| `workspace_status.py` | 320 | 狀態列與縮放指示 |
| `workspace_shortcuts.py` | 313 | 快捷鍵（登錄表管理的鍵經 `shortcut_binding` 建立，`apply_shortcut_registry` 套用重新指定）、筆刷調整、歡迎提示 |
| `workspace_presets.py` | 265 + `workspace_preset_dialog.py`(316) | 具名 dock 佈局預設 |
| `workspace_autosave.py` | 142 + `auto_save.py`(242) | 自動存檔與當機復原 |
| `action_recorder.py` | 240 + `action_recorder_dialog.py`(197) | 動作錄製 / 重播 |
| `shortcut_registry.py` | 183 + `shortcut_binding.py`(111) + `shortcut_dialog.py`(180) + `shortcuts_dialog.py`(107) | 可自訂快捷鍵登錄；`shortcut_binding.py` 標記擁有各登錄項的 `QAction` / `QShortcut`，把使用者重新指定的鍵套上去（只換登錄表的那個鍵，保留別名）；`fixed_shortcut_keys` 列出登錄表外動作已占用的鍵，對話框把撞到的列標紅並說明被誰占用 |
| `tablet_mapping.py` | 230 | 數位板按鍵 → 動作對應 |
| `recent_files.py` | 72 | 最近開啟清單 |
| `export_presets.py` | 276 + `export_utils.py`(231) | 批次匯出設定檔、浮水印、逐圖層匯出、切片匯出 |
| `canvas_presets.py` | 184 | New Canvas 尺寸預設 |
| 選單 | — | `paint_menu_bar.py`(90)、`file_menu.py`(543)、`edit_menu.py`(259)、`image_menu.py`(265)、`layer_menu.py`(323)、`filter_menu.py`(440)、`view_menu.py`(311)、`tools_menu.py`(158)、`settings_menu.py`(127)、`filter_preview_dialog.py`(179) |

#### `paint/docks/`（7 檔 · 1,863 行）

`brushes.py`(445) 筆刷與填色 dock · `layers.py`(431) 圖層 dock · `color.py`(369) 顏色 dock ·
`materials.py`(265) 素材庫 dock · `navigators.py`(247) 導覽器 / 歷史 / 頁面導覽 dock ·
`_helpers.py`(150) 共用元件、圖示與混合模式下拉選單

#### `paint/tools/`（6 檔 · 1,866 行）

`painting.py`(416) 筆刷/橡皮/填色/滴管 · `shapes.py`(444) 形狀與裁切 ·
`special.py`(353) 鋼筆/仿製印章/變形控點/對話氣泡 · `select.py`(302) 矩形/套索/魔術棒/快速選取、選取區搬移 ·
`retouch.py`(346) 漸層/塗抹/模糊/加深減淡/海綿

### 6.15 `Imervue/puppet/`

57 個檔、15,296 行。2D 骨架人偶動畫，Live2D Cubism 相容。原本是外掛，因為核心路徑
（GL / mesh / 純 NumPy 變形）跑在預設相依上，所以收進主程式當內建分頁；唯一的重量級選用相依
是 Cubism Native SDK DLL，缺了會優雅降級。

#### 資料模型與 I/O

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `document.py` | 395 | `.puppet` v1 檔案格式的純 Python 資料模型（`Drawable` / `Deformer` / `Parameter` / `Motion` / `HitArea`） |
| `document_io.py` | 884 | `.puppet` zip 容器讀寫 |
| `cubism_import.py` | 550 | Live2D Cubism v3 檔案格式匯入 |
| `cubism_native_bridge.py` | 443 | `Live2DCubismCore.dll` 的 ctypes 綁定（官方 Cubism SDK for Native） |
| `cubism_native_convert.py` | 643 | `.moc3` → `PuppetDocument` 轉換 |
| `psd_import.py` | 186 | PSD 多圖層 → `PuppetDocument` |
| `auto_mesh.py` | 172 | 從單張 PNG 自動生成網格 |
| `auto_rig.py` | 402 | 依圖層命名慣例自動推導 Cubism 式綁定 |
| `standard_params.py` | 116 | Cubism 標準參數目錄 |
| `requirements.py` | 75 | 選用相依清單 |

#### 執行期（變形 / 物理 / 取樣）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `runtime.py` | 846 | **每幀參數取樣 + deformer 組合**（核心迴圈） |
| `deformers.py` | 262 | 純 NumPy deformer 實作 |
| `physics.py` | 141 | Verlet 物理引擎 |
| `render_prep.py` | 103 | `PuppetDocument` → GL-ready draw list |
| `canvas.py` | 853 | `PuppetCanvas`（`QOpenGLWidget`）：文件、參數、選取、網格編輯、`paintGL` / 離屏渲染與滑鼠互動；實際繪製來自 `canvas_render.py` |
| `canvas_render.py` | 537 | `PuppetCanvasRenderMixin`：棋盤背景、桌寵陰影、drawable 繪製與 stencil 裁切、選取框與錨點、頂點緩衝與貼圖（預乘 alpha 的 `_premultiply_alpha`）快取 |
| `clip_masks.py` | 56 | `Drawable.clip_mask` 參照解析 |
| `ik.py` | 89 | 兩節骨骼解析式 IK |
| `bone_weights.py` | 100 | 骨骼 LBS 權重驗證與修復 |
| `hit_test.py` | 120 | `HitArea` 純 Python 命中測試 |
| `mesh_edit.py` | 93 · `mesh_repair.py` 230 · `symmetrize.py` 138 | 網格編輯 / 拓樸修復 / X 軸自動對稱 |
| `operations.py` | 228 | `PuppetDocument` 的純編輯操作 |
| `validator.py` | 296 | 靜態健康檢查 |

#### 動作 / 表情 / 閒置

`motion_sampler.py`(148) 純取樣 · `motion_player.py`(375) Qt 播放驅動 · `motion_recorder.py`(166) 錄製 ·
`motion_timeline.py`(355) 曲線圖編輯 · `motion_compress.py`(113) 移除冗餘關鍵幀 ·
`motion_picker.py`(53) 群組隨機挑選 · `synth_motions.py`(286) 為轉檔 rig 合成閒置動作 ·
`idle_driver.py`(143) · `idle_motion_cycler.py`(151) · `easing.py`(203) 緩動預設 ·
`motion_dock.py`(193) · `expression_dock.py`(121) · `parameter_dock.py`(197) · `bone_tree_dock.py`(196)

#### 即時輸入驅動

`input_engine.py`(212) 把即時輸入灌進 canvas · `input_drivers.py`(215) 純對應函式（游標→角度參數等）·
`mouse_gaze_driver.py`(239) 頭+眼追游標 · `webcam_tracker.py`(393) 攝影機 → 參數 ·
`webcam_preview_dialog.py`(224) · `face_landmark_mapper.py`(212) MediaPipe FaceMesh → 參數 ·
`audio_lipsync.py`(99) 音檔驅動嘴型

#### 輸出

`recorder.py`(199) 幀擷取 · `batch_export.py`(186) 每個 motion 匯出成 MP4/GIF/WebM ·
`spritesheet.py`(67) · `virtual_camera.py`(243) 系統虛擬攝影機 · `ndi_output.py`(222) NDI 來源廣播 ·
`vts_api.py`(385) VTube Studio Public API server（最小子集）

`workspace.py`(851) 是頂層 `PuppetWorkspace`（`QMainWindow`），掛載 canvas 與各 dock、開存檔、rig 編輯、驅動開關、驗證與批次匯出；另外混入三個 mixin：`workspace_menus.py`(286，所有 `QAction`、選單列、切換工具列、範例／最近檔案子選單；`RECENT_KEY`)、`workspace_import.py`(361，PNG sprite sheet／PSD／Cubism 匯入)、`workspace_live.py`(222，錄影、webcam 追蹤與預覽、虛擬攝影機、NDI、VTube Studio API)。

### 6.16 `Imervue/desktop_pet/`

34 個檔、8,261 行。無邊框、透明、永遠置頂的桌面寵物懸浮視窗，**共用整個 Puppet 執行期**。
Tab 4 本身只是控制面板，角色住在獨立的 top-level `PetWindow`。

#### 視窗與互動

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `pet_window.py` | 836 | `PetWindow`：無邊框透明視窗，host 一個 pet 模式的 `PuppetCanvas` |
| `pet_window_flags.py` | 174 | `PetWindowFlagsMixin`：`PetWindow` 的視窗旗標組合（置頂／置底、點擊穿透）、鎖定位置、吸附門檻、透明度、全螢幕時隱藏 |
| `pet_feature_toggles.py` | 219 | `PetFeatureTogglesMixin`：`PetWindow` 的各功能開關（眨眼、對嘴、webcam、熱鍵、OBS／Twitch、虛擬攝影機、LLM、音樂律動、閒置小遊戲、通知、webhook、陰影、音效、滑鼠注視），只轉給對應控制器並存設定 |
| `pet_workspace.py` | 714 | Tab 4 控制面板（rig 選擇、驅動開關、可見性 / 點擊穿透 / 尺寸預設） |
| `pet_interaction.py` | 214 | 指標互動控制器：拖曳移動、點擊路由、命中偵測 |
| `pet_placement.py` | 153 | 邊緣吸附、多螢幕位置還原、預設角落停靠 |
| `edge_snap.py` | 165 | 純 Python 邊緣吸附數學 |
| `pet_context_menu.py` | 140 | 右鍵選單建構器 |
| `pet_registry.py` | 134 | 多隻寵物的生命週期登錄表（以 pet id 為鍵） |
| `pet_shadow.py` | 137 + `pet_shadow_controller.py`(83) | 放射漸層落地陰影（單一 draw call） |
| `speech_bubble.py` | 208 | 對話泡泡覆蓋視窗（自動淡出） |
| `tray_icon.py` | 151 | 系統匣切換 |
| `settings.py` | 304 | 設定持久化（schema + 預設值 + 載入夾限） |
| `fullscreen_detector.py` | 166 | 偵測同螢幕有全螢幕程式時自動隱藏 |

#### 驅動與功能控制器（兩個家族）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `pet_feature_base.py` | 171 | `FeatureHost` Protocol + `IntegrationController` 骨架 |
| `pet_features.py` | 178 | 具體整合控制器：OBS / Twitch / Webhook / Windows 通知 / 全域熱鍵 |
| `pet_drivers.py` | 243 | canvas 驅動控制器：音樂律動 / 閒置小遊戲 / 點擊音效 / LLM 對話 |
| `pet_canvas_drivers.py` | 168 | canvas 輸入驅動子系統（自動眨眼 / 拖曳追頭 / 麥克風對嘴） |

> 這兩個家族的存在是為了把 `PetWindow` 從 god-object 拉回「協調者」。

#### 外部整合

`obs_event_hook.py`(195) OBS WebSocket → 動作群組 · `twitch_chat_hook.py`(277) Twitch 聊天關鍵字 ·
`webhook_server.py`(323) localhost HTTP POST `/trigger` · `windows_notification_hook.py`(293) Windows toast →
`Notify` 動作 + 朗讀標題 · `hotkey_manager.py`(248) 全域熱鍵（pynput）+ `hotkey_conflicts.py`(46) 衝突偵測 ·
`command_parser.py`(77) 可重用的聊天指令路由器（exact / prefix / substring / regex）

#### 個性與行為

`pet_script.py`(436) JSON 支撐的台詞 + 排程事件引擎 · `pet_script_editor.py`(521) 內建編輯器 ·
`schedule_rules.py`(101) 時段 / 星期閘門 · `idle_minigame.py`(278) 閒置好奇 / 打呵欠 ·
`llm_dialogue.py`(242) 本地 LLM（預設 Ollama）對話 · `music_rhythm.py`(463) WASAPI loopback 抓系統音訊隨節奏擺動 ·
`click_sfx.py`(168) 事件音效

### 6.17 `Imervue/plugin/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `plugin_base.py` | 206 | `ImervuePlugin` 基底類別，12 個 hook：`on_plugin_loaded/unloaded`、`on_build_menu_bar`、`on_build_context_menu`、`on_build_main_tabs`、`on_image_loaded/folder_opened/image_switched/image_deleted`、`on_key_press`、`get_translations`、`on_app_closing` |
| `plugin_manager.py` | 228 | 探索與載入（把 `plugins/` 插進 `sys.path`，找 `plugin_class`）、hook 分派、統一 try/except 隔離（單一外掛炸掉不會拖垮主程式） |
| `plugin_downloader.py` | 530 | 從公開發佈 repo 下載外掛：一次遞迴 git-tree 呼叫列出清單（純函式 `parse_plugin_tree`，只收 `plugins`/`languages` 類別、只收外掛目錄下的扁平檔），檔案走 raw.githubusercontent。含 `_https_urlopen` 守衛（拒絕非 https scheme） |
| `pip_installer.py` | 850 | 外掛相依安裝器：下載內嵌 Python、安裝 pip 套件（凍結環境亦可），每次安裝都帶 `pip_constraints` 的約束檔；再匯出 `python_finder` 的名稱（外掛依賴 `pip_installer._find_python`） |
| `python_finder.py` | 218 | 找有 pip 的 Python 直譯器：非凍結用 `sys.executable`，凍結時依序查 PATH、registry／安裝資料夾（或 Unix 路徑）、內嵌 Python；`_verify_python` 以 `pip --version` 驗證 |
| `pip_constraints.py` | 50 | 外掛相依安裝的 pip 約束（純函式）：所有 OpenCV 發行版鎖在 5 以下（共用同一個 `cv2` 目錄；OpenCV 5 移除了 Haar 分類器），組 `pip install -c` 指令 |
| `model_dir.py` | 50 | 外掛模型目錄的共用解析 |
| `subprocess_util.py` | 36 | 外掛 worker 呼叫子 Python 的共用 helper |
| `worker_host.py` | 74 | **`WorkerHostMixin`**：擁有背景 `QThread` 的 `QDialog` 共用拆卸邏輯，修掉「QThread destroyed while running」當機（約 90 個對話框使用） |

### 6.18 `Imervue/mcp_server/`

把 Imervue 的影像能力以 Model Context Protocol 暴露給 LLM 代理。**完全無 Qt、無選用相依**。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `server.py` | 439 | JSON-RPC 2.0 over stdio 的協定迴圈 |
| `tools.py` | 172 | 工具集的對外門面：re-export 全部 56 個處理器，`_TOOL_DEFINITIONS`（讀取類在前、編輯類在後，即 `tools/list` 順序）與 `register_default_tools` |
| `tools_read.py` | 639 | 20 個讀取／分析類處理器：`list_images`、`read_image_metadata`、`read_xmp_tags`、`extract_gps`、`image_statistics`、`quality_metrics`、`ocr_text`、`find_similar`、`search_images`、`convert_format`、`puppet_inspect`… |
| `tools_edit.py` | 883 | 36 個寫出類處理器（讀 `source`、寫 `destination`）：浮水印、外框、拼貼、裁切／縮放／旋轉與各種效果（`levels_image`、`curve_image`、`clahe_image`、`lens_correction_image`…） |
| `tool_support.py` | 77 | 兩組處理器共用：`IMAGE_EXTENSIONS`（即 `formats.RASTER_EXTENSIONS`）、`NO_ALPHA_FORMATS`、`open_upright` / `load_rgba_array`（委派 `shown.open_shown` / `load_shown_rgba`，RAW 經 libraw 顯像；每個工具都在依 EXIF 轉正後的影像上運作，尺寸與座標也以它為準）、`validated_dir`／`validated_file`、`json_safe` |
| `tool_defs_read.py` | 351 | `READ_TOOL_DEFINITIONS`：讀取類工具的名稱、描述、輸入 schema、處理器 |
| `tool_defs_edit.py` | 929 | `EDIT_TOOL_DEFINITIONS`：寫出類工具的同上資料 |
| `tool_schemas.py` | 578 | 每個工具的輸出 schema 與 annotation（有 parity test 強制與 `_TOOL_DEFINITIONS` 對齊） |
| `prompts.py` | 228 | 影像助理的 prompt 範本 |
| `resources.py` | 132 | 把圖片暴露成可讀 MCP resource |
| `progress.py` | 66 | 長時間工具呼叫的進度通知 |
| `notifications.py` | 66 | 同步 stdio 迴圈上的 server-push 通知 |
| `completion.py` | 39 | prompt 參數值建議 |
| `logging.py` | 38 | RFC 5424 嚴重度與 emit 過濾 |

---

## 7. `plugins/` 外掛實作

**外掛 vs 主程式的判準不是「AI 功能就進外掛」，而是相依表面：**

進外掛的條件（任一成立）：① 需要重量級 / 選用執行期相依（rembg、onnxruntime、torch、opencv、大模型權重）；
② 需要失敗隔離（ML / GPU / CUDA 崩潰不該拖垮檢視器）；③ 需要獨立發版節奏。

留在主程式：跑在預設相依集、失敗最多壞一張圖、屬於日常瀏覽 / 顯影流程。

| 外掛 | 檔案/行數 | 功用 | 重量級相依 |
| --- | --- | --- | --- |
| `safety_review` | 15 / 4,622 | NSFW 偵測與馬賽克（僅生殖器與肛門，**絕不處理乳頭/胸部**）。含手動編輯器、YOLO 資料集匯出、fine-tune 腳本；打碼幾何與繪製集中在 `_censor_core.py`，App 內偵測與凍結環境的 `_runner.py`（以同層檔案載入）共用；NudeNet 偵測器一律包成 `_AnyPathDetector`（先 `np.fromfile` + `cv2.imdecode` 解碼再交給它，Windows 上路徑含非 ASCII 字元也讀得到）；存檔一律走 `_censor_core._save_as`（`.tmp` + `os.replace`，覆寫原檔模式失敗也不毀原圖） | nudenet, ultralytics, huggingface_hub |
| `spanish_translation` | 3 / 1,773 | 西班牙文語言外掛，示範 `register_language()` | — |
| `ai_background_remover` | 3 / 915 | rembg (U²-Net) 去背，單張 + 批次，凍結環境走子行程 | rembg, onnxruntime |
| `ai_object_remove` | 4 / 823 | 點選物件 → 洪水填色遮罩 → 擴散修補；另有 SAM ONNX point-prompt 路徑 | onnxruntime (SAM) |
| `object_splitter` | 4 / 701 | 去背 + 連通元件（`_components.py`，scipy 為主、BFS 後備，外掛與 `_runner.py` 共用）→ 每個物件存成透明 PNG | rembg |
| `video_source` | 3 / 612 | 瀏覽影片並抽出靜幀 | imageio-ffmpeg |
| `ai_motion_deblur` | 3 / 581 | Wiener 反捲積 + 選用 ONNX | onnxruntime |
| `ai_portrait_relight` | 3 / 565 | 啟發式 Lambert 打光 + 選用 ONNX | onnxruntime |
| `ai_smart_resize` | 3 / 524 | Seam carving 內容感知縮放 | — (重運算) |
| `npr_filters` | 3 / 502 | 鉛筆 / 油畫 / 水彩 / 線稿 | opencv-python |
| `ai_colorize` | 3 / 505 | 黑白上色：啟發式調色盤 + ONNX | onnxruntime |
| `cloud_share` | 3 / 485 | 上傳到 WebDAV / Imgur（HTTPS-only 守衛，僅在使用者按下上傳時執行） | — |
| `ai_denoise` | 3 / 458 | 雙邊濾波（純 NumPy）或 ONNX 神經降噪 | onnxruntime |
| `ai_style_transfer` | 3 / 400 | ONNX 快速神經風格轉換，自動探索 `models/*.onnx` | onnxruntime |
| `portrait_mode` | 3 / 384 | rembg 主體遮罩 + 背景模糊（假淺景深） | rembg |
| `ai_outpaint` | 3 / 237 | 擴張畫布 + 擴散填補邊界 | — |
| `png_to_icon` | 2 / 195 | PNG → 多尺寸 `.ico` + `.png`（純函式 `write_icon_set`，測試 `tests/test_png_to_icon.py`） | — (Pillow 為預設相依) |

**發佈規則（硬性要求）**：`/plugins/` 在本 repo 是 gitignored（新檔要 `git add -f`），
且外掛透過另一個公開 repo `D:\Codes\Imervue_Plugins`（remote `Jeffrey-Plugin-Repos/Imervue_Plugins`）
發給使用者。下載器讀的是 **`main` 分支**，且只抓外掛目錄下的**扁平檔案**（`models/` 之類子目錄不會下載）。

---

## 8. `tests/` 測試體系

889 個檔、148,198 行。`pyproject.toml` 定義三個互斥層級 marker：

| 層級 | 定義 | 判定方式 |
| --- | --- | --- |
| `fast` | 不建 Qt widget、不跨子系統 | 預設 |
| `gui` | 建立或操作 Qt widget | fixture 用到 `qapp`/`qtbot`，或原始碼含 `PySide6.QtWidgets` |
| `integration` | 跨多個子系統或完整流程 | 檔名含 `integration` / `_full` 結尾 |

`conftest.py` 在 collection 期自動分類並依 `--test-layer` 取捨，同時把 `plugins/` 注入 `sys.path`
（鏡像執行期 `plugin_manager` 的行為），讓測試能 `from ai_denoise.denoise import …`。

**共用 fixture**：`qapp`、`tmp_path`、`sample_*_array`、`image_folder`、`pump_until`（等候排隊中的 Qt 訊號）、
`fake_clipboard`（行程內剪貼簿），以及 autouse 的 `_isolate_user_settings`（把設定路徑導開，測試絕不寫真的
`user_setting.json`）、`os_trash`（以行程內假回收筒取代 `send2trash`，測試絕不碰系統資源回收筒）和 `_restore_app_appearance`（還原測試改過的 QApplication 字型與樣式表，避免同一 xdist worker 後續檔案的元件尺寸被改變）。

**輔助模組**：`_qt_skip.py`（GL widget 的 CI skip marker）、`_instant_worker.py`、`_toast_spy.py`、`_app_appearance.py`（`app_appearance_restored`：字型與樣式表還原 context manager）。

### Qt / OpenGL 在無頭 CI 上的硬規則

GitHub Actions Windows runner 在同一個 pytest session 建太多 `QOpenGLWidget` 會
`Windows fatal exception: access violation`（offscreen GL surface pool 有限，溢出會毀壞行程記憶體）。

因此**每個會建構 `PetWindow` / `PuppetCanvas` / `PuppetWorkspace` 或任何 `QOpenGLWidget` 子類的測試檔**
都必須在模組頂端加：

```python
from _qt_skip import pytestmark  # noqa: E402,F401
```

驗證：`CI=true py -m pytest <file> -q` — 檔內每個測試都必須是 `s`。

---

## 9. 建置、封裝與 CI

| 項目 | 檔案 | 說明 |
| --- | --- | --- |
| PyInstaller | `Imervue.spec` / `Imervue_mac.spec` | Windows / macOS spec |
| Nuitka | `build_nuitka/`、`nuitka.md` | 需在 import OpenGL 前關掉 `USE_ACCELERATE` |
| auto-py-to-exe | `packaging/auto_py_to_exe_config.json` | |
| AppImage | `packaging/build_appimage.sh` | Linux |
| 跨平台說明 | `packaging/CROSS_PLATFORM.md` | |
| CI | `.github/workflows/test.yml`、`release.yml` | release.yml 釘死所有相依且 wheels-only；**Nuitka 只有 sdist，必須維持 `--no-binary` 豁免** |
| 文件 | `docs/`（Sphinx，10 語言）+ `README.md` 與 `README/`（9 語言） | `README.md` 與 `docs/en` 是正規來源；CI 以 `sphinx -W` 建置，警告即失敗。翻譯檔裡行內標記緊鄰中日韓文字時，要在標記與文字之間加 `\ `（跳脫空白），CJK 標題底線要以顯示寬度（全形算 2）計 |

### 品質閘（專案規範的 Definition of Done）

任何行為變更提交前必須全過：

```bash
py -m pytest tests/                        # 單元測試（新程式必須有新測試）
py -m ruff check .                         # 無新錯誤（含 plugins/：respect-gitignore = false）
py -m bandit -c pyproject.toml -r Imervue/ plugins/  # 必須 "No issues identified"（-c 不可省）
```

外加：commit message 不得含任何 AI 工具 / 模型名稱，不得有 `Co-Authored-By`。

**ruff 設定重點**：line-length 100，啟用 `E/F/W/B/SIM/UP/PL/S/C90/N`，
`mccabe.max-complexity = 15`（工作區規則的上限，專案只能更嚴不能放寬）。
Qt override 的 camelCase（N802/N803/N806/N815）與品牌名 `Imervue`（N999）已豁免。

**外部儀表板**：Codacy（`app.codacy.com/gh/JeffreyChen-s-Utils/Imervue`）與
SonarCloud（`JeffreyChen-s-Utils_Imervue`）。

---

## 10. 跨切面模式（重要）

這些模式反覆出現在全樹，改動時務必沿用而非另起爐灶。

### 10.1 Pure logic / Qt shell 二分

單圖工具的標準形狀：`Imervue/image/<feature>.py`（純 NumPy）+ `Imervue/gui/<feature>_dialog.py`（Qt 外殼）
+ `Imervue/menu/extra_tools_menu.py` 的一個 `_open_<feature>()`。

### 10.2 `_apply_save.py` 骨架

約 30 個「載入當前圖 → 套用 → 另存副本」對話框共用 `gui/_apply_save.py` 的 `EffectWorker(QThread)`。
新增同型工具時直接接上，不要再手寫 worker。

### 10.3 `WorkerHostMixin`

`Imervue/plugin/worker_host.py`。凡是擁有背景 `QThread` 的 `QDialog` 都繼承它，
解決關閉對話框時 `QThread destroyed while still running` 的當機。**不要手寫 `closeEvent` 拆卸邏輯。**

### 10.4 Collaborator 拆解

`GPUImageView`、`PetWindow`、`PaintWorkspace` 都遵循同一手法：Qt 類別只留事件覆寫與生命週期，
行為搬進具名 collaborator（`InputController`、`OverlayPainter`、`PetInteraction`、`ToolDispatcher`…），
再把其中的數學抽成純函式模組讓它可被無 GL 測試。

### 10.5 `settle_poll` / `singleShot(0)` 陷阱

`singleShot(0)` 的重試鏈跨不過作業系統的視窗變更（換螢幕、還原幾何）。
正解是 `gui/settle_poll.py` 的 `poll_settle`：有界地重跑佈局步驟直到穩定。
新增類似邏輯時必須同時檢查所有呼叫端。

延遲呼叫一律走 `system/qt_timers.call_later(ms, owner, fn)`，不寫 `QTimer.singleShot(ms, lambda: …)` 或 `QTimer.singleShot(ms, obj.method)`：
lambda 與綁定方法都不會隨物件刪除而取消（PySide6 6.11 實測：Python 方法與 `widget.update` 這類 C++ 槽都照樣執行），只有帶 context 的多載
會被 Qt 自動取消。`tests/test_qt_timers.py` 會拒絕 bare-lambda `singleShot`，以及主程式裡的 `singleShot(ms, obj.method)`（外掛要能在沒有 `call_later` 的舊版上執行，保留原寫法）。

### 10.6 批次刪除必須走 `trash_ops`

`send2trash` 每次呼叫固定成本 ~0.27s，一次送整份清單則約 0.016s/檔。
所有刪除路徑（單檔、多選、樹狀刪除）都必須匯進 `Imervue/system/trash_ops.py` 的背景批次，
**禁止 per-file 迴圈**。

### 10.7 網路安全守衛

所有 `urllib.request.urlopen` 必須走模組級 `_https_urlopen`（`urlparse` 檢查 scheme 只允許 https）。
守衛內部那一行是唯一允許的直接呼叫，且必須帶 `# nosec B310  # scheme validated above`。
HuggingFace 下載必須釘 `revision=`（bandit `B615`）。

### 10.8 抑制註解不可互換

| 工具 | 形式 | 備註 |
| --- | --- | --- |
| ruff / flake8 | `# noqa: <CODE>` | 必須列具體碼，禁止裸 `# noqa` |
| bandit | `# nosec B<NNN>` | ruff 的 `# noqa` 不會抑制 bandit |
| SonarCloud | `# NOSONAR` | 注意：在 YAML block scalar 內無效 |
| pylint | `# pylint: disable=<name>` | 優先重構而非抑制 |

系統性誤報一律在設定檔層級處理（`.bandit` + `pyproject.toml [tool.bandit]` 兩邊同步 +
`.codacy.yaml` 的 `engines.<slug>.exclude_paths`；Semgrep 的 slug 是 `opengrep`）。

### 10.9 設定寫入

一律透過 `user_settings/user_setting_dict.py`：去抖非同步存檔 + atomic `.tmp` → `os.replace()`。啟動時讀不到的設定檔由 `system/unreadable_guard.UnreadableFileGuard` 看守：第一次覆寫前先另存 `<檔名>.unreadable-<時間>`，存不了副本就不覆寫，啟動後再以 `gui/settings_notice.py` 告知使用者。
關閉前呼叫 `cancel_pending_save()` 再立即 flush。

### 10.10 選單走訪不可用 `QAction.menu()`

PySide6（6.11.0 / 6.11.1 實測）的 `QAction.menu()` 會把回傳的 `QMenu` wrapper 在 shiboken 擁有權樹裡
改掛到那個暫時的 `QAction` wrapper 下；action wrapper 一被回收，menu wrapper 就被作廢，連帶其他地方
快取的參照（`language_menu`、`_plugin_menu`、paint 的 `_<key>_menu`）都會丟出
「Internal C++ object already deleted」，雖然 C++ 選單還活著。走訪選單一律用 `gui/menu_tree.py`
（`findChildren(QMenu)` + `menuAction()` 對照），要找特定選單就給它 object name 再 `findChild`
（`extra_tools.<key>`、`language_menu`、`plugin_menu`）。

### 10.11 例外處理：只接看得到的型別

ruff 啟用 `BLE`（flake8-blind-except），`except Exception` 必須收窄，或在處理器裡用
`logger.exception`／`exc_info=True` 的 error 級紀錄留下 traceback。常用的收窄方式：

- **讀圖**：接 `image/read_errors.py:IMAGE_READ_ERRORS`（`OSError`、`ValueError`、
  `DecompressionBombError`）。後者不是 `OSError`，漏掉它，超大圖就會把整批流程打斷。
  `tests/test_image_reads_catch_every_read_error.py` 檢查每個包住解碼呼叫的 `try` 都接得住它。
- **Worker 邊界**：對話框在等 worker 的訊號，所以預期的失敗照常回報；最後一層 `except Exception`
  先 `logger.exception` 再回報，不能讓例外跑出執行緒，否則對話框會永遠卡住（範本見 `gui/_apply_save.py`、
  `plugin/plugin_downloader.py`）。`tests/test_workers_always_report.py` 檢查每個 `QThread.run` 最上層的 `try`
  都以這種處理收尾（或在 `finally` 發訊號）。
- **第三方失敗型別沒有邊界時**（piexif 的編碼器、GL 驅動、外掛 import），才保留寬鬆捕捉，寫
  `# noqa: BLE001 - <理由>`，並附 traceback 紀錄。

### 10.12 改名／搬移檔案時帶走每路徑資料

設定（`image_ratings`、`image_tags`、`bookmarks`…）與圖庫 DB（notes、culling、image_tags）都以圖片的絕對路徑為鍵，
sidecar（`IMG.xmp`、`IMG.JPG.xmp`、`IMG.JPG.annotations.json`）則靠檔名對應。主程式自己改名或搬移檔案的路徑
（Batch Rename、Token Rename、檔案樹、`transfer_into` 的所有使用者、Image Organizer）搬完後一律呼叫
`system/file_transfer.carry_along`；在 worker 執行緒裡只能呼叫 `carry_sidecars`，再用訊號把 `{old: new}` 交回 GUI 執行緒呼叫
`follow_saved_data`（設定字典不能在 worker 裡改）。遺失檔重新連結用 `follow_saved_data(..., keep_existing=True)`。
新增以路徑為鍵的設定時，把鍵加進 `user_settings/path_metadata.py` 的 `_VALUE_KEYS`／`_LIST_KEYS`／`_GROUP_KEYS`；
新增以路徑為鍵的 DB 表時，加進 `library/image_index._PATH_TABLES`。測試一律透過 `conftest` 的 `_isolate_library_db`
使用暫存 DB。

---

## 11. 持久化檔案一覽

| 檔案 | 位置 | 內容 |
| --- | --- | --- |
| `user_setting.json` | 應用資料目錄 | 多帳號（profile）容器：語言、主題、UI 縮放、視窗幾何、最近清單、書籤、標籤、色標籤、外部編輯器、桌面寵物設定… |
| recipe store JSON | 應用資料目錄 | 所有圖片的非破壞性 recipe 與 virtual copies |
| library SQLite | 應用資料目錄 | 跨資料夾索引：中繼資料、標籤、smart album、pHash、挑片旗標 |
| 縮圖磁碟快取 | 應用資料目錄 | `image/thumbnail_disk_cache.py` |
| `.imervue-session.json` | 使用者選定 | Session / Workspace 快照 |
| `.xmp` sidecar | 圖片旁 | 星等、標題、關鍵字、色標籤（跨編輯器互通） |
| `.imervue` | 使用者選定 | Paint 原生 NPZ 文件 bundle |
| `.puppet` | 使用者選定 | Puppet zip 容器 |
| pet_script JSON | 應用資料目錄 | 桌面寵物台詞與排程事件 |

---

## 12. 架構注意事項與已知陷阱

1. **Modify 分頁的中央不是 viewer。** 中央是 `develop_panel` 在綁定圖片時插進 splitter 第 1 格的
   `AnnotationCanvas`；`GPUImageView` 一直留在 Imervue 分頁，在 Modify 分頁是隱藏的、沒有 reparent，
   所以收不到鍵盤與 resize。鍵盤、resize、fit 行為都掛在 canvas 上。

2. **`plugins/` 是 gitignored。** 新增外掛檔案要 `git add -f`，否則會靜默漏掉。
   而且改完必須鏡像到 `D:\Codes\Imervue_Plugins` 的 `main` 分支才會到使用者手上；
   `CLAUDE.md` 的 parity 指令逐檔比對內容（忽略換行符），沒有輸出才算同步。

3. **完整測試套件會在全部測試通過後才以 `-1073741819`（0xC0000005）結束。**
   已在 stash 過的乾淨樹上驗證是既有現象，不是新引入的。

4. **`sonar-project.properties` 的 issue-ignore 規則實際上沒有作用**，要靠改程式或
   `# NOSONAR` 清掉。

5. **OpenGL 符號一律明確列名匯入**（`from OpenGL.GL import (glBindTexture, ...)`），全樹沒有 wildcard
   import，所以也沒有 `F403/F405` 豁免。測試會在模組上 monkeypatch 這些 GL 符號（例如
   `paint/canvas.py` 的貼圖上傳），搬動用到它們的程式碼時 patch 目標要跟著改。僅 `gl_renderer.py`、
   `paint/canvas.py`、`paint/canvas_overlays.py` 保留 `E702`（`glTexCoord`/`glVertex` 成對寫在同一行）。

6. **檔案長度上限 1000 行**是專案規則，目前所有模組都符合（`multi_language/*.py` 是資料字典，不適用）。
   最大的是 `gui/file_tree_view.py`(947) 與 `mcp_server/tool_defs_edit.py`(929)；要在接近 1000 行的檔案
   加程式，先把一組內聚的方法拆成模組（mixin 或模組函式），並先補特性測試。
   大型 Qt 類別的拆法：把內聚的方法群原封不動搬進 `<類別>…Mixin`，類別繼承它們，對外方法名不變；
   原模組若是別處的匯入來源，用 `__all__` 保住 re-export（自動移除未用 import 會把只為轉手存在的名稱刪掉）。
   測試若在原模組上 monkeypatch 某個名稱，要改到實際查找它的新模組。

7. **MCP 工具新增流程**：處理器寫在 `tools_read.py` 或 `tools_edit.py`，定義加進對應的 `tool_defs_*.py`，並從 `tools.py` re-export（加進 import 與 `__all__`）；同時必須在 `tool_schemas.py` 加 schema
   （有 parity test 強制），且工具必須保持無 Qt、無選用相依。

8. **Qt 對話框測試**：在 `qapp` fixture 下建立對話框時 parent 傳 `None`，
   不要傳暫時性的 `QWidget`，否則 teardown 會 access violation。

9. **不要用 `QAction.menu()` 走訪選單**（§10.10）。它讓外掛語言從語言選單消失、讓命令面板用過之後
   「重新載入外掛」拿到失效的 Plugins 選單。外掛的 `on_build_menu_bar` 拿到的是 Plugins `QMenu`
   不是 `QMenuBar`，要放進 Extra Tools 子選單請 `findChild(QMenu, "extra_tools.<key>")`。

10. **`QPdfWriter` 寫不進目標時不丟例外。** 只會讓 `QPainter.begin` 回傳 `False`，之後的繪製全是
    no-op，呼叫端照常回報「已儲存」。PDF 輸出一律用 `export/pdf_output.py:begin_pdf_painter`，
    它在失敗時丟 `OSError`。`QImage.save` / `QPixmap.save` 同理只回傳 `bool`，回傳值一定要檢查。

11. **有 57 個模組沒有任何正式程式 import**（清單在 `tests/test_unwired_modules.py` 的 `_KNOWN_UNWIRED`，
    34 個在 `paint/`）。它們都有測試，也列在本地圖的各套件表裡，但使用者從 UI 碰不到。看到表裡的功能描述，
    不代表它已經接上選單；`paint/watercolor.py`、`paint/comic_formats.py`、`paint/speech_bubbles.py`
    另有已接上的實作。新增模組若沒被 import，該測試會失敗；要接上或刪除由擁有者決定（`progress.md` #22）。

12. **同一視窗裡同一個按鍵只能有一個啟用中的快捷鍵。** 兩個 `WindowShortcut` 範圍的 `QAction` / `QShortcut`
    綁同一鍵，Qt 視為歧義、兩個都不觸發，也不會報錯。Paint 分頁嵌在主視窗裡，所以它的按鍵和主視窗自己的
    `QShortcut`、選單列共用一張表：工具鍵只綁在 Tools 選單（工具列只顯示），主視窗的資料夾分頁鍵
    （`Ctrl+T/W/Tab/Shift+Tab`）離開 Imervue 分頁就停用。`tests/test_main_window_shortcut_conflicts.py`
    逐分頁檢查。
13. **很多 import 寫在函式裡，改名或移除時容易漏改。** 那一處只有在函式第一次執行時才會 `ImportError`，
    測試若沒走到就一路綠燈（移除 `image_loader._RAW_EXTS` 時，`deep_zoom_loading` 的漸進解碼判斷就這樣壞掉，
    檢視器每次重新套用 recipe 都丟例外）。`tests/test_internal_imports_resolve.py` 掃描 `Imervue/` 與
    `plugins/` 每一個 `from Imervue... import 名稱`（含函式內），確認名稱真的存在。
14. **Windows 上 send2trash 在沒有資源回收筒的磁碟會直接永久刪除。** 它不帶 `FOF_WANTNUKEWARNING` 又不確認，
    所以網路磁碟、USB 隨身碟、記憶卡上的檔案不會進回收筒。所有送回收筒的路徑都要經過
    `system/trash_ops`（`recycle_bin_holds` 只放行固定磁碟），不可在別處直接呼叫 `send2trash`；
    留在原處的檔案由 `gui/trash_failure_notice.offer_permanent_delete` 交給使用者決定。



