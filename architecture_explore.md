# Imervue 架構全覽 (architecture_explore)

> 產出日期：2026-08-03 · 對應 commit `694e63c` · 分支 `dev` · 版本 `1.0.86`
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
| `tests/` | 731 | 121,899 |
| `Imervue/paint/`（含 `docks/`、`tools/`） | 180 | 45,700 |
| `Imervue/gui/` | 143 | 30,914 |
| `Imervue/puppet/` | 53 | 15,131 |
| `Imervue/image/` | 112 | 12,807 |
| `Imervue/gpu_image_view/`（含 `actions/`、`images/`） | 60 | 12,634 |
| `Imervue/multi_language/` | 8 | 11,299 |
| `Imervue/desktop_pet/` | 32 | 8,175 |
| `Imervue/mcp_server/` | 11 | 4,422 |
| `Imervue/library/` | 32 | 4,140 |
| `Imervue/menu/` | 11 | 3,463 |
| `Imervue/` 根層 | 5 | 3,147 |
| `Imervue/plugin/` | 9 | 2,200 |
| `Imervue/system/` | 15 | 1,771 |
| `Imervue/export/` | 8 | 1,047 |
| `Imervue/user_settings/` | 9 | 992 |
| `Imervue/sessions/` + `macros/` + `external/` | 9 | 933 |
| `plugins/`（17 個外掛） | 62 | 14,315 |
| **總計** | **1,490** | **294,989** |

其中 `Imervue/` 套件本身 697 檔 / 158,775 行。

測試碼與產品碼比約 **0.70 : 1**（122k vs 173k），這是專案開發規範中「無測試即未完成」規則的直接體現。

> 數字以 `CLAUDE.md`「Architecture Map」章節裡的指令重新產生，不要手改。

---

## 3. 執行入口與啟動流程

進入點：`Imervue/__main__.py`（`py -m Imervue`）。

```
py -m Imervue [--debug] [--software_opengl] [file]
   │
   ├─ 1. 凍結環境偵測 → 關閉 OpenGL_accelerate（Nuitka 打包後 Cython 擴充會壞）
   ├─ 2. Windows：強制 UTF-8 I/O（避免 CJK 顯示成 ?）
   ├─ 3. _set_windows_app_user_model_id() → 工作列圖示身分
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
| `py -m Imervue.cli …` | `Imervue/cli.py` | headless 批次：resize / watermark / info / convert，只用純 NumPy+Pillow 路徑，完全不起 Qt |
| `py -m Imervue.mcp_server` | `Imervue/mcp_server/__main__.py` | stdio JSON-RPC 2.0 MCP server |
| `exe/start_Imervue.py` | — | PyInstaller / auto-py-to-exe 的啟動 shim |

---

## 4. 頂層結構：一個主視窗、五個分頁

`ImervueMainWindow(QMainWindow)`（`Imervue/Imervue_main_window.py`，2,296 行）是唯一的協調者。
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
| `__main__.py` | 102 | CLI 參數解析、凍結環境修補、QApplication 建立、主視窗啟動 |
| `Imervue_main_window.py` | 2,296 | `ImervueMainWindow`：5 分頁協調者、狀態列、過濾列、分頁狀態機、螢幕自適應、資料夾監控 |
| `cli.py` | 578 | headless 批次 CLI（resize / watermark / info / convert…），只走純 NumPy+Pillow 路徑 |
| `integration_guide.py` | 175 | 外掛系統初始化：建立 `PluginManager`、dispatch 主分頁 hook、把外掛語言掛進語言選單 |

### 6.2 `Imervue/system/`

作業系統與應用程式層級的基礎設施。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `app_paths.py` | 110 | 凍結環境安全的路徑解析（icon / plugins / 設定檔），PyInstaller & Nuitka 都適用 |
| `clipboard_monitor.py` | 145 | ShareX 式剪貼簿監聽：PrintScreen 截圖 → 自動開啟註解視窗 |
| `error_report.py` | 146 | 一鍵支援包產生器（日誌 + 環境資訊打包） |
| `file_association.py` | 240 | 跨平台檔案關聯「用 Imervue 開啟」註冊 / 取消 |
| `file_tree_watcher.py` | 172 | watchdog 遞迴監看樹根，跨執行緒 signal 回 UI 觸發 model refresh |
| `log_setup.py` | 40 | 集中式 logging 設定 |
| `macos_bundle.py` | 67 | macOS `.app` Info.plist 文件型別關聯 |
| `onboarding.py` | 82 | 首次啟動導覽步驟註冊表 |
| `release_notes.py` | 112 | What's-New 對話框的版本說明資料 |
| `theme_color_math.py` | 92 | WCAG 對比度數學，供主題撰寫與無障礙稽核 |
| `themes.py` | 176 | 內建配色主題 |
| `trash_ops.py` | 200 | **背景批次刪除**：`send2trash` 單次呼叫成本 ~0.27s，因此所有刪除必須走這裡，禁止 per-file 迴圈 |
| `ui_scale.py` | 62 | 應用程式全域 UI 縮放係數（必須在任何 widget 佈局前套用） |
| `watch_folder.py` | 141 | 監控資料夾自動化：新檔案進來自動套用動作 |

### 6.3 `Imervue/user_settings/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `user_setting_dict.py` | 338 | **全域設定字典**。多帳號（profile）容器、v1→v2 自動遷移、去抖非同步存檔、atomic JSON writer（`.tmp` + `os.replace`） |
| `bookmark.py` | 91 | 跨資料夾書籤 / 收藏集合 |
| `code_replacements.py` | 70 | 片語展開（caption、keyword 用的縮寫） |
| `color_labels.py` | 121 | 每圖色標籤（紅/黃/綠/藍/紫），與五星評分獨立 |
| `metadata_template.py` | 73 | IPTC/XMP 欄位範本（stationery pad） |
| `recent_image.py` | 66 | 最近資料夾 / 圖片追蹤，上限由設定控制 |
| `tag_validator.py` | 107 | 標籤 / 相簿集合的完整性檢查與清理 |
| `tags.py` | 134 | 自訂標籤與虛擬相簿管理 |

### 6.4 `Imervue/multi_language/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `language_wrapper.py` | 87 | 單例 `language_wrapper`。內建 5 語言；`register_language()` 供外掛新增語言，`merge_translations()` 供外掛補鍵（不覆寫既有鍵） |
| `english.py` | 2,235 | 英文字典（**正規來源**，其他語言以它為鍵集基準） |
| `traditional_chinese.py` | 2,200 | 繁體中文 |
| `chinese.py` | 2,201 | 簡體中文 |
| `japanese.py` | 2,214 | 日文 |
| `korean.py` | 2,212 | 韓文 |
| `translation_validation.py` | 157 | 字典進入 `LanguageWrapper` 前的驗證（缺鍵 / 型別） |

> 第 6 個語言（西班牙文）以 `plugins/spanish_translation/` 形式提供，示範外掛語言註冊流程。

### 6.5 `Imervue/sessions/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `session_manager.py` | 248 | Session / Workspace 存檔與還原（開啟的資料夾、圖片、視圖狀態） |
| `session_migration.py` | 134 | `.imervue-session.json` 的驗證、版本遷移與合併 |
| `folder_session.py` | 39 | 每資料夾視圖 session 的純函式助手 |

### 6.6 `Imervue/macros/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `macro_manager.py` | 300 | 巨集錄製 / 重播：把一批動作套用到選取集 |
| `macro_step_validator.py` | 112 | 錄下來的巨集步驟驗證與整理 |

### 6.7 `Imervue/external/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `editors.py` | 104 | 外部編輯器啟動器。設定存在 `user_setting_dict["external_editors"]`，以非阻塞 `subprocess.Popen` 啟動 |

### 6.8 `Imervue/export/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `contact_sheet.py` | 182 | 索引表 PDF 產生器，用 `QPdfWriter`+`QPainter`（不需 reportlab） |
| `contact_sheet_layouts.py` | 56 | 具名版面預設（紙張 / 格線 / 邊界 / 說明文字） |
| `web_gallery.py` | 262 | 靜態 HTML 相簿產生器，輸出自足資料夾（無外部 JS/CSS 相依） |
| `gallery_sort.py` | 76 | 匯出前的排序 / 過濾 / 分組（依名稱、時間、大小、副檔名、資料夾、拍攝日） |
| `slideshow_mp4.py` | 141 | 幻燈片 MP4 產生器（imageio + ffmpeg） |
| `slideshow_effects.py` | 102 | 純 NumPy 轉場效果（fade、dissolve、wipe…），逐幀決定性 |
| `cheat_sheet.py` | 234 | 可列印的快捷鍵速查表 PDF，隨當前語言產生 |

### 6.9 `Imervue/image/`（純運算核心）

112 個模組、12,919 行，**全部無 Qt import**（少數用 `QPainter` 光柵化文字者除外），可在 worker
執行緒直接呼叫，也是 `cli.py`、`mcp_server/`、`plugins/` 共用的演算法庫。

#### 非破壞性顯影核心（最重要的三個檔）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `recipe.py` | 599 | **`Recipe` dataclass**：一張圖的完整非破壞性編輯描述。`apply()` 是固定順序的管線：幾何(旋轉/翻轉/裁切) → 曝光 → 亮度對比 → vibrance → 飽和度，再依 `extra` 套用 split toning / levels / channel mixer / gradient map / threshold+posterize / lens flare / film grain / layer stack / masks / LUT。另提供 `to_dict`/`from_dict` 往返、`recipe_hash`、`is_identity`，以及 `file_identity()`（md5(前 4KB \| 檔案大小)，避免 mtime 改變就失效） |
| `recipe_store.py` | 367 | 單一 JSON 檔支撐的記憶體 recipe 索引。以路徑為主的 API（`get_for_path`/`set_for_path`），並支援 **virtual copies**（同一張圖的具名 recipe 變體） |
| `recipe_adjustments.py` | 125 | `Recipe.apply` 用到的逐通道色調調整 |
| `recipe_diff.py` | 64 | 兩個 recipe 的 diff 與選擇性合併 |
| `develop_presets.py` | 103 | 具名顯影預設與批次 recipe 同步 |

#### 色調 / 顏色

`curves.py`(246) 曲線 · `tone_curve.py`(153) flag-based 曲線 · `levels.py`(96) 黑白場+gamma ·
`channel_mixer.py`(130) 3×3 矩陣 · `hsl_mixer.py`(110) 分頻 HSL · `split_toning.py`(68) ·
`gradient_map.py`(170) · `gradient_perceptual.py`(145) OkLab/OkLCH 感知混色 ·
`colormap.py`(64) 科學色階 · `lut.py`(238) Adobe `.cube` 讀取與套用 ·
`auto_color_balance.py`(191) 四種自動白平衡 · `posterize.py`(131) · `solarize.py`(52) ·
`velvia.py`(66) 亮度加權飽和 · `film_negative.py`(68) 負片轉正 · `filmic_tonemap.py`(95) ·
`tone_equalizer.py`(81) 分區曝光 · `soft_proof.py`(66) ICC 軟打樣 + 色域外標示

#### 局部對比 / 細節 / 銳利化 / 降噪

`local_contrast.py`(101) clarity+texture · `clahe.py`(107) · `detail_equalizer.py`(76) 分尺度對比 ·
`denoise.py`(84) · `dehaze.py`(85) 暗通道先驗 · `defringe.py`(86) 邊緣色散 ·
`frequency_separation.py`(125) 高低頻分離 · `focus_peaking.py`(64) · `sharpness.py`(54) ·
`flatten_field.py`(98) 去漸層（光害/暗角）

#### 幾何 / 變形

`geometry.py`(151) 裁切+校正+透視 · `crop_geometry.py`(76) 純裁切幾何+三分線 ·
`auto_straighten.py`(93) Hough 水平線偵測 · `lens_correction.py`(151) 畸變/暗角/色差 ·
`distort.py`(66) swirl/pinch/ripple · `polar.py`(69) 極座標 · `kaleidoscope.py`(67) ·
`equirectangular.py`(78) 360° tiny planet · `resample.py`(44) 共用反向映射重採樣 ·
`orientation.py`(56) EXIF orientation 烘焙

#### 藝術效果 / 疊加

`film_grain.py`(147) · `lens_flare.py`(166) · `glow.py`(71) Orton bloom · `emboss.py`(86) ·
`frosted_glass.py`(50) · `dither.py`(57) Bayer · `pixel_sort.py`(59) · `graduated_density.py`(104) ND 漸層 ·
`false_color.py`(57) 曝光分區上色 · `meme.py`(101) · `photo_frame.py`(68) 相框/拍立得/說明文字 ·
`watermark.py`(138) · `scale_bar.py`(72) 比例尺 · `test_charts.py`(76) 校正圖表產生

#### 多影像合成

`hdr_merge.py`(119) · `panorama.py`(84)（包 OpenCV `Stitcher`） · `focus_stack.py`(122) ·
`stack_blend.py`(119) 統計堆疊 · `collage.py`(65) · `anaglyph.py`(80) 紅藍 3D ·
`deflicker.py`(109) 縮時去閃 · `id_photo_sheet.py`(73) 證件照拼版 · `print_layout.py`(112) ·
`multipage.py`(73) 多頁 PDF/TIFF 合併與拆分

#### 遮罩 / 修補 / 圖層

`masks.py`(297) 筆刷/放射/線性遮罩 · `layers.py`(255) 疊加圖層合成 · `healing.py`(104) OpenCV inpaint ·
`clone_stamp.py`(138) · `inpaint.py`(55) 無模型擴散修補 · `segmentation.py`(131) 天空/前景/背景遮罩 ·
`saliency.py`(171) 啟發式顯著性 + 三分法裁切建議

#### 二值化 / 文件

`binarize.py`(50) Sauvola · `otsu.py`(60) · `steganography.py`(76) LSB 隱寫 ·
`ela.py`(54) 錯誤層級分析 · `copy_move.py`(85) 複製貼上偽造偵測

#### I/O、格式與快取

`raw_loader.py`(125) 省記憶體 RAW 載入 · `heif_support.py`(61) · `jxl_support.py`(51) ·
`save_formats.py`(97) 輸出格式中繼資料 · `optimize.py`(74) 目標檔案大小編碼 ·
`export_presets.py`(95) 匯出預設包 · `video_frames.py`(232) 影片解碼原語（瀏覽器與外掛共用） ·
`pyramid.py`(39) `DeepZoomImage` 金字塔 · `tile_manager.py`(95) 圖磚 LRU 快取與淘汰 ·
`thumbnail_disk_cache.py`(231) 縮圖磁碟快取 · `folder_index.py`(60) 每資料夾圖片清單快取

#### 中繼資料

`xmp_sidecar.py`(387) XMP sidecar 讀寫（跨編輯器互通） · `metadata_sync.py`(77) XMP↔EXIF 評分調和 ·
`gps.py`(87) EXIF GPS 擷取 · `gps_geotag.py`(63) 寫入 · `reverse_geocode.py`(152) 離線逆地理編碼 ·
`geo_keywords.py`(46) 地點寫進 XMP 關鍵字 · `face_detection.py`(110) 人臉偵測與人物標籤 ·
`annotations.py`(271) JSON sidecar 註解 · `info.py`(181) 圖片資訊組裝與對話框

#### 分析 / 品質

`histogram.py`(104) · `statistics.py`(66) 逐通道統計 + CSV · `scopes.py`(67) 波形/RGB parade ·
`quality_metrics.py`(89) 無參考品質 · `quality_score.py`(63) 篩選用技術評分 ·
`perceptual_hash.py`(135) pHash 與近似重複分組

#### 其他

`browser_state.py`(403) 共用瀏覽狀態（過濾規格、中繼資料索引、遺失檔案偵測與重定位）·
`batch_move_planner.py`(105) 無碰撞批次搬移規劃 · `animation_edit.py`(96) GIF/APNG 反轉/回力鏢/速度 ·
`caption.py`(92) 本地視覺 LLM 產生 alt-text · `ocr.py`(143) Tesseract · `portrait_retouch.py`(178) ·
`speech_*`／`text_*` 相關在 `paint/`

### 6.10 `Imervue/gpu_image_view/`

OpenGL 檢視器。`GPUImageView(QOpenGLWidget)`（1,758 行）只保留 GL 生命週期與 Qt 事件覆寫，
其餘拆成約 40 個協作者。有兩種顯示狀態：**tile wall**（縮圖牆）與 **deep zoom**（單張深縮放）。

#### 檢視器主體與渲染

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `gpu_image_view.py` | 1,758 | 主 widget：GL 初始化、`paintGL`、事件轉發、deep-zoom 載入狀態機、prefetch、記憶體壓力處理 |
| `gl_renderer.py` | 342 | 現代 OpenGL 渲染器（VBO + GLSL），shader 編譯失敗時退回 immediate mode |
| `tile_grid_renderer.py` | 280 | 縮圖牆 GL 繪製 |
| `deep_zoom_renderer.py` | 281 | Deep-zoom 圖磚 + minimap GL 繪製 |
| `overlay_painter.py` | 1,121 | 所有 `QPainter` 疊層：OSD、HUD、直方圖、badge、filmstrip、letterbox |
| `texture_upload.py` | 163 | 統一 RGBA 材質上傳（含 RGB→RGBA padding） |
| `pbo_uploader.py` | 244 | Pixel-Buffer-Object 串流上傳，避免 GUI 執行緒卡在驅動 staging copy |
| `gl_context.py` | 54 | 判斷在 `paintGL` 之外釋放材質時是否需要先 make-current |

#### 視圖數學（純函式，可無 GL 測試）

`viewport_math.py`(52) 螢幕↔影像座標 · `view_nav.py`(134) · `fit_view.py`(235) fit window/width/height ·
`view_state.py`(117) 每圖縮放記憶 + 隨機跳圖 · `view_animator.py`(207) 緩動（淡入、縮放、慣性平移）·
`minimap.py`(109) · `tile_layout.py`(116) 格線佈局 · `tile_focus.py`(114) 鍵盤焦點游標 ·
`filmstrip.py`(106) 底部縮圖帶佈局 · `video_badge.py`(58) ▶ 播放徽章幾何 ·
`screen_fit`(在 `gui/`) 與 `settle_poll`(在 `gui/`) 配合處理跨螢幕重排

#### 輸入與動作路由

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `input_controller.py` | 430 | 滑鼠 / 滾輪 / 手勢：滾輪縮放、minimap 點擊導航、圖磚框選、中鍵平移 |
| `key_input_handler.py` | 269 | 鍵盤事件路由（F8 HUD、F1-F5 色標籤、Esc、方向鍵） |
| `key_action_dispatcher.py` | 351 | 把 shortcut_manager 解析出的**動作名稱**表格化派送到檢視器操作 |
| `browse_features.py` | 196 | Deep-zoom 瀏覽行為：filmstrip 導航、閱讀模式捲動、平移夾限 |
| `history_controller.py` | 120 | Alt+←/→ 瀏覽歷史堆疊 |
| `drop_handler.py` | 76 | 拖放檔案/資料夾開啟 |
| `clipboard_paste.py` | 83 | 剪貼簿貼上圖片並插入模型 |
| `hover_preview_binding.py` | 56 | 縮圖懸停預覽彈窗綁定 |
| `cull_actions.py` | 110 | 色標籤與 pick/reject 挑片狀態套用 |
| `status_info.py` | 77 | 狀態列欄位組裝 |

#### 資源管理與效能

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `tile_loader.py` | 551 | 縮圖牆非同步載入：距離感知優先權、grid mutex 下收集結果、進度合併 |
| `tile_textures.py` | 139 | 圖磚 GPU 材質配置與 VRAM 預算淘汰 |
| `tile_wall_loading.py` | 100 | 牆面 loading 狀態與轉圈幾何（大資料夾/網路磁碟不再空白） |
| `prefetch_scheduler.py` | 177 | Deep-zoom 鄰居預載排程、取消過期 worker、淘汰快取 |
| `deep_zoom_priority.py` | 41 | 圖磚渲染優先權 |
| `vram_budget.py` | 68 | 純函式：使用者覆寫值 + 夾限策略 |
| `vram_detect.py` | 102 | 廠商 GL 探測實際 VRAM（`glGetIntegerv`） |
| `memory_pressure.py` | 241 | 狀態列記憶體壓力指示器（綠/黃/紅 + 百分比，點擊清快取） |
| `worker_pools.py` | 111 | 執行緒池分池策略：縮圖爆量不再和 deep-zoom worker 搶資源 |
| `signal_coalescer.py` | 90 | 次幀 signal 合併，避免 N 個縮圖回呼各觸發一次進度更新 |
| `cvd_view_mode.py` | 99 | 色覺障礙模擬（view-time 模組級開關，載入時套用） |

#### `gpu_image_view/images/` — 載入層

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `image_loader.py` | 486 | **核心載入路徑**：`load_image_file()`（RAW/SVG/HEIF/JXL/一般點陣 → RGBA，可套 recipe）、`LoadDeepZoomWorker`（背景建金字塔）、`FolderScanWorker`（分批掃描大資料夾）、`open_path()` 對外入口 |
| `load_thumbnail_worker.py` | 166 | 單張縮圖解碼 `QRunnable` |
| `image_model.py` | 25 | `ImageModel`：目前資料夾的圖片路徑清單 |
| `prefetch.py` | 179 | 預載視窗大小與方向追蹤（`NavigationDirectionTracker`） |

#### `gpu_image_view/actions/` — 檢視器動作

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `delete.py` | 222 | **軟刪除 / 復原**：先隱藏不落地，`commit_pending_deletions()` 在關閉時一次送 `trash_ops` |
| `select.py` | 209 | 上下張切換（含 wrap-around toast）、跳到上/下一個有圖的兄弟資料夾、框選圖磚 |
| `batch_ops.py` | 307 | 批次重新命名 / 移動 / 複製 / 旋轉 |
| `compare_dialog.py` | 570 | 圖片比對：並排(2/4)、疊加(alpha)、差異(gain-boost) |
| `slideshow.py` | 212 | 幻燈片播放控制器 + 對話框 |
| `animation_player.py` | 240 | GIF / APNG / Animated WebP 播放器 |
| `search_dialog.py` | 281 | 檔名即時搜尋 |
| `goto_dialog.py` | 103 | Ctrl+G 跳至第 N 張 |
| `keyboard_actions.py` | 304 | 鍵盤快捷動作實作 |
| `lossless_rotate.py` | 132 | JPEG 改 EXIF Orientation 真無損旋轉，其他格式退回 PIL transpose |
| `drag_out.py` | 71 | 從圖磚拖出檔案 URI 到 Explorer / Chrome / Discord |
| `undo_commands.py` | 83 | `RotateCommand` / `RatingCommand` / `FavoriteCommand` |
| `recipe_commands.py` | 61 | `EditRecipeCommand`：顯影編輯的 undo/redo（存新舊 recipe dict） |
| `undo_coalescer.py` | 62 | 把滑桿拖曳產生的密集編輯合併成單一 undo 步驟 |

### 6.11 `Imervue/library/`

SQLite 支撐的跨資料夾相片庫索引與整理演算法（純邏輯，無 Qt）。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `image_index.py` | 667 | **核心 SQLite 索引**：跨資料夾中繼資料、註記、階層標籤、smart album、pHash、挑片旗標 |
| `scanner.py` | 178 | 背景掃描器，走訪 library roots 填索引 |
| `maintenance.py` | 55 | 索引與檔案系統對帳 |
| `smart_album.py` | 349 | Smart Albums：保存查詢並重新套用 |
| `search_query.py` | 216 | 自由文字查詢 → Smart Album 規則 |
| `album_io.py` | 75 | Smart Album 匯出 / 匯入為可攜 JSON |
| `clip_search.py` | 365 | CLIP 語意搜尋（「找出符合這句話的照片」） |
| `auto_tag.py` | 111 | 啟發式內容分類 + 選用 CLIP ONNX |
| `phash.py` | 84 | 64-bit DCT pHash |
| `bloom_filter.py` | 151 | 純 Python bloom filter，快速判斷「看過這個指紋沒」 |
| `dedupe_resolver.py` | 61 | 從一組重複中挑出該保留的那張 |
| `stacks.py` | 90 | RAW + JPEG 配對堆疊 |
| `events.py` | 90 | 依拍攝時間間隔把照片分成「事件」 |
| `calendar_index.py` | 159 | 依拍攝日分桶，供 Calendar View |
| `capture_time.py` | 50 | 批次位移 EXIF 時間戳 |
| `date_import.py` | 102 | 依拍攝日匯入到日期資料夾 |
| `gpx_geotag.py` | 114 | GPX 軌跡對時取得座標 |
| `auto_cull.py` | 58 | 依銳利度自動剔除模糊 |
| `quality_cull.py` | 55 | 依綜合技術品質剔除 |
| `group_cull.py` | 96 | 每組保留最佳一張 |
| `face_clustering.py` | 79 | 人臉特徵分群 → People Albums |
| `keyword_index.py` | 41 | XMP sidecar 關鍵字匯入索引 |
| `keyword_vocabulary.py` | 164 | 受控詞彙展開（Photo Mechanic 式） |
| `keyword_vocabulary_store.py` | 45 | 詞彙的設定檔儲存 |
| `tag_relations.py` | 50 | 標籤共現 → 相關標籤建議 |
| `metadata_audit.py` | 41 | 找出中繼資料不完整的圖片 |
| `metadata_export.py` | 129 | 中繼資料 CSV / JSON 匯出 |
| `collection_stats.py` | 82 | 集合的評分/收藏/色標籤/挑片統計 |
| `reference_pins.py` | 96 | 釘選參考圖籃子 |
| `staging_tray.py` | 120 | 跨資料夾選取籃 |
| `token_rename.py` | 197 | Token 式批次改名 |

### 6.12 `Imervue/gui/`

143 個檔、31,057 行 —— 全部是 Qt 前端。多數對話框只是外殼，數學在 `image/`。

#### 主視窗組件（非對話框）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `develop_panel.py` | 1,332 | **Modify 分頁面板**：`build_left_panel()` 工具列、`build_right_panel()` 顯影滑桿、內嵌 `AnnotationCanvas`。發出 `recipe_committed` signal |
| `annotation_canvas.py` | 1,623 | 註解畫布 widget + `QUndoCommand`（新增/刪除/修改/烘焙），支援手繪、形狀、文字、馬賽克、模糊、裁切、選取 |
| `annotation_dialog.py` | 1,055 | macOS Preview 式標註對話框（存 PNG/JPEG 或存專案） |
| `annotation_models.py` | 580 | 註解資料模型 + **無 Qt 的 PIL 渲染路徑**（可在 worker / 測試中使用） |
| `file_tree_view.py` | 945 | `_FileTreeView`：左側檔案樹，含快捷鍵與右鍵選單、重名處理 |
| `file_tree_sort.py` | 150 | `FileTreeSortProxy`：`QFileSystemModel` 沒有的「建立日期」等具名排序鍵 |
| `folder_thumbnail_model.py` | 183 | `QFileSystemModel` 子類，用資料夾第一張圖當樹狀圖示（取代不穩定的 Windows shell 縮圖） |
| `image_list_view.py` | 593 | 清單檢視（`QTableView`，縮圖牆的替代） |
| `dual_image_view.py` | 196 | 雙圖檢視：Split / Manga / Manga RTL 三種模式 |
| `exif_sidebar.py` | 422 | 可收合的 EXIF 側邊欄（含星等元件） |
| `breadcrumb_bar.py` | 148 | 麵包屑路徑列 |
| `timeline_view.py` | 365 | 時間軸檢視（年/月/日分組） |
| `toast.py` | 97 | Toast / snackbar 通知 |
| `hover_preview.py` | 185 | 縮圖懸停放大彈窗 |
| `image_issue_panel.py` | 143 | 圖片載入問題面板（dock） |
| `multi_monitor_window.py` | 275 | 多螢幕鏡像視窗 |
| `command_palette.py` | 170 | Ctrl+Shift+P，走訪 `menuBar()` 展平所有 `QAction` 的模糊搜尋啟動器 |
| `modify_actions_widget.py` | 204 | 共用的 Modify 動作按鈕組（選單與右鍵共用） |
| `main_tab_nav.py` | 48 | Modify/Paint 分頁左右鍵的純路由決策 |
| `screen_fit.py` | 63 | 換螢幕時主視窗自適應的純幾何 |
| `settle_poll.py` | 54 | **有界重試**：視窗還在 settle 時反覆重跑佈局步驟（解決 `singleShot(0)` 跨不了 OS 視窗變更的問題） |
| `workspace_manager.py` | 155 | 具名工作區預設（幾何 + 佈局快照） |
| `query_search.py` | 42 | 查詢字串輸入 → 過濾縮圖牆 |
| `_apply_save.py` | 156 | **共用的「載入 → 套用 → 另存副本」骨架**（`EffectWorker(QThread)`），約 30 個單圖工具對話框共用 |

#### 顯影 / 調色對話框（多為 `_apply_save` 外殼）

`tone_curve_dialog.py`(289) · `levels_dialog.py`(170) · `channel_mixer_dialog.py`(149) ·
`hsl_mixer_dialog.py`(131) · `split_toning_dialog.py`(115) · `gradient_map_dialog.py`(166) ·
`colormap_dialog.py`(92) · `lut_dialog.py`(121) · `posterize_dialog.py`(158) ·
`solarize_dialog.py`(140) · `velvia_dialog.py`(85) · `film_negative_dialog.py`(82) ·
`filmic_tonemap_dialog.py`(107) · `tone_equalizer_dialog.py`(97) · `detail_equalizer_dialog.py`(92) ·
`auto_color_balance_dialog.py`(207) · `local_contrast_dialog.py`(121) · `clahe_dialog.py`(101) ·
`defringe_dialog.py`(96) · `graduated_density_dialog.py`(96) · `soft_proof_dialog.py`(135) ·
`develop_presets_dialog.py`(164) · `virtual_copies_dialog.py`(160) · `before_after_dialog.py`(175) 分割滑桿對照 ·
`layers_dialog.py`(449) 疊加圖層堆疊管理 · `masks_dialog.py`(224) 局部調整遮罩

#### 效果 / 濾鏡對話框

`glow_dialog.py`(159) · `emboss_dialog.py`(97) · `film_grain_dialog.py`(136) · `lens_flare_dialog.py`(135) ·
`frosted_glass_dialog.py`(86) · `dither_dialog.py`(92) · `distort_dialog.py`(102) · `polar_dialog.py`(81) ·
`kaleidoscope_dialog.py`(82) · `pixel_sort_dialog.py`(107) · `meme_dialog.py`(95) ·
`photo_frame_dialog.py`(108) · `scale_bar_dialog.py`(107) · `anaglyph_dialog.py`(122) ·
`frequency_separation_dialog.py`(152) 輸出兩個圖層檔 · `binarize_dialog.py`(101) · `otsu_dialog.py`(90) ·
`flatten_field_dialog.py`(96) · `test_charts_dialog.py`(102) · `steganography_dialog.py`(119)

#### 幾何 / 修補 / 多圖

`crop_straighten_dialog.py`(221) · `auto_straighten_dialog.py`(199) · `lens_correction_dialog.py`(169) ·
`smart_crop_dialog.py`(127) 顯著性裁切建議 · `tiny_planet_dialog.py`(112) ·
`clone_stamp_dialog.py`(219) · `healing_brush_dialog.py`(254) · `sky_replace_dialog.py`(154) ·
`portrait_retouch_dialog.py`(170) · `noise_sharpen_dialog.py`(168) · `face_detection_dialog.py`(225) ·
`hdr_merge_dialog.py`(159) · `panorama_dialog.py`(169) · `focus_stack_dialog.py`(157) ·
`stack_blend_dialog.py`(178) · `collage_dialog.py`(89) · `deflicker_dialog.py`(208) ·
`id_photo_sheet_dialog.py`(107) · `print_layout_dialog.py`(176)

#### 批次 / 匯出 / 管理

`batch_convert_dialog.py`(375) · `batch_export_dialog.py`(393) · `export_dialog.py`(248) ·
`optimize_dialog.py`(112) 目標檔案大小 · `gif_video_dialog.py`(392) · `contact_sheet_dialog.py`(199) ·
`web_gallery_dialog.py`(157) · `slideshow_mp4_dialog.py`(200) · `image_organizer_dialog.py`(543) ·
`duplicate_detection_dialog.py`(563) 檔案雜湊 + pHash · `image_sanitize_dialog.py`(786) 淨化重繪（剝除所有隱藏資料）·
`exif_strip_dialog.py`(305) · `token_rename_dialog.py`(123) · `culling_dialog.py`(257) 挑片 ·
`ai_upscale_dialog.py`(715) Real-ESRGAN via ONNX（模型自 HuggingFace 下載）

#### 相片庫 / 中繼資料 / 搜尋

`library_search_dialog.py`(228) · `smart_albums_dialog.py`(298) · `semantic_search_dialog.py`(171) ·
`similar_search_dialog.py`(105) · `advanced_filter_dialog.py`(291) · `tag_album_dialog.py`(532) ·
`tag_filter_dialog.py`(172) · `hierarchical_tags_dialog.py`(185) · `auto_tag_dialog.py`(173) ·
`keyword_editor_dialog.py`(218) · `keyword_vocabulary_dialog.py`(71) · `exif_editor.py`(170) ·
`gps_geotag_dialog.py`(91) · `map_view_dialog.py`(172) OSM 底圖 · `calendar_view_dialog.py`(109) ·
`events_dialog.py`(51) · `metadata_export_dialog.py`(95) · `xmp_sidecar_dialog.py`(121) ·
`bookmark_dialog.py`(350) · `staging_tray_dialog.py`(185) · `reference_panel_dialog.py`(298) ·
`image_statistics_dialog.py`(91) · `quality_report_dialog.py`(62) · `image_inspector_dialog.py`(85) 波形/parade/false colour/focus peaking ·
`ocr_dialog.py`(115)

#### 設定 / 系統

`preferences_dialog.py`(269) · `shortcut_settings_dialog.py`(405) · `profiles_dialog.py`(208) 多帳號 ·
`workspace_dialog.py`(243) · `external_editors_settings.py`(152) · `recycle_bin_dialog.py`(368) 軟刪除回收桶 ·
`cache_maintenance_dialog.py`(54) · `watch_folder_dialog.py`(117) · `macro_manager_dialog.py`(339) ·
`dual_pane_dialog.py`(179) 雙窗格檔案管理 · `onboarding_dialog.py`(136) 首次導覽 · `whats_new_dialog.py`(144)

### 6.13 `Imervue/menu/`

選單建構層 —— 只負責組 `QAction` 與呼叫對應對話框，不含業務邏輯。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `extra_tools_menu.py` | 811 | **最大的選單**：Batch / Library / Views / CVD / Workflow / Export / Develop / Retouch / Multi-image 九個子選單，約 100 個 `_open_*` 進入點 |
| `right_click_menu.py` | 897 | 檢視器右鍵選單：在檔案總管顯示、複製路徑、遺失檔案重定位、重試載入、OCR、批次動作、staging tray、桌布、比較、書籤、標籤… |
| `file_menu.py` | 483 | 開啟資料夾/圖片、新視窗、檔案關聯註冊、剪貼簿貼上、書籤、標籤相簿、快捷鍵設定、偏好設定、回收桶、多帳號、Session、工作區、外部編輯器 |
| `tip_menu.py` | 291 | 操作說明選單 + 快捷鍵速查對話框 |
| `filter_menu.py` | 276 | 依副檔名 / 星等過濾 |
| `plugin_menu.py` | 264 | 外掛管理：檢視已載入、下載、啟用/停用、開啟資料夾 |
| `recent_menu.py` | 193 | 最近資料夾 / 最近圖片子選單（teardown-safe，會自動剔除不存在路徑） |
| `sort_menu.py` | 175 | 依名稱 / 日期 / 大小 / 解析度排序 |
| `language_menu.py` | 53 | 語言切換（提示重新啟動） |
| `modify_menu.py` | 30 | Deep-Zoom 專用的「修改」選單動作 |

### 6.14 `Imervue/paint/`

180 個檔、45,880 行 —— 全樹最大的子系統，是一個完整的點陣繪圖 + 漫畫製作工作區。

#### 核心文件模型與畫布

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `document.py` | 1,388 | `PaintDocument`：圖層堆疊 + 選取範圍 + 作用中圖層 |
| `canvas.py` | 1,853 | `PaintCanvas`：GPU 加速的中央繪圖表面 |
| `compositing.py` | 439 | 純 NumPy 圖層合成 |
| `layer_model.py` | 117 | 圖層與圖層群組資料模型 |
| `layer_ops.py` | 172 | 向下合併 / 合併可見 / 平面化的純函式 |
| `document_io.py` | 446 | 原生 `.imervue` NPZ bundle 存讀 |
| `psd_io.py` | 867 | Photoshop `.psd` 匯入 / 匯出（互通子集） |
| `undo_stack.py` | 193 | 每文件的 undo / redo |
| `damage.py` | 123 | 破損矩形記帳，供部分材質上傳 |
| `blend_modes.py` | 64 | 共用 RGB 混色模式數學 |
| `blend_if.py` | 334 | Blend-If：依亮度範圍決定逐像素可見度 |

#### 筆刷引擎

`brush_engine.py`(650) 純 NumPy 光柵化 · `gpu_brush.py`(682) OpenGL FBO+GLSL 加速 ·
`brush_dynamics.py`(151) · `brush_random.py`(144) 散佈/色彩抖動/傾斜旋轉 · `brush_cursor.py`(499) 筆跡游標預覽 ·
`brush_presets.py`(350) · `default_brush_presets.py`(165) · `brush_preset_io.py`(241) 含外部格式匯入 ·
`brush_preset_dialog.py`(268) · `brush_kind_preview.py`(90) · `brush_tip_capture.py`(138) 從選區擷取筆尖 ·
`custom_brush.py`(96) · `pressure_curve.py`(147) + `pressure_curve_dialog.py`(256) 筆壓曲線 ·
`stabilizer.py`(85) 筆畫穩定器 · `catmull_rom_spline.py`(81) 平滑重採樣 · `symmetry.py`(86) 對稱繪製 ·
`smudge.py`(147) 塗抹/混色筆 · `blur.py`(88) · `dodge_burn.py`(113) · `sponge.py`(81) ·
`watercolor.py`(183) 濕畫法模擬 · `stamp_tool.py`(159) + `stroke_along_path.py`(100)

#### 選取 / 變形

`selection.py`(296) · `selection_ops.py`(326) 選區精修 · `selection_transform.py`(203) 仿射變換 ·
`marquee.py`(94) 選區邊界線段 · `quick_mask.py`(220) 快速遮罩 · `magnetic_lasso.py`(119) 磁性套索 ·
`stroke_selection.py`(141) 描邊選區 · `transform_handles.py`(271) · `perspective_warp.py`(203) 四角透視 ·
`mesh_warp.py`(296) 控制網格雙線性變形 · `liquify.py`(263) + `liquify_dialog.py`(289) 液化 ·
`crop.py`(94) + `crop_tool.py`(91) · `canvas_transforms.py`(77) · `image_resize.py`(150)

#### 填色 / 形狀 / 向量 / 文字

`fill.py`(369) 洪水填色 · `auto_region_fill.py`(254) 一次填滿所有封閉區 · `auto_base_color.py`(246) 線稿自動平塗 ·
`divide_layer.py`(159) 依顏色拆圖層 · `pattern_fill.py`(131) · `gradient.py`(169) + `gradient_editor.py`(283) +
`gradient_map_presets.py`(89) · `shape_engine.py`(266) + `shape_tool.py`(311) ·
`bezier_path.py`(218) + `pen_commit.py`(107) 鋼筆工具 · `polyline_offset.py`(76) 平行曲線 ·
`vector_layer.py`(312) 非破壞性向量線條 · `binary_layer.py`(140) 1-bit 墨線圖層 ·
`image_trace.py`(221) 遮罩 → 輪廓向量化 · `line_cleanup.py`(169) Chaikin 平滑 + 補小縫 ·
`text_render.py`(226) · `text_tool.py`(210) · `rich_text.py`(585) 逐字樣式 · `text_on_path.py`(174) ·
`text_on_selection.py`(93)

#### 顏色

`color_math.py`(84) · `color_wheel.py`(263) + `color_wheel_widget.py`(205) · `color_palette.py`(169) +
`color_palette_io.py`(304) 外部調色盤格式 · `color_sampler.py`(175) 取樣點 · `swatch_panel.py`(248) ·
`palette_extract.py`(169) median-cut 抽色 · `match_color.py`(97) · `match_palette.py`(109) ·
`color_management.py`(182) ICC · `color_blindness.py`(119) CVD 模擬 · `auto_correct.py`(80) ·
`adjustments.py`(740) 純 NumPy 非破壞性調整種類與套用管線 · `histogram.py`(129) + `histogram_dock.py`(142)

#### 漫畫 / 網點

`manga_menu.py`(622) · `manga_effects.py`(348) 速度線 + 網點 · `manga_panels.py`(263) 分鏡版面 ·
`halftone.py`(358) 網點引擎 · `speedlines.py`(211) · `speech_bubble.py`(205) + `speech_bubbles.py`(488) 對話框氣泡 ·
`comic_stamps.py`(267) + `stamp_dock.py`(89) · `comic_formats.py`(162) · `flash_effect.py`(133) 爆炸效果 ·
`frame_splitter.py`(138) · `bleed_guides.py`(155) 裁切/出血/安全線 · `page_templates.py`(267) ·
`page_numbering.py`(157) · `page_dock.py`(350) 頁面瀏覽 · `paint_project.py`(148) 多頁專案 +
`paint_project_io.py`(112) + `paint_project_export.py`(131) · `new_project_dialog.py`(106)

#### 動畫

`animation.py`(479) 時間軸 + 洋蔥皮 · `animation_timeline.py`(199) 純 NumPy 模型 ·
`animation_dock.py`(290) 幀條 + 播放控制 · `animation_export.py`(166) · `timelapse.py`(127) 縮時匯出

#### 素材 / 參考 / 姿勢

`material_library.py`(298) · `material_procedural.py`(222) 程序化材質 · `material_drop.py`(123) ·
`save_region_as_material.py`(108) · `reference_dock.py`(257) + `reference_panel.py`(282) ·
`pose_skeleton.py`(211) + `pose_dock.py`(186) + `pose_drop.py`(129) 2D 火柴人姿勢參考

#### 輔助線 / 檢視

`rulers.py`(493) 繪圖輔助尺 · `smart_guides.py`(169) 智慧吸附 · `snap_guides.py`(125) ·
`visual_guides.py`(263) 像素格線 · `view_transform.py`(147) 平移/縮放/旋轉 · `multi_view.py`(247) 同文件第二視窗 ·
`size_hud.py`(139) + `size_hud_bridge.py`(64) 筆刷大小 HUD · `welcome_overlay.py`(223) ·
`layer_thumbnail.py`(184) · `layer_effects.py`(342) 陰影/外光暈/描邊

#### 工作區骨架與選單

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `paint_workspace.py` | 752 | 頂層 `PaintWorkspace` widget |
| `tool_dispatcher.py` | 1,028 | 把 `PointerEvent` 路由到作用中工具的處理器 |
| `tool_state.py` | 897 | **無 Qt** 的工具狀態模型 |
| `tool_bar.py` | 426 | 工具列 |
| `workspace_tabs.py` | 327 | 多文件分頁 |
| `workspace_docks.py` | 419 | dock 建構與佈局持久化 |
| `workspace_content.py` | 434 | 文件內容命令 |
| `workspace_status.py` | 321 | 狀態列與縮放指示 |
| `workspace_shortcuts.py` | 309 | 快捷鍵、筆刷調整、歡迎提示 |
| `workspace_presets.py` | 266 + `workspace_preset_dialog.py`(318) | 具名 dock 佈局預設 |
| `workspace_autosave.py` | 143 + `auto_save.py`(243) | 自動存檔與當機復原 |
| `action_recorder.py` | 241 + `action_recorder_dialog.py`(198) | 動作錄製 / 重播 |
| `shortcut_registry.py` | 176 + `shortcut_dialog.py`(163) + `shortcuts_dialog.py`(119) | 可自訂快捷鍵登錄 |
| `tablet_mapping.py` | 231 | 數位板按鍵 → 動作對應 |
| `recent_files.py` | 73 | 最近開啟清單 |
| `export_presets.py` | 274 + `export_utils.py`(232) | 批次匯出設定檔、浮水印、逐圖層匯出、切片匯出 |
| `canvas_presets.py` | 185 | New Canvas 尺寸預設 |
| 選單 | — | `paint_menu_bar.py`(91)、`file_menu.py`(540)、`edit_menu.py`(257)、`image_menu.py`(265)、`layer_menu.py`(313)、`filter_menu.py`(441)、`view_menu.py`(312)、`tools_menu.py`(130)、`settings_menu.py`(120)、`filter_preview_dialog.py`(180) |

#### `paint/docks/`（7 檔 · 1,863 行）

`brushes.py`(440) 筆刷與填色 dock · `layers.py`(412) 圖層 dock · `color.py`(370) 顏色 dock ·
`materials.py`(253) 素材庫 dock · `navigators.py`(248) 導覽器 / 歷史 / 頁面導覽 dock ·
`_helpers.py`(138) 共用元件與圖示

#### `paint/tools/`（4 檔 · 1,218 行）

`painting.py`(417) 筆刷/橡皮/填色/滴管 · `shapes.py`(445) 形狀與裁切 ·
`special.py`(354) 鋼筆/仿製印章/變形控點/對話氣泡

### 6.15 `Imervue/puppet/`

53 個檔、15,184 行。2D 骨架人偶動畫，Live2D Cubism 相容。原本是外掛，因為核心路徑
（GL / mesh / 純 NumPy 變形）跑在預設相依上，所以收進主程式當內建分頁；唯一的重量級選用相依
是 Cubism Native SDK DLL，缺了會優雅降級。

#### 資料模型與 I/O

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `document.py` | 396 | `.puppet` v1 檔案格式的純 Python 資料模型（`Drawable` / `Deformer` / `Parameter` / `Motion` / `HitArea`） |
| `document_io.py` | 870 | `.puppet` zip 容器讀寫 |
| `cubism_import.py` | 550 | Live2D Cubism v3 檔案格式匯入 |
| `cubism_native_bridge.py` | 474 | `Live2DCubismCore.dll` 的 ctypes 綁定（官方 Cubism SDK for Native） |
| `cubism_native_convert.py` | 642 | `.moc3` → `PuppetDocument` 轉換 |
| `psd_import.py` | 187 | PSD 多圖層 → `PuppetDocument` |
| `auto_mesh.py` | 173 | 從單張 PNG 自動生成網格 |
| `auto_rig.py` | 403 | 依圖層命名慣例自動推導 Cubism 式綁定 |
| `standard_params.py` | 117 | Cubism 標準參數目錄 |
| `requirements.py` | 76 | 選用相依清單 |

#### 執行期（變形 / 物理 / 取樣）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `runtime.py` | 847 | **每幀參數取樣 + deformer 組合**（核心迴圈） |
| `deformers.py` | 263 | 純 NumPy deformer 實作 |
| `physics.py` | 142 | Verlet 物理引擎 |
| `render_prep.py` | 104 | `PuppetDocument` → GL-ready draw list |
| `canvas.py` | 1,308 | `PuppetCanvas`（`QOpenGLWidget`）：繪製材質三角形堆疊 |
| `clip_masks.py` | 57 | `Drawable.clip_mask` 參照解析 |
| `ik.py` | 90 | 兩節骨骼解析式 IK |
| `bone_weights.py` | 101 | 骨骼 LBS 權重驗證與修復 |
| `hit_test.py` | 121 | `HitArea` 純 Python 命中測試 |
| `mesh_edit.py` | 94 · `mesh_repair.py` 230 · `symmetrize.py` 138 | 網格編輯 / 拓樸修復 / X 軸自動對稱 |
| `operations.py` | 229 | `PuppetDocument` 的純編輯操作 |
| `validator.py` | 297 | 靜態健康檢查 |

#### 動作 / 表情 / 閒置

`motion_sampler.py`(149) 純取樣 · `motion_player.py`(376) Qt 播放驅動 · `motion_recorder.py`(167) 錄製 ·
`motion_timeline.py`(356) 曲線圖編輯 · `motion_compress.py`(114) 移除冗餘關鍵幀 ·
`motion_picker.py`(54) 群組隨機挑選 · `synth_motions.py`(287) 為轉檔 rig 合成閒置動作 ·
`idle_driver.py`(144) · `idle_motion_cycler.py`(152) · `easing.py`(204) 緩動預設 ·
`motion_dock.py`(194) · `expression_dock.py`(122) · `parameter_dock.py`(198) · `bone_tree_dock.py`(197)

#### 即時輸入驅動

`input_engine.py`(213) 把即時輸入灌進 canvas · `input_drivers.py`(216) 純對應函式（游標→角度參數等）·
`mouse_gaze_driver.py`(240) 頭+眼追游標 · `webcam_tracker.py`(365) 攝影機 → 參數 ·
`webcam_preview_dialog.py`(225) · `face_landmark_mapper.py`(213) MediaPipe FaceMesh → 參數 ·
`audio_lipsync.py`(100) 音檔驅動嘴型

#### 輸出

`recorder.py`(195) 幀擷取 · `batch_export.py`(186) 每個 motion 匯出成 MP4/GIF/WebM ·
`spritesheet.py`(68) · `virtual_camera.py`(243) 系統虛擬攝影機 · `ndi_output.py`(222) NDI 來源廣播 ·
`vts_api.py`(370) VTube Studio Public API server（最小子集）

`workspace.py`(1,680) 是頂層 `PuppetWorkspace`（`QMainWindow`），掛載 canvas、工具列、最近檔案與各 dock。

### 6.16 `Imervue/desktop_pet/`

32 個檔、8,207 行。無邊框、透明、永遠置頂的桌面寵物懸浮視窗，**共用整個 Puppet 執行期**。
Tab 4 本身只是控制面板，角色住在獨立的 top-level `PetWindow`。

#### 視窗與互動

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `pet_window.py` | 1,184 | `PetWindow`：無邊框透明視窗，host 一個 pet 模式的 `PuppetCanvas` |
| `pet_workspace.py` | 708 | Tab 4 控制面板（rig 選擇、驅動開關、可見性 / 點擊穿透 / 尺寸預設） |
| `pet_interaction.py` | 215 | 指標互動控制器：拖曳移動、點擊路由、命中偵測 |
| `pet_placement.py` | 154 | 邊緣吸附、多螢幕位置還原、預設角落停靠 |
| `edge_snap.py` | 166 | 純 Python 邊緣吸附數學 |
| `pet_context_menu.py` | 141 | 右鍵選單建構器 |
| `pet_registry.py` | 135 | 多隻寵物的生命週期登錄表（以 pet id 為鍵） |
| `pet_shadow.py` | 138 + `pet_shadow_controller.py`(84) | 放射漸層落地陰影（單一 draw call） |
| `speech_bubble.py` | 209 | 對話泡泡覆蓋視窗（自動淡出） |
| `tray_icon.py` | 152 | 系統匣切換 |
| `settings.py` | 305 | 設定持久化（schema + 預設值 + 載入夾限） |
| `fullscreen_detector.py` | 167 | 偵測同螢幕有全螢幕程式時自動隱藏 |

#### 驅動與功能控制器（兩個家族）

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `pet_feature_base.py` | 171 | `FeatureHost` Protocol + `IntegrationController` 骨架 |
| `pet_features.py` | 179 | 具體整合控制器：OBS / Twitch / Webhook / Windows 通知 / 全域熱鍵 |
| `pet_drivers.py` | 244 | canvas 驅動控制器：音樂律動 / 閒置小遊戲 / 點擊音效 / LLM 對話 |
| `pet_canvas_drivers.py` | 169 | canvas 輸入驅動子系統（自動眨眼 / 拖曳追頭 / 麥克風對嘴） |

> 這兩個家族的存在是為了把 `PetWindow` 從 god-object 拉回「協調者」。

#### 外部整合

`obs_event_hook.py`(194) OBS WebSocket → 動作群組 · `twitch_chat_hook.py`(278) Twitch 聊天關鍵字 ·
`webhook_server.py`(294) localhost HTTP POST `/trigger` · `windows_notification_hook.py`(293) Windows toast →
`Notify` 動作 + 朗讀標題 · `hotkey_manager.py`(249) 全域熱鍵（pynput）+ `hotkey_conflicts.py`(47) 衝突偵測 ·
`command_parser.py`(78) 可重用的聊天指令路由器（exact / prefix / substring / regex）

#### 個性與行為

`pet_script.py`(438) JSON 支撐的台詞 + 排程事件引擎 · `pet_script_editor.py`(522) 內建編輯器 ·
`schedule_rules.py`(102) 時段 / 星期閘門 · `idle_minigame.py`(279) 閒置好奇 / 打呵欠 ·
`llm_dialogue.py`(243) 本地 LLM（預設 Ollama）對話 · `music_rhythm.py`(464) WASAPI loopback 抓系統音訊隨節奏擺動 ·
`click_sfx.py`(169) 事件音效

### 6.17 `Imervue/plugin/`

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `plugin_base.py` | 206 | `ImervuePlugin` 基底類別，12 個 hook：`on_plugin_loaded/unloaded`、`on_build_menu_bar`、`on_build_context_menu`、`on_build_main_tabs`、`on_image_loaded/folder_opened/image_switched/image_deleted`、`on_key_press`、`get_translations`、`on_app_closing` |
| `plugin_manager.py` | 229 | 探索與載入（把 `plugins/` 插進 `sys.path`，找 `plugin_class`）、hook 分派、統一 try/except 隔離（單一外掛炸掉不會拖垮主程式） |
| `plugin_downloader.py` | 469 | 從公開發佈 repo 下載外掛。含 `_https_urlopen` 守衛（拒絕非 https scheme） |
| `pip_installer.py` | 963 | 外掛相依安裝器：尋找/下載 Python、安裝 pip 套件（凍結環境亦可） |
| `plugin_manifest.py` | 174 | manifest schema + 版本 / 相依相容性檢查 |
| `model_dir.py` | 51 | 外掛模型目錄的共用解析 |
| `subprocess_util.py` | 37 | 外掛 worker 呼叫子 Python 的共用 helper |
| `worker_host.py` | 75 | **`WorkerHostMixin`**：擁有背景 `QThread` 的 `QDialog` 共用拆卸邏輯，修掉「QThread destroyed while running」當機（約 90 個對話框使用） |

### 6.18 `Imervue/mcp_server/`

把 Imervue 的影像能力以 Model Context Protocol 暴露給 LLM 代理。**完全無 Qt、無選用相依**。

| 模組 | 行數 | 功用 |
| --- | ---: | --- |
| `server.py` | 440 | JSON-RPC 2.0 over stdio 的協定迴圈 |
| `tools.py` | 2,812 | 56 個工具處理器（讀取類：`list_images`、`read_image_metadata`、`read_xmp_tags`、`image_statistics`、`quality_metrics`、`ocr_text`、`find_similar`、`extract_gps`… 影像處理類：`resize_image`、`crop_image`、`levels_image`、`curve_image`、`clahe_image`、`lens_correction_image`…） |
| `tool_schemas.py` | 579 | 每個工具的輸出 schema 與 annotation（有 parity test 強制與 `tools.py` 對齊） |
| `prompts.py` | 229 | 影像助理的 prompt 範本 |
| `resources.py` | 133 | 把圖片暴露成可讀 MCP resource |
| `progress.py` | 67 | 長時間工具呼叫的進度通知 |
| `notifications.py` | 67 | 同步 stdio 迴圈上的 server-push 通知 |
| `completion.py` | 40 | prompt 參數值建議 |
| `logging.py` | 39 | RFC 5424 嚴重度與 emit 過濾 |

---

## 7. `plugins/` 外掛實作

**外掛 vs 主程式的判準不是「AI 功能就進外掛」，而是相依表面：**

進外掛的條件（任一成立）：① 需要重量級 / 選用執行期相依（rembg、onnxruntime、torch、opencv、大模型權重）；
② 需要失敗隔離（ML / GPU / CUDA 崩潰不該拖垮檢視器）；③ 需要獨立發版節奏。

留在主程式：跑在預設相依集、失敗最多壞一張圖、屬於日常瀏覽 / 顯影流程。

| 外掛 | 檔案/行數 | 功用 | 重量級相依 |
| --- | --- | --- | --- |
| `safety_review` | 14 / 4,675 | NSFW 偵測與馬賽克（僅生殖器與肛門，**絕不處理乳頭/胸部**）。含手動編輯器、YOLO 資料集匯出、fine-tune 腳本 | nudenet, ultralytics, huggingface_hub |
| `spanish_translation` | 3 / 1,776 | 西班牙文語言外掛，示範 `register_language()` | — |
| `ai_background_remover` | 3 / 926 | rembg (U²-Net) 去背，單張 + 批次，凍結環境走子行程 | rembg, onnxruntime |
| `ai_object_remove` | 4 / 814 | 點選物件 → 洪水填色遮罩 → 擴散修補；另有 SAM ONNX point-prompt 路徑 | onnxruntime (SAM) |
| `object_splitter` | 3 / 701 | 去背 + 連通元件 → 每個物件存成透明 PNG | rembg |
| `video_source` | 3 / 614 | 瀏覽影片並抽出靜幀 | imageio-ffmpeg |
| `ai_motion_deblur` | 3 / 581 | Wiener 反捲積 + 選用 ONNX | onnxruntime |
| `ai_portrait_relight` | 3 / 563 | 啟發式 Lambert 打光 + 選用 ONNX | onnxruntime |
| `ai_smart_resize` | 3 / 539 | Seam carving 內容感知縮放 | — (重運算) |
| `npr_filters` | 3 / 506 | 鉛筆 / 油畫 / 水彩 / 線稿 | opencv-python |
| `ai_colorize` | 3 / 504 | 黑白上色：啟發式調色盤 + ONNX | onnxruntime |
| `cloud_share` | 3 / 488 | 上傳到 WebDAV / Imgur（HTTPS-only 守衛，僅在使用者按下上傳時執行） | — |
| `ai_denoise` | 3 / 458 | 雙邊濾波（純 NumPy）或 ONNX 神經降噪 | onnxruntime |
| `ai_style_transfer` | 3 / 402 | ONNX 快速神經風格轉換，自動探索 `models/*.onnx` | onnxruntime |
| `portrait_mode` | 3 / 390 | rembg 主體遮罩 + 背景模糊（假淺景深） | rembg |
| `ai_outpaint` | 3 / 247 | 擴張畫布 + 擴散填補邊界 | — |
| `png_to_icon` | 2 / 192 | PNG → 多尺寸 `.ico` | Pillow |

**發佈規則（硬性要求）**：`/plugins/` 在本 repo 是 gitignored（新檔要 `git add -f`），
且外掛透過另一個公開 repo `D:\Codes\Imervue_Plugins`（remote `Jeffrey-Plugin-Repos/Imervue_Plugins`）
發給使用者。下載器讀的是 **`main` 分支**，且只抓外掛目錄下的**扁平檔案**（`models/` 之類子目錄不會下載）。

---

## 8. `tests/` 測試體系

731 個檔、122,630 行。`pyproject.toml` 定義三個互斥層級 marker：

| 層級 | 定義 | 判定方式 |
| --- | --- | --- |
| `fast` | 不建 Qt widget、不跨子系統 | 預設 |
| `gui` | 建立或操作 Qt widget | fixture 用到 `qapp`/`qtbot`，或原始碼含 `PySide6.QtWidgets` |
| `integration` | 跨多個子系統或完整流程 | 檔名含 `integration` / `_full` 結尾 |

`conftest.py` 在 collection 期自動分類並依 `--test-layer` 取捨，同時把 `plugins/` 注入 `sys.path`
（鏡像執行期 `plugin_manager` 的行為），讓測試能 `from ai_denoise.denoise import …`。

**共用 fixture**：`qapp`、`tmp_path`、`sample_*_array`、`image_folder`，以及 autouse 的
`_isolate_user_settings`（把設定路徑導開，測試絕不寫真的 `user_setting.json`）。

**輔助模組**：`_qt_skip.py`（GL widget 的 CI skip marker）、`_instant_worker.py`、`_toast_spy.py`。

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
| 文件 | `docs/`（Sphinx，10 語言）+ `README.md` 與 `README/`（9 語言） | `README.md` 與 `docs/en` 是正規來源 |

### 品質閘（專案規範的 Definition of Done）

任何行為變更提交前必須全過：

```bash
py -m pytest tests/                        # 單元測試（新程式必須有新測試）
py -m ruff check .                         # 無新錯誤
py -m bandit -c pyproject.toml -r Imervue/ # 必須 "No issues identified"（-c 不可省）
```

外加：commit message 不得含任何 AI 工具 / 模型名稱，不得有 `Co-Authored-By`。

**ruff 設定重點**：line-length 100，啟用 `E/F/W/B/SIM/UP/PL/S/C90/N`，
`mccabe.max-complexity = 16`（對齊 SonarQube 認知複雜度門檻）。
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

一律透過 `user_settings/user_setting_dict.py`：去抖非同步存檔 + atomic `.tmp` → `os.replace()`。
關閉前呼叫 `cancel_pending_save()` 再立即 flush。

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

1. **Modify 分頁的中央不是 viewer。** 中央是 `AnnotationCanvas`；真正的 `GPUImageView` 在該分頁是隱藏
   的（雖有 reparent 程式碼）。鍵盤、resize、fit 行為都掛在 canvas 上。
   `Imervue_main_window.py:348` 附近的註解已過時。

2. **`plugins/` 是 gitignored。** 新增外掛檔案要 `git add -f`，否則會靜默漏掉。
   而且改完必須鏡像到 `D:\Codes\Imervue_Plugins` 的 `main` 分支才會到使用者手上；
   專案規範裡的 parity 指令只比對「目錄名」，抓不到檔案層級的漂移。

3. **完整測試套件會在全部測試通過後才以 `-1073741819`（0xC0000005）結束。**
   已在 stash 過的乾淨樹上驗證是既有現象，不是新引入的。

4. **`sonar-project.properties` 的 issue-ignore 規則實際上沒有作用**，要靠改程式或
   `# NOSONAR` 清掉。

5. **`gpu_image_view.py` 與 `gl_renderer.py` 使用 `from OpenGL.GL import *`**，因此在
   `pyproject.toml` 有 per-file `F403/F405` 豁免；新增 GL 程式碼時沿用即可。

6. **檔案長度上限 1000 行**是專案規則，但 `Imervue_main_window.py`(2296)、`canvas.py`(1853)、
   `gpu_image_view.py`(1758)、`workspace.py`(1680)、`annotation_canvas.py`(1623)、
   `document.py`(1388)、`develop_panel.py`(1332)、`puppet/canvas.py`(1308)、
   `tool_dispatcher.py`(1028)、`annotation_dialog.py`(1055)、`overlay_painter.py`(1121)、
   `pet_window.py`(1184)、`mcp_server/tools.py`(2812) 仍超標 —— 這些是後續拆分的候選清單。
   （`multi_language/*.py` 是資料字典，不適用。）

7. **MCP 工具新增流程**：`tools.py` 加處理器的同時必須在 `tool_schemas.py` 加 schema
   （有 parity test 強制），且工具必須保持無 Qt、無選用相依。

8. **Qt 對話框測試**：在 `qapp` fixture 下建立對話框時 parent 傳 `None`，
   不要傳暫時性的 `QWidget`，否則 teardown 會 access violation。



