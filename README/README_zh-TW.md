<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  基於 PySide6 和 OpenGL 的 GPU 加速圖片瀏覽器
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## 目錄

- [概述](#概述)
- [功能特色](#功能特色)
- [支援的圖片格式](#支援的圖片格式)
- [安裝](#安裝)
- [使用方式](#使用方式)
- [瀏覽模式](#瀏覽模式)
- [鍵盤與滑鼠快捷鍵](#鍵盤與滑鼠快捷鍵)
- [選單結構](#選單結構)
- [外掛系統](#外掛系統)
- [多語言支援](#多語言支援)
- [使用者設定](#使用者設定)
- [架構](#架構)
- [授權](#授權)

---

## 概述

Imervue 是一款高效能圖片瀏覽器，專為流暢的瀏覽體驗和大量圖片集合的高效處理而設計。透過 OpenGL 的 GPU 加速，為縮圖網格和深度縮放圖片檢視提供快速渲染。

核心設計原則：

- **效能優先** — 使用現代 GLSL 著色器和 VBO 進行 GPU 加速渲染
- **支援大量集合** — 虛擬化磁磚網格僅載入可見縮圖
- **流暢體驗** — 非同步多執行緒圖片載入與預取機制
- **可擴展** — 完整的外掛系統，支援生命週期、選單、圖片和輸入鉤子

---

## 功能特色

### 核心功能

- 透過 OpenGL 的 GPU 加速渲染（GLSL 1.20 著色器 + VBO）
- 深度縮放圖片檢視，使用多層圖片金字塔（512×512 磁磚）
- 虛擬化磁磚縮圖網格，支援延遲載入
- 非同步多執行緒圖片載入
- 縮圖磁碟快取系統（NumPy `.npy` 格式，MD5 快取金鑰）
- 預載入前後各 ±3 張相鄰圖片
- 復原/重做系統（QUndoStack 用於編輯，傳統堆疊用於刪除）

### 導航與檢視

- 資料夾瀏覽和單張圖片檢視
- 全螢幕模式，UI 在閒置 2 秒後自動隱藏
- 深度縮放模式下的小地圖覆蓋層
- RGB 直方圖覆蓋層
- 圖片旋轉（包括透過 piexif 的無損 JPEG 旋轉）
- 動態 GIF/APNG 播放，支援逐幀控制
- 幻燈片模式，可自訂間隔時間
- 並排圖片比較
- 依檔名搜尋/篩選圖片

### 整理功能

- 書籤系統（最多 5000 個書籤）
- 評分系統（1–5 星）和最愛功能
- 依名稱、修改日期、建立日期、檔案大小或解析度排序
- 依副檔名或評分篩選
- 最近資料夾和最近圖片追蹤
- 啟動時自動恢復上次開啟的資料夾

### 編輯與匯出

- 內建圖片編輯器（裁切、亮度、對比、飽和度、旋轉）
- 匯出/另存新檔，支援格式轉換（PNG、JPEG、WebP、BMP、TIFF）
- 有損格式品質滑桿（JPEG、WebP）
- 批次操作（重新命名、移動/複製、旋轉選取的圖片）
- 設為桌面桌布
- 複製圖片/圖片路徑到剪貼簿

### 中繼資料

- EXIF 資料顯示於可摺疊側邊欄
- EXIF 編輯器對話框
- 圖片資訊對話框（尺寸、檔案大小、日期）

### 系統整合

- Windows 右鍵「以 Imervue 開啟」內容選單（透過登錄檔進行檔案關聯）
- 使用 QFileSystemWatcher 進行資料夾監控（變更時自動重新整理）
- 多語言支援（5 種內建語言）
- 外掛系統，附帶線上外掛下載器
- Toast 通知系統（資訊、成功、警告、錯誤層級）

---

## 支援的圖片格式

### 點陣圖格式

| 格式 | 副檔名 |
|------|--------|
| PNG | `.png` |
| JPEG | `.jpg`、`.jpeg` |
| BMP | `.bmp` |
| TIFF | `.tiff`、`.tif` |
| WebP | `.webp` |
| GIF | `.gif`（動態） |
| APNG | `.apng`（動態） |

### 向量圖格式

| 格式 | 副檔名 |
|------|--------|
| SVG | `.svg`（透過 QSvgRenderer 渲染，縮圖縮小至最大 512px） |

### RAW 相機格式

| 格式 | 副檔名 | 相機品牌 |
|------|--------|---------|
| CR2 | `.cr2` | Canon |
| NEF | `.nef` | Nikon |
| ARW | `.arw` | Sony |
| DNG | `.dng` | Adobe Digital Negative |
| RAF | `.raf` | Fujifilm |
| ORF | `.orf` | Olympus |

RAW 檔案支援嵌入式預覽擷取，並在無法擷取時退回使用半尺寸處理。

---

## 安裝

### 系統需求

- Python >= 3.10
- 支援 OpenGL 的 GPU（可使用軟體渲染作為備援）

### 從原始碼安裝

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### 安裝為套件

```bash
pip install .
```

### 相依套件

| 套件 | 用途 |
|------|------|
| PySide6 | Qt6 GUI 框架 |
| qt-material | Material Design 主題 |
| Pillow | 圖片處理 |
| PyOpenGL | OpenGL 繫結 |
| PyOpenGL_accelerate | OpenGL 效能最佳化 |
| numpy | 陣列操作與縮圖快取 |
| rawpy | RAW 圖片解碼 |
| imageio | 圖片輸入/輸出 |

---

## 使用方式

### 基本啟動

```bash
python -m Imervue
```

### 開啟特定圖片

```bash
python -m Imervue /path/to/image.jpg
```

### 開啟資料夾

```bash
python -m Imervue /path/to/folder
```

### 命令列選項

| 選項 | 說明 |
|------|------|
| `--debug` | 啟用除錯模式 |
| `--software_opengl` | 使用軟體 OpenGL 渲染（設定 `QT_OPENGL=software` 和 `QT_ANGLE_PLATFORM=warp`）。當 GPU 驅動不可用或有問題時使用。 |
| `file` | （位置引數）啟動時開啟的圖片或資料夾 |

---

## 瀏覽模式

### 網格模式（磁磚網格）

開啟資料夾時，圖片會以虛擬化縮圖網格顯示：

- **延遲載入** — 僅渲染和載入可見的縮圖
- **動態縮圖大小** — 可設定為 128×128、256×256、512×512、1024×1024 或自動
- **捲動和縮放** — 流暢瀏覽大量集合
- **多選** — 拖曳框選或長按進入選取模式
- **批次操作** — 重新命名、移動/複製、旋轉或刪除選取的圖片
- **磁碟快取** — 縮圖以 `.npy` 檔案快取，使用 MD5 失效機制

### 單張圖片模式（深度縮放）

開啟單張圖片或雙擊縮圖時：

- **多層圖片金字塔** — 512×512 像素磁磚，使用 LANCZOS 降取樣
- **LRU 磁磚快取** — GPU 上最多快取 256 個磁磚（1.5 GB VRAM 上限）
- **流暢平移和縮放** — GPU 加速，支援各向異性過濾（最高 8x）
- **小地圖覆蓋層** — 顯示目前視窗位置
- **RGB 直方圖** — 按 `H` 鍵切換
- **載入時置中** — 預設適應視窗大小
- **相鄰圖片預載入** — 預載入前後各 ±3 張相鄰圖片

---

## 鍵盤與滑鼠快捷鍵

### 導航（兩種模式通用）

| 快捷鍵 | 動作 |
|--------|------|
| 方向鍵 | 捲動網格 / 切換圖片（深度縮放模式下左右切換） |
| Shift + 方向鍵 | 精細捲動（半步） |
| Home | 重設縮放和平移至原點 |
| Ctrl+F 或 / | 開啟搜尋對話框 |
| S | 開啟幻燈片對話框 |
| Ctrl+Z | 復原 |
| Ctrl+Shift+Z / Ctrl+Y | 重做 |

### 深度縮放 / 單張圖片模式

| 快捷鍵 | 動作 |
|--------|------|
| F | 切換全螢幕 |
| R | 順時針旋轉 |
| Shift+R | 逆時針旋轉 |
| E | 開啟圖片編輯器 |
| W | 適應寬度 |
| Shift+W | 適應高度 |
| H | 切換 RGB 直方圖覆蓋層 |
| B | 切換目前圖片的書籤 |
| Ctrl+C | 複製圖片到剪貼簿 |
| Ctrl+V | 從剪貼簿貼上圖片 |
| 0 | 切換最愛（愛心） |
| 1–5 | 快速評分（1–5 星） |
| Delete | 將目前圖片移至垃圾桶（可復原） |
| Escape | 離開深度縮放 / 離開全螢幕 |

### 動畫播放（GIF / APNG）

| 快捷鍵 | 動作 |
|--------|------|
| Space | 播放 / 暫停 |
| ,（逗號） | 上一幀 |
| .（句號） | 下一幀 |
| [ | 降低播放速度 |
| ] | 提高播放速度 |

### 磁磚網格模式

| 快捷鍵 | 動作 |
|--------|------|
| 方向鍵 | 捲動網格 |
| Delete | 刪除選取的磁磚 |
| Escape | 取消全部選取 |

### 滑鼠控制

| 動作 | 行為 |
|------|------|
| 左鍵點擊 | 選取磁磚或開啟圖片 |
| 左鍵拖曳 | 網格中框選多張圖片 |
| 長按（500ms） | 進入磁磚選取模式 |
| 中鍵拖曳 | 深度縮放中平移/捲動 |
| 滾輪 | 放大/縮小或捲動 |
| 右鍵 | 開啟右鍵選單 |

---

## 選單結構

### 檔案

- 新視窗
- 開啟圖片
- 開啟資料夾
- 最近（子選單：最近資料夾和圖片）
- 書籤（管理已加入書籤的圖片）
- 確認待處理的刪除（確認復原堆疊）
- 檔案關聯（僅限 Windows — 註冊/取消註冊右鍵內容選單）
- 結束

### 檢視

- 磁磚大小：128×128 / 256×256 / 512×512 / 1024×1024 / 自動

### 排序

- 依名稱 / 依修改日期 / 依建立日期 / 依檔案大小 / 依解析度
- 遞增 / 遞減

### 篩選

- 依副檔名：全部、JPG、PNG、BMP、TIFF、SVG、RAW
- 依評分：全部、已加入最愛、1–5 星
- 清除篩選

### 語言

- English / 繁體中文 / 简体中文 / 한국어 / 日本語

### 外掛

- 已載入的外掛（顯示各外掛名稱和版本）
- 下載外掛（開啟線上外掛下載器）
- 開啟外掛資料夾

### 說明

- 鍵盤與滑鼠快捷鍵（詳細的快捷鍵參考對話框）

### 右鍵選單

- 導航（上層資料夾、下一張/上一張圖片）
- 快速操作（在檔案總管中顯示、複製路徑、複製圖片）
- 變形（順時針/逆時針旋轉、編輯圖片）
- 批次操作（批次重新命名、移動/複製、全部旋轉）
- 刪除（刪除目前/選取的項目）
- 設為桌布
- 比較 / 幻燈片
- 匯出（另存新檔，可選擇格式）
- 無損 JPEG 旋轉
- 書籤（新增/移除書籤）
- 圖片資訊
- 最近選單
- 外掛貢獻的項目

---

## 外掛系統

Imervue 支援外掛系統以擴展功能。完整說明請參閱[外掛開發指南](../PLUGIN_DEV_GUIDE.md)。

### 快速開始

1. 在專案根目錄的 `plugins/` 資料夾中建立一個資料夾
2. 定義一個繼承 `ImervuePlugin` 的類別
3. 在 `__init__.py` 中以 `plugin_class = YourPlugin` 註冊
4. 重新啟動 Imervue

### 可用的鉤子

| 鉤子 | 觸發時機 |
|------|---------|
| `on_plugin_loaded()` | 外掛實例化後 |
| `on_plugin_unloaded()` | 應用程式關閉時 |
| `on_build_menu_bar(menu_bar)` | 預設選單列建立完成後 |
| `on_build_context_menu(menu, viewer)` | 右鍵選單開啟時 |
| `on_image_loaded(path, viewer)` | 圖片在深度縮放中載入後 |
| `on_folder_opened(path, images, viewer)` | 資料夾在網格中開啟後 |
| `on_image_switched(path, viewer)` | 在圖片間導航時 |
| `on_image_deleted(paths, viewer)` | 圖片被軟刪除後 |
| `on_key_press(key, modifiers, viewer)` | 按鍵時（回傳 True 以消耗事件） |
| `on_app_closing(main_window)` | 應用程式關閉前 |
| `get_translations()` | 提供國際化字串 |

### 外掛下載器

可透過 **外掛 > 下載外掛** 從官方倉庫下載外掛。下載器從 GitHub 上的 [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins) 取得。

---

## 多語言支援

### 內建語言

| 語言 | 代碼 |
|------|------|
| English | `English` |
| 繁體中文 | `Traditional_Chinese` |
| 简体中文 | `Chinese` |
| 한국어 | `Korean` |
| 日本語 | `Japanese` |

可從 **語言** 選單變更語言。變更後需要重新啟動才會生效。

### 透過外掛新增語言

外掛可以使用 `language_wrapper.register_language()` 註冊全新的語言，或透過 `get_translations()` 為現有語言新增翻譯。詳情請參閱[外掛開發指南](../PLUGIN_DEV_GUIDE.md#internationalization-i18n)。

---

## 使用者設定

設定儲存在工作目錄的 `user_setting.json` 中。

| 設定 | 型別 | 說明 |
|------|------|------|
| `language` | 字串 | 目前語言代碼 |
| `user_recent_folders` | 列表 | 最近開啟的資料夾 |
| `user_recent_images` | 列表 | 最近開啟的圖片 |
| `user_last_folder` | 字串 | 上次開啟的資料夾（啟動時自動恢復） |
| `bookmarks` | 列表 | 已加入書籤的圖片路徑（最多 5000 個） |
| `sort_by` | 字串 | 排序方式（name/modified/created/size/resolution） |
| `sort_ascending` | 布林 | 排序順序 |
| `image_ratings` | 字典 | 圖片路徑 → 評分（1–5）對應 |
| `image_favorites` | 集合 | 已加入最愛的圖片路徑 |
| `thumbnail_size` | 整數/null | 網格縮圖大小（128/256/512/1024/null 為自動） |

---

## 架構

```
Imervue/
├── __main__.py              # 應用程式進入點
├── Imervue_main_window.py   # 主視窗（QMainWindow）
├── gpu_image_view/          # GPU 加速檢視器
│   ├── gpu_image_view.py    # 主要檢視器元件（QOpenGLWidget）
│   ├── gl_renderer.py       # OpenGL 著色器渲染器
│   ├── actions/             # 檢視器操作（縮放、平移、旋轉等）
│   └── images/              # 圖片載入、金字塔、磁磚管理
├── gui/                     # UI 元件
│   ├── bookmark_dialog.py   # 書籤管理對話框
│   ├── exif_editor.py       # EXIF 中繼資料編輯器
│   ├── exif_sidebar.py      # 可摺疊 EXIF 側邊欄
│   ├── export_dialog.py     # 匯出/另存新檔對話框
│   ├── image_editor.py      # 圖片編輯器（裁切、調整、旋轉）
│   └── toast.py             # Toast 通知系統
├── image/                   # 圖片工具
│   ├── info.py              # 圖片資訊擷取
│   ├── pyramid.py           # 深度縮放圖片金字塔
│   ├── thumbnail_disk_cache.py  # 縮圖快取（MD5 + .npy）
│   └── tile_manager.py      # 磁磚網格管理
├── menu/                    # 選單定義
│   ├── file_menu.py         # 檔案選單
│   ├── filter_menu.py       # 篩選選單
│   ├── language_menu.py     # 語言選單
│   ├── plugin_menu.py       # 外掛選單
│   ├── recent_menu.py       # 最近項目子選單
│   ├── right_click_menu.py  # 右鍵選單
│   ├── sort_menu.py         # 排序選單
│   └── tip_menu.py          # 說明選單
├── multi_language/          # 國際化
│   ├── language_wrapper.py  # 語言單例管理器
│   ├── english.py           # 英文翻譯
│   ├── chinese.py           # 简体中文
│   ├── traditional_chinese.py  # 繁體中文
│   ├── korean.py            # 韓文
│   └── japanese.py          # 日文
├── plugin/                  # 外掛系統
│   ├── plugin_base.py       # ImervuePlugin 基底類別
│   ├── plugin_manager.py    # 外掛探索與生命週期
│   └── plugin_downloader.py # 線上外掛下載器
├── system/                  # 系統整合
│   └── file_association.py  # Windows 檔案關聯（登錄檔）
└── user_settings/           # 使用者設定
    ├── user_setting_dict.py # 設定讀寫（執行緒安全）
    ├── bookmark.py          # 書籤管理
    └── recent_image.py      # 最近圖片追蹤
```

### 渲染管線

1. **OpenGL 上下文** — `GPUImageView` 繼承 `QOpenGLWidget`
2. **著色器程式** — 兩個 GLSL 1.20 程式（材質四邊形 + 純色矩形）
3. **材質管理** — LRU 快取，256 磁磚上限，1.5 GB VRAM 預算
4. **深度縮放金字塔** — 多層磁磚金字塔，使用 LANCZOS 重新取樣，512×512 磁磚大小
5. **各向異性過濾** — 硬體支援時最高 8x
6. **備援** — 著色器編譯失敗時使用立即模式渲染

### 縮圖快取

- **金鑰**：`{path}|{mtime_ns}|{file_size}|{thumbnail_size}` 的 MD5 雜湊
- **格式**：NumPy `.npy` 二進位（快速 I/O，無壓縮開銷）
- **位置**：`%LOCALAPPDATA%/Imervue/cache/thumbnails`（Windows）或 `~/.cache/imervue/thumbnails`（Linux/macOS）
- **失效機制**：檔案中繼資料變更時自動失效

---

## 授權

本專案採用 [MIT 授權](../LICENSE)。

Copyright (c) 2026 JE-Chen
