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
- 縮圖磁碟快取系統（壓縮 PNG 格式，MD5 快取金鑰）
- 預載入前後各 ±3 張相鄰圖片
- 復原/重做系統（QUndoStack 用於編輯，傳統堆疊用於刪除）

### 導航與檢視

- 資料夾瀏覽和單張圖片檢視
- **縮圖格 / 清單（詳細）瀏覽模式** — Ctrl+L 切換；清單模式顯示名稱、大小、修改日期、尺寸，並新增星等專欄
- **麵包屑路徑列** — viewer 上方可點擊分段路徑
- 全螢幕 + **劇場模式**（Shift+Tab 隱藏所有外殼）
- 深度縮放模式下的小地圖覆蓋層
- RGB 直方圖覆蓋層
- **F8 OSD**（檔案資訊疊加層）/ **Ctrl+F8 Debug HUD**（VRAM / 快取 / 執行緒）
- **像素檢視**（Shift+P）— 縮放 ≥ 400% 顯示網格與每個像素的 RGB/HEX
- **色彩模式**（Shift+M）— 正常 / 灰階 / 反相 / 懷舊（GLSL 實作，非破壞性）
- 圖片旋轉（包括透過 piexif 的無損 JPEG 旋轉）
- 動態 GIF/APNG 播放，支援逐幀控制
- 幻燈片模式，可自訂間隔時間
- **增強的比對視窗** — 並排 / 重疊（alpha 滑桿）/ 差異（增益滑桿）/ **A|B 分割**（before/after 分頁，可拖曳分割線）
- **分割檢視**（Shift+S）/ **雙頁閱讀**（Shift+D；Ctrl+Shift+D 右至左）
- **多螢幕視窗**（Ctrl+Shift+M）在副螢幕鏡像顯示當前圖片
- **Hover 預覽彈窗** — 縮圖懸停 500 ms 後顯示大預覽
- **觸控板手勢** — 捏合縮放、水平滑動切換圖片
- **瀏覽歷史**（Alt+←/→）+ **隨機圖片**（X）
- **跨資料夾導航**（Ctrl+Shift+←/→）— 跳至前/下一個兄弟資料夾
- 模糊搜尋，子字串高亮（Ctrl+F / `/`）
- **跳至圖片** 對話框（Ctrl+G）— 依編號跳轉
- **命令面板**（Ctrl+Shift+P）— 依指令名稱模糊搜尋並立即執行
- 末端自動循環

### 整理功能

- 書籤系統（最多 5000 個書籤）
- 評分系統（1–5 星）和最愛功能
- **色彩標籤**（F1–F5 → 紅/黃/綠/藍/紫）— 獨立於星等的 Lightroom 風格 flag
- 標籤與相簿，支援**多標籤過濾**（AND / OR 布林邏輯）
- 依名稱、修改日期、建立日期、檔案大小或解析度排序
- 依副檔名、評分、色彩標籤、標籤/相簿篩選
- **進階過濾器** — 解析度 / 檔案大小 / 方向 / 修改日期範圍
- 最近資料夾和最近圖片追蹤
- 啟動時自動恢復上次開啟的資料夾
- **縮圖狀態徽章** — 左緣色條、最愛愛心、書籤星、評分星
- **縮圖排列密度** — 緊湊 / 標準 / 寬鬆
- **檔案樹增強** — F5 刷新、新增資料夾、全部展開/收合
- **RAW+JPEG 堆疊** — 同名的 RAW/JPEG 對自動折疊顯示，保留優先級
- **Session 儲存/還原** — 儲存目前資料夾、選取、縮放與檢視狀態，可日後載入
- **巨集錄製/重播** — 錄製評分、色彩、標籤、最愛等操作並批次套用到多張圖片（Alt+M 重播上次巨集）

### 編輯與匯出

- 內建圖片編輯器（裁切、亮度、對比、飽和度、曝光、旋轉、翻轉），支援非破壞性預覽 — 編輯即時顯示在畫布上，僅在明確儲存時才寫入磁碟
- **Develop 調整面板** — 白平衡（色溫 / 色調）、色階區（陰影 / 中間調 / 高光）、鮮豔度（Vibrance），與傳統曝光 / 對比 / 飽和度並列；所有調整皆透過 per-image recipe 非破壞性保存
- **浮水印疊加** — 可設定文字或圖片浮水印，支援 9 個錨點位置、不透明度與縮放比例；僅在匯出時套用，原圖不受影響
- **匯出預設組合** — 一鍵套用常用輸出設定：Web 1600（長邊 1600 px JPEG）、Print 300 dpi（全解析度、色彩管理）、Instagram 1080（正方或直式 1080 px）
- 匯出/另存新檔，支援格式轉換（PNG、JPEG、WebP、BMP、TIFF）
- 有損格式品質滑桿（JPEG、WebP）
- 批次操作（重新命名、移動/複製、旋轉選取的圖片）
- 設為桌面桌布
- 複製圖片/圖片路徑到剪貼簿
- **聯絡表（Contact Sheet）PDF 匯出** — 可自訂列/行、頁面大小、標題、檔名說明
- **Web Gallery HTML 匯出** — 產生自含式 HTML 藝廊（縮圖 + Lightbox），可選擇複製原始圖片
- **幻燈片 MP4 匯出** — 匯出影片幻燈片（可設解析度、fps、停留秒數、淡入淡出）
- **外部編輯器整合** — 登錄任意外部編輯器並從選單直接以當前圖片開啟

### 中繼資料

- EXIF 資料顯示於可摺疊側邊欄，內含 **星等快速條**，可直接點擊設定 0–5 星
- EXIF 編輯器對話框
- 圖片資訊對話框（尺寸、檔案大小、日期）
- **XMP sidecar**（`.xmp` 檔）— 讀寫星等、標題、描述、關鍵字與色彩標籤，與 Adobe Lightroom / Capture One 互通（透過 `defusedxml` 安全解析 XML）

### 額外功能

- **圖片淨化重繪** — 從原始像素重新繪製圖片，徹底移除所有隱藏資料（EXIF、中繼資料、隱寫內容、尾部位元組），以日期 + 隨機字串重新命名，可選使用傳統方法（Lanczos、Bicubic、Nearest Neighbor）或 AI（Real-ESRGAN）放大至常用解析度（1080p / 2K / 4K / 5K / 8K），保持比例
- **批次格式轉換** — 批次轉換圖片格式（PNG、JPEG、WebP、BMP、TIFF），支援品質控制
- **AI 圖片放大** — 使用 Real-ESRGAN 超解析度放大（x2 / x4 一般、x4 動漫），支援 CUDA / DML / CPU；另有傳統無損方法（Lanczos、Bicubic、Nearest Neighbor）；支援資料夾選擇與遞迴掃描
- **重複圖片偵測** — 使用精確雜湊或感知比對找出重複圖片
- **圖片整理工具** — 依日期、解析度、類型、大小或數量自動分類到子資料夾
- **EXIF 批次清除** — 移除資料夾中所有圖片的 EXIF、GPS 及其他中繼資料
- **裁剪工具** — 互動式裁剪，支援比例預設（自由 / 1:1 / 4:3 / 3:2 / 16:9 / 9:16）與三分法參考線
- **色調曲線編輯器** — 可拖曳控制點的 RGB 與 R/G/B 個別通道曲線（monotone cubic 內插），存在 recipe 裡非破壞性套用
- **.cube LUT 套用** — 匯入任何 Adobe 3D LUT（最高 64³），三線性插值並可用強度滑桿混合
- **Virtual Copies（虛擬副本）** — 為同一張圖儲存多組命名 recipe 快照，隨時切換；副本與主 recipe 同儲存
- **HDR 合成** — 透過 OpenCV Mertens 曝光融合（可選 AlignMTB 對齊）合併多張不同曝光
- **全景接圖** — 以 OpenCV `Stitcher` 接合重疊影像（Panorama / Scans 兩種模式），可自動裁去黑邊
- **Focus Stacking（景深合成）** — 融合不同對焦距離的多張影像（Laplacian 清晰度圖 + Gaussian 混合），可選 ECC 對齊
- **修復筆刷 / 斑點移除** — 點擊新增圓形修復區，使用 OpenCV inpainting（Telea / Navier-Stokes）輸出清理後的圖片
- **鏡頭校正** — 純 numpy 的徑向失真（桶型 / 枕型）、暗角補光、紅 / 藍色差校正，附 4 個滑桿
- **地圖檢視** — 用 Leaflet + OpenStreetMap（需 QtWebEngine）顯示具 GPS 的照片；未安裝時降級為座標列表
- **行事曆檢視** — 以拍攝日期瀏覽圖庫，`QCalendarWidget` 會標示有照片的日期
- **人臉偵測** — OpenCV Haar 正面臉部分類器偵測臉部區域，名稱保存到 recipe 的 `extra`
- **局部調整遮罩** — 筆刷 / 放射 / 線性漸層三種遮罩，每個遮罩有曝光、亮度、對比、飽和度、白平衡等局部 delta，含羽化滑桿並以非破壞方式混入 recipe
- **色調分離** — Lightroom 風格的陰影 / 高光色相+飽和度與平衡樞紐，寫入 recipe.extra 並進入 develop pipeline
- **複製印章** — Shift+點擊設定來源、點擊目的地即完成羽化複製，彌補修復筆刷無法精準搬移內容的場景
- **裁切 / 拉直** — 0..1 的正規化裁切矩形，加上任意角度的自動裁切拉直（不留黑角）
- **自動拉直** — 以 Hough line 偵測地平線 / 垂直線，一鍵算出應該旋轉的角度並套用
- **降噪 / 銳化** — 邊緣保留 bilateral 降噪（可選僅亮度通道），搭配 amount / radius / threshold 的 unsharp mask 銳化
- **天空 / 背景** — 以漸層取代偵測到的天空，或把背景去除成透明 / 白底；安裝 rembg (U²-Net) 時自動升級
- **螢幕校樣** — 載入 ICC 描述檔模擬輸出色域，並把超出色域的像素以洋紅疊色顯示
- **GPS 地理標記** — 讀寫 EXIF GPS 座標（piexif，支援 JPEG）
- **列印排版** — 可設定 A4/A3/Letter/Legal 頁面、方向、格線、邊界、內距、裁切標記，匯出多頁 PDF 列印排版

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
| imageio-ffmpeg | 幻燈片 MP4 匯出（ffmpeg 後端） |

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
- **磁碟快取** — 縮圖以壓縮 PNG 檔案快取，使用 MD5 失效機制

### 單張圖片模式（深度縮放）

開啟單張圖片或雙擊縮圖時：

- **多層圖片金字塔** — 512×512 像素磁磚，使用 LANCZOS 降取樣
- **LRU 磁磚快取** — GPU 上最多快取 256 個磁磚（1.5 GB VRAM 上限）
- **流暢平移和縮放** — GPU 加速，支援各向異性過濾（最高 8x）
- **小地圖覆蓋層** — 顯示目前視窗位置
- **RGB 直方圖** — 按 `H` 鍵切換
- **像素檢視**（Shift+P）— 縮放 ≥ 400% 顯示像素網格與游標下的 RGB/HEX
- **色彩模式**（Shift+M）— 正常 / 灰階 / 反相 / 懷舊（GLSL，非破壞性）
- **載入時置中** — 預設適應視窗大小
- **相鄰圖片預載入** — 預載入前後各 ±3 張相鄰圖片

### 清單模式（詳細）

**Ctrl+L** 切換。以可排序的表格取代縮圖格：

- 欄位：預覽 · 標籤 · 名稱 · 解析度 · 大小 · 類型 · 修改時間
- 任一欄皆可排序（包含色彩標籤）
- 雙擊列開啟深度縮放；Esc 回到清單
- 縮圖 / 元資料在背景執行緒惰性載入

### 分割檢視 & 雙頁閱讀

- **分割檢視**（Shift+S）— 在主視窗並排顯示兩張圖片
- **雙頁閱讀**（Shift+D）— 連續圖片以跨頁顯示；方向鍵一次走 2 張
- **漫畫右至左**（Ctrl+Shift+D）— 雙頁閱讀採右至左順序
- Esc 返回先前模式（縮圖格或清單）

### 多螢幕視窗

**Ctrl+Shift+M** 開啟無邊框第二視窗，於副螢幕最大化，鏡像顯示主
viewer 當前的圖片。主視窗可繼續獨立瀏覽。

---

## 鍵盤與滑鼠快捷鍵

### 導航（兩種模式通用）

| 快捷鍵 | 動作 |
|--------|------|
| 方向鍵 | 捲動網格 / 切換圖片（深度縮放模式下左右切換） |
| Shift + 方向鍵 | 精細捲動（半步） |
| Ctrl+Shift+←/→ | 跳至前/下一個含圖片的兄弟資料夾 |
| Alt+← / Alt+→ | 瀏覽歷史 返回 / 前進（類似瀏覽器） |
| Ctrl+G | 依編號跳至圖片 |
| X | 隨機跳到一張圖片 |
| Home | 重設縮放和平移至原點 |
| Ctrl+F 或 / | 開啟模糊搜尋對話框 |
| Ctrl+Shift+P | 開啟命令面板 |
| Alt+M | 重播上次執行的巨集 |
| S | 開啟幻燈片對話框 |
| Ctrl+Z | 復原 |
| Ctrl+Shift+Z / Ctrl+Y | 重做 |

### 深度縮放 / 單張圖片模式

| 快捷鍵 | 動作 |
|--------|------|
| F | 切換全螢幕 |
| Shift+Tab | 切換**劇場模式**（隱藏所有外殼） |
| R | 順時針旋轉 |
| Shift+R | 逆時針旋轉 |
| E | 開啟圖片編輯器 |
| W | 適應寬度 |
| Shift+W | 適應高度 |
| H | 切換 RGB 直方圖覆蓋層 |
| F8 | 切換 OSD 資訊疊加層（檔名 / 尺寸 / 類型） |
| Ctrl+F8 | 切換 Debug HUD（VRAM / 快取 / 執行緒） |
| Shift+P | 切換像素檢視（≥ 400 % 顯示網格與 RGB 值） |
| Shift+M | 循環色彩模式（正常 / 灰階 / 反相 / 懷舊） |
| B | 切換目前圖片的書籤 |
| Ctrl+C | 複製圖片到剪貼簿 |
| Ctrl+V | 從剪貼簿貼上圖片 |
| 0 | 切換最愛（愛心） |
| 1–5 | 快速評分（1–5 星） |
| F1–F5 | 快速**色彩標籤**（紅 / 黃 / 綠 / 藍 / 紫） |
| Shift+S | 開啟分割檢視（並排兩張圖片） |
| Shift+D | 開啟雙頁閱讀（漫畫/寫真集） |
| Ctrl+Shift+D | 雙頁閱讀（右至左順序） |
| Ctrl+Shift+M | 切換副螢幕鏡像視窗 |
| Delete | 將目前圖片移至垃圾桶（可復原） |
| Escape | 離開深度縮放 / 離開全螢幕 / 關閉雙圖或清單模式 |

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
| Ctrl+L | 切換 縮圖格 ↔ 清單（詳細）瀏覽模式 |
| Hover (500 ms) | 顯示較大的 Hover 預覽彈窗 |
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

### 觸控板手勢

| 手勢 | 動作 |
|------|------|
| 捏合 | 在深度縮放中放大/縮小（以捏合中心為錨點） |
| 水平滑動 | 上一張 / 下一張圖片 |

---

## 選單結構

### 檔案

- 新視窗
- 開啟圖片
- 開啟資料夾
- 最近（子選單：最近資料夾和圖片）
- 書籤（管理已加入書籤的圖片）
- **Session**（子選單：儲存 Session / 載入 Session）
- **以外部編輯器開啟**（子選單：已註冊的外部編輯器）
- **外部編輯器設定…**
- 確認待處理的刪除（確認復原堆疊）
- 快捷鍵設定（自訂鍵盤快捷鍵）
- 檔案關聯（僅限 Windows — 註冊/取消註冊右鍵內容選單）
- 結束

### 額外功能

- 批次格式轉換
- AI 圖片放大
- 重複圖片偵測
- 圖片整理工具
- EXIF 批次清除
- 圖片淨化重繪
- **巨集管理員…** — 錄製、編輯並重播操作巨集
- **聯絡表（Contact Sheet）PDF…** — 匯出 PDF 縮圖頁
- **Web Gallery…** — 匯出自含式 HTML 藝廊
- **幻燈片影片（MP4）…** — 匯出影片幻燈片

### 檢視

- 磁磚大小：128×128 / 256×256 / 512×512 / 1024×1024 / 自動
- **瀏覽模式**：縮圖格 / 清單（Ctrl+L 切換）
- **縮圖排列密度**：緊湊 / 標準 / 寬鬆

### 排序

- 依名稱 / 依修改日期 / 依建立日期 / 依檔案大小 / 依解析度
- 遞增 / 遞減

### 篩選

- 依副檔名：全部、JPG、PNG、BMP、TIFF、SVG、RAW
- **依色彩標籤**：全部 / 任一色 / 無標籤 / 紅 / 黃 / 綠 / 藍 / 紫
- 依評分：全部、已加入最愛、1–5 星
- 依標籤（單選）/ 依相簿（單選）
- **多標籤過濾…** — 多選標籤或相簿，支援 AND / OR 布林邏輯
- **進階過濾…** — 解析度 / 檔案大小 / 方向 / 修改日期範圍
- **堆疊 RAW+JPEG 對** — 勾選時同名的 RAW/JPEG 對折疊成單一項目
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
- 額外功能（批次轉換、AI 放大、重複偵測、圖片整理、EXIF 清除、圖片淨化重繪）
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
| `image_color_labels` | 字典 | 圖片路徑 → 色彩名（`red`/`yellow`/`green`/`blue`/`purple`） |
| `thumbnail_size` | 整數/null | 網格縮圖大小（128/256/512/1024/null 為自動） |
| `tile_padding` | 整數 | 縮圖格邊距像素（0 緊湊 / 8 標準 / 16 寬鬆） |
| `navigation_auto_loop` | 布林 | 末端按 →/← 是否自動循環（預設 `true`） |
| `keyboard_shortcuts` | 字典 | 自訂 `action_id → [key, modifiers]` 覆寫 |
| `window_geometry` | 字串 | Base64 編碼的視窗幾何位置（關閉時儲存） |
| `window_state` | 字串 | Base64 編碼的視窗狀態（dock / 工具列配置） |
| `window_maximized` | 布林 | 上次關閉時視窗是否為最大化 |
| `stack_raw_jpeg_pairs` | 布林 | 是否將同名的 RAW/JPEG 對折疊顯示 |
| `external_editors` | 列表 | 已註冊的外部編輯器（`name`、`executable`、`arguments`） |
| `macros` | 列表 | 已儲存的巨集（步驟陣列 + 建立時間） |
| `macro_last_name` | 字串 | Alt+M 重播時使用的最後巨集名稱 |

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
├── external/                # 外部編輯器整合
│   └── editors.py           # 編輯器登錄與啟動（subprocess）
├── export/                  # 匯出子系統
│   ├── contact_sheet.py     # 聯絡表 PDF 匯出（QPdfWriter）
│   ├── web_gallery.py       # Web Gallery HTML 匯出
│   └── slideshow_mp4.py     # 幻燈片 MP4 匯出（imageio-ffmpeg）
├── macros/                  # 巨集錄製/重播
│   └── macro_manager.py     # 巨集管理員（ACTION_REGISTRY）
├── sessions/                # Session 儲存/還原
├── library/                 # 圖庫聚合工具
├── gui/                     # UI 元件
│   ├── ai_upscale_dialog.py # AI 圖片放大對話框
│   ├── annotation_dialog.py # 裁剪工具對話框
│   ├── batch_convert_dialog.py # 批次格式轉換對話框
│   ├── bookmark_dialog.py   # 書籤管理對話框
│   ├── command_palette.py   # 命令面板（Ctrl+Shift+P）
│   ├── contact_sheet_dialog.py  # 聯絡表 PDF 對話框
│   ├── develop_panel.py     # 開發面板
│   ├── duplicate_detection_dialog.py # 重複圖片偵測對話框
│   ├── exif_editor.py       # EXIF 中繼資料編輯器
│   ├── exif_sidebar.py      # 可摺疊 EXIF 側邊欄
│   ├── exif_strip_dialog.py # EXIF 批次清除對話框
│   ├── export_dialog.py     # 匯出/另存新檔對話框
│   ├── external_editors_settings.py # 外部編輯器設定對話框
│   ├── image_editor.py      # 圖片編輯器（裁切、調整、旋轉）
│   ├── image_organizer_dialog.py # 圖片整理工具對話框
│   ├── image_sanitize_dialog.py  # 圖片淨化重繪對話框
│   ├── macro_manager_dialog.py  # 巨集管理員對話框
│   ├── shortcut_settings_dialog.py # 自訂快捷鍵設定
│   ├── slideshow_mp4_dialog.py  # 幻燈片 MP4 對話框
│   ├── web_gallery_dialog.py    # Web Gallery 對話框
│   └── toast.py             # Toast 通知系統
├── image/                   # 圖片工具
│   ├── info.py              # 圖片資訊擷取
│   ├── pyramid.py           # 深度縮放圖片金字塔
│   ├── thumbnail_disk_cache.py  # 縮圖快取（MD5 + PNG）
│   └── tile_manager.py      # 磁磚網格管理
├── menu/                    # 選單定義
│   ├── extra_tools_menu.py  # 額外功能選單
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
- **格式**：壓縮 PNG（`compress_level=1` — 寫入快速、佔用空間小；舊版 `.npy` 於首次存取時自動清除）
- **位置**：`%LOCALAPPDATA%/Imervue/cache/thumbnails`（Windows）或 `~/.cache/imervue/thumbnails`（Linux/macOS）
- **失效機制**：檔案中繼資料變更時自動失效

---

## 授權

本專案採用 [MIT 授權](../LICENSE)。

Copyright (c) 2026 JE-Chen
