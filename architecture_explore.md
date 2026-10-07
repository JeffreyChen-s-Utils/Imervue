# Imervue 架構全覽 (architecture_explore)

> 產出日期：2026-08-03（全樹掃描）· 最後同步：2026-10-07 · 對應提交見 `git log -1 -- architecture_explore.md` · 分支 `dev` · 版本 `1.0.90`
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
`Imervue/mcp_server/`（Model Context Protocol server，把 58 個影像工具暴露給 LLM 代理）。

**必要相依只有 11 個套件**：PySide6、qt-material、Pillow、PyOpenGL(+accelerate)、numpy、
rawpy、imageio(+ffmpeg)、defusedxml、watchdog。所有重量級 / ML 相依都被推到 `plugins/`。

---

## 2. 規模統計

| 區域 | 檔案數 | 行數 |
| --- | ---: | ---: |
| `tests/` | 949 | 158,466 |
| `Imervue/paint/`（含 `docks/`、`tools/`） | 172 | 43,251 |
| `Imervue/gui/` | 175 | 35,158 |
| `Imervue/puppet/` | 60 | 16,393 |
| `Imervue/image/` | 129 | 15,444 |
| `Imervue/gpu_image_view/`（含 `actions/`、`images/`） | 70 | 13,661 |
| `Imervue/multi_language/` | 8 | 15,240 |
| `Imervue/desktop_pet/` | 29 | 7,089 |
| `Imervue/mcp_server/` | 16 | 4,753 |
| `Imervue/library/` | 33 | 4,774 |
| `Imervue/menu/` | 11 | 3,627 |
| `Imervue/` 根層 | 6 | 1,951 |
| `Imervue/plugin/` | 13 | 2,788 |
| `Imervue/system/` | 33 | 3,203 |
| `Imervue/export/` | 8 | 1,006 |
| `Imervue/user_settings/` | 10 | 1,234 |
| `Imervue/sessions/` + `macros/` + `external/` | 8 | 802 |
| `plugins/`（19 個外掛） | 80 | 16,021 |
| `scripts/`（開發與發佈工具） | 8 | 1,189 |
| **總計** | **1,818** | **346,058** |

其中 `Imervue/` 套件本身 781 檔 / 170,382 行。

測試碼與產品碼比約 **0.85 : 1**（158k vs 186k，產品碼含 `plugins/`），這是專案開發規範中「無測試即未完成」規則的直接體現。

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
   │      └─ 內部：apply_saved_language()（存下的不是內建語言時，先匯入外掛、
   │                只呼叫各外掛類別的 register_languages() 註冊語言）
   │                → 還原視窗幾何 → 建分頁（Puppet、Desktop Pet 依偏好設定開關，開著的也先是空頁，第一次打開才建）→ create_menu()
   │                → _init_plugin_system_example() 載入外掛
   │                → QTimer(800ms) 顯示 What's New / 首次導覽
   └─ 7. 命令列帶檔案 → QTimer(100ms) open_path(viewer, path)
```

**其他入口**

| 入口 | 檔案 | 用途 |
| --- | --- | --- |
| `py -m Imervue.cli …` | `Imervue/cli.py` | headless 批次：resize / watermark / info / convert，只用純 NumPy+Pillow 路徑，完全不起 Qt；每個 MCP 工具也是一個子指令（`cli_tools.py`）；直接執行時先 `configure_pillow()` |
| `py -m Imervue.mcp_server` | `Imervue/mcp_server/__main__.py` | stdio JSON-RPC 2.0 MCP server（啟動前 `configure_pillow()`） |
| `exe/start_Imervue.py` | — | PyInstaller / auto-py-to-exe 的啟動 shim |

---

## 4. 頂層結構：一個主視窗、五個分頁

`ImervueMainWindow(QMainWindow)`（`Imervue/Imervue_main_window.py`，714 行）是唯一的協調者；篩選列、遺失檔、資料夾監看、分頁、螢幕、檢視模式、狀態列、瀏覽模式各由 `Imervue/gui/main_window_*.py` 的 mixin 提供。
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
│   ├── Tab 2  "Paint"         ← `_paint_page`；PaintWorkspace 第一次用到才建立（`paint_workspace` property），有待還原的自動存檔時啟動就建；切回分頁保留現有文件，首次進入顯示空白畫布
│   ├── Tab 3  "Puppet"        ← 選用（`gui/optional_tabs.py`）；`_puppet_page`，第一次打開才建 PuppetWorkspace (QMainWindow-in-tab)
│   └── Tab 4  "Desktop Pet"   ← 選用；`_pet_page`，第一次打開（或寵物設定為啟動時顯示）才建 PetWorkspace（控制面板；角色在另一個 top-level PetWindow）
├── QStatusBar  ← 訊息 + 色標籤 chip + index/解析度/大小/縮放/游標 + MemoryPressureIndicator + 進度條
├── QDockWidget "Image load issues"  ← ImageIssuePanel
└── 系統匣 PetTrayIcon（平台支援、且 Desktop Pet 分頁已建立時）
```

**主視窗自己負責的職責**（其餘全部委派）：

- 分頁切換路由（`_on_main_tab_changed`）、Modify/Paint 分頁的左右鍵改為換圖（`eventFilter`）
- 瀏覽模式切換 grid / list / dual、Theater mode（隱藏所有 chrome）、多螢幕鏡像視窗
- 檔名 / 標籤 / 星等 / 日期過濾列，以及「檔案不見了」的批次修復（自動比對同名、移除、換根目錄）
- 資料夾監控：開啟的資料夾約每秒輪詢一次修改時間（`system/folder_poll.py`，不持有目錄 handle，Windows 才能改名／搬移上層資料夾），變更經 500ms 去抖重掃；資料夾樹不監看（`DontWatchForChanges`），在 F5、回到前景、開啟的資料夾有變更時 refresh
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
- `gpu_image_view.py`（774 行）本身只留 GL 生命週期與 Qt 事件轉發，
  其餘全部委派給約 40 個 collaborator 模組。

---

## 6. 套件逐一說明

### 6.1 `Imervue/`（根層）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `__main__.py` | 130 | `main()`：先設定 logging 與 excepthook，再 import Qt；CLI 參數解析、凍結環境修補、QApplication 建立、主視窗啟動 |
| `Imervue_main_window.py` | 722 | `ImervueMainWindow`：分頁協調者（3 個核心分頁 + 2 個選用分頁）（建構、分頁切換、將瀏覽圖片開成新的 Paint 文件、記憶體壓力、拖放、關閉）；其餘職責來自 `gui/main_window_*.py` 的九個 mixin |
| `cli.py` | 688 | headless 批次 CLI（resize / watermark / info / convert…），只走純 NumPy+Pillow 路徑；輸入一律經 `shown.open_shown` / `load_shown_rgba`（RAW 經 libraw 顯像、其餘轉 sRGB 並轉正），`info` 經 `dimensions.probe_image`，資料夾收 `RASTER_EXTENSIONS`，沿用副檔名的輸出遇到 RAW 改寫 PNG；讀不到的檔案記為錯誤、其餘照跑；`build_parser` 依序加手寫子指令、`cli_tools` 由 MCP 工具產生的 46 個、最後 `list-ops` |
| `cli_tools.py` | 273 | 由 MCP 工具定義產生 CLI 子指令：`COVERED_BY`（10 個已有手寫子指令的工具）＋ `BRIDGED`（其餘 48 個的 CLI 名稱）；依 JSON schema 分三類（`source`+`destination` → 批次 writer、`path` → 每檔 reporter、其他 → 執行一次印 JSON），每個 schema 屬性變成 `--kebab-case` 選項（型別、預設、`enum` 照抄，布林用 `--x/--no-x`，定長陣列取 N 個值），直接呼叫 MCP 處理器；影片／OCR 後端的 `RuntimeError` 轉成 `ToolError`（`ValueError`）算單檔錯誤；`add_argument_as_written` 加選項後把 help 設回原文（Python 3.10 會替 `--x/--no-x` 的 help 補上 ` (default: …)`，之後的版本不會），`cli.py` 的手寫子指令也經它加選項 |
| `integration_guide.py` | 145 | 外掛系統初始化：建立 `PluginManager`、dispatch 主分頁 hook、把外掛語言掛進語言選單（按 object name 找選單） |

### 6.2 `Imervue/system/`

作業系統與應用程式層級的基礎設施。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `app_paths.py` | 109 | 凍結環境安全的路徑解析（icon / plugins / 設定檔），PyInstaller & Nuitka 都適用 |
| `clipboard_monitor.py` | 136 | ShareX 式剪貼簿監聽：PrintScreen 截圖 → 自動開啟註解視窗 |
| `error_report.py` | 177 | 一鍵支援包產生器（日誌 + 環境資訊打包） |
| `file_association.py` | 252 | 跨平台檔案關聯「用 Imervue 開啟」註冊 / 取消；副檔名即 `formats.STILL_IMAGE_EXTENSIONS`（排序），MIME 用 freedesktop shared-mime-info 的名稱 |
| `folder_poll.py` | 70 | `FolderPoller`：約每秒讀一次開啟資料夾的修改時間（`folder_signature`），變了就發 `directoryChanged`；取代 `QFileSystemWatcher`，因為任何變更通知 handle 都讓 Windows 不能改名或搬移上層資料夾 |
| `qimage_convert.py` | 33 | `pil_to_qimage()` / `qimage_to_pil()`：經 RGBA8888 並複製緩衝區的雙向轉換（標註與剪貼簿共用） |
| `log_setup.py` | 100 | 集中式 logging 設定：`setup_logging()`（可重複呼叫；`app_dir()` 不可寫時退到使用者目錄；凍結時不掛 stderr handler）與 `install_exception_logging()` |
| `macos_bundle.py` | 74 | macOS `.app` Info.plist 文件型別關聯；每種相機 RAW 對到 `public.camera-raw-image` |
| `onboarding.py` | 81 | 首次啟動導覽步驟註冊表 |
| `release_notes.py` | 111 | What's-New 對話框的版本說明資料 |
| `themes.py` | 175 | 內建配色主題 |
| `best_effort.py` | 29 | `best_effort(step)`：不中斷呼叫端地執行一段收尾步驟，失敗時以 warning 帶 traceback 記錄（取代無聲的 `suppress(Exception)`） |
| `qt_translations.py` | 60 | `install_qt_translations(app, language)`：依介面語言載入 PySide6 附帶的 `qtbase_<locale>.qm`，讓 Qt 內建字串（確定 / 取消、是 / 否、檔案對話框、分頁關閉提示）跟著翻譯；英文或外掛語言不裝 |
| `job_state.py` | 172 | 純 thread-safe JobState／immutable snapshots，durable item outputs／errors、cooperative cancel 與只含失敗來源的重試集合；O(1) summary polling |
| `qt_timers.py` | 27 | `call_later(ms, owner, fn)`：延遲呼叫，`owner`（QObject）先被銷毀就由 Qt 取消；取代 `QTimer.singleShot(ms, lambda: …)` 與 `singleShot(ms, obj.method)`，兩者在物件刪除後都照樣執行 |
| `file_manager.py` | 59 | `reveal_in_file_manager(path, select=)`：用 OS 的檔案總管開啟路徑（Windows `explorer`，命令列由 `explorer_command` 組成、路徑一律加引號，因為 Explorer 以逗號與 `=` 分隔參數；macOS `open [-R]`、Linux `xdg-open`），檔案總管啟動不了時丟 `OSError`；`reveal_or_warn` 包一層、失敗記警告，給沒有更好處理方式的選單動作用（檔案樹、右鍵選單、清單檢視、外掛選單） |
| `wallpaper.py` | 161 | `set_desktop_wallpaper(path)`：設為桌布（Windows `SystemParametersInfoW`、macOS 以 argv 傳路徑給 `osascript`、GNOME `gsettings` 同時設亮／暗色）；JPEG／PNG／BMP 以外的格式與帶 EXIF 方向的照片先經 `wallpaper_file` 存成檢視器所見的 JPEG 副本（轉正、sRGB、透明處鋪黑，放在 `%LOCALAPPDATA%/Imervue/wallpaper`，檔名隨來源的大小與修改時間變、只留最新一份；做不出副本時交原檔），因為 Windows 拿到解不開的檔案會回報成功卻把桌面變黑；失敗只記錄；右鍵選單在 `QThreadPool` 裡呼叫 |
| `local_origin.py` | 28 | `is_allowed_origin(origin)`：分辨瀏覽器裡的他站網頁與本機用戶端，桌寵 webhook 與 puppet VTS API 共用，擋掉跨站請求 |
| `local_llm.py` | 46 | 對本機 LLM 伺服器（預設 Ollama）送 JSON：`validate_base_url`（loopback 的 http 或任何 https）、`post_json`；圖片說明與桌寵對話共用，不依賴 Qt |
| `trash_ops.py` | 327 | **背景批次刪除**：`send2trash` 單次呼叫成本 ~0.27s，因此所有刪除必須走這裡，禁止 per-file 迴圈；刪除後各檔的 sidecar 同路處理（不計進結果）；`recycle_bin_holds`：Windows 上只有固定磁碟才交給 shell（記憶卡、USB 隨身碟、網路磁碟會被直接永久刪除），其餘留在原處算失敗；`purge_batch` 裡這類「送回收筒」的項目改為直接刪除（使用者已確認永久刪除）；`delete_outright(paths)`：確認後直接刪，資料夾連內容一起（`_unlink_chunk` 仍只刪檔案，culling 不會清空資料夾） |
| `file_transfer.py` | 251 | `transfer_into(sources, dest_dir, *, move)`：搬移／複製進資料夾一律走這裡；以 `batch_move_planner` 規劃不重複的檔名（依檔案系統大小寫規則），寫入前再確認目標不存在，絕不覆蓋（Move/Copy 對話框、雙窗格、staging tray 共用）；`carry_along(pairs, *, move)`：檔案搬移／改名／複製後帶走 sidecar（`IMG.xmp`、`IMG.JPG.xmp`、`IMG.JPG.annotations.json`；RAW+JPEG 共用的 `IMG.xmp` 改用複製），搬移時再呼叫 `follow_saved_data`；`carry_sidecars`：只搬 sidecar，worker 執行緒可用；`follow_saved_data(files, folders, *, keep_existing)`：設定（`path_metadata`）與圖庫（`image_index.move_paths`）的每路徑資料改指新路徑，資料夾展開成其下每個檔；`sidecars_of(path)`：只屬於這個檔的 sidecar（刪除時一起帶走）；`is_same_file(a, b)`：兩個路徑是否指同一個檔（Windows 只改大小寫的改名不算衝突） |
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
| `metadata_template.py` | 95 | IPTC/XMP 欄位範本（stationery pad；`photo_tokens` 給每張的代換值，Metadata Template 對話框用） |
| `path_metadata.py` | 140 | 設定裡以圖片路徑為鍵的資料（評分、色標籤、標題、描述、收藏、書籤、staging tray、參考圖釘選、最近圖片、標籤與相簿成員）跟著改名／搬移的檔案走：`move_path_metadata(mapping, *, keep_existing)` 同時改鍵（`a→b` 與 `b→c` 並存也只搬一次），新路徑上前一個檔案留下的資料清掉；`folder_moves` 把資料夾搬移展開成其下每個路徑；`stored_paths` |
| `recent_image.py` | 65 | 最近資料夾 / 圖片追蹤，上限由設定控制 |
| `tag_validator.py` | 159 | 標籤 / 相簿集合的完整性檢查與清理（`name_problem` 擋只差大小寫的新名稱；`plan_cleanup` / `clean_collection` 給 Tags & Albums 的 Clean Up…） |
| `tags.py` | 133 | 自訂標籤與虛擬相簿管理 |

### 6.4 `Imervue/multi_language/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `language_wrapper.py` | 140 | 單例 `language_wrapper`（外掛字串進來前先經 `translation_validation` 檢查、記錄問題，空字串或 `{placeholder}` 與英文不符的丟掉，改顯示內建文字）。內建 5 語言；`register_language()` 供外掛新增語言（重複註冊就地更新同一個字典），`merge_translations()` 供外掛補鍵（不覆寫既有鍵） |
| `english.py` | 2,992 | 英文字典（**正規來源**，其他語言以它為鍵集基準） |
| `traditional_chinese.py` | 2,957 | 繁體中文 |
| `chinese.py` | 2,957 | 簡體中文 |
| `japanese.py` | 2,970 | 日文 |
| `korean.py` | 2,968 | 韓文 |
| `translation_validation.py` | 156 | 字典進入 `LanguageWrapper` 前的驗證（缺鍵 / 空值 / placeholder；`register_language` 與 `merge_translations` 都會跑） |

> 第 6 個語言（西班牙文）以 `plugins/spanish_translation/` 形式提供，示範外掛語言註冊流程。

### 6.5 `Imervue/sessions/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `session_manager.py` | 249 | Session / Workspace 存檔與還原（開啟的資料夾、圖片、視圖狀態） |
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
| `contact_sheet_layouts.py` | 55 | 具名版面預設（格線 / 邊界 / 說明文字；Contact Sheet 對話框的 Layout 選單用它） |
| `web_gallery.py` | 262 | 靜態 HTML 相簿產生器，輸出自足資料夾（無外部 JS/CSS 相依）；縮圖經 `decode_image`（轉正、sRGB、RAW 可讀） |
| `slideshow_mp4.py` | 140 | 幻燈片 MP4 產生器（imageio + ffmpeg） |
| `slideshow_effects.py` | 101 | 純 NumPy 轉場效果（fade、dissolve、wipe…），逐幀決定性 |
| `cheat_sheet.py` | 237 | 可列印的快捷鍵速查表 PDF，隨當前語言產生 |
| `pdf_output.py` | 21 | `begin_pdf_painter`：在 `QPdfWriter` 上開啟 `QPainter`，目標無法寫入時丟 `OSError`（`QPdfWriter` 本身不丟例外，只讓 `begin` 回傳 `False`） |

### 6.9 `Imervue/image/`（純運算核心）

128 個模組、15,249 行，**只有 `info.py` import Qt**（用 `QMessageBox` 顯示圖片資訊對話框），其餘都可在 worker
執行緒直接呼叫，也是 `cli.py`、`mcp_server/`、`plugins/` 共用的演算法庫。

#### 非破壞性顯影核心（最重要的三個檔）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `recipe.py` | 707 | **`Recipe` dataclass**：一張圖的完整非破壞性編輯描述。`apply()` 是固定順序的管線，定義成具名階段表 `_STAGES`（名稱依序在 `STAGE_NAMES`）：幾何(旋轉/翻轉/裁切) → 白平衡 → 曝光 → 亮部/陰影 → 白場/黑場 → 亮度對比 → vibrance → 飽和度 → 色調曲線，再依 `extra` 套用 split toning / LUT / masks / levels / channel mixer / gradient map / threshold+posterize / lens flare / film grain / layer stack；`apply_stages(arr, first, last)` 只跑其中一段（GPU 顯影外掛把中間一段放到 GPU，其餘交給它）。另提供 `to_dict`/`from_dict` 往返、`recipe_hash`、`is_identity`、`exif_oriented` / `base_is_oriented()`（舊存檔缺這個鍵、又帶幾何時，仍套在未轉正的像素上），以及 `file_identity()`（md5(前、中、後各 4KB \| 檔案大小)，避免 mtime 改變就失效；只看前 4KB 時，同尺寸的未壓縮掃描檔會共用一個 identity）與 `file_identities()`（連同舊版只含前 4KB 的 identity，供遷移）；`turned_with_file(recipe, clockwise, size)`：檔案轉 90° 後的 recipe（翻轉互換、裁切框隨之旋轉；帶位置的 extra 不轉） |
| `develop_preview.py` | 149 | Modify 的純 CPU 預覽：共享不變來源、快取完整幾何／低解析像素、縮放局部遮罩座標；全尺寸模式與 `Recipe.apply` 像素相同，每個具名階段之間檢查取消 |
| `recipe_store.py` | 477 | 單一 JSON 檔支撐的記憶體 recipe 索引。以路徑為主的 API（`get_for_path`/`set_for_path`），並支援 **virtual copies**（同一張圖的具名 recipe 變體）；`rekey(old, new, transform)` 把 recipe 與虛擬副本搬到新 identity（不能全部轉換就不動），`identity_for(path)` 查詢前先把存在舊版 identity 下的 recipe 搬到新 identity（每個檔案只搬一次）；`carry_recipe(path, change, transform)` 在改寫檔案（EXIF、無損旋轉）後讓 recipe 跟著檔案；讀不到的 store 檔由 `UnreadableFileGuard` 看守，解不開的單筆原樣寫回 |
| `recipe_adjustments.py` | 125 | `Recipe.apply` 用到的逐通道色調調整 |
| `develop_backends.py` | 106 | 顯影後端登錄表：外掛以 `register(BackendProvider(key, probe, open))` 提供另一個 recipe 算繪器（`probe()` 回報標籤或 `None`、`open()` 建立 `DevelopRenderer`）；`available()` 列出這台機器能跑的後端（probe 丟 `RuntimeError`/`OSError`/`ImportError` 就略過），`open_renderer(key)` 開不起來回 `None`（`"cpu"` 保留給內建），`render(arr, recipe, renderer)` 沒有算繪器或算繪器丟 `RuntimeError` 時改用 `Recipe.apply`。批次匯出的「運算裝置」用它 |
| `recipe_diff.py` | 63 | 兩個 recipe 的 diff 與選擇性合併 |
| `develop_presets.py` | 102 | 具名顯影預設與批次 recipe 同步 |

#### 色調 / 顏色

`curves.py`(245) 曲線 · `tone_curve.py`(152) flag-based 曲線 · `levels.py`(95) 黑白場+gamma ·
`channel_mixer.py`(129) 3×3 矩陣 · `hsl_mixer.py`(109) 分頻 HSL · `split_toning.py`(67) ·
`gradient_map.py`(169) · `gradient_perceptual.py`(144) OkLab/OkLCH 感知混色 ·
`colormap.py`(63) 科學色階 · `lut.py`(265) Adobe `.cube` 讀取與套用（含 Resolve 的 `LUT_*_INPUT_RANGE`、BOM）·
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
`deflicker.py`(108) 縮時去閃 · `id_photo_sheet.py`(72) 證件照拼版 · `print_layout.py`(131) 列印拼版 PDF（reportlab；影像經 `decode_image`） ·
`multipage.py`(116) 多頁 PDF/TIFF 合併與拆分（`page_count`：頁數是影格數，但 PSD 的影格是同一張圖的圖層、相機 JPEG 的 MPF 預覽（Pillow 開成 MPO）不是一頁，都算 1 頁，只有 MPF 標成立體／多角度／全景的才有多頁；`in_place_save.frame_count` 也照這個算，右鍵「拆分頁面」也用它；合併時每頁經檢視器的 `decode_image` 轉正、轉 sRGB，以 `replace_atomically` 寫入；拆出的頁面經 `free_names` 一組挑名，不蓋掉上次拆出的頁面）

#### 遮罩 / 修補 / 圖層

`masks.py`(296) 筆刷/放射/線性遮罩 · `layers.py`(258) 疊加圖層合成 · `healing.py`(103) OpenCV inpaint ·
`clone_stamp.py`(137) · `inpaint.py`(54) 無模型擴散修補 · `segmentation.py`(130) 天空/前景/背景遮罩 ·
`saliency.py`(170) 啟發式顯著性 + 三分法裁切建議

#### 二值化 / 文件

`binarize.py`(49) Sauvola · `otsu.py`(59) · `steganography.py`(75) LSB 隱寫 ·
`ela.py`(53) 錯誤層級分析 · `copy_move.py`(84) 複製貼上偽造偵測

#### I/O、格式與快取

`raw_loader.py`(218) 省記憶體 RAW 載入；`raw_dimensions()` 只讀標頭取成像尺寸；`develop_raw(path, *, thumbnail)` 顯像成 8-bit RGB（嵌入預覽經 `upright_preview` 依 libraw `flip` 轉正，沒有可用預覽就半尺寸顯像；縮圖 worker 也用它），`LibRawError` 轉 `OSError`，不依賴 Qt（MCP 伺服器也用） · `in_place_save.py`(295) `can_rewrite_in_place(path)` / `in_place_format(path)` / `frame_count(path)`：能否把編輯後的像素寫回原檔（RAW、HEIC、JXL、SVG、多影格一律否）；旋轉、Modify 套用裁切、註解儲存都先問它；`carried_save_kwargs(source, fmt, path)` 把原檔的描述性 EXIF（`descriptive_exif`，白名單、不帶轉向與 TIFF 版面標籤）/ ICC / DPI / XMP / PNG 文字 / 壓縮設定（`webp_is_lossless`）轉成重存參數；`save_over_source(path, edited)` 把編輯後（已轉正、sRGB）的影像原子寫回原檔並帶回這些 metadata（不帶 ICC 與轉向），Modify 套用裁切／儲存註解、註解編輯器的 Save 與 AI 放大的覆寫都走它；`save_edited_copy(source, edited, target)` 寫新檔時也帶回來源的描述性 EXIF 與 DPI（同格式則全套）；`descriptive_exif(..., keep_location=False)` 另外去掉 GPS IFD 與 XMP，`keep_maker_note=False`（匯出與換格式的副本）去掉 MakerNote；`can_rewrite_exif` / `rewrite_exif(path, update)`：只換 EXIF 區塊（JPEG 走 `jpeg_exif`、WebP 走 `webp_exif`）並原子寫回，GPS 地理標記與 EXIF 編輯器共用 · `export_metadata.py`(84) 匯出的 metadata 政策：`export_save_options(source, policy)` 依「全部／位置以外（預設）／無」回傳 `{"exif": bytes}`，不帶轉向與像素尺寸 · `jpeg_orientation.py`(65) `set_jpeg_orientation(data, code)`：只改 JPEG 的 EXIF 轉向值（有標籤就原地改 2 bytes，沒有才重組 EXIF 或新增 APP1 段），像素與其他 metadata 不動 · `webp_exif.py`(105) `update_webp_exif(data, update)`：換掉 WebP 的 `EXIF` chunk（簡單格式先升級成帶 `VP8X` 的延伸格式、畫布與 alpha 旗標取自位元串流），影像資料位元組不變 · `jpeg_exif.py`(169) 只靠 Pillow 改 JPEG 的 EXIF：`header_segments` / `exif_segment` / `replace_exif_segment` 換掉 APP1 段、`serialize_exif(exif, original)` 補回 `Image.Exif.tobytes` 會丟的 IFD1 縮圖、`update_jpeg_exif(data, update)` 一次做完（像素位元組不變） · `exif_types.py`(121) `restore_types(payload, original)`：把 Pillow `Exif.tobytes` 猜錯的項目型別（UNDEFINED 被寫成 BYTE、非負 SRATIONAL 被寫成 RATIONAL）依 EXIF 規格表或原檔改回，只換同元素大小的型別，值與位移不動；`jpeg_exif`、`export_metadata`、`in_place_save` 序列化 EXIF 都經過它 · `exif_fields.py`(153) EXIF 編輯器的純邏輯：`EDITABLE_FIELDS`、`read_fields` / `apply_fields`（UTF-8 文字標籤、依區塊位元組序的 UNICODE UserComment，空白即移除）、`can_edit`（JPEG、WebP）、`save_fields`（經 `in_place_save.rewrite_exif` 原子寫回） · `dimensions.py`(47) `image_dimensions(path)`：讀檔頭取像素尺寸的共用入口（RAW 走 libraw，Pillow 會回報內嵌預覽的尺寸）；`probe_image(path)` 另回報格式與模式（RAW 為副檔名與 `RGB`），CLI `info` 用它 · `heif_support.py`(60) HEIC / HEIF 經選用的 pillow-heif（1.x 起不處理 AVIF）· `avif_support.py`(18) AVIF 由 Pillow 內建外掛讀寫，`avif_available()` 回報這個 Pillow 有沒有 libavif · `jxl_support.py`(50) ·
`formats.py`(86) 能開的副檔名唯一來源：`JPEG_EXTENSIONS`（`.jpg`／`.jpeg`／`.jpe`／`.jfif`／`.jif`，類型篩選、影像整理、各批次工具與 Paint 的 JPEG 判斷都用它）、`PILLOW_EXTRA_EXTENSIONS`（ICO、TGA、DDS、QOI、JPEG 2000、Netpbm、PCX、PSD 的合併圖：Pillow 自己讀得了，只供檢視，原地存檔不認得它們）、`RAW_EXTENSIONS`（LibRaw 讀得了的 23 種相機 RAW；RAW+JPEG 堆疊也用它）、`STILL_IMAGE_EXTENSIONS`（媒體庫）、`VIEWER_EXTENSIONS`（再加影片；檢視器、檔案樹、拖放、開啟對話框）、`RASTER_EXTENSIONS`（去掉要 Qt 的 SVG；CLI 與 MCP）、`ensure_pillow_opener(ext)` ·
`save_formats.py`(106) 輸出格式中繼資料與 `save_image`（寫到路徑一律原子替換）；HEIC、JXL 依選用套件，AVIF 依 Pillow 有無 libavif 決定是否提供· `optimize.py`(73) 目標檔案大小編碼 ·
`export_presets.py`(94) 匯出預設包 · `video_frames.py`(231) 影片解碼原語（瀏覽器與外掛共用） ·
`pyramid.py`(38) `DeepZoomImage` 金字塔 · `tile_manager.py`(94) 圖磚 LRU 快取與淘汰 ·
`thumbnail_disk_cache.py`(242) 縮圖磁碟快取（鍵含 `_KEY_VERSION`，快取像素的意義改變時遞增；相機 RAW 另用 `_RAW_KEY_VERSION`，只讓 RAW 的項目失效） · `folder_index.py`(91) 每資料夾圖片清單快取（只用於依解析度排序：其他排序直接以 `scandir` 掃描，比逐檔確認快取的路徑還在快得多） ·
`read_errors.py`(15) `IMAGE_READ_ERRORS`：Pillow 讀圖失敗會丟的例外（`OSError`、`ValueError`、`SyntaxError`（損壞的 WebP EXIF）、`DecompressionBombError`）

#### 中繼資料

`xmp_sidecar.py`(611) XMP sidecar 讀寫（跨編輯器互通）；`load` 沒有 sidecar 時讀檔案內嵌的 XMP 封包（JPEG／PNG／WebP／TIFF／CR3／RW2／RWL／ORF／RAF）再以 EXIF `Rating`／`RatingPercent` 補評分（`load_embedded`，經 `metadata_sync.percent_to_rating`）；找 `foo.xmp`（Adobe），只有 `foo.jpg.xmp`（darktable／digiKam）時讀寫它；`label_color` 把 Lightroom（`Red`）與 Bridge（`Select`）的標籤對到 Imervue 顏色，匯出照 Lightroom 寫法並保留同色的既有用字；`xmp:Rating` -1（Lightroom／Bridge／darktable 的拒絕）與圖庫的挑片 reject 雙向對應；`save` 合併進既有檔：只換評分／標籤／標題／描述／關鍵字／作者，其他編輯器寫的內容（RAW 顯影設定等）與命名空間前綴保留，無法解析的檔丟 `UnreadableSidecarError`（`OSError`）不覆寫 · `metadata_sync.py`(76) XMP↔EXIF 評分調和 ·
`raw_exif.py`(311) Pillow 打不開的 RAW 容器的 EXIF：CR3 的 `CMT1`／`CMT2`／`CMT4` 盒、RW2／RWL／ORF（換掉魔術數字後由 Pillow seek 讀取，RW2 去掉 Panasonic 私有標籤但保留 ISO）、RAF 內嵌 JPEG 的 APP1；`raw_xmp` 讀相機內嵌的 XMP（CR3 的 Adobe UUID 盒、TIFF tag 700、RAF JPEG XMP APP1），供相機內評分匯入；UUID 盒支援 64 位元大小並拒絕截斷與不完整標頭；只 seek 到中繼資料 · `gps.py`(84) EXIF GPS 擷取 · `gps_geotag.py`(84) 寫入（JPEG / WebP 經 `in_place_save.rewrite_exif`，不需 piexif） · `reverse_geocode.py`(151) 離線逆地理編碼 ·
`geo_keywords.py`(52) 地點寫進 XMP 關鍵字 · `face_detection.py`(148) 人臉偵測與人物標籤（Haar，需 OpenCV 4；缺時丟 `FaceDetectorUnavailableError`；cascade XML 由 Python 讀入後從記憶體載入，OpenCV 裝在非 ASCII 路徑下也能用） ·
`shown.py`(76) `as_shown(img, code=None)`：檢視器看到的樣子（先依內嵌描述檔轉 sRGB、再依 EXIF 轉正）；`open_shown(path)` 不靠 Qt 解整個檔案（相機 RAW 經 `develop_raw` 顯像，其餘先註冊 HEIC / JXL opener），`load_shown_rgb(path)` / `load_shown_rgba(path)` 建在它上面（16 位元與浮點灰階先縮放）；`as_shown_8bit(img, code=None, mode="RGBA")` 是送到螢幕的 8 位元版本，16 位元與浮點灰階先經 `to_eight_bit` 縮放、不讓 `convert` 截斷成全白（清單檢視、懸停預覽、比較、拖出、重複偵測、影像檢查、時間軸、圖層疊加、參考圖、CLIP 用它），`as_shown` 本身保留位元深度（EXIF 清除的副本仍是 16 位元）；預覽、工具輸入、匯出、Modify、註解、合成、OCR、CLIP、MCP、Paint 的姿勢圖／素材／參考圖都走它 · `high_bit_depth.py`(67) `to_eight_bit(img)`：16 位元灰階（`I;16` 各位元組序）依 0..65535 縮成 8 位元，32 位元整數在 16 位元內時同樣縮放、否則最小到最大拉伸，浮點在 0..1 內對應黑到白、否則拉伸，NaN 與無限大顯示黑色；其他模式原樣傳回（Pillow 的 `convert` 對這些模式是截斷，16 位元灰階掃描幾乎全白） · `color_profile.py`(86) `to_srgb(img)`：內嵌 ICC（Display P3、Adobe RGB、CMYK）轉 sRGB；灰階（`L`／`LA`）的灰階描述檔（Dot Gain 20%、Gray Gamma 1.8）先算成 256 階曲線（`_grey_curve`）再套到灰階值，結果仍是灰階；無描述檔、sRGB 或描述檔與模式不符時原樣回傳，transform 與曲線依描述檔快取 · `exif_merge.py`(86) `read_exif(path)`（任何格式的 EXIF，子 IFD 在檔案開著時讀好，RAW 容器經 `raw_exif`；GPS、拍攝時間、Token 重新命名、中繼資料匯出都用它）、`merged_exif(img 或 Exif)`、`get_exif_data(path)`（以標籤名稱回傳、HEIC／JXL 先註冊 opener；不依賴 Qt，MCP、圖庫、面板共用）：IFD0 + Exif 子 IFD、GPS 巢狀，與 Pillow 的 `_getexif()` 同形狀但每種格式都有 · `info.py`(171) 圖片資訊組裝與對話框；EXIF 由 `exif_merge.get_exif_data` 讀，HEIC / JXL 也讀得到

#### 分析 / 品質

`histogram.py`(103) · `statistics.py`(65) 逐通道統計 + CSV · `scopes.py`(66) 波形/RGB parade ·
`quality_metrics.py`(88) 無參考品質 · `quality_score.py`(62) 篩選用技術評分 ·
`perceptual_hash.py`(157) pHash 與近似重複分組（`upright`：先依 EXIF 轉正再雜湊，未帶標籤者雜湊值不變；`grey_levels`：16 位元與浮點灰階先經 `to_eight_bit` 縮放再轉 8 位元灰階，dHash、aHash 與圖庫的 pHash 共用）

#### 其他

`browser_state.py`(400) 共用瀏覽狀態（過濾規格、中繼資料索引、遺失檔案偵測與重定位）·
`batch_move_planner.py`(114) 無碰撞批次搬移規劃 · `animation_edit.py`(95) GIF/APNG 反轉/回力鏢/速度 ·
`caption.py`(91) 本地視覺 LLM 產生 alt-text（經 `system/local_llm.post_json`；EXIF 編輯器的 Describe 用它） · `ocr.py`(159) Tesseract · `portrait_retouch.py`(177) ·
`speech_*`／`text_*` 相關在 `paint/`

### 6.10 `Imervue/gpu_image_view/`

OpenGL 檢視器。`GPUImageView(QOpenGLWidget)`（774 行）只保留 GL 生命週期與 Qt 事件覆寫，
其餘拆成約 40 個協作者。有兩種顯示狀態：**tile wall**（縮圖牆）與 **deep zoom**（單張深縮放）。

#### 檢視器主體與渲染

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `gpu_image_view.py` | 774 | 主 GL widget 與 Qt 事件轉發；cancel 退休 viewport queue／pending markers，實際解碼仍由 pool 持有到結束；快捷鍵橋接與下面四個 mixin |
| `view_state_init.py` | 279 | 建構子狀態初始化（tile grid、deep zoom、互動、顯示）；追蹤 cached tile 最大尺寸供 O(1) viewport bound，不碰 GL |
| `deep_zoom_loading.py` | 306 | `DeepZoomLoadingMixin`：開一張圖的狀態機（預覽解碼→完整解碼、套 recipe、過期結果丟棄、失敗重試一次、首幀通知；全尺寸圖上螢幕後分派外掛的 `on_image_loaded`） |
| `shown_file_watch.py` | 87 | `ShownFileWatch`：deep zoom 顯示中那張圖的檔案監看；`load_deep_zoom_image` 每次載入時 `follow` 並記下大小與修改時間，之後每 `POLL_MS`（500 ms）用 `os.stat` 量一次，變了之後又連續一次沒變（寫完了）才經 `_reload_rewritten_image` 重新載入並重解縮圖；外部編輯器就地覆寫、寫副本再改名蓋過去、保留原修改時間的存檔都看得到。刻意不用 `QFileSystemWatcher` 監看檔案：在 Windows 上它讓其他程式改名蓋過去的存檔約一成被拒絕存取（實測 600 次 54 次），資料夾監看與 `os.stat` 都不會 |
| `view_fitting.py` | 304 | `ViewFittingMixin`：fit window/width/height、新圖初始視圖、版面／換螢幕／載入後的 settle 重算（`settle_poll`） |
| `prefetch_memory.py` | 127 | `PrefetchMemoryMixin`：相鄰圖預取與 RSS 壓力清理；CPU 陣列以視窗 RAM 配額判斷，不混用 VRAM |
| `view_mouse.py` | 148 | `ViewMouseMixin`：滾輪縮放（含放大鏡倍率、格線與閱讀模式捲動）、按壓／拖曳／放開、雙擊切換 |
| `gl_renderer.py` | 349 | 現代 OpenGL 渲染器（VBO + GLSL），shader 編譯失敗時退回 immediate mode |
| `tile_grid_renderer.py` | 282 | 只依共享 TileViewport 候選列／欄繪製；繪製、載入與淘汰使用同一 frame geometry，失敗也清除 transient geometry；零面積 tile／placeholder 不繪製 |
| `tile_viewport.py` | 112 | 純運算格線 viewport、列／欄 buffer 候選、cell origin 與 cached 最大尺寸；繪製／載入／淘汰共用 |
| `thumbnail_queue.py` | 92 | 純運算 bounded 工作計畫；捲動替換 unstarted work、source membership 索引、current workload 進度、filmstrip／retry 與 full-size extent 的 bounded backfill |
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
| `input_controller.py` | 437 | 滑鼠／滾輪／手勢、minimap、框選與平移；可見 tile 命中後以載入索引驗證路徑與 Deep Zoom 位置 |
| `key_input_handler.py` | 303 | 鍵盤事件路由；Esc 回縮圖牆保留有效 viewport queue、warm cache 與 grid offsets；cold／stale 與尺寸變更仍初始化重載 |
| `key_action_dispatcher.py` | 359 | 把 shortcut_manager 解析出的**動作名稱**表格化派送到檢視器操作 |
| `browse_features.py` | 195 | Deep-zoom 瀏覽行為：filmstrip 導航、閱讀模式捲動、平移夾限 |
| `history_controller.py` | 119 | Alt+←/→ 瀏覽歷史堆疊 |
| `drop_handler.py` | 75 | 拖放檔案/資料夾開啟 |
| `clipboard_paste.py` | 109 | 剪貼簿貼上圖片並插入模型 |
| `hover_preview_binding.py` | 55 | 縮圖懸停預覽彈窗綁定 |
| `cull_actions.py` | 128 | 色標籤與 pick/reject 挑片狀態套用；`resolve_cull_targets` 決定按鍵作用的照片：多選的格子 → deep zoom 的圖 → 方向鍵焦點（焦點框顯示時）→ 滑鼠下的格子，評分與我的最愛也用它；`apply_color_label`／`apply_cull_state` 可用 `targets=` 指定照片（清單檢視的選取列） |
| `status_info.py` | 76 | 狀態列欄位組裝 |

#### 資源管理與效能

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `tile_loader.py` | 649 | bounded viewport 縮圖排程與 generation／O(1) membership 驗證；visible buffer／filmstrip／retry 共用 slots，重複請求合併、source rewrite 另排一次；每 4 秒背景 stat 與清單 refetch 保留 |
| `tile_textures.py` | 136 | incoming mipmap 容量前先淘汰畫面外貼圖；使用共享 viewport 候選計算精確 cached visibility，GL 刪除成功才記帳 |
| `tile_wall_loading.py` | 99 | 牆面 loading 狀態與轉圈幾何（大資料夾/網路磁碟不再空白） |
| `prefetch_scheduler.py` | 235 | QObject 預取協作者：實際 pyramid bytes／解碼 ticket 共用 RAM 配額、過期退休與 queued terminal identity 驗證、owner destruction 回收未送達結果 |
| `deep_zoom_priority.py` | 40 | 圖磚渲染優先權 |
| `ram_budget.py` | 135 | 純運算、thread-safe RAM admission；sensor/header 解碼估算、actual NumPy buffer 去重、cache／reservation 原子轉移、process cap 與公平視窗份額、optional psutil fallback |
| `vram_budget.py` | 67 | 純函式：使用者覆寫值 + 夾限策略 |
| `vram_detect.py` | 104 | 廠商 GL 探測實際 VRAM（`glGetIntegerv`） |
| `memory_pressure.py` | 246 | 狀態列記憶體壓力指示器（綠/黃/紅 + 百分比，點擊清快取） |
| `worker_pools.py` | 110 | 執行緒池分池策略：縮圖爆量不再和 deep-zoom worker 搶資源 |
| `signal_coalescer.py` | 92 | 次幀 signal 合併，避免 N 個縮圖回呼各觸發一次進度更新 |
| `cvd_view_mode.py` | 98 | 色覺障礙模擬（view-time 模組級開關，載入時套用） |

#### `gpu_image_view/images/` — 載入層

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `image_loader.py` | 554 | **核心載入路徑**：`decode_image_file()`（解碼成檢視器看到的 RGBA，不套 recipe 與檢視模擬；Modify 與 Paint 用它當底圖）、`decode_image(path, *, max_edge=None)`（同一份解碼成 Pillow 影像，全不透明轉 RGB，可縮到長邊；輸出與預覽共用）、`load_image_file()`（RAW/SVG/HEIF/JXL/一般點陣 → RGBA，可套 recipe）、`LoadDeepZoomWorker`（背景建金字塔；預取模式在 worker 讀 header、先預留解碼 scratch、queued 結果保留 actual bytes，所有退出路徑都發 completed）、`FolderScanWorker`（分批掃描大資料夾；兩種掃描都經 `_is_listed` 跳過隱藏檔，直接開啟的隱藏檔仍加進清單；依解析度或拍攝日期這類要逐檔讀標頭的排序（`_HEADER_SORTS`）走 `folder_index` 快取）、`open_path()` 對外入口；點陣圖（大圖與縮圖）先經 `to_eight_bit` 把 16 位元與浮點灰階縮成 8 位元、再轉 sRGB，並依 EXIF Orientation 轉正（舊 recipe 帶幾何時例外，見 `Recipe.base_is_oriented`）；能開的副檔名取自 `image/formats.py` |
| `load_thumbnail_worker.py` | 149 | 單張縮圖解碼 `QRunnable`（點陣圖交給 `image_loader._load_raster_thumbnail`／`_load_raster`，和檢視器同一條解碼：EXIF 轉正、sRGB、16 位元灰階縮放、巨圖一次一張的 `decode_slot`；RAW 取 `raw_loader.develop_raw(thumbnail=True)` 的轉正預覽） |
| `image_model.py` | 24 | `ImageModel`：目前資料夾的圖片路徑清單 |
| `prefetch.py` | 178 | 預載視窗大小與方向追蹤（`NavigationDirectionTracker`） |

#### `gpu_image_view/actions/` — 檢視器動作

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `delete.py` | 227 | **軟刪除 / 復原**：先隱藏不落地，`commit_pending_deletions()` 在關閉時一次送 `trash_ops`，回傳留在原處的檔案 |
| `select.py` | 239 | 上下張切換（含 wrap-around toast）、跳到上/下一個有圖的兄弟資料夾（和資料夾樹同一個順序：自然排序、略過隱藏資料夾）、框選圖磚；`selected_in_view_order` / `selection_or_all` 依瀏覽順序回傳選取（`selected_tiles` 是 set） |
| `batch_ops.py` | 289 | 批次重新命名（經 `batch_rename.rename_files`）/ 移動 / 複製（經 `file_transfer.transfer_into`，不覆蓋）/ 旋轉（逐檔走 `lossless_rotate`） |
| `compare_dialog.py` | 601 | 圖片比對：並排(2/4)、疊加(alpha)、差異(gain-boost) |
| `slideshow.py` | 211 | 幻燈片播放控制器 + 對話框 |
| `animation_player.py` | 341 | GIF / APNG / Animated WebP 播放器；只有 `_ANIMATED_FORMATS`（GIF、PNG、WebP、AVIF、JXL）會播放，多頁 TIFF（`_PAGED_FORMATS`）是 `paged`：不播放、用逐格鍵翻頁、OSD 顯示「第 2/5 頁」（`anim_indicator_text`），其他 Pillow 回報多格的檔案（相機 JPEG 的 MPF 預覽被開成 MPO、PSD 的圖層）不當動畫；APNG 的預設影像（Pillow 的第 0 格、`default_image`）不播放，逐格與串流都從第 1 格起算（`_first`），載入後先把第一格放上畫面；每格和靜態圖一樣經 `to_eight_bit` 與 `to_srgb`；解碼後超過 `_DECODED_FRAMES_BUDGET`（512 MB）就改為串流：留住檔案位元組（BytesIO，不鎖檔），播到哪格才解哪格，只快取最後一格 |
| `search_dialog.py` | 280 | 檔名即時搜尋 |
| `goto_dialog.py` | 102 | Ctrl+G 跳至第 N 張 |
| `keyboard_actions.py` | 343 | 鍵盤快捷動作實作（Ctrl+C 複製檢視器顯示的金字塔底層，沒有時才解碼檔案；評分 `rate_current_image` 與我的最愛 `toggle_favorite` 作用在 `resolve_cull_targets` 的照片上，全都已是那個狀態時清除；兩者都可用 `targets=` 指定照片） |
| `lossless_rotate.py` | 115 | 90° 旋轉檔案：JPEG 只改 EXIF 轉向標籤（`jpeg_orientation`，不需 piexif、其餘位元組不變）；其他格式從檢視器看到的影像轉後原子重存，以 `in_place_save.carried_save_kwargs` 帶回 metadata 與壓縮設定；RAW、多影格等無法完整寫回的檔案拒絕處理；經 `recipe_store.carry_recipe` 讓 Modify recipe 跟著轉（`recipe.turned_with_file`） |
| `drag_out.py` | 75 | 從圖磚拖出檔案 URI 到 Explorer / Chrome / Discord |
| `recipe_commands.py` | 65 | `EditRecipeCommand`：顯影編輯的 undo/redo（存新舊 recipe dict） |

### 6.11 `Imervue/library/`

SQLite 支撐的跨資料夾相片庫索引與整理演算法（純邏輯，無 Qt）。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `image_index.py` | 752 | **核心 SQLite 索引**：跨資料夾中繼資料、註記、階層標籤、smart album、pHash、挑片旗標；`move_paths(mapping, *, keep_existing)` 在一個交易內把 images／notes／culling／image_tags 的路徑改到新位置（檔案改名、搬移、重新連結時），`stored_paths()` 列出所有表的路徑 |
| `scanner.py` | 273 | 背景掃描器，走訪 library roots 填索引（走訪沿用 `maintenance.scan_image_files`，HEIC / JXL 先註冊解碼器）；增量：mtime + size 相同就跳過（要 pHash 而列上沒有時不跳過，補算）；要讀的檔在 `probe_workers()` 條執行緒（核心數 − 1，最多 8）上解碼、不持 DB 鎖，每 256 檔一個交易寫入；寫入時尺寸與 pHash 以這次讀到的為準（`set_decoded_fields`，沒讀就清空）；JobState 只在 chunk commit 後紀錄成功；exact-path failure retry，cancel hook 接共享生命週期 |
| `maintenance.py` | 46 | 索引與檔案系統對帳；`scan_image_files()` 經 `list_images(recursive=True)` 收 `formats.STILL_IMAGE_EXTENSIONS`，跳過隱藏檔與隱藏資料夾（磁碟根目錄的 `$RECYCLE.BIN`、Mac 的 `.Trashes`），也是掃描器的走訪 |
| `smart_album.py` | 361 | Smart Albums：保存查詢並重新套用 |
| `search_query.py` | 219 | 自由文字查詢 → Smart Album 規則 |
| `album_io.py` | 74 | Smart Album 匯出 / 匯入為可攜 JSON |
| `clip_search.py` | 373 | CLIP 語意搜尋（「找出符合這句話的照片」）；後端是 `clip_onnx` 的 ONNX 模型（不用 torch），快取另記模型 id，別的模型寫的快取不載入；向量連同檔案的大小與修改時間快取在 `clip_cache.npz`，`is_current` 判斷可沿用，`query_text(within=)` 只在指定路徑裡排名 |
| `clip_onnx.py` | 232 | CLIP ViT-B/32 的 onnxruntime 後端：Hugging Face `Xenova/clip-vit-base-patch32` 固定 commit 的 int8 量化文字 / 影像編碼器（約 150 MB，首次使用下載）；影像前處理（短邊 224 bicubic、中心裁切、OpenAI mean/std）；provider 只用 CUDA（一定是獨顯）或 CPU，不用 DirectML（混合筆電預設裝置常是內顯）；`rank_labels` 零樣本標籤；`default_embedder()` 讓語意搜尋與 Auto-Tag 共用一份模型 |
| `clip_tokenizer.py` | 151 | 純 Python 的 CLIP byte-level BPE 斷詞器（讀模型的 `vocab.json` / `merges.txt`，NFC、空白合併、小寫、依 Unicode 類別切段、`<|startoftext|>` / `<|endoftext|>` 任何位置都先切出），與 `tokenizers` 參考實作 5000 句隨機字串逐 id 相同 |
| `auto_tag.py` | 153 | 啟發式內容分類；CLIP 模型已下載時改用 `clip_onnx` 零樣本標籤（最多三個，提示詞向量依模型與標籤組快取），Auto-Tag 自己不觸發下載 |
| `phash.py` | 85 | 64-bit DCT pHash（轉正後經 `perceptual_hash.grey_levels` 取灰階） |
| `bloom_filter.py` | 150 | 純 Python bloom filter，快速判斷「看過這個指紋沒」 |
| `dedupe_resolver.py` | 60 | 從一組重複中挑出該保留的那張 |
| `stacks.py` | 89 | RAW + JPEG 配對堆疊 |
| `events.py` | 89 | 依拍攝時間間隔把照片分成「事件」 |
| `calendar_index.py` | 158 | 依拍攝日分桶，供 Calendar View；`capture_datetime()` 是讀拍攝時間的共用入口（Exif 子 IFD → IFD0 → 修改時間），整理工具、時間軸、圖片淨化都走它 |
| `capture_time.py` | 99 | 批次位移 EXIF 時間戳（`exif_capture_time` 只讀 EXIF、`write_capture_time` 就地改寫三個日期；Edit Capture Time 對話框用） |
| `date_import.py` | 101 | 依拍攝日匯入到日期資料夾 |
| `gpx_geotag.py` | 132 | GPX 軌跡對時取得座標（`match_photos` 對整批；Geotag from GPX Track 對話框用） |
| `auto_cull.py` | 61 | 依銳利度自動剔除模糊（每張經檢視器的 `decode_image` 讀成最長邊 512 px：RAW 走內嵌預覽、HEIC 可讀、已轉正；讀不了的跳過） |
| `quality_cull.py` | 58 | 依綜合技術品質剔除（每張經檢視器的 `decode_image` 讀成最長邊 512 px：RAW 走內嵌預覽、HEIC 可讀、已轉正；讀不了的跳過） |
| `group_cull.py` | 95 | 每組保留最佳一張 |
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

175 個檔、35,158 行 —— 全部是 Qt 前端。多數對話框只是外殼，數學在 `image/`。

#### 主視窗組件（非對話框）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `develop_panel.py` | 920 | **Modify 分頁面板**：工具列、內嵌 `AnnotationCanvas`、來源解碼／存檔與 recipe 提交。背景預覽由 `DevelopPreviewMixin` 協作，右側面板與 splitter 尺寸由既有 mixin 提供；發出 `recipe_committed` signal |
| `develop_preview.py` | 169 | `PreviewScheduler`：每面板至多一個低解析與一個完整 worker，最新請求覆蓋等待項目，版本與取消雙重守衛；QImage 在背景準備，UI queued signal 安装；sender 由 application 持有至 queued delete |
| `develop_preview_panel.py` | 132 | `DevelopPreviewMixin`：拖曳低解析／防抖完整品質、幾何座標與狀態、過期結果檢查；儲存／破壞性效果先取得完整像素，避免保存暫時預覽 |
| `develop_right_panel.py` | 331 | `DevelopRightPanelMixin`：Modify 右側屬性面板（裁切、繪圖屬性、標註存檔、顯影滑桿、recipe 重設／復原）與預覽工作／失敗標籤，每段一個 `_build_*` 方法 |
| `modify_splitter.py` | 131 | `ModifySplitterMixin` + 純函式 `canvas_splitter_sizes()` / `splitter_is_alive()`：把剩餘寬度給中央畫布，並在換螢幕時以 `settle_poll` 持續重算 |
| `annotation_canvas.py` | 860 | 註解畫布 widget + `QUndoCommand`、座標／選取／文字／鍵盤；可用低解析 QImage 配完整幾何，原生底圖改變訊號與完整品質 resolver 保護烘焙／存檔；繪製、裁切、馬賽克／模糊由 mixin 提供 |
| `annotation_drawing.py` | 417 | `AnnotationDrawingMixin`：各種標註與九種筆刷的 QPainter 繪製、選取控點、裁切遮罩；`HANDLE_SIZE` |
| `annotation_crop.py` | 172 | `AnnotationCropMixin`：裁切工具的比例、控點命中與拖曳；`handle_cursor()` |
| `annotation_destructive.py` | 252 | `AnnotationDestructiveMixin` + `_BakeDestructiveCommand`：先解析完整品質，再顯示馬賽克／模糊強度對話框、區域預覽與烘焙進底圖 |
| `annotation_dialog.py` | 805 | macOS Preview 式標註對話框（編輯器版面、工具、快捷鍵、狀態列） |
| `annotation_file_actions.py` | 202 | `AnnotationFileActionsMixin`：標註的存檔／另存（`.tmp` 原子寫入；寫回原檔時經 `save_over_source` 保留 metadata）；模組層 `ask_save_as_path`（無法寫出的副檔名補 `.png`）/ `write_annotated` 也供 Modify 分頁在 RAW／HEIC／多影格上改存副本、複製到剪貼簿、存／讀 `.imervue_annot.json` 專案 |
| `dialog_rows.py` | 135 | 批次／資料夾／單張工具對話框共用的列與路徑挑選：`save_path_into()` / `open_path_into()`（檔案對話框選到的路徑寫入輸入框；`save_path_into` 也回傳它，取消時回傳 None）、`may_replace()`（目標已存在又不是存檔對話框確認過的，經 `ask_to_replace()` 問要不要取代，預設不取代）、`confirm(parent, title, text)`（刪除、清空、覆寫前的是／否確認，預設「否」；Qt 自己會把「是」設成預設，所有 `QMessageBox.question` 都要指定預設按鈕，`test_questions_default_to_no` 守著）、`image_save_filter()`（PNG / JPEG / TIFF 存檔篩選）；`path_browse_row()`（路徑輸入框＋瀏覽…）、`folder_picker_row()`（再加前置標籤）、`quality_slider()`（「品質：N」標籤＋0–100 滑桿）、`action_button_row()`（靠右按鈕列）；檔案對話框與顯示切換由呼叫端負責 |
| `color_swatch.py` | 46 | `ColorSwatchButton`：以目前顏色填滿的按鈕，點擊開啟 `QColorDialog`，`rgb()` 讀回（邊框與說明文字對話框用） |
| `file_filters.py` | 38 | 檔案對話框篩選字串：`name_filter(label, exts)`、`translated_filter(key, default, exts)`、`image_filter(exts)`（標籤走語言字典，副檔名樣式留在程式）；`viewer_filter()` 直接取 `formats.VIEWER_EXTENSIONS`，開啟圖片與重新定位遺失檔案的對話框因此列出檢視器能開的全部格式 |
| `slider_spin.py` | 75 | `make_slider_spin()` / `link_slider_spin()`：滑桿與數字框雙向同步（訊號阻斷、每次編輯只回報一次）；取代各面板手寫的 `blockSignals` 配對 |
| `main_window_filter.py` | 262 | `MainWindowFilterMixin`：檢視器上方的篩選列（檔名／副檔名／標籤／日期／評分）、套用並盡量保住目前圖片、狀態存回 |
| `main_window_missing.py` | 160 | `MainWindowMissingMixin`：遺失檔批次處理（依檔名自動配對、移除、整個根目錄搬移）與每路徑中繼資料的遷移 |
| `main_window_folders.py` | 306 | `MainWindowFoldersMixin`：輪詢目前資料夾（回到前景時立刻檢查並 refresh 資料夾樹）、重整清單時保住 deep-zoom 圖、資料夾消失時的復原、每資料夾工作階段存取 |
| `main_window_tabs.py` | 219 | `MainWindowTabsMixin`：資料夾分頁的開關、移動、循環、右鍵選單，讓分頁、檔案樹與檢視器指向同一路徑 |
| `main_window_screens.py` | 205 | `MainWindowScreensMixin`：視窗幾何存回（落在仍存在的螢幕上）、跨不同縮放比例螢幕時重算、移動／縮放後重新適配 |
| `main_window_views.py` | 124 | `MainWindowViewsMixin`：雙視窗、多螢幕視窗、劇院模式 |
| `main_window_status.py` | 94 | `MainWindowStatusMixin`：狀態列訊息、掃描進度條、圖片資訊標籤 |
| `main_window_layout.py` | 372 | `MainWindowLayoutMixin`：主視窗建構子呼叫的 `_build_*`（檔案樹、檢視器欄、圖片分頁列、視圖堆疊、工作區分頁、狀態列）；選用分頁 Puppet／Desktop Pet 只在開著時加一個空頁，第一次打開才建工作區（`_build_puppet_workspace`、`_build_pet_workspace`，後者另建系統匣圖示並重接外掛的 pet hook；寵物設定為啟動時顯示就在啟動時建） |
| `optional_tabs.py` | 34 | 選用分頁的設定：`tab_enabled`／`set_tab_enabled`（`puppet_tab_enabled`、`desktop_pet_tab_enabled`，預設開、下次啟動生效）、`pet_shows_on_launch` |
| `main_window_browse.py` | 147 | `MainWindowBrowseMixin`：縮圖牆／清單切換、清單啟動、從 deep zoom 返回、縮圖尺寸與間距；`refetch_list_rows` 把磁碟上變了的路徑轉給清單檢視；`delete_list_selection` 走縮圖牆的 `delete_selected_tiles`（可復原、之後整批進回收筒），`undo_from_list` 執行檢視器的 undo 後重建清單；`escape_from_list`：清單裡的 Esc 先離開全螢幕，否則回縮圖牆；`mark_list_selection` 把選取列交給評分、最愛、挑片、色彩標籤的同一組函式（`targets=`） |
| `annotation_models.py` | 603 | 註解資料模型 + **無 Qt 的 PIL 渲染路徑**（可在 worker / 測試中使用）；`jitter_seed()` 給噴槍／炭筆／蠟筆穩定的亂數種子（CRC32，不受行程的 str hash 隨機化影響） |
| `file_tree_view.py` | 944 | `_FileTreeView`：左側檔案樹，含快捷鍵與右鍵選單、重名處理；model 不監看資料夾，`refresh()` 由主視窗在回到前景與資料夾變更時呼叫 |
| `file_tree_sort.py` | 149 | `FileTreeSortProxy`：`QFileSystemModel` 沒有的「建立日期」等具名排序鍵 |
| `folder_thumbnail_model.py` | 173 | `QFileSystemModel` 子類，用資料夾第一張圖當樹狀圖示（`folder_preview_path` 經 `list_images`：自然排序、跳過 `._` 等隱藏檔，和縮圖牆的第一張一致；取代不穩定的 Windows shell 縮圖） |
| `image_list_view.py` | 723 | 清單檢視（`QTableView`，縮圖牆的替代）；名稱自然排序，使用者點選的排序欄在 `set_paths` 重建後照樣套用（沒點過時維持檢視器的順序、不顯示箭頭）；點星等欄依點到的星（`star_at`）評分；`refetch(paths)` 讓外部改寫、刪除或復原的列重新讀取（舊縮圖留到新的到為止，讀取中途檔案變了就丟掉那次結果重讀）；Delete／Undo 與評分、我的最愛、挑片、色彩標籤（F1–F5）照「快捷鍵設定」解讀（`_handle_edit_key`），刪除、復原、標記選取列都交給主視窗 |
| `dual_image_view.py` | 196 | 雙圖檢視：Split / Manga / Manga RTL 三種模式 |
| `exif_sidebar.py` | 438 | 可收合的 EXIF 側邊欄（含星等元件） |
| `breadcrumb_bar.py` | 147 | 麵包屑路徑列 |
| `timeline_view.py` | 362 | 時間軸檢視（年/月/日分組） |
| `toast.py` | 96 | Toast / snackbar 通知 |
| `settings_notice.py` | 40 | `warn_if_settings_unreadable(parent)`：啟動時設定檔讀不到，就用非阻塞 `QMessageBox` 說明已改用預設值、副本會存在哪、怎麼取回（主視窗啟動後 800 ms 呼叫） |
| `trash_failure_notice.py` | 59 | `offer_permanent_delete(parent, paths)`：提交刪除後送不進回收筒、留在原處的檔案，列出來問使用者要不要永久刪除（預設保留；確定就 `delete_outright`，資料夾連內容、檔案連 sidecar 一起刪）；關閉時與 File 選單的立即提交都會呼叫 |
| `hover_preview.py` | 192 | 縮圖懸停放大彈窗（預覽依 EXIF 轉正，標題列顯示圖片本身尺寸） |
| `image_issue_panel.py` | 142 | 圖片載入問題面板（dock） |
| `multi_monitor_window.py` | 295 | 多螢幕鏡像視窗 |
| `command_palette.py` | 160 | Ctrl+Shift+P，走訪 `menuBar()` 展平所有 `QAction` 的模糊搜尋啟動器（經 `menu_tree`） |
| `menu_tree.py` | 59 | 不經 `QAction.menu()` 走訪選單樹（`submenu_index` / `iter_menu_actions`），見 §10.10 |
| `modify_actions_widget.py` | 203 | 共用的 Modify 動作按鈕組（選單與右鍵共用） |
| `main_tab_nav.py` | 47 | Modify/Paint 分頁左右鍵的純路由決策 |
| `screen_fit.py` | 62 | 換螢幕時主視窗自適應的純幾何 |
| `settle_poll.py` | 58 | **有界重試**：視窗還在 settle 時反覆重跑佈局步驟（解決 `singleShot(0)` 跨不了 OS 視窗變更的問題）；`owner=` 讓鏈隨物件銷毀而停 |
| `workspace_manager.py` | 154 | 具名工作區預設（幾何 + 佈局快照） |
| `query_search.py` | 41 | 查詢字串輸入 → 過濾縮圖牆 |
| `background_jobs.py` | 327 | application-owned JobRegistry 與跨視窗 modeless 工作面板；Qt-parent 解綁保留 actual thread exit，failure-only retry、500 筆優先失敗明細／完整 atomic JSON report、clickable outputs |
| `_apply_save.py` | 207 | **共用的「載入 → 套用 → 另存副本」骨架**（`EffectWorker(QThread)`），約 30 個單圖工具對話框與外掛的 `ToolDialogMixin` 共用；`load_rgba()` 回傳檢視器看到的陣列（RAW 全尺寸顯像、sRGB、依 EXIF 轉正）；`output_path(s)` 給出原圖旁不存在的檔名（`photo_clahe.png` → `_1` …，一組共用編號，由 `system/free_names` 挑名），工具再跑一次不會蓋掉上次結果；`finalize_worker()` 在 custom done 提前送達時 passive 背景退場，保留 owner／actual worker lifetime；`show_toast()` / `notify_saved()`（成功字串可換鍵）回報結果（外掛也 import，見 architecture.md §6） |

#### 顯影 / 調色對話框（多為 `_apply_save` 外殼）

`tone_curve_dialog.py`(288) · `levels_dialog.py`(169) · `channel_mixer_dialog.py`(148) ·
`hsl_mixer_dialog.py`(130) · `split_toning_dialog.py`(114) · `gradient_map_dialog.py`(165) ·
`colormap_dialog.py`(91) · `lut_dialog.py`(111) · `posterize_dialog.py`(157) ·
`solarize_dialog.py`(139) · `velvia_dialog.py`(84) · `film_negative_dialog.py`(81) ·
`filmic_tonemap_dialog.py`(106) · `tone_equalizer_dialog.py`(96) · `detail_equalizer_dialog.py`(91) ·
`auto_color_balance_dialog.py`(199) · `local_contrast_dialog.py`(120) · `clahe_dialog.py`(100) ·
`defringe_dialog.py`(95) · `graduated_density_dialog.py`(113) · `soft_proof_dialog.py`(128) ·
`develop_presets_dialog.py`(166) · `virtual_copies_dialog.py`(159) · `before_after_dialog.py`(174) 分割滑桿對照 ·
`layers_dialog.py`(449) 疊加圖層堆疊管理 · `masks_dialog.py`(223) 局部調整遮罩

#### 效果 / 濾鏡對話框

`glow_dialog.py`(158) · `emboss_dialog.py`(96) · `film_grain_dialog.py`(135) · `lens_flare_dialog.py`(134) ·
`frosted_glass_dialog.py`(85) · `dither_dialog.py`(91) · `distort_dialog.py`(101) · `polar_dialog.py`(80) ·
`kaleidoscope_dialog.py`(81) · `pixel_sort_dialog.py`(106) · `meme_dialog.py`(94) ·
`photo_frame_dialog.py`(120) · `scale_bar_dialog.py`(106) · `anaglyph_dialog.py`(111) ·
`frequency_separation_dialog.py`(143) 輸出兩個圖層檔 · `binarize_dialog.py`(100) · `otsu_dialog.py`(89) ·
`flatten_field_dialog.py`(95) · `test_charts_dialog.py`(101) · `steganography_dialog.py`(125)

#### 幾何 / 修補 / 多圖

`crop_straighten_dialog.py`(207) · `auto_straighten_dialog.py`(192) · `lens_correction_dialog.py`(153) ·
`smart_crop_dialog.py`(126) 顯著性裁切建議 · `tiny_planet_dialog.py`(113) ·
`clone_stamp_dialog.py`(205) · `healing_brush_dialog.py`(241) · `sky_replace_dialog.py`(139) ·
`portrait_retouch_dialog.py`(162) · `noise_sharpen_dialog.py`(152) · `face_detection_dialog.py`(236) ·
`hdr_merge_dialog.py`(148) · `panorama_dialog.py`(160) · `focus_stack_dialog.py`(148) ·
`stack_blend_dialog.py`(168) · `collage_dialog.py`(87) · `deflicker_dialog.py`(240) 縮時去閃（檢視器解碼；輸出到 `deflickered/`，可寫回的格式沿用並帶 EXIF，RAW 存 PNG） ·
`id_photo_sheet_dialog.py`(106) · `print_layout_dialog.py`(222)

#### 批次 / 匯出 / 管理

`batch_convert_dialog.py`(403) 批次格式轉換（經 `upright_image` 解碼、帶回全部 EXIF；「刪除原檔」只把單影格點陣靜態圖一次送進資源回收筒） · `batch_export_dialog.py`(449) 批次匯出（格式、品質、縮放、浮水印、metadata；有顯影後端時多一列「運算裝置」，預設選第一個後端，worker 在自己的執行緒開啟算繪器、結束時關閉，`result_ready` 一定從 `finally` 發出） · `export_dialog.py`(256) 單張匯出（預設檔名經 `free_names` 挑還沒被占用的；目標就是原圖本身時另外詢問，其他既有檔案經 `dialog_rows.may_replace`，預設不取代） · `export_source.py`(55) `recipe_base_image()`（recipe 套用的底圖：轉正，舊幾何 recipe 例外；智慧裁切、人臉偵測在它上面算座標）、`upright_image()`（`image_loader.decode_image` 的別名入口；AI 放大與批次轉換共用） · `shown_qimage.py`(33) `shown_qimage(path, *, max_edge)`：檢視器解碼成 QImage，讀不到回傳空 QImage（比較、雙圖、多螢幕、資料夾縮圖取代 `QPixmap(path)`）、`open_export_source(path, renderer=None)`：兩個匯出共用的來源（經 `decode_image_file`：RAW 全尺寸、SVG 點陣化、sRGB、依 EXIF 轉正，再經 `develop_backends.render` 套 recipe，批次匯出可傳入 GPU 算繪器；輸出不帶 ICC 與轉向標籤，所以都烘進像素）· `export_metadata_combo.py`(44) `metadata_row()`：兩個匯出對話框共用的「Metadata」下拉（全部／位置以外／無），選擇記在 user settings `export_metadata` ·
`optimize_dialog.py`(111) 目標檔案大小 · `gif_video_dialog.py`(420) 多張圖做 GIF／MP4（預設輸出經 `free_names` 挑沒被占用的 `output.gif`；既有檔案經 `dialog_rows.may_replace` 詢問） · `contact_sheet_dialog.py`(239) Layout 預設選單（選了填入格線，手動改就回到 Custom） ·
`web_gallery_dialog.py`(160) · `slideshow_mp4_dialog.py`(194) · `image_organizer_dialog.py`(533) ·
`duplicate_detection_dialog.py`(542) 檔案雜湊 + pHash · `image_sanitize_dialog.py`(744) 淨化重繪（剝除所有隱藏資料）·
`exif_strip_dialog.py`(309) EXIF 批次清除（覆寫原檔走 `replace_atomically`；另存的 `_clean` 副本經 `free_names` 挑名） · `token_rename_dialog.py`(124) · `culling_dialog.py`(247) 挑片 ·
`ai_upscale_dialog.py`(712) Real-ESRGAN via ONNX（模型自 HuggingFace 下載）

#### 相片庫 / 中繼資料 / 搜尋

`library_search_dialog.py`(240) · `smart_albums_dialog.py`(298) · `semantic_search_dialog.py`(221) ·
`similar_search_dialog.py`(104) · `advanced_filter_dialog.py`(286) · `tag_album_dialog.py`(580) Tags & Albums（新增／改名檢查名稱、Clean Up… 清掉已不存在的檔案並合併只差大小寫的名稱） ·
`tag_filter_dialog.py`(165) · `hierarchical_tags_dialog.py`(190) · `auto_tag_dialog.py`(172) ·
`keyword_editor_dialog.py`(217) · `keyword_vocabulary_dialog.py`(70) · `exif_editor.py`(216) EXIF 編輯對話框（外殼；讀寫在 `image/exif_fields`，不支援的格式顯示說明；Describe 以 `CaptionWorker`〔QRunnable〕向本機 Ollama 要描述填入 Description） ·
`gps_geotag_dialog.py`(90) · `gpx_geotag_dialog.py`(184) 用 GPX 軌跡對整批相片寫 GPS（時區、間隔上限、內插） · `capture_time_dialog.py`(193) 整批位移 EXIF 拍攝時間（輸入位移或第一張的正確時間） · `metadata_template_dialog.py`(178) 把記住的標題／描述／關鍵字範本（含 `{token}`）蓋到整批相片 · `map_view_dialog.py`(180) OSM 底圖 · `calendar_view_dialog.py`(108) ·
`events_dialog.py`(50) · `metadata_export_dialog.py`(94) · `xmp_sidecar_dialog.py`(126) ·
`bookmark_dialog.py`(345) · `staging_tray_dialog.py`(180) · `reference_panel_dialog.py`(298) ·
`image_statistics_dialog.py`(90) · `quality_report_dialog.py`(61) · `image_inspector_dialog.py`(84) 波形/parade/false colour/focus peaking ·
`ocr_dialog.py`(118)

#### 設定 / 系統

`preferences_dialog.py`(295) 偏好設定（VRAM、UI 縮放、主題、瀏覽輔助、選用分頁） · `shortcut_settings_dialog.py`(407) · `profiles_dialog.py`(206) 多帳號 ·
`workspace_dialog.py`(231) · `external_editors_settings.py`(151) · `recycle_bin_dialog.py`(358) 軟刪除回收桶 ·
`cache_maintenance_dialog.py`(53) · `watch_folder_dialog.py`(111) · `macro_manager_dialog.py`(334) ·
`dual_pane_dialog.py`(167) 雙窗格檔案管理 · `onboarding_dialog.py`(135) 首次導覽 · `whats_new_dialog.py`(143)

### 6.13 `Imervue/menu/`

選單建構層 —— 只負責組 `QAction` 與呼叫對應對話框，不含業務邏輯。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `extra_tools_menu.py` | 852 | **最大的選單**：Batch / Library / Views / CVD / Workflow / Export / Develop / Retouch / Multi-image 九個子選單，約 100 個 `_open_*` 進入點。子選單帶 `extra_tools.<key>` object name（`submenu_object_name`），外掛靠它 `findChild` 放入口，是對 Imervue_Plugins 的契約 |
| `right_click_menu.py` | 874 | 檢視器右鍵選單：在檔案總管顯示、複製路徑、遺失檔案重定位、重試載入、OCR、批次動作、staging tray、桌布、比較、書籤、標籤… |
| `file_menu.py` | 532 | 開啟資料夾/圖片、將目前圖片開成新的 Paint 文件、新視窗、檔案關聯註冊、剪貼簿貼上、書籤、標籤相簿、快捷鍵設定、偏好設定、回收桶、多帳號、Session、工作區、外部編輯器 |
| `tip_menu.py` | 290 | 操作說明選單 + 快捷鍵速查對話框 |
| `filter_menu.py` | 281 | Filter 選單：依副檔名 / 色彩標籤 / 星等 / 標籤 / 相簿 / 分揀狀態過濾，多標籤與進階過濾，RAW+JPEG 堆疊，清除篩選 |
| `plugin_menu.py` | 334 | 外掛管理：檢視已載入、下載、啟用/停用、開啟資料夾；記錄外掛加進選單的入口（`dispatch_plugin_menus`），重新載入前先移除（`remove_plugin_menu_entries`） |
| `recent_menu.py` | 192 | 最近資料夾 / 最近圖片子選單（teardown-safe，會自動剔除不存在路徑） |
| `sort_menu.py` | 185 | 依名稱 / 修改日期 / 建立日期 / 拍攝日期（`library.calendar_index.capture_datetime`：EXIF 拍攝時間，沒有就用修改時間；同一秒的連拍依檔名）/ 大小 / 解析度排序 |
| `language_menu.py` | 58 | 語言切換（提示重新啟動）；選單 object name `language_menu` |
| `modify_menu.py` | 29 | Deep-Zoom 專用的「修改」選單動作 |

### 6.14 `Imervue/paint/`

172 個檔、43,251 行 —— 全樹最大的子系統，是一個完整的點陣繪圖 + 漫畫製作工作區。

#### 核心文件模型與畫布

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `document.py` | 905 | `PaintDocument`：圖層、群組、選取與參考索引；deepcopy 複製可編輯內容並排除 listener，adopt_content 保留文件身分與 listener、一次通知 |
| `document_geometry.py` | 214 | `DocumentGeometryMixin`：裁切（矩形／選取／非透明）、翻轉、90/180° 旋轉、縮放、自由變形，圖層、遮罩與已存選取一起改 |
| `document_merge.py` | 201 | `DocumentMergeMixin`：依色塊拆分作用中圖層、向下合併、合併可見、平面化 |
| `document_groups.py` | 136 | `DocumentGroupsMixin`：圖層群組的建立／刪除／改名、成員與群組屬性 |
| `canvas.py` | 855 | `PaintCanvas`：GPU 加速的中央繪圖表面——文件與選取、GL 生命週期與 `paintGL`、材質上傳；疊加繪製、輸入、視圖變換來自下面三個 mixin，`PointerEvent` 等由 `__all__` re-export |
| `canvas_overlays.py` | 538 | `PaintCanvasOverlaysMixin`：棋盤背景（`build_checker_pattern`）、行進螞蟻選取框、工具預覽、多邊形預覽、出血線、洋蔥皮、尺寸 HUD、拖放高亮、像素格線 VBO |
| `canvas_input.py` | 365 | `PaintCanvasInputMixin`：指標與繪圖板事件、平移縮放、鋼筆與拖放；素材插入完成時經 dispatcher 建立 Undo 步驟 |
| `canvas_view.py` | 187 | `PaintCanvasViewMixin` + `ZOOM_MIN`/`ZOOM_MAX`、`clamp_zoom()`、`wrap_rotation()`：縮放、繞中心旋轉、適配、螢幕↔影像座標 |
| `pointer_event.py` | 35 | `PointerEvent`（工具收到的指標快照）與 `ToolDispatcher` 型別；不依賴 Qt widget |
| `compositing.py` | 438 | 純 NumPy 圖層合成 |
| `layer_model.py` | 116 | 圖層與圖層群組資料模型 |
| `layer_ops.py` | 171 | 向下合併 / 合併可見 / 平面化的純函式 |
| `document_io.py` | 453 | 原生 .imervue NPZ 文件讀寫、圖層／遮罩／向量／選取與漫畫 PanelLayout metadata（可選欄位相容既有 version 1） |
| `psd_io.py` | 873 | Photoshop `.psd` 匯入 / 匯出（互通子集） |
| `undo_stack.py` | 189 | 每文件 512 MiB／50 步驟容量歷史；不可變共用像素與完整 metadata 復原、存活圖層身分；available_snapshot 提供已持有快照，背景保存不在 timer 捕捉整張陣列 |
| `history_pixels.py` | 151 | 純運算 256px 不可變 tile、弱 interning 索引、完整／區域 capture 與差異 patch，計算唯一資料及 Python 狀態容量 |
| `damage.py` | 151 | 破損矩形記帳，供部分材質上傳；另有 `(x, y, w, h)` 元組版的 `union_rects()` / `from_rect()` 給修飾工具累積筆畫用 |
| `blend_modes.py` | 63 | 共用 RGB 混色模式數學 |
| `blend_if.py` | 333 | Blend-If：依亮度範圍決定逐像素可見度 |

#### 筆刷引擎

`brush_engine.py`(686) 純 NumPy 光柵化 · `gpu_brush.py`(686) OpenGL FBO+GLSL 加速（散佈、色彩抖動、跟隨筆傾斜的筆畫留在 CPU）·
`brush_dynamics.py`(150) · `brush_random.py`(169) 每筆觸點的散佈 / 色彩抖動 / 依筆傾斜收窄並轉向筆尖（`BrushStroke` 依 Brush dock 設定套用）· `brush_cursor.py`(515) 筆跡游標預覽 ·
`brush_presets.py`(349) · `default_brush_presets.py`(164) · `brush_preset_io.py`(240) 含外部格式匯入 ·
`brush_preset_dialog.py`(264) · `brush_kind_preview.py`(89) · `brush_tip_capture.py`(137) 從選區擷取筆尖 ·
`custom_brush.py`(97) · `pressure_curve.py`(146) + `pressure_curve_dialog.py`(255) 筆壓曲線 ·
`stabilizer.py`(84) 筆畫穩定器 · `catmull_rom_spline.py`(80) 平滑重採樣（鋼筆 Options bar 的 Smooth：穿過各點的一條曲線）· `symmetry.py`(85) 對稱繪製 ·
`smudge.py`(120) 塗抹/混色筆 · `blur.py`(74) · `dodge_burn.py`(100) · `sponge.py`(68) ·
`stamp_tool.py`(151) + `stroke_along_path.py`(99)

#### 選取 / 變形

`selection.py`(295) · `selection_ops.py`(325) 選區精修 · `selection_transform.py`(202) 仿射變換 ·
`marquee.py`(93) 選區邊界線段 · `quick_mask.py`(219) 快速遮罩 · `magnetic_lasso.py`(118) 磁性套索（Options bar 的 Magnetic，放開時把套索輪廓吸到 10 px 內最強邊緣）·
`stroke_selection.py`(140) 描邊選區 · `transform_handles.py`(270) · `liquify.py`(262) + `liquify_dialog.py`(288) 液化 ·
`crop.py`(93) + `crop_tool.py`(90) · `canvas_transforms.py`(76) · `image_resize.py`(149)

#### 填色 / 形狀 / 向量 / 文字

`fill.py`(372) 洪水填色 · `auto_region_fill.py`(253) 一次填滿所有封閉區 · `auto_base_color.py`(344) 線稿自動平塗（Bucket dock 的 Base colours：每個封閉區一色、放在線稿下的新圖層；以列段 union-find 標記區域，A4 300dpi 一頁不到一秒）·
`divide_layer.py`(158) 依顏色拆圖層 · `gradient.py`(168) + `gradient_editor.py`(324) 多色標漸層（存在設定，增刪移改色標）+ `gradient_editor_dialog.py`(256) 漸層編輯器（Options bar 的 Edit…）+
`gradient_map_presets.py`(88) · `shape_engine.py`(265) ·
`bezier_path.py`(217) + `pen_commit.py`(130) 鋼筆工具 ·
`vector_layer.py`(311) 非破壞性向量線條 · `binary_layer.py`(139) 1-bit 墨線圖層 ·
`image_trace.py`(220) 遮罩 → 輪廓向量化 ·
`text_render.py`(225) · `text_tool.py`(209) · `text_on_path.py`(173) 沿折線排字 ·
`text_on_selection.py`(92) 沿選區輪廓排字（Manga > Text Along Selection…，新「Text」圖層）

#### 顏色

`color_math.py`(83) · `color_wheel.py`(262) + `color_wheel_widget.py`(204) 色相環 + SV 三角（Color dock 上方）· `color_palette.py`(189) 具名調色盤（內建 Standard／Pastel／Manga + 自訂；Swatches dock 的選單、Match Swatches 用它）+
`color_palette_io.py`(303) 外部調色盤格式 · `swatch_panel.py`(348) ·
`palette_extract.py`(168) median-cut 抽色 · `match_color.py`(96) Filter > Match Colour…（參考圖片的色調）· `match_palette.py`(108) Filter > Match Swatches…（換成最近的色票顏色）·
`color_blindness.py`(118) CVD 模擬 ·
`adjustments.py`(739) 純 NumPy 非破壞性調整種類與套用管線 · `histogram.py`(128) + `histogram_dock.py`(141)

#### 漫畫 / 網點

`manga_menu.py`(625) · `manga_panels.py`(300) 分鏡版面與 PanelLayout JSON 編解碼（原生文件與自動快照保留配置；Panel Cutter 把版面存在 `document.panel_layout`，筆刷的 Snap to panel 經 `ToolDispatcher` 的 `panel_layout_provider` 依它裁切；`layout_for_canvas` 在畫布尺寸變了後不再套用） ·
`halftone.py`(357) 網點引擎 · `speedlines.py`(210) · `speech_bubble.py`(204) 對話框氣泡 ·
`comic_stamps.py`(266) + `stamp_dock.py`(88) · `flash_effect.py`(132) 爆炸效果 ·
`bleed_guides.py`(154) 裁切/出血/安全線 · `page_templates.py`(266) ·
`page_numbering.py`(156) · `page_dock.py`(348) 頁面瀏覽 · `paint_project.py`(147) 多頁專案 +
`paint_project_io.py`(114) `.imervue-proj` 整本漫畫存檔（File > Save / Open Comic Project…）+ `paint_project_export.py`(130) · `new_project_dialog.py`(105)

#### 動畫

`animation.py`(478) 時間軸 + 洋蔥皮 · `animation_timeline.py`(198) 純 NumPy 模型 ·
`animation_dock.py`(350) 幀條 + 播放控制 + Export…（GIF／WebP／APNG）· `animation_export.py`(193) 動畫匯出，吃 dock 的 `AnimationTimeline` 或 `Animation`，`export_animation` 依副檔名選格式

#### 素材 / 參考 / 姿勢

`material_library.py`(330) 素材索引；`material_dock_index` = 使用者的 `<app_dir>/materials/` 與擷取的筆刷形狀 + 內建程序化素材 · `material_procedural.py`(221) 程序化材質 · `material_drop.py`(121) ·
`save_region_as_material.py`(113) Edit > Save Selection as Material…（不覆寫同名素材） · `reference_dock.py`(258) Paint 參考圖 dock（經 `decode_image_file` 以檢視器的樣子顯示：轉正、sRGB、RAW 顯像） ·
`pose_skeleton.py`(210) + `pose_dock.py`(185) + `pose_drop.py`(128) 2D 火柴人姿勢參考

#### 輔助線 / 檢視

`rulers.py`(492) 繪圖輔助尺 · `snap_guides.py`(124) ·
`visual_guides.py`(262) 像素格線 · `multi_view.py`(246) 同文件第二視窗 ·
`size_hud.py`(138) + `size_hud_bridge.py`(63) 筆刷大小 HUD · `welcome_overlay.py`(222) ·
`layer_thumbnail.py`(183) · `layer_effects.py`(341) 陰影/外光暈/描邊

#### 工作區骨架與選單

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `paint_workspace.py` | 778 | 頂層 PaintWorkspace；筆刷／橡皮擦手勢提交完整 damage hints，dock 與未知操作保守完整捕捉；confirm_close 由主視窗呼叫 |
| `tool_dispatcher.py` | 478 | 工具事件路由與手勢提交；累計筆刷／橡皮擦 damage，僅提交回呼期間提供區域 hints；切頁、切工具與部分失敗保守捕捉 |
| `tool_state.py` | 983 | **無 Qt** 的工具狀態模型 |
| `tool_bar.py` | 491 | 工具列：按鈕只在提示顯示按鍵，工具按鍵由 `tools_menu.py`（`tool_shortcut`）獨佔；上方選項列 `PaintOptionsBar` 的筆刷／填色／選取／漸層頁與 `ToolState` 雙向同步 |
| `workspace_tabs.py` | 339 | 多文件分頁、髒狀態；切頁更新該文件最後自動存檔時間，關閉清除該文件快照與歷史 |
| `workspace_docks.py` | 417 | dock 建構與佈局持久化 |
| `workspace_content.py` | 469 | 文件內容命令；姿勢與材質插入透過 workspace_history 提交 Undo 與髒狀態 |
| `workspace_history.py` | 15 | 圖層選單、漫畫圖層與素材插入共用的完整編輯提交邊界 |
| `workspace_status.py` | 320 | 狀態列與縮放指示 |
| `workspace_shortcuts.py` | 317 | 快捷鍵、筆刷調整、歡迎提示；圖層排序完成時提交 Undo，邊界不建立空步驟 |
| `workspace_presets.py` | 265 + `workspace_preset_dialog.py`(332) | 具名 dock 佈局預設 |
| `workspace_autosave.py` | 352 | dirty tabs 定時共用 immutable committed snapshots 至背景 queue，超過歷史 cap 時 UI 獨立複製；結果在 UI 記錄 owned paths／timestamps，替換與關閉取消 late output；原有同步 explicit API／復原保留 |
| `autosave_jobs.py` | 159 | 一個背景 writer／每文件最新 pending；immutable materialization／NPZ 壓縮／file IO，application-owned QObject signals 與取消後清除 late snapshots，queued UI 完成與 sender retirement |
| `auto_save.py` | 268 | Qt-free 原生快照／原子 metadata、每文件八份 quota、排序與損壞快照回復，供同步入口與背景 writer 共用 |
| `shortcut_registry.py` | 183 + `shortcut_binding.py`(111) + `shortcut_dialog.py`(180) + `shortcuts_dialog.py`(107) | 可自訂快捷鍵登錄；`shortcut_binding.py` 標記擁有各登錄項的 `QAction` / `QShortcut`，把使用者重新指定的鍵套上去（只換登錄表的那個鍵，保留別名）；`fixed_shortcut_keys` 列出登錄表外動作已占用的鍵，對話框把撞到的列標紅並說明被誰占用 |
| `recent_files.py` | 72 | 最近開啟清單 |
| `export_presets.py` | 278 | 批次匯出設定檔 |
| `canvas_presets.py` | 184 + `new_canvas_dialog.py`(136) | File > New Canvas… 的尺寸預設（紙張／漫畫／螢幕 + 自訂，存在設定）與對話框（尺寸、白或透明背景）|
| 選單 | — | `paint_menu_bar.py`(90)、`file_menu.py`(635)、`edit_menu.py`(327)、`image_menu.py`(265)、`layer_menu.py`(322)、`filter_menu.py`(563)、`view_menu.py`(311)、`tools_menu.py`(158)、`settings_menu.py`(147)、`filter_preview_dialog.py`(198) 單一滑桿濾鏡的即時預覽（圖層中央 480×480 原尺寸裁切） |

#### `paint/docks/`（7 檔 · 1,955 行）

`brushes.py`(464) 筆刷與填色 dock · `layers.py`(446) 圖層 dock（完整操作後發出 edit_committed，列選取不建立 Undo 步驟） · `color.py`(382) 顏色 dock（色輪、HSB／RGB 滑桿、hex）·
`materials.py`(265) 素材庫 dock · `navigators.py`(247) 導覽器 / 歷史 / 頁面導覽 dock ·
`_helpers.py`(150) 共用元件、圖示與混合模式下拉選單

#### `paint/tools/`（6 檔 · 1,911 行）

`painting.py`(443) 筆刷/橡皮/填色/滴管；橡皮逐 dab 回報 damage · `shapes.py`(444) 形狀與裁切 ·
`special.py`(357) 鋼筆/仿製印章/變形控點/對話氣泡 · `select.py`(314) 矩形/套索/魔術棒/快速選取、選取區搬移 ·
`retouch.py`(357) 漸層（前景→背景或存下的多色標漸層）/塗抹/模糊/加深減淡/海綿

### 6.15 `Imervue/puppet/`

60 個檔、16,393 行。2D 骨架人偶動畫，Live2D Cubism 相容。原本是外掛，因為核心路徑
（GL / mesh / 純 NumPy 變形）跑在預設相依上，所以收進主程式當內建分頁；唯一的重量級選用相依
是 Cubism Native SDK DLL，缺了會優雅降級。

#### 資料模型與 I/O

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `document.py` | 395 | `.puppet` v1 檔案格式的純 Python 資料模型（`Drawable` / `Deformer` / `Parameter` / `Motion` / `HitArea`） |
| `document_io.py` | 884 | `.puppet` zip 容器讀寫；第一個項目是未壓縮的 `mimetype`（`application/vnd.imervue.puppet+zip`），每個 JSON 帶 `$schema`；較新的格式版本以「請更新 Imervue」拒絕，布林 `true` 不算版本 1 |
| `format_schema.py` | 327 | `.puppet` v1 的四份 JSON Schema（draft 2020-12：puppet / motion / expression / physics，`$id` 是 `docs/schemas/` 在 `main` 上的 raw URL；`python -m Imervue.puppet.format_schema docs/schemas` 重產）與 `check_puppet_file`：schema → 載入器規則 → `validator` 的 rig 檢查（CLI `puppet-validate`、MCP `puppet_validate`） |
| `schema_check.py` | 124 | 只涵蓋上述 schema 所用子集的 JSON Schema 驗證器（`$ref`、type、enum、const、properties、required、additionalProperties、items、min/maxItems、minimum/maximum、minLength、allOf、anyOf、if/then），不依賴第三方套件；與 `jsonschema` 對拍 7200 個變造檔判定一致 |
| `cubism_import.py` | 550 | Live2D Cubism v3 檔案格式匯入 |
| `cubism_native_bridge.py` | 443 | `Live2DCubismCore.dll` 的 ctypes 綁定（官方 Cubism SDK for Native） |
| `cubism_native_convert.py` | 646 | `.moc3` → `PuppetDocument` 轉換 |
| `psd_import.py` | 186 | PSD 多圖層 → `PuppetDocument` |
| `auto_mesh.py` | 172 | 從單張 PNG 自動生成網格 |
| `auto_rig.py` | 429 | 依圖層命名慣例自動推導 Cubism 式綁定 |
| `standard_params.py` | 116 | Cubism 標準參數目錄 |
| `requirements.py` | 75 | 選用相依清單 |

#### 執行期（變形 / 物理 / 取樣）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `runtime.py` | 846 | **每幀參數取樣 + deformer 組合**（核心迴圈） |
| `deformers.py` | 262 | 純 NumPy deformer 實作 |
| `physics.py` | 138 | Verlet 物理引擎（純浮點數積分，由 `PuppetCanvas` 的物理時鐘推進） |
| `render_prep.py` | 103 | `PuppetDocument` → GL-ready draw list |
| `canvas.py` | 934 | `PuppetCanvas`（`QOpenGLWidget`）：文件、參數、選取、網格編輯、`paintGL` / 離屏渲染與滑鼠互動，以及物理鏈自己的時鐘（顯示中且有鏈時約 60 Hz 推進）；實際繪製來自 `canvas_render.py` |
| `canvas_render.py` | 537 | `PuppetCanvasRenderMixin`：棋盤背景、桌寵陰影、drawable 繪製與 stencil 裁切、選取框與錨點、頂點緩衝與貼圖（預乘 alpha 的 `_premultiply_alpha`）快取 |
| `clip_masks.py` | 56 | `Drawable.clip_mask` 參照解析 |
| `bone_weights.py` | 100 | 骨骼 LBS 權重驗證與修復（Repair Rig 的權重正規化） |
| `hit_test.py` | 120 | `HitArea` 純 Python 命中測試 |
| `mesh_edit.py` | 128 · `mesh_repair.py` 246 · `symmetrize.py` 138 | 網格編輯（`remap_vertex_data`：刪頂點或修復後讓骨骼權重與頂點 morph 跟著重新編號）/ 拓樸修復（`match_uvs` 保留貼圖接縫、`sources` 回報來源頂點）/ X 軸自動對稱 |
| `rig_repair.py` | 62 | Tools > Repair Rig：每個 drawable 跑 `repair_mesh`（UV 也相同才合併）＋權重正規化，回報合計 |
| `operations.py` | 228 | `PuppetDocument` 的純編輯操作 |
| `validator.py` | 296 | 靜態健康檢查 |

#### 動作 / 表情 / 閒置

`motion_sampler.py`(148) 純取樣 · `motion_player.py`(381) Qt 播放驅動（循環依動作自己的 `loop`） · `motion_recorder.py`(166) 錄製 ·
`motion_timeline.py`(460) 曲線圖編輯（數值軸用參數自己的範圍；Ease 把整軌改成具名緩動、Simplify Keys 依參數範圍百分比精簡關鍵幀） · `motion_compress.py`(113) 移除冗餘關鍵幀（Simplify Keys） ·
`motion_picker.py`(53) 群組隨機挑選 · `synth_motions.py`(286) 為轉檔 rig 合成閒置動作 ·
`idle_driver.py`(143) · `idle_motion_cycler.py`(151) · `easing.py`(250) 緩動預設（`ease_track`：單一 bezier 或 elastic／bounce 取樣成線段，時間軸的 Ease 用它） ·
`motion_dock.py`(197) · `expression_dock.py`(121) · `pose_dock.py`(118) 姿勢群組挑成員（跟著 canvas 的 `pose_changed`）· `parameter_dock.py`(197) · `bone_tree_dock.py`(196)

#### 即時輸入驅動

`input_engine.py`(213) 把即時輸入灌進 canvas · `input_drivers.py`(215) 純對應函式（游標→角度參數等）·
`mouse_gaze_driver.py`(239) 頭+眼追游標 · `webcam_tracker.py`(393) 攝影機 → 參數 ·
`webcam_preview_dialog.py`(224) · `face_landmark_mapper.py`(212) MediaPipe FaceMesh → 參數 ·
`audio_lipsync.py`(139) 音檔驅動嘴型（Live > Lip-sync from Audio File…：`lipsync_motion` 把 WAV 響度做成 `ParamMouthOpenY` 動作、以該檔為配音）

#### 輸出

`recorder.py`(239) 幀擷取 · `batch_export.py`(186) 每個 motion 匯出成 MP4/GIF/WebM ·
`spritesheet.py`(67) · `virtual_camera.py`(243) 系統虛擬攝影機 · `ndi_output.py`(222) NDI 來源廣播 ·
`vts_api.py`(385) VTube Studio Public API server（最小子集）

`workspace.py`(933) 是頂層 `PuppetWorkspace`（`QMainWindow`），掛載 canvas 與各 dock、開存檔、rig 編輯、驅動開關、驗證與批次匯出；另外混入三個 mixin：`workspace_menus.py`(299，所有 `QAction`、選單列、切換工具列、範例／最近檔案子選單；`RECENT_KEY`)、`workspace_import.py`(361，PNG sprite sheet／PSD／Cubism 匯入)、`workspace_live.py`(222，錄影、webcam 追蹤與預覽、虛擬攝影機、NDI、VTube Studio API)。

### 6.16 `Imervue/desktop_pet/`

29 個檔、7,089 行。無邊框、透明、永遠置頂的桌面寵物懸浮視窗，**共用整個 Puppet 執行期**。
Tab 4 本身只是控制面板，角色住在獨立的 top-level `PetWindow`。套件的 `__init__` 和 puppet 一樣用模組 `__getattr__` 延遲匯出 `PetWindow`／`PetWorkspace`／`PetTrayIcon` 等名稱，所以 import `desktop_pet.settings` 之類的輕量子模組不會載入視窗、工作區與 Puppet canvas。

#### 視窗與互動

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `pet_window.py` | 867 | `PetWindow`：無邊框透明視窗，host 一個 pet 模式的 `PuppetCanvas`；`add_integration` / `remove_integration` / `integration` 讓外掛把 `IntegrationController` 掛進 `shutdown()` 會停的登錄表 |
| `pet_window_flags.py` | 201 | `PetWindowFlagsMixin`：`PetWindow` 的視窗旗標組合（置頂／置底、點擊穿透）、鎖定位置、吸附門檻、透明度、全螢幕時隱藏 |
| `pet_feature_toggles.py` | 188 | `PetFeatureTogglesMixin`：`PetWindow` 的各功能開關（眨眼、對嘴、webcam、熱鍵、虛擬攝影機、LLM、音樂律動、閒置小遊戲、陰影、音效、滑鼠注視），只轉給對應控制器並存設定 |
| `pet_workspace.py` | 817 | Tab 4 控制面板（rig 選擇、驅動開關、可見性 / 點擊穿透 / 尺寸預設、全域熱鍵：拒絕別的動作已用的鍵，開分頁時列出共用同一鍵的已存綁定）；建立寵物視窗時發 `pet_created`，外掛經 `PluginManager.connect_pet_hooks` 收到 `on_pet_created` |
| `pet_interaction.py` | 214 | 指標互動控制器：拖曳移動、點擊路由、命中偵測 |
| `pet_placement.py` | 153 | 邊緣吸附、多螢幕位置還原、預設角落停靠 |
| `edge_snap.py` | 165 | 純 Python 邊緣吸附數學 |
| `pet_context_menu.py` | 171 | 右鍵選單建構器 |
| `pet_shadow.py` | 137 + `pet_shadow_controller.py`(83) | 放射漸層落地陰影（單一 draw call） |
| `speech_bubble.py` | 208 | 對話泡泡覆蓋視窗（自動淡出） |
| `tray_icon.py` | 151 | 系統匣切換 |
| `settings.py` | 293 | 設定持久化（schema + 預設值 + 載入夾限） |
| `fullscreen_detector.py` | 166 | 偵測同螢幕有全螢幕程式時自動隱藏 |

#### 驅動與功能控制器（兩個家族）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `pet_feature_base.py` | 159 | `FeatureHost` Protocol + `IntegrationController` 骨架 |
| `pet_features.py` | 77 | 內建整合控制器：全域熱鍵；OBS / Twitch / Webhook / Windows 通知是 `plugins/pet_integrations` 外掛，經 `add_integration` 加進同一個登錄表 |
| `pet_drivers.py` | 243 | canvas 驅動控制器：音樂律動 / 閒置小遊戲 / 點擊音效 / LLM 對話 |
| `pet_canvas_drivers.py` | 168 | canvas 輸入驅動子系統（自動眨眼 / 拖曳追頭 / 麥克風對嘴） |

> 這兩個家族的存在是為了把 `PetWindow` 從 god-object 拉回「協調者」。

#### 外部整合

OBS / Twitch 聊天 / webhook / Windows 通知已是外掛 `plugins/pet_integrations`（§7） ·
寵物外掛的穩定介面見 `plugin_base.on_pet_created` ·
`hotkey_manager.py`(248) 全域熱鍵（pynput）+ `hotkey_conflicts.py`(60) 衝突偵測（`clashing_action`／`find_conflicts`，Desktop Pet 分頁的熱鍵欄位用） ·
`command_parser.py`(77) 可重用的聊天指令路由器（exact / prefix / substring / regex；`pet_integrations` 外掛的 Twitch 關鍵字走它）

#### 個性與行為

`pet_script.py`(437) JSON 支撐的台詞 + 排程事件引擎 · `pet_script_editor.py`(521) 內建編輯器 ·
`schedule_rules.py`(101) 時段 / 星期閘門 · `idle_minigame.py`(278) 閒置好奇 / 打呵欠 ·
`llm_dialogue.py`(206) 本地 LLM（預設 Ollama）對話（URL 規則與 POST 在 `system/local_llm`） · `music_rhythm.py`(463) WASAPI loopback 抓系統音訊隨節奏擺動 ·
`click_sfx.py`(168) 事件音效

### 6.17 `Imervue/plugin/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `plugin_base.py` | 264 | `ImervuePlugin` 基底類別，13 個 hook 加上類別方法 `register_languages()`（主視窗建立前註冊外掛語言）：`on_plugin_loaded/unloaded`、`on_build_menu_bar`、`on_build_context_menu`、`on_build_main_tabs`、`on_image_loaded/folder_opened/image_switched/image_deleted`、`on_key_press`、`get_translations`、`on_pet_created`（寵物視窗建立時，或外掛載入時寵物已存在）、`on_app_closing` |
| `plugin_manager.py` | 337 | 探索與載入（把 `plugins/` 插進 `sys.path`，找 `plugin_class`；匯入前先用 `plugin_api.check_compatible` 檢查 `plugin.json`，需要較新外掛 API 或讀不懂的就記 log 跳過、不匯入）、hook 分派（`connect_pet_hooks` 接上桌面寵物分頁的 `pet_created`，載入 / 重新載入時補發給已存在的寵物）、統一 try/except 隔離（單一外掛炸掉不會拖垮主程式）；`apply_saved_language()` / `register_plugin_languages()`：主視窗建立前只匯入外掛並呼叫 `register_languages()`，讓存下的外掛語言套用得到 |
| `plugin_downloader.py` | 579 | 從公開發佈 repo 下載外掛：一次遞迴 git-tree 呼叫列出清單（純函式 `parse_plugin_tree`，只收 `plugins`/`languages` 類別、只收外掛目錄下的扁平檔），檔案走 raw.githubusercontent，先下載到暫存目錄，換上前用 `plugin_api.check_compatible` 拒絕需要較新 Imervue 的外掛（保留已安裝版本，狀態列顯示 `needs_newer_text`）。含 `_https_urlopen` 守衛（拒絕非 https scheme）；one atomic plugin job／failure retry 與 cooperative cancellation；dialog 使用非阻塞 WorkerHost retirement，已完成安裝保留 |
| `pip_installer.py` | 850 | 外掛相依安裝器：下載內嵌 Python、安裝 pip 套件（凍結環境亦可），每次安裝都帶 `pip_constraints` 的約束檔；再匯出 `python_finder` 的名稱（外掛依賴 `pip_installer._find_python`） |
| `python_finder.py` | 218 | 找有 pip 的 Python 直譯器：非凍結用 `sys.executable`，凍結時依序查 PATH、registry／安裝資料夾（或 Unix 路徑）、內嵌 Python；`_verify_python` 以 `pip --version` 驗證 |
| `pip_constraints.py` | 50 | 外掛相依安裝的 pip 約束（純函式）：所有 OpenCV 發行版鎖在 5 以下（共用同一個 `cv2` 目錄；OpenCV 5 移除了 Haar 分類器），組 `pip install -c` 指令 |
| `model_dir.py` | 50 | 外掛模型目錄的共用解析 |
| `plugin_api.py` | 73 | **外掛 API 版本**（純函式）：`PLUGIN_API_VERSION`、讀外掛目錄的 `plugin.json`（`min_api_version`，沒有檔案視為 1）、`check_compatible` 對需要較新版本的外掛丟 `IncompatiblePluginError`；docstring 列出每一版新增的主程式介面 |
| `tool_dialog.py` | 125 | **`ToolDialogMixin`**（外掛 API 2）：外掛單次影像工具對話框的共用流程，OK → `_required_packages` 的套件安裝詢問 → `EffectWorker` 跑 `_transform()` → 存 `<stem>_<output_suffix>.png` → toast 結果並在成功時關閉；含 `WorkerHostMixin`。並轉出 `make_slider`、`slider_row`、`output_path`、`show_toast` 給外掛用；shared transform jobs／settings-only retry factory，原生 cross-project constructors 不變 |
| `subprocess_util.py` | 36 | 外掛 worker 呼叫子 Python 的共用 helper |
| `worker_host.py` | 112 | **`WorkerHostMixin`**：QDialog 共用非阻塞拆卸；中斷／斷開輸出，標題取消狀態與 disabled controls，背景退場完成後才完成原始結果；non-Qt adapter 保留同步契約 |
| `worker_retirement.py` | 90 | 獨立 QThread 持有 owner／reparented workers；背景 stop／abort／wait，queued terminal slot 以 wait(0) 確认 TLS exit 後釋放；owner destroyed 保護與 final app-exit drain |

### 6.18 `Imervue/mcp_server/`

把 Imervue 的影像能力以 Model Context Protocol 暴露給 LLM 代理。**完全無 Qt、無選用相依**。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `server.py` | 439 | JSON-RPC 2.0 over stdio 的協定迴圈 |
| `tools.py` | 176 | 工具集的對外門面：re-export 全部 58 個處理器，`_TOOL_DEFINITIONS`（讀取類在前、編輯類在後，即 `tools/list` 順序）與 `register_default_tools` |
| `tools_read.py` | 662 | 22 個讀取／分析類處理器：`list_images`、`read_image_metadata`、`read_xmp_tags`、`extract_gps`、`image_statistics`、`quality_metrics`、`ocr_text`、`find_similar`、`search_images`、`convert_format`、`puppet_inspect`、`puppet_validate`、`puppet_schema`… |
| `tools_edit.py` | 883 | 36 個寫出類處理器（讀 `source`、寫 `destination`）：浮水印、外框、拼貼、裁切／縮放／旋轉與各種效果（`levels_image`、`curve_image`、`clahe_image`、`lens_correction_image`…） |
| `tool_support.py` | 77 | 兩組處理器共用：`IMAGE_EXTENSIONS`（即 `formats.RASTER_EXTENSIONS`）、`NO_ALPHA_FORMATS`、`open_upright` / `load_rgba_array`（委派 `shown.open_shown` / `load_shown_rgba`，RAW 經 libraw 顯像；每個工具都在依 EXIF 轉正後的影像上運作，尺寸與座標也以它為準）、`validated_dir`／`validated_file`、`json_safe` |
| `tool_defs_read.py` | 387 | `READ_TOOL_DEFINITIONS`：讀取類工具的名稱、描述、輸入 schema、處理器 |
| `tool_defs_edit.py` | 929 | `EDIT_TOOL_DEFINITIONS`：寫出類工具的同上資料 |
| `tool_schemas.py` | 602 | 每個工具的輸出 schema 與 annotation（有 parity test 強制與 `_TOOL_DEFINITIONS` 對齊） |
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

留在主程式：跑在預設相依集、失敗最多壞一張圖、屬於日常瀏覽 / 顯影流程。例外：AI 放大（`gui/ai_upscale_dialog.py`）與 CLIP 語意搜尋 / Auto-Tag（`library/clip_onnx.py`）在主程式裡，首次使用才經 `ensure_dependencies` 安裝 onnxruntime，模型依固定 revision 下載。

| 外掛 | 檔案/行數 | 功用 | 重量級相依 |
| --- | --- | --- | --- |
| `safety_review` | 15 / 4,622 | NSFW 偵測與馬賽克（僅生殖器與肛門，**絕不處理乳頭/胸部**）。含手動編輯器、YOLO 資料集匯出、fine-tune 腳本；打碼幾何與繪製集中在 `_censor_core.py`，App 內偵測與凍結環境的 `_runner.py`（以同層檔案載入）共用；NudeNet 偵測器一律包成 `_AnyPathDetector`（先 `np.fromfile` + `cv2.imdecode` 解碼再交給它，Windows 上路徑含非 ASCII 字元也讀得到）；存檔一律走 `_censor_core._save_as`（`.tmp` + `os.replace`，覆寫原檔模式失敗也不毀原圖） | nudenet, ultralytics, huggingface_hub |
| `spanish_translation` | 3 / 1,824 | 西班牙文語言外掛，示範在 `register_languages()` 裡呼叫 `register_language()` | — |
| `pet_integrations` | 9 / 1,735 | 桌面寵物整合（OBS 事件、Twitch 聊天關鍵字〔`=hi` 整則、`!dance*` 開頭、`/re/` 正規式，經主程式 `desktop_pet.command_parser`〕、本機 webhook `127.0.0.1:9876/trigger`、Windows 通知），也是寵物外掛的範例：`on_pet_created` 把四個 `IntegrationController` 交給寵物（`add_integration`）並恢復存成開啟的；外掛選單的核取項目（缺套件先 `ensure_dependencies`）與設定對話框；卸載時 `remove_integration` | obs-websocket-py、winrt（首次使用時安裝） |
| `ai_background_remover` | 3 / 915 | rembg (U²-Net) 去背，單張 + 批次，凍結環境走子行程 | rembg, onnxruntime |
| `ai_object_remove` | 4 / 832 | 點選物件 → 洪水填色遮罩 → 擴散修補；另有 SAM ONNX point-prompt 路徑 | onnxruntime (SAM) |
| `object_splitter` | 4 / 701 | 去背 + 連通元件（`_components.py`，scipy 為主、BFS 後備，外掛與 `_runner.py` 共用）→ 每個物件存成透明 PNG | rembg |
| `gpu_develop` | 7 / 664 | 批次匯出在獨立顯示卡上套用顯影 recipe：登錄 `develop_backends` 後端（多個視窗各有實例，最後一個卸載才取消登錄）；`adapter_policy` 只選 `DiscreteGPU`（Windows 先 Vulkan 再 D3D12：wgpu 的 D3D12 經 FXC 編譯，浮點運算被重排，與 CPU 差得較多），內建顯示卡與軟體算繪器一律不用，wgpu instance 也只啟用這些 API（Vulkan 與 OpenGL 一起探測曾讓 `wgpuCreateInstance` 當掉）；`params` 把逐通道階段（白平衡、曝光、白黑場、亮度、對比、色調曲線）用 CPU 階段本身跑過 0..255 斜坡做成查表，只有亮部/陰影、vibrance、飽和度在 shader 裡算；對比要整張圖的平均亮度，所以分兩次 dispatch；`develop_shader` 不用 workgroup 記憶體與 barrier（某 D3D12 驅動因此整批不處理），亮度總和用每個 workgroup 一格的全域 atomic；`renderer` 大圖分段、wgpu 錯誤轉 `RuntimeError`（該張改回 CPU），主程式的階段表與 `GPU_STAGES` 不符時不提供 GPU。24MP 約 0.12 秒（CPU 約 7 秒），單一階段與 CPU 差最多 1 階 | wgpu（首次使用時安裝） |
| `video_source` | 3 / 612 | 瀏覽影片並抽出靜幀 | imageio-ffmpeg |
| `cloud_share` | 3 / 484 | 上傳到 WebDAV / Imgur（HTTPS-only 守衛，僅在使用者按下上傳時執行） | — |
| `ai_motion_deblur` | 3 / 480 | Wiener 反捲積 + 選用 ONNX | onnxruntime |
| `ai_portrait_relight` | 3 / 464 | 啟發式 Lambert 打光 + 選用 ONNX | onnxruntime |
| `ai_smart_resize` | 3 / 459 | Seam carving 內容感知縮放 | — (重運算) |
| `npr_filters` | 3 / 428 | 鉛筆 / 油畫 / 水彩 / 線稿 | opencv-python |
| `ai_colorize` | 3 / 406 | 黑白上色：啟發式調色盤 + ONNX | onnxruntime |
| `ai_denoise` | 3 / 366 | 雙邊濾波（純 NumPy）或 ONNX 神經降噪 | onnxruntime |
| `ai_style_transfer` | 3 / 309 | ONNX 快速神經風格轉換，自動探索 `models/*.onnx` | onnxruntime |
| `portrait_mode` | 3 / 307 | rembg 主體遮罩 + 背景模糊（假淺景深） | rembg |
| `png_to_icon` | 2 / 195 | PNG → 多尺寸 `.ico` + `.png`（純函式 `write_icon_set`，測試 `tests/test_png_to_icon.py`） | — (Pillow 為預設相依) |
| `ai_outpaint` | 3 / 192 | 擴張畫布 + 擴散填補邊界 | — |

上表的 `ai_colorize`、`ai_denoise`、`ai_motion_deblur`、`ai_portrait_relight`、`ai_smart_resize`、`ai_style_transfer`、`npr_filters`、`portrait_mode`、`ai_outpaint` 這 9 個單圖工具都以主程式的 `ToolDialogMixin` 建對話框（只留 `_transform()` / `_required_packages()` 與 toast 鍵），`ai_object_remove`、`cloud_share` 用它的 `show_toast` / `output_path`；這 11 個與 `gpu_develop` 都帶 `plugin.json`（`{"min_api_version": 2}`）。

**發佈規則（硬性要求）**：`/plugins/` 在本 repo 是 gitignored（新檔要 `git add -f`），
且外掛透過另一個公開 repo `D:\Codes\Imervue_Plugins`（remote `Jeffrey-Plugin-Repos/Imervue_Plugins`）
發給使用者。下載器讀的是 **`main` 分支**，且只抓外掛目錄下的**扁平檔案**（`models/` 之類子目錄不會下載）。

---

## 8. `tests/` 測試體系

946 個檔、157,840 行。`pyproject.toml` 定義三個互斥層級 marker：

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

Windows 的 `offscreen` 平台不會自動列出系統字型；`qapp` 在字型資料庫為空時載入系統的 Segoe UI 與 Courier New，並沿用原字級把預設字型設為 Segoe UI，讓頁碼、沿選取範圍文字、字型預覽與介面縮放測試使用真實字形。字型預覽測試切換到資料庫內另一個字型，不假設某個字型在所有作業系統都有安裝。

**輔助模組**：`_qt_skip.py`（GL widget 的 CI skip marker）、`_instant_worker.py`、`_toast_spy.py`、`_app_appearance.py`（`app_appearance_restored`：字型與樣式表還原 context manager）。

**CI 的行程結束碼**：`CI=true` 時 `conftest.py` 為了避開 Qt teardown 的 access violation 會提前結束行程，結束碼一律是
pytest 回報的那一個。`pytest_sessionfinish` 把它記在該次執行的 `config.stash`；全過（0）時 `pytest_unconfigure` 在印完
摘要後直接 `TerminateProcess`，其餘由 `pytest_configure` 註冊的 `atexit` 以該結束碼 `os._exit`。session 沒跑完就沒有
結束碼可帶（例如選項打錯），兩層都不介入，行程照 pytest 自己的結束碼結束。pytest 是以 `tests.conftest` 載入這個檔，
測試要用它一律寫 `from tests import conftest` 或 `from tests.conftest import …`；裸的 `import conftest` 會把同一個檔
再執行一份。`tests/test_conftest_exit_status.py` 以子行程實跑三種結束碼（有失敗、全過、選項錯誤），並掃描 `tests/`
不得出現裸 import。
子程序同時將 rootdir 與 confcutdir 設為自己的測試目錄，保留專案設定與 fixture 插件；
跨磁碟的單檔 probe 不再掃描系統暫存目錄的相鄰路徑。消失目錄的回歸測試驗證隔離邊界。

### Qt / OpenGL 在無頭 CI 上的硬規則

GitHub Actions Windows runner 在同一個 pytest session 建太多 `QOpenGLWidget` 會
`Windows fatal exception: access violation`（offscreen GL surface pool 有限，溢出會毀壞行程記憶體）。

因此**每個會建構 `PetWindow` / `PuppetCanvas` / `PuppetWorkspace` 或任何 `QOpenGLWidget` 子類的測試檔**
都必須在模組頂端加：

```python
from _qt_skip import pytestmark  # noqa: E402,F401
```

驗證：`CI=true py -m pytest <file> -q` — 檔內每個測試都必須是 `s`。

`.github/workflows/test.yml` 的獨立 `real-gl` job 在 Ubuntu 24.04／Mesa software GL／Xvfb 使用 `CI=false`、`QT_QPA_PLATFORM=xcb`，不改 Windows guard。實際 shader／FBO／像素與 GL handles 驗證、完整工作區切頁／多文件復原／異常與 multiwindow close 選取十個案例；JUnit 必須至少十個通過、零 skipped／failed／error 且有 actual renderer property。`scripts/verify_gl_report.py` 拒絕未執行／只有 skip 的假成功，artifact 保留七天；此 job 也是 dev 發佈必要條件。GL CI 是實際 API correctness，不是硬體 GPU throughput。詳見 `docs/testing-real-gl.md`。

一般 suite 的 `test_autosave_crash_integration.py` 以 fresh child／isolated profile 實跑兩份背景 autosave，再於第三份 bundle 與 metadata commit 之間 os._exit(23)；新的復原子程序只還原兩份 coherent versions 到 dirty tabs、忽略 orphan 且不可重複復原。`test_workspace_lifecycle_gl.py` 的 five cases 在實際 windows／workers 驗證切頁、Undo／Redo／mask、關閉取消、寫入中關閉、磁碟滿／permission、damaged image handoff、多視窗 GL release；所有 GL 模組仍保留 shared skip marker。

---

## 9. 建置、封裝與 CI

| 項目 | 檔案 | 說明 |
| --- | --- | --- |
| PyInstaller | `Imervue.spec` / `Imervue_mac.spec` | Windows / macOS spec |
| Nuitka | `build_nuitka/`、`nuitka.md` | 需在 import OpenGL 前關掉 `USE_ACCELERATE` |
| auto-py-to-exe | `packaging/auto_py_to_exe_config.json` | |
| AppImage | `packaging/build_appimage.sh` | Linux |
| 跨平台說明 | `packaging/CROSS_PLATFORM.md` | |
| CI | `.github/workflows/test.yml`、`release.yml` | release.yml 釘死所有相依且 wheels-only；**Nuitka 只有 sdist，必須維持 `--no-binary` 豁免**。持有 PyPI token 的兩個 job（`release.yml` 的 `release`、`test.yml` 的 `publish-dev`）只安裝雜湊鎖定的 `.github/requirements/publish.txt`（`build`、`twine`、`setuptools`，由同目錄的 `publish.in` 產生，指令寫在 `publish.in` 開頭），並以 `python -m build --no-isolation` 建置，所以建置後端也是鎖定的那一版；這兩個 job 出現其他 `pip install`、隔離建置，或 `build-system.requires` 的下限高於鎖定版本時，`tests/test_workflow_actions.py` 會失敗 |
| dev 頻道發佈 | `test.yml` 的 `publish-dev` job、`scripts/dev_release.py`、`dev.toml` | 推到 `dev` 且 `lint`／`docs`／`fast`／`extended`／`real-gl` 全過後，以 `dev.toml` 建出 `Imervue_dev` 上傳 PyPI；只在該 commit 仍是 `dev` 頂端、且 wheel 與 PyPI 上最新一版內容不同時才上傳。版號由 `dev_release.py` 取 PyPI 最新版加一個 patch（`dev.toml` 的版號只是下限），不回寫 repo。建置工具與 release.yml 相同：兩邊都只安裝 `.github/requirements/publish.txt`，並以 `python -m build --no-isolation` 建置（`tests/test_dev_release.py` 把關）；`dev.toml` 與 `pyproject.toml` 出貨內容一致由 `tests/test_packaging_metadata.py` 把關 |
| 實際 GL regression | `scripts/verify_gl_report.py`、`tests/test_workspace_lifecycle_gl.py`、`tests/test_tile_textures_gl.py` | 獨立 Linux／Mesa／Xvfb job；先 ldd 檢查 XCB／GLX runtime，uncaptured Qt diagnostics，再 no-skip／case count／renderer evidence gate；像素、貼圖容量／zoom／handles 與跨工作區／多文件／異常／多視窗行為；正常 Windows headless jobs 仍 skip GL construction |
| 開發效能基準 | `scripts/performance_benchmark.py`（428 行）、`performance_support.py`（187 行）、`performance_gl.py`（88 行）、`performance_ram.py`（107 行）、`performance_autosave.py`（101 行）、`performance_workers.py`（107 行） | 新子程序／隔離 profile、固定合成資料、RSS／原始樣本／真實 GL 像素；Modify 分別記錄 UI 請求、低解析／完整結果、CPU 與 heartbeat，來源雜湊辨識未提交工作樹。Paint 額外記錄同筆畫提交後的 retained history bytes 與明確 damage hints。背景 autosave 分開記錄 UI enqueue、worker materialize／compress-write、request-to-recorded、heartbeat 與 RSS。worker 工具以真實 QDialog／QThread 驗證不可中斷與 blocking stop 下 UI／actual retirement／heartbeat。RAM 工具以提供的 RAW／raster 跑兩個真實 decoder、保留結果、actual bytes／ticket peak／RSS 與 admission refusal，fresh profile 隔離使用者資料。只限 checkout，不進產品 CLI；`docs/performance/` 保存基準／門檻，測試涵蓋擁有權、報告、子程序／GL 與換行無關雜湊 |
| PyPI 套件內容 | `pyproject.toml`、`dev.toml` 的 `[tool.setuptools.packages] find`，`MANIFEST.in` | 兩個 wheel 都只裝一個頂層套件 `Imervue`：`find` 的 `include = ["Imervue", "Imervue.*"]` 把套件探索限制在它底下，否則有 `__init__.py` 的 `tests/` 會被裝成頂層 `tests` 套件。sdist 也不帶測試（`MANIFEST.in` 最後一行的 `prune tests`；少了它 setuptools 會自動把 `tests/test_*.py` 收進 sdist），測試只從 repo 的 checkout 執行。`namespaces = false` 會丟掉沒有 `__init__.py` 的目錄。三件事都由 `tests/test_packaging_metadata.py` 把關 |
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
外掛的同型對話框改繼承 `plugin/tool_dialog.py` 的 `ToolDialogMixin`（9 個影像外掛），只寫 `_transform()` 與 toast 鍵；用到它的外掛要在 `plugin.json` 宣告外掛 API 2（`plugin/plugin_api.py`，`tests/test_plugin_api.py` 檢查）。

### 10.3 `WorkerHostMixin`

`Imervue/plugin/worker_host.py`。凡是擁有背景 `QThread` 的 `QDialog` 都繼承它，
解決關閉對話框時 `QThread destroyed while still running` 的當機。它覆寫 `done()`（`accept()`、`reject()` 都走到這裡）與 `closeEvent`；UI 只要求中斷、斷開 worker 輸出、暫停 controls 並更新標題，立即返回。`worker_retirement.py` 持有宿主並將 worker reparent 到獨立 retirement QThread，在背景呼叫 stop／abort 與 wait。所有 worker 確實退出後，以 queued signal 完成第一個 dialog result；晚到的 accept 不可覆寫 cancel，關閉事件在等待中 ignore。宿主提前 destroyed 仍保留執行緒，不再觸碰 UI。retirement 自身 finished 之後也以 wait(0) 檢查 TLS 退場，不在 UI join。**不要手寫 `closeEvent` / `accept` 拆卸邏輯。**

取消 hooks 必須只操作 thread-safe flags／子程序，不能操作 GUI；現有 bundled consumers 的 hooks 符合此契約。`_apply_save.finalize_worker` 對共享工具的 custom done 也使用 passive retirement（不取消成功輸出），避免 result signal 早於 run／TLS 結束時 UI 等待。non-Qt adapters 保留同步 duck-typed teardown。最終 application event-loop exit 才 drain 尚未退出的 retirement threads，這個終止等待不在可繼續操作的 dialog-cancel 延遲門檻內。

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

### 10.13 Modify 的最新版本背景預覽

`gui/develop_preview.PreviewScheduler` 合併等待請求，每面板至多一個低解析與一個完整 worker。
worker 只讀共享來源與獨立 recipe，於具名 CPU 階段間檢查取消；版本檢查再擋掉無法立即停止的舊結果。
完整 QImage 在背景準備，queued QObject slot 才更新 canvas；signal sender 由 application 保留至 UI queued delete，
面板銷毀時不等待 thread pool。低解析顯示配完整幾何，保存／破壞性效果先解析完整品質；
尚未完成時的明確保存可同步等待，不能把近似預覽烘焙進原檔。

---

### 10.14 Paint 歷史的容量與增量像素

`UndoStack` 保留完整結構／屬性 metadata 與弱圖層身分，像素由 `PixelStore` 切為 256px 不可變區塊並共用。
筆刷／橡皮擦的 dispatcher 僅在提交回呼期間提供完整 damage；未知操作、來源更換與部分失敗比較所有陣列，
不以相同陣列身分推論像素未改變。Undo／Redo patch 存活的可寫陣列；刪除／重建與幾何操作可實體化完整狀態。
容量計算包含 baseline、Undo、Redo、唯一 tile payload、Python metadata 與弱索引；512 MiB 超額淘汰最舊步驟並重建索引。
單一狀態超額清除歷史，保留 live 文件。`committed_snapshot().materialize()` 產生獨立可編輯陣列，callback／Qt／composite 不入歷史。

### 10.15 縮圖牆共用可見範圍與 bounded jobs

`TileViewport` 依 row／column 間距計算候選索引，不遍歷 model；buffer 為周邊一列／欄，精確淘汰只保護有正面積交集的 cached tiles。
已載入大 SVG／full-size tile 的實際尺寸也入 conservative bound，正常 landing 在 O(1) 更新最大尺寸。
renderer 保留 frame geometry 供 texture admission／loader 共用，`finally` 清除，下一幀重新反映捲動／縮放／DPR。
`ThumbnailQueue` 不為未拜訪列建立 QRunnable；完成訊號釋出 slot，重新優先載入目前 viewport。
進度只計目前可見／buffer、仍執行與明確請求；舊世代 completion 不會啟動新世代工作或清除 filmstrip 標記。
full-resolution mode 為可能跨 cell 的圖片保留 bounded background discovery；普通尺寸只按需載入。
filmstrip／retry 共用 slots 並合併 active 請求；source rewrite 保留一個新版本再解碼。Esc 保留有效 queue／warm cache／原捲動位置。

### 10.16 預取 RAM admission 與實際 worker 生命週期

`RamBudget` 的 process cap 為 physical RAM 20%（256 MiB–8 GiB），psutil 缺少／失敗共用 2 GiB fallback；live budgets 公平分配視窗份額。
只管理 speculative Deep Zoom 預取：actual pyramid NumPy buffers 加所有 in-flight／queued result tickets，與 VRAM 材質預算獨立。
RAW header 取 libraw sensor dimensions，不把 embedded preview 或檔案大小當成解碼大小；24／48 bytes-per-pixel 估一般／RAW scratch，非 identity recipe 160，unknown 512 MiB。
Header 與 admission 在 worker 執行，拒絕不等待；result ticket 換 actual bytes 後 queued 回 UI，store 原子轉為 cache bytes，淘汰最舊 cache，同時保留張數 ceiling。
cancel 只退休 identity／設 abort，不提前歸還仍執行的 ticket；所有成功／拒絕／失敗／abort 都發 completed，stale 同路徑 worker 不影響 replacement。
owner destruction 回收已完成但未送達的票券；仍執行的 worker 持有 budget，abort 返回時自行歸還。被提升為前景的 refused job 走一般 foreground load。
新視窗縮小 quota 後，舊 cache 在下一次 schedule 淘汰；既有 reservation 不改名、不失蹤，超額時停止新 admission。
這是估算與快取 admission，不是 allocator 或整個 process RSS 上限；foreground image／縮圖牆／編輯器與第三方 decoder scratch 不冒稱受此 speculative quota 控制。

### 10.17 背景 autosave 與一致文件版本

QObject 工作區 timer 取 UndoStack.available_snapshot 的 immutable committed content，O(1) 建立 SaveRequest，不在 worker 讀 live pixels；正在進行的 stroke 不混入舊版本。
缺少／超出歷史 cap 的 document 先在 UI 深複製為獨立 OwnedContent；此 fallback 可能有複製停頓，不能冒稱所有文件都是 O(1) enqueue。
AutosaveJobs 每 workspace 只有一個 writer、每 document_id 一個最新 pending；duplicate active version 清除 obsolete pending，Undo 回正在寫入的版本不會留下較新的錯誤待存版本。
worker materialize、NPZ 壓縮、metadata 寫入／quota 輪替都離開 UI，沿用 auto_save 的 atomic／每文件 quota。失敗保留舊有效檔並在 UI toast，空文件不冒稱成功。
request 與 writer 不持有 canvas，signals／Jobs 由 QApplication 持有到 queued 完成；UI 直接記錄 timestamps／owned paths，避免中間另一事件 close 造成 unowned 檔案。
替換 document／關閉 tab／discard all 標記取消；已執行 compression 不等待，在 writer 結束或 UI delivery 檢查後另派 discard job 清除 late snapshot。
explicit take_autosave_snapshot_now 仍同步回傳 path，非 QObject adapter 保留同步行為；一般 GUI timer 走 background queue。

### 10.18 跨視窗的背景工作與 durable item results

`system/job_state.py` 是 pure thread-safe state；export／scanner／AI upscale／shared plugin
EffectWorker／plugin downloader 在輸出或 chunk transaction 成功後才 record item。
`gui/background_jobs.py` 以 100ms O(1) immutable summaries 輪詢，不依賴可能被 WorkerHost
斷開的 worker signals；register 時 setParent(None)，避免 QWidget 的 C++ destruction
摧毀活著的 QThread。Terminal packet 不等於 actual exit，wait(0) 成功才 release／retry。
原始與每次 retry 都是不同 job，factory 只取 failed_paths，不碰已完成輸出；未完成且取消
的項目不混作失敗。Plugin install 是整套原子項目，暫存檔不算完成；下載重試整套失敗安裝。
未開始項目只保留來源 key，不預先配置 JobItem；已完成資料使用 slotted immutable records。
finish 以總數 O(1) 結束，不逐項改寫未完成資料；需要時才 resolve failure／cancel 狀態。
500 筆 detail rows 只 materialize bounded results、優先失敗，無輸出的索引成功項目不展開；完整結果另存 atomic JSON；已完成歷史由 Clear finished 釋放。
Registry 與原始對話框互相獨立，Qt ownership／retirement 完成後才清除 actual worker。
最後主視窗的 os._exit 路徑明確 drain registry 與 retiring workers，再卸載外掛；不能只靠 aboutToQuit，次要視窗不做 global drain。


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
   接近上限的包括 `gui/file_tree_view.py`(944)、`mcp_server/tool_defs_edit.py`(929) 與 `gui/develop_panel.py`(920)；要在接近 1000 行的檔案
   加程式，先把一組內聚的方法拆成模組（mixin 或模組函式），並先補特性測試。
   大型 Qt 類別的拆法：把內聚的方法群原封不動搬進 `<類別>…Mixin`，類別繼承它們，對外方法名不變；
   原模組若是別處的匯入來源，用 `__all__` 保住 re-export（自動移除未用 import 會把只為轉手存在的名稱刪掉）。
   測試若在原模組上 monkeypatch 某個名稱，要改到實際查找它的新模組。

7. **MCP 工具新增流程**：處理器寫在 `tools_read.py` 或 `tools_edit.py`，定義加進對應的 `tool_defs_*.py`，並從 `tools.py` re-export（加進 import 與 `__all__`）；同時必須在 `tool_schemas.py` 加 schema，並在 `cli_tools.py` 的 `BRIDGED` 給它一個 CLI 名稱（`tests/test_cli_tools.py` 強制每個 MCP 工具都有 CLI 子指令）
   （有 parity test 強制），且工具必須保持無 Qt、無選用相依。

8. **Qt 對話框測試**：在 `qapp` fixture 下建立對話框時 parent 傳 `None`，
   不要傳暫時性的 `QWidget`，否則 teardown 會 access violation。

9. **不要用 `QAction.menu()` 走訪選單**（§10.10）。它讓外掛語言從語言選單消失、讓命令面板用過之後
   「重新載入外掛」拿到失效的 Plugins 選單。外掛的 `on_build_menu_bar` 拿到的是 Plugins `QMenu`
   不是 `QMenuBar`，要放進 Extra Tools 子選單請 `findChild(QMenu, "extra_tools.<key>")`。

10. **`QPdfWriter` 寫不進目標時不丟例外。** 只會讓 `QPainter.begin` 回傳 `False`，之後的繪製全是
    no-op，呼叫端照常回報「已儲存」。PDF 輸出一律用 `export/pdf_output.py:begin_pdf_painter`，
    它在失敗時丟 `OSError`。`QImage.save` / `QPixmap.save` 同理只回傳 `bool`，回傳值一定要檢查。

11. **每個模組都要有正式程式 import 它**：`tests/test_unwired_modules.py` 掃 `Imervue/`、`plugins/` 與根目錄
    `*.spec` 的 import，新增模組若沒人 import 就失敗（`Imervue_mac.spec` 用 `system/macos_bundle.py` 也算）。
    當初沒人 import 的 56 個模組，27 個已刪除、29 個已逐一接上 UI，`_KNOWN_UNWIRED` 現在是空的、只能維持空的。

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





15. **切換到 Paint 不得載入瀏覽圖片。** `_on_main_tab_changed` 只確保工作區已建立；
    主視窗 File 選單的 `Open Current Image in Paint` 與 Paint 主分頁列的左右翻圖，
    才呼叫 `_bind_paint_workspace_to_current_image`。先解碼成功，再開新文件；沒有目前圖片
    或解碼失敗時保留全部文件、髒狀態與復原紀錄。`E` 仍開啟獨立的註解編輯器。

## FrontEngine puppet consumer

FrontEngine optionally reuses the public puppet reader/Canvas/controllers and desktop-pet
script engine in its own windows. It does not instantiate PetWindow or modify Imervue
preferences. Archive v1 and runtime import contracts are listed in architecture.md §6.
FrontEngine validates containers and tests reference reader round trips plus real GL frames.
