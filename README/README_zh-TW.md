<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  基於 PySide6 和 OpenGL 的 GPU 加速影像瀏覽器 / 顯影器 / 繪圖工作室 / 偶動畫編輯器
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <strong>繁體中文</strong> ·
  <a href="README_zh-CN.md">简体中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md">한국어</a> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <a href="README_de.md">Deutsch</a> ·
  <a href="README_pt-BR.md">Português (BR)</a> ·
  <a href="README_ru.md">Русский</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## 目錄

- [概述](#概述)
- [安裝](#安裝)
- [使用方式](#使用方式)
- [Imervue — 圖片瀏覽與圖庫](#imervue--圖片瀏覽與圖庫)
- [Modify — 非破壞顯影](#modify--非破壞顯影)
- [Paint — 本格的なラスター描画 風格繪圖](#paint--本格的なラスター描画-風格繪圖)
- [Puppet — 2D 綁骨偶動畫](#puppet--2d-綁骨偶動畫)
- [Desktop Pet — 無邊框桌面寵物](#desktop-pet--無邊框桌面寵物)
- [鍵盤與滑鼠快捷鍵](#鍵盤與滑鼠快捷鍵)
- [選單結構](#選單結構)
- [外掛系統](#外掛系統)
- [MCP 伺服器](#mcp-伺服器)
- [多語言支援](#多語言支援)
- [使用者設定](#使用者設定)
- [架構](#架構)
- [授權](#授權)

---

## 概述

Imervue 是一款 GPU 加速的影像工作站，提供 **五個頂層分頁**：

| 分頁 | 功能 |
|---|---|
| **Imervue** | 瀏覽、檢視、整理、搜尋、批次處理你的圖庫 |
| **Modify** | 非破壞顯影管線 — 滑桿、曲線、LUT、遮罩、修圖、多影像合成 |
| **Paint** | 本格的なラスター描画 風格的點陣繪圖工作室，含筆刷、圖層、動畫、漫畫工具、PSD I/O |
| **Puppet** | 從零打造的 2D 綁骨偶動畫器 — 網格、變形器、參數、動作、物理 |
| **Desktop Pet** | 無邊框 / 透明背景 / 永遠置頂的桌面寵物 overlay；用同一條 puppet runtime 帶即時驅動（idle / blink / mic / webcam / drag-track） |

設計原則：

- **效能優先** — 使用現代 GLSL 著色器和 VBO 進行 GPU 加速渲染
- **支援大量集合** — 虛擬化磁磚網格僅載入可見縮圖
- **流暢體驗** — 非同步多執行緒圖片載入與預取機制
- **非破壞顯影** — 每次調整都儲存在每張影像的 recipe 中，原始檔案直到明確匯出才會被覆寫
- **可擴展** — 完整外掛系統（生命週期 / 選單 / 圖片 / 輸入鉤子）；MCP 伺服器將純邏輯工具暴露給 AI 助手使用

---

## 安裝

### 需求

- Python >= 3.10
- 支援 OpenGL 的 GPU（也提供軟體渲染備援）

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

### 依賴套件

| 套件 | 用途 |
|---------|---------|
| PySide6 | Qt6 GUI 框架 |
| qt-material | Material Design 主題 |
| Pillow | 圖片處理 |
| PyOpenGL | OpenGL 綁定 |
| PyOpenGL_accelerate | OpenGL 效能最佳化 |
| numpy | 陣列運算與縮圖快取 |
| rawpy | RAW 影像解碼 |
| imageio | 圖片 I/O |
| imageio-ffmpeg | 幻燈片 MP4 匯出（H.264 透過 ffmpeg） |
| defusedxml | 安全 XML 解析（XMP 邊車檔） |

選用（feature-gated；不裝就停用該功能）：

| 套件 | 用途 |
|---------|---------|
| open_clip_torch + torch | CLIP 語意搜尋 |
| onnxruntime | Real-ESRGAN AI 放大 / CLIP ONNX 自動標籤 |
| opencv-python | HDR 合成、全景拼接、焦點堆疊、人臉偵測、修復筆刷 |
| sounddevice | Puppet 麥克風對嘴 |
| mediapipe | Puppet 攝影機臉部追蹤 |

---

## 使用方式

### 基本啟動

```bash
python -m Imervue
```

### 開啟指定圖片或資料夾

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### 命令列選項

| 選項 | 說明 |
|--------|-------------|
| `--debug` | 啟用除錯模式 |
| `--software_opengl` | 使用軟體 OpenGL 渲染（設定 `QT_OPENGL=software` 和 `QT_ANGLE_PLATFORM=warp`） |
| `file` | （位置參數）啟動時要開啟的圖片或資料夾 |

---

## Imervue — 圖片瀏覽與圖庫

**Imervue** 分頁是預設的著陸頁，整合圖片檢視器與資料夾樹、EXIF 側邊欄、圖庫整理工具。

### 檢視器

- **GPU 加速渲染** — OpenGL（GLSL 1.20 著色器 + VBO）
- **深度縮放金字塔** — 512×512 磁磚多層 LANCZOS 縮放，LRU 快取上限 256 磁磚 / 1.5 GB VRAM 預算，最高 8× 各向異性過濾
- **非同步載入** — 多執行緒解碼 + ±3 張預取
- **虛擬化縮圖網格** — 只渲染可見磁磚；縮圖尺寸可選（128 / 256 / 512 / 1024 / 自動）
- **磁碟快取** — MD5 失效檢測的壓縮 PNG 縮圖，存於 `%LOCALAPPDATA%/Imervue/cache/thumbnails`（或 `~/.cache/imervue/thumbnails`）
- **動畫播放** — GIF / APNG，含播放 / 暫停 / 逐格 / 速度控制

### 瀏覽模式

- **網格**（預設）— 虛擬化磁磚網格，懸停預覽（500 ms 延遲）
- **清單（詳細）** — `Ctrl+L` 切換；欄位：預覽 · 標籤 · 名稱 · 解析度 · 大小 · 類型 · 修改時間
- **深度縮放** — 雙擊磁磚；GPU 流暢平移 / 縮放 + 小地圖
- **分割檢視**（`Shift+S`）— 兩張影像並列
- **雙頁閱讀**（`Shift+D`、`Ctrl+Shift+D` 為漫畫右至左）— 對開頁閱讀器
- **多螢幕鏡射**（`Ctrl+Shift+M`）— 副螢幕視窗
- **劇場模式**（`Shift+Tab`）— 隱藏所有外殼
- **比較對話框** — 並列 / 重疊（alpha 滑桿）/ 差異（增益滑桿）/ A|B 拖曳分割
- **Timeline / Calendar / Map** 檢視 — 按拍攝日期分組、日曆瀏覽、Leaflet + OpenStreetMap 地理座標

### 螢幕疊加層

- RGB 直方圖（`H`）
- F8 OSD（檔名 / 大小 / 類型）、Ctrl+F8 除錯 HUD（VRAM / 快取 / 執行緒）
- 像素檢視（`Shift+P`）— ≥ 400 % 縮放顯示網格 + 每像素 RGB / HEX
- 色彩模式（`Shift+M`）— Normal / Grayscale / Invert / Sepia（GLSL）

### 導航

- 方向鍵、瀏覽器式歷史（`Alt+←/→`）、隨機跳轉（`X`）
- 跨資料夾導航（`Ctrl+Shift+←/→`）
- 跳到第 N 張（`Ctrl+G`）
- 模糊搜尋（`Ctrl+F` / `/`）
- **命令面板**（`Ctrl+Shift+P`）— 模糊搜尋所有選單動作
- 資料夾末端自動循環
- 觸控板捏合縮放 + 水平滑動切換影像

### 整理

- **書籤** — 最多 5000 個路徑
- **評等** — 0-5 星（`1`-`5`）+ 收藏愛心（`0`）
- **顏色標籤** — other XMP-aware photo managers 式 紅 / 黃 / 綠 / 藍 / 紫（`F1`-`F5`）
- **挑片**（Culling）— other XMP-aware photo managers 三狀態旗標（`P` = 保留、`Shift+X` = 拒絕、`U` = 取消）；按狀態過濾；批次刪除拒絕；**自動挑片** 會在每組近重複中挑出最清晰的一張保留、其餘標為拒絕
- **階層式標籤** — 樹狀路徑如 `animal/cat/british`；自動匹配子孫
- **Tags & Albums** 含多標籤 AND / OR 過濾
- **智慧相簿** — 儲存規則式查詢並一鍵重新套用；過濾條件涵蓋副檔名、解析度與 **長寬比**、**檔案大小**、評等 **下限 / 上限**、顏色、挑片、標籤（含 **排除**）、**相機 / 鏡頭**、**檔名 regex / glob** 以及 **檔案年齡**，並可 **匯出 / 匯入** 成可攜的 JSON 檔
- **疊合 RAW+JPEG 對** — 將同檔名擷取折疊成單一磁磚；RAW 仍可從手足存取
- **每圖筆記** — 在 EXIF 側欄，自動防抖儲存，跨工作階段持久
- **暫存盤** — 跨資料夾籃，重啟後保留；批次移動 / 複製 / 匯出
- **雙窗格檔案管理員** — 雙窗格的雙樹檢視
- **Session / 工作區佈局** — 將分頁 / 選取 / 過濾 / 浮動座標快照成 `.imervue-session.json`；可儲存命名佈局（Browse / Develop / Export 排列）
- **巨集** — 錄製 / 重放評等 / 收藏 / 顏色 / 標籤動作批次（`Alt+M` 重放上一個巨集）
- **縮圖徽章 + 密度** — 顏色條 / 收藏 / 書籤 / 評等星；Compact / Standard / Relaxed 內邊距
- **拖出到外部 App** — 直接把磁磚拖進 Explorer / Chrome / Discord
- **最近資料夾 / 圖片** 追蹤；上次資料夾啟動時自動還原

### 排序與過濾

- 按名稱 / 修改時間 / 建立時間 / 大小 / 解析度排序（升 / 降）
- 按副檔名、顏色標籤、評等、標籤 / 相簿、挑片狀態過濾
- **進階過濾** — 解析度 / 檔案大小 / 方向 / 修改日期範圍
- **多標籤過濾** 對話框含 AND / OR

### 搜尋

- **模糊檔名搜尋** 含子字串高亮
- **找相似** — pHash（64-bit DCT）含可調 Hamming 距離
- **圖庫搜尋** — SQLite 多根索引，搭配精簡的查詢 DSL：關鍵字、標籤（含否定）、評等、顏色、副檔名、地點、挑片、收藏、長寬比、年齡、大小、尺寸、相機 / 鏡頭，以及檔名 regex / glob
- **找相似（average hash）** — pHash 與 dHash 再搭配選用的 average-hash（aHash），提供互補的近重複度量
- **語意搜尋（CLIP）** — 自然語言查詢（如「雪中的黃金獵犬」）透過快取的 embedding；`open_clip_torch` + `torch` 未安裝時優雅停用
- **自動標籤** — 啟發式分類 + 選用 CLIP ONNX 升級

### 元資料

- **EXIF 側欄** 含可折疊群組 + 內嵌 0-5 星評等列
- **EXIF 編輯器** 對話框
- **關鍵字編輯器** — 標題 / 創作者 / 描述 / 關鍵字，並從標籤共現提供 **相關標籤建議**，以及 **受控詞彙展開**（輸入葉節點關鍵字會自動套用其祖先＋同義詞，詞彙為可編輯的階層結構）
- **影像資訊** 對話框（尺寸 / 大小 / 日期）
- **XMP 邊車檔**（`.xmp` 同伴檔）— 評等 / 標題 / 描述 / 關鍵字 / 顏色標籤雙向同步 other XMP-aware photo managers（透過 `defusedxml` 安全解析）
- **GPS 地理標記編輯器** — 讀寫 EXIF GPS 經緯度（JPEG）
- **權杖批次重新命名** — 即時預覽範本 `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **匯出元資料 CSV / JSON** — 每張影像一列含挑片 / 評等 / 標籤 / 筆記

### 額外工具（Imervue 分頁 — 批次處理）

從 **Tools** 選單存取；分為功能群組子選單：

- **批次** — 格式轉換 · EXIF 清除 · 影像清洗器（重新渲染移除所有隱藏資料）· 影像整理器 · 權杖批次重命名
- **AI / 啟發式** — AI 影像放大（Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU）· 找重複 · 找相似 · 自動標籤 · 人臉偵測
- **圖庫與元資料** — 圖庫搜尋 · 智慧相簿 · 階層標籤 · 匯出元資料 · XMP 邊車檔 · GPS 標記

### 系統整合

- Windows 右鍵 **以 Imervue 開啟**（透過登錄檔註冊）
- 資料夾監控（`QFileSystemWatcher` 自動重新整理）
- Toast 通知系統（info / success / warning / error）
- 外掛系統含線上下載器（見 [外掛系統](#外掛系統)）

---

## Modify — 非破壞顯影

**Modify** 分頁是顯影工作站。每次調整都儲存在每張影像的 **recipe** 中 — 原始檔案直到你明確 **匯出** 或 **另存新檔** 才會被覆寫。

### 顯影滑桿

- 白平衡 — 色溫 / 色調
- 色調區段 — 陰影 / 中間調 / 高光
- 曝光 / 對比 / 飽和度 / 鮮豔度
- 裁切、旋轉、水平 / 垂直翻轉
- 所有調整透過 recipe 儲存，全程非破壞

### 曲線與 LUT

- **色調曲線編輯器** — 可拖曳 RGB 曲線 + 個別 R / G / B 通道，含 monotone cubic 插值
- **套用 .cube LUT** — 載入任何 Adobe 3D LUT（最高 64³），trilinear 插值，混合強度滑桿
- **分離色調** — 旗標式陰影 / 高光色相 + 飽和度，含平衡樞紐

### 創意效果

- **曝色反轉（Solarize）** — 暗房式色調反轉（閾值 + 混合）
- **柔光暈染（Diffuse Glow / Orton）** — 柔焦高光暈染（強度 / 半徑 / 高光閾值）
- **漸層映射（Gradient Map）** — 亮度 → 調色盤，可選 **感知（OkLCH）** 插值模式，讓飽和漸層的中點維持鮮豔而不變灰
- **有序抖動（Ordered Dither）** — Bayer 矩陣量化至 N 階（保留極值）
- **漸層減光（Graduated Density）** — 依角度 / 硬度 / 偏移的線性 ND 漸層，可加色調，免手繪遮罩平衡天空與前景
- **色調等化器（Tone Equalizer）** — 依亮度分區獨立調整曝光（陰影 → 高光），經平滑遮罩跟隨場景色調
- **細節等化器（Detail Equalizer）** — 依頻帶重新加權對比（細部紋理 vs 粗對比），超越單一清晰度滑桿
- **電影調色（Filmic Tone Map）** — 純 Reinhard / Hable 高光滾降 + 樞軸對比 + 飽和度復原，處理高反差單張曝光
- **Velvia** — 亮度加權飽和度提升，強化淡色同時保護已飽和色與陰影
- **負片轉正（Film Negative）** — 反轉掃描彩色負片、扣除橙色片基，含輸出 gamma
- **去色邊（Defringe）** — 去除高反差邊緣的紫 / 綠色像差色邊，保留平面色彩
- **浮雕（Emboss）** — 由亮度高度場做方向光浮雕
- **極座標（Polar Coordinates）** — 將畫面捲成圓盤或展開（tiny-planet / 極座標反轉）
- **萬花筒（Kaleidoscope）** — 將單一角楔鏡射成 n 重對稱
- **毛玻璃（Frosted Glass）** — 可重現的隨機種子局部像素散射
- **顯影預設** — 儲存 recipe 後可整份 **套用**，或只 **合併** 其有設定的調整到其他影像（保留各影像自身的裁切等）

### 局部調整

- **筆刷 / 放射 / 線性漸層遮罩**，含每遮罩的曝光 / 亮度 / 對比 / 飽和度 / 白平衡偏移 + 羽化滑桿
- 遮罩透過顯影管線非破壞混合

### 修圖與變形

- **修復筆刷** — 圓形點，OpenCV inpainting（Telea 或 Navier-Stokes）
- **仿製圖章** — Shift+點擊來源、羽化貼至目標
- **裁切 / 拉直** — 標準化裁切矩形 + 任意角度拉直，自動裁到最大內接矩形
- **自動拉直** — Hough-line 地平線 / 垂直線偵測
- **鏡頭校正** — 純 numpy 徑向畸變（桶狀 / 枕狀）、暈影提升、各通道色差校正
- **雜訊抑制 / 銳化** — 邊緣保留雙邊去噪 + unsharp mask 銳化
- **天空 / 背景** — 偵測天空換成漸層或去除背景（透明或白色填色）；可選 `rembg` / U²-Net 升級

### 多影像

- **HDR 合成** — 透過 OpenCV Mertens fusion 合併包圍曝光（含 AlignMTB 預先對齊）
- **全景拼接** — OpenCV `Stitcher`（panorama 或 scans 模式），黑邊自動裁切
- **焦點堆疊** — Laplacian 焦點圖 + Gaussian 混合 + 選用 ECC 對齊

### 輸出

- **浮水印疊加** — 文字或圖片，9 個錨點、不透明度、縮放；只在匯出時套用
- **匯出預設** — Web 1600 / Print 300 dpi / Instagram 1080 一鍵流水線
- **另存新檔 / 匯出** — PNG / JPEG / WebP / BMP / TIFF，有損格式提供品質滑桿
- **批次操作** — 重命名、移動 / 複製、旋轉選取影像
- **聯絡單 PDF** — 多頁網格含說明（A4 / A3 / Letter / Legal）
- **網頁圖庫 HTML** — 自包含資料夾含 `index.html` + JPEG 縮圖 + 內嵌燈箱
- **幻燈片 MP4** — H.264 影片，FPS / 每張保留秒數 / 淡入淡出 / 溶接 / 滑入 / 抹除轉場可設（`imageio-ffmpeg`）
- **列印佈局** — 多頁 PDF（A4/A3/Letter/Legal）含網格 / 邊距 / 裝訂溝 / 裁切標記
- **軟校樣** — 載入 ICC profile、模擬目標色域、用洋紅色標示超出色域的像素
- **虛擬副本** — 每影像命名的 recipe 快照；可切換不同風格而不弄丟主本

### 外部編輯器

從 **File > External Editors…** 註冊程式（your image editor /  / …），再從 **File > Open in External Editor** 啟動。

---

## Paint — 本格的なラスター描画 風格繪圖

**Paint** 分頁是完整功能的點陣繪圖工作室，以獨立 `QMainWindow` 嵌入，含選單、左工具列、上下文敏感的選項列、右側分頁式擺放欄。多文件編輯 — 同時開多張圖，每張有獨立復原堆疊。

### 工具（27）

筆刷 · 橡皮擦 · 填色 · 滴管 · 矩形 / 套索 / 魔棒 / 快速選取 · 移動 · 文字 · 漸層 · 模糊 · 塗抹 · Dodge · Burn · Sponge · 鋼筆 · 仿製圖章 · 對話框 · 矩形 · 橢圓 · 線條 · 多邊形 · 裁切 · 變形 · 抓手 · 縮放

暗房調色三件組 — **Dodge**（提亮）、**Burn**（加深）與 **Sponge**（加 / 減飽和度）— 在局部繪製色調與彩度調整，依筆刷與陰影 / 中間調 / 高光遮罩加權。

單鍵快捷：`B / E / G / I / V / T / U / R / P / S / C / Z / H`；`Shift+R/E/I/P` 切形狀變體。

### 筆刷

鋼筆 / 麥克筆 / 鉛筆 / 螢光筆 / 噴漆 / 書法 / 水彩 / 木炭 / 蠟筆，含大小 / 不透明度 / 硬度 / 密度 / 混合模式。壓力曲線編輯器、選取捕獲筆尖、筆刷預設匯入 / 匯出。

### 圖層

完整圖層面板含縮圖、可見性、拖曳重排、混合模式、不透明度、搜尋、向量圖層、1-bit 圖層、**圖層遮罩**（新增 / 從選取 / 反轉 / 套用）、**剪裁遮罩**、**圖層效果**（陰影 / 外發光 / 描邊）。按顏色分割圖層、漸層映射預設。

### 選取

矩形 / 套索 / 魔棒 / 快選 含 **取代 / 加 / 減 / 交集** 模式 + 羽化。**快速遮罩模式**（`Q`）。**描邊選取** 對話框。

### 動畫與漫畫

- **動畫** — 影格時間軸停泊含快照、播放、洋蔥皮、MP4 / GIF 匯出
- **漫畫工具** — 分鏡切割 · 網點層 · 蓋頁碼 · 速度線（放射 / 平行 / 爆發）· 動作閃光 · 對話框工具

### 濾鏡與檢視輔助

- **濾鏡** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone（每個含即時預覽對話框）
- **檢視輔助** — 像素格 · 對齊像素 · 對齊邊緣 · 洋蔥皮 · 出血指引 · 畫布旋轉（`Ctrl+Shift+H` CCW 旋轉）

### 擺放欄（10 個，分頁式）

色彩 · 筆刷 · 圖層 · 導航 · 素材庫 · 歷史 · 色票 · 參考 · 直方圖 · 動畫。每個擺放欄可移動 / 浮動。**Settings > Workspace Layouts** 儲存與召回命名排列。

### 檔案 I/O

- 開啟 / 儲存 **PSD**（Photoshop）含完整圖層往返
- 匯出 PNG / JPEG / WebP，多頁漫畫匯出 **CBZ** 或 **PDF**
- 自動儲存快照 + 還原最新

### 強化使用者體驗

- **Tab** 切換所有擺放欄（無干擾繪圖）
- `Ctrl+Tab` 循環 Paint 分頁
- `,` / `.` 切換筆刷種類
- `0`-`9` 筆刷不透明度 10 % 步進
- `Alt+[` / `Alt+]` 下 / 上切換作用圖層
- 畫布右鍵打開快速 Undo / Redo / 全選 / 取消選 / Fit / 100 %
- 每分頁修改星號、復原 / 重做 toast、啟動時還原自動儲存對話框

從深度縮放按 `E` 把目前圖片直接送入新的 Paint 分頁。

---

## Puppet — 2D 綁骨偶動畫

> **完整教學**：[`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md) 涵蓋直播（OBS / NDI / 虛擬攝影機）與動畫製作（錄製 / 時間軸編輯 / MP4 匯出）的端到端流程。英文版於 [`puppet_guide.md`](../puppet_guide.md)、簡體中文於 [`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md)。

**Puppet** 分頁是從零打造的 2D 綁骨偶動畫系統。功能對標 Live2D（網格變形綁骨、參數、動作、物理、表情、姿勢、對嘴、攝影機臉部追蹤），但 **不依賴任何專利 SDK**、**不使用 `live2d-py`**，採用完全開放的 `.puppet` 檔案格式，規格完整記錄於 `Imervue/puppet/FORMAT.md`。

### 檔案格式

`.puppet` 是 zip 容器：

- `puppet.json` — manifest（drawables、deformers、parameters、motions、pose groups、parts、hit areas）
- `textures/*.png` — atlas 紋理
- `motions/*.json` — keyframe tracks
- `expressions/*.json` — 參數疊加
- `physics.json` — Verlet 物理配置

JSON 為主，人類可 diff，沒有專利二進位。

### 渲染器

`QOpenGLWidget` 含 vertex-array textured-triangle 繪製（依 draw_order）、每 drawable 混合模式（normal / additive / multiply）、pose-group 互斥、影像空間正交投影、GL_REPEAT 平鋪的透明度棋盤背景、滾輪縮放 + 中鍵拖曳平移。針對大型 rig 最佳化 — March 7th（307 drawables / 2965 vertex morphs）在 CPU 上達 60 FPS。

### 編輯

- **匯入 PNG** → 自動產生考慮 alpha 的三角網格
- **新增旋轉變形器**（anchor + angle）/ **新增 warp 變形器**（rows × cols bezier lattice）工具列動作
- **新增參數** → 在滑桿端點按 **Set Key** 在參數擺放欄記錄關鍵形狀
- **網格編輯器** — 切換 Edit Mesh 拖曳頂點；點擊 8 px 內吸附到最近頂點
- **另存新檔…** 把整個 rig 寫成 `.puppet` zip

### 執行

- **參數綁定** — 每個參數保有 key 清單，將滑桿值對應到部分 deformer-form 快照；執行時採樣並逐欄位線性插值
- **動作播放** — 底部擺放欄含動作清單 + 播放 / 暫停 / 停止 / 循環 / 拖曳；曲線取樣器支援 `linear`、`stepped`、`inverse-stepped`、`cubic-bezier` 段（牛頓迭代 time → param）；每動作淡入 / 淡出
- **表情** — `additive` / `multiply` / `overwrite` 參數疊加堆疊
- **姿勢群組** — 互斥 drawable 可見性（武器切換、嘴形變體）
- **物理** — Verlet 鐘擺鏈用於頭髮 / 衣物 / 緞帶；輸入參數移動鏈錨點，重力 + 阻尼 + 每粒子彈簧回復靜止
- **頂點 morph** — Cubism 式線性混合於 rest 與 ±extreme deltas；每幀向量化 numpy，60 FPS
- **不透明度 keys** — 參數驅動的 alpha 曲線；讓替代姿勢 mesh 隨手勢參數淡入 / 淡出

### 即時輸入

- 滑鼠拖曳 → 頭部角度參數
- 自動眨眼，cosine open → close → open 曲線
- 麥克風對嘴 via `sounddevice` RMS → `ParamMouthOpenY`（選用依賴）
- 攝影機臉部追蹤 via OpenCV + MediaPipe FaceMesh → 頭部 yaw / pitch / roll + 眼 / 嘴開合（選用依賴）
- 自訂動作錄製 — 滑動滑桿 / 對攝影機 / 物理運行時以 30 Hz 擷取參數值；停止時烘焙成線性段 Motion

### Cubism 互通

可插入 **Cubism Native SDK**（使用者自備 DLL — Live2D 的 Free Material License 禁止重新散佈）將任何 `.moc3` 模型轉成 `.puppet` zip。轉換器執行 sample-and-reconstruct 掃描，同時擷取 vertex-morph delta 與參數驅動的可見度切換，所以手勢切換（比耶 / 捂臉 / 照相 …）能完整保留。

### 輸出

- **擷取畫面…** 透過 `glReadPixels` 存 PNG
- **錄製…** 切換 30 FPS 影格循環，透過 `imageio` 寫成 GIF / WebM / MP4
- **虛擬攝影機** — 把 puppet canvas 暴露成系統的 webcam
- **NDI 輸出** — 在區網廣播 puppet 成 NDI 來源
- **VTube Studio API 伺服器** — 可選的 WebSocket API，給 VTS 相容客戶端讀參數

### OBS 直播整合

兩條路：A 是「開箱即用」，B 是低延遲、高品質、需要區網。

#### A. 虛擬攝影機（最簡單）

把 puppet canvas 變成假的 webcam，OBS 用標準「視訊擷取裝置」來源即可吃到。

1. `pip install pyvirtualcam`
2. 各平台對應驅動：
   - **Windows**：裝 OBS Studio 26+，會自帶 *OBS Virtual Camera* 驅動。第一次打開 OBS、右下角點 **Start Virtual Camera** 註冊驅動，之後 `pyvirtualcam` 才找得到它。
   - **macOS**：OBS for Mac 自帶 system extension，首次執行會要求在「系統設定 → 隱私權與安全性」啟用。
   - **Linux**：`sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"`（要先 `apt install v4l2loopback-dkms` 之類）。
3. Puppet 分頁打開 rig，工具列 / **Output > Virtual camera** 打勾。狀態列會印出實際裝置名稱。
4. OBS：**Sources > + > Video Capture Device**，下拉選步驟 3 印出的裝置名（通常是 *OBS Virtual Camera*）。

Imervue 會把輸出影格的長邊強制壓到 1080 px，所以 Cubism 原生畫布（March 7th 是 3503×7777）不會被 DirectShow 虛擬攝影機驅動拒絕。長寬比保留，OBS 端可以再縮。

每一幀都會用 off-screen framebuffer 重畫 — 只渲染角色本身、不含棋盤格背景與編輯器外殼。所以 OBS 看到的就是「角色 + 一張純洋紅色背景」。

##### 為什麼是洋紅色背景？（以及怎麼去掉）

虛擬攝影機走的是 **DirectShow**（Windows）/ **AVFoundation**（macOS）/ **v4l2loopback**（Linux），這三種傳輸格式**只有 RGB、沒有 alpha 通道**。OBS 的「視訊擷取裝置」來源把進來的影像當成不透明 RGB，所以 Imervue 在角色以外填什麼顏色，OBS 就顯示什麼顏色。

選 **洋紅色 `#FF00FF`** 是業界標準的 chroma-key 色：它幾乎不會出現在自然膚色、髮色、瞳色裡，去背容差可以開很寬而不誤傷角色。

OBS 端去背步驟：

1. 加進來的「視訊擷取裝置」來源右鍵 → **濾鏡（Filters）**
2. 左下角 **效果濾鏡（Effect Filters）** 區塊 → **+** → **色彩鍵（Color Key）**
3. 設定：
   - **Key Color Type**：`Custom Color`
   - **Custom Color**：HEX 輸入 `FF00FF`（或 R = 255 / G = 0 / B = 255）
   - **Similarity**：從 `80` 開始，邊緣若有殘留洋紅色拉到 `200–300`。數值越大去得越乾淨
   - **Smoothness**：`30–50`，讓邊緣不要太硬、不會像 pixel art
4. 關閉對話框。OBS 把這條濾鏡跟來源綁在一起，之後啟用虛擬攝影機都自動套用

若你的角色配色裡剛好有洋紅色（罕見、costume / 道具上可能），色鍵會把那些像素也吃掉。改走下面的 NDI — 帶 alpha 通道，不用色鍵。

**疑難排解：OBS 還是看得到洋紅色**

- 確認 Color Key 濾鏡是加在**視訊擷取裝置來源本身**，不是加在 Scene 上。加在來源上的濾鏡跟著走；加在 Scene 的會晚一步、在來源繪製完之後才作用。
- HEX 確認是 `FF00FF` 一字不差 — `FF00FE` 之類捕不到全部洋紅色像素。
- 角色輪廓邊緣若有一圈薄薄的洋紅色 halo，把 *Similarity* 拉到 `300`。那一圈是 GL_LINEAR 在角色邊緣跟洋紅色背景內插出來的，容差放寬就能蓋掉。

#### B. NDI（低延遲、專業）

NDI（Newtek 的 Network Device Interface）以 < 50 ms 的延遲在 LAN 上傳遞 puppet 畫面、保留 alpha 通道。

1. 從 <https://ndi.video/tools/> 下載安裝 **NDI Tools**（包含 NDI runtime）。
2. `pip install ndi-python`
3. OBS 端安裝 **obs-ndi** 外掛：<https://github.com/obs-ndi/obs-ndi/releases>
4. Puppet 分頁工具列 / **Output > NDI output** 打勾。狀態列會印 NDI 來源名（預設 *Imervue Puppet*）。
5. OBS：**Sources > + > NDI Source**，下拉選步驟 4 的來源名。

NDI 也吃 1080 上限的縮放，但傳輸 RGBA — off-screen render 把角色外的區域填成完全透明，alpha 通道原樣傳出去，OBS / vMix 端直接把角色疊到自己的場景上，完全不用做色鍵。

#### C. 視窗擷取（保底）

OBS **Sources > + > Window Capture** 可以直接抓 Imervue 視窗，零依賴。畫質較差、要自己 crop 掉外殼，但在不能裝驅動的鎖定機器上能跑。

### 範例

範例 rig 在 [`examples/puppet/march_7th.puppet`](../examples/puppet/march_7th.puppet) — 307 drawable 的 Cubism Live2D 角色倉庫內轉換。從 **開啟 puppet…** 開啟，rig 居中載入；點擊 18 個動作（Idle 群組 + Gesture 群組）任意一個即播放。手勢涵蓋比耶、捂臉、照相、臉紅、黑臉、哭、流汗、星星、流星 — rig 定義的所有命名手勢。

---

## Desktop Pet — 無邊框桌面寵物

第五個分頁。**Desktop Pet** 把任意 `.puppet` 角色以無邊框、透明背景的 overlay 跑在桌面上。分頁本身是控制面板；實際角色會浮在其他視窗之上（或之下）。在 Puppet 分頁能玩的所有東西 — 動作、表情、物理、idle 驅動、攝影機 / 麥克風輸入 — 在這裡也都能用。

### 你可以做的事

| 功能 | 說明 |
|---|---|
| 無邊框 overlay | 沒有視窗外殼、沒有 taskbar entry — 桌面上就是一個角色。 |
| 透明背景 | 角色沒有畫到的地方就讓桌面透出來。 |
| 拖曳移動 | 左鍵拖角色到新位置。釋放時若靠近螢幕邊緣會自動 **吸附** 貼齊邊緣。 |
| 點擊穿透模式 | 讓寵物忽略你的滑鼠，你可以繼續在它底下工作。 |
| 鎖定位置 | 凍結寵物位置，誤拖也動不了。 |
| 永遠置底 | 把寵物壓在所有其他視窗下方 — 像桌面小工具而不是 always-on-top。 |
| 全螢幕時自動隱藏 | 當其他應用（遊戲 / 影片 / 簡報）在同一螢幕進入全螢幕時自動隱藏；全螢幕結束時回來。 |
| 隱藏時暫停 | 寵物看不見時停止動畫 — 離開畫面時零 CPU。 |
| 尺寸 preset | 小 / 中 / 大。以中心為錨點縮放，調尺寸時寵物不會跨螢幕跳。 |
| 不透明度滑桿 | 把寵物從 10% 淡到 100%，可以當作低調的桌面裝飾。 |
| 記住你擺的位置 | 把寵物拖到你喜歡的角落；下次啟動會回到那裡。 |

### 點擊互動

- **左鍵點身體** — 若 rig 定義了 hit area（例如戳頭），就播放對應的動作。否則寵物會用對話泡泡跟你打招呼。
- **任意位置右鍵** — 開啟內容選單：隱藏寵物、Live drivers、Play motion（rig 裡所有動作清單）、Apply expression、鎖定位置、點擊穿透、永遠置底、全螢幕時自動隱藏、對話泡泡、Size。
- **系統托盤 icon** — 左鍵點切換顯示，右鍵開選單（顯示 / 隱藏、點擊穿透、Open puppet、隱藏寵物）。

### 即時驅動

從分頁或右鍵選單裡任意勾選組合。每個預設都是關的 — 只開你想要的。

- **Auto idle** — 呼吸 + 微飄移，讓角色看起來有生命感。
- **Idle motions** — 隨機循環 rig 的 idle 群組動作。
- **Auto-blink** — 每隔幾秒自然眨眼。
- **Drag-track head** — 頭部會轉去追你的游標。
- **Mic lip-sync** — 嘴巴跟著你的聲音開合（需要 `sounddevice`）。
- **Webcam tracking** — 你的頭 / 眼 / 嘴驅動寵物的（需要 `opencv-python` 和 `mediapipe`）。

### 怎麼開始

1. 切到 **Desktop Pet** 分頁。
2. 點 **Load bundled March 7th** 用內建角色，或 **Open Puppet…** 選你自己的 `.puppet` 檔。
3. 勾 **Show pet on desktop**。
4. 把角色拖到你想要的位置；挑選想開的驅動；調整不透明度 / 尺寸。
5. 隨時右鍵開啟快速動作選單，或用系統托盤 icon 直接隱藏寵物，不用回到分頁。

所有設定 — 位置、驅動、不透明度、點擊穿透、尺寸 — 都會在下次啟動時記住。

---

## 鍵盤與滑鼠快捷鍵

### 導航（所有模式）

| 快捷鍵 | 動作 |
|----------|--------|
| 方向鍵 | 滾動網格 / 切換影像（深度縮放中左 / 右） |
| Shift + 方向 | 細微滾動（半步） |
| Ctrl+Shift+←/→ | 跳到前 / 下個含影像的手足資料夾 |
| Alt+← / Alt+→ | 歷史返回 / 前進 |
| Ctrl+G | 跳到第 N 張 |
| X | 隨機跳轉 |
| Home | 重設縮放與平移 |
| Ctrl+F 或 / | 模糊搜尋對話框 |
| Ctrl+Shift+P | 開啟命令面板 |
| Alt+M | 在目前選取重放上一個巨集 |
| S | 開啟幻燈片對話框 |
| Ctrl+Z | 復原 |
| Ctrl+Shift+Z / Ctrl+Y | 重做 |

### 深度縮放 / 單張影像

| 快捷鍵 | 動作 |
|----------|--------|
| F | 切換全螢幕 |
| Shift+Tab | 切換劇場模式 |
| R / Shift+R | 順時針 / 逆時針旋轉 |
| E | 開啟影像編輯器（Modify 分頁） |
| W / Shift+W | 適合寬度 / 高度 |
| H | 切換 RGB 直方圖 |
| F8 / Ctrl+F8 | OSD 疊加層 / 除錯 HUD |
| Shift+P | 切換像素檢視（≥ 400 % 顯示網格 + RGB） |
| Shift+M | 循環色彩模式 |
| B | 切換書籤 |
| Ctrl+C / Ctrl+V | 複製 / 貼上影像至 / 自剪貼簿 |
| 0 / 1-5 | 切換收藏 / 快速評等 |
| F1-F5 | 快速顏色標籤 |
| P / Shift+X / U | 挑片：保留 / 拒絕 / 取消 |
| Shift+S | 分割檢視 |
| Shift+D / Ctrl+Shift+D | 雙頁（LTR / RTL） |
| Ctrl+Shift+M | 多螢幕鏡射視窗 |
| Delete | 移到資源回收筒（可復原） |
| Escape | 結束深度縮放 / 全螢幕 |

### 動畫播放（GIF / APNG）

| 快捷鍵 | 動作 |
|----------|--------|
| 空白鍵 | 播放 / 暫停 |
| ,（逗號）/ .（句號）| 前一影格 / 下一影格 |
| [ / ] | 降低 / 提高播放速度 |

### 磁磚網格

| 快捷鍵 | 動作 |
|----------|--------|
| Ctrl+L | 切換網格 ↔ 清單 |
| 懸停（500 ms） | 懸停預覽彈窗 |
| Delete | 刪除選取磁磚 |
| Escape | 取消全選 |

### 滑鼠 / 觸控板

| 動作 | 行為 |
|--------|----------|
| 左鍵點擊 | 選取磁磚或開啟影像 |
| 左鍵拖曳 | 網格矩形多選 |
| 長按（500 ms） | 進入磁磚選取模式 |
| 中鍵拖曳 | 深度縮放中平移 |
| 滾輪 | 縮放或滾動 |
| 右鍵點擊 | 上下文選單 |
| 捏合 | 深度縮放中縮放 |
| 水平滑動 | 上一張 / 下一張 |

### Paint 分頁（額外）

| 快捷鍵 | 動作 |
|----------|--------|
| B / E / G / I | 筆刷 / 橡皮擦 / 填色 / 滴管 |
| V / T / U / R | 移動 / 文字 / 漸層 / 矩形選取 |
| P / S / C / Z / H | 鋼筆 / 塗抹 / 仿製 / 縮放 / 抓手 |
| Q | 切換快速遮罩模式 |
| Tab | 切換所有擺放欄 |
| Ctrl+Tab | 循環 Paint 分頁 |
| , / . | 循環筆刷種類 |
| 0-9 | 筆刷不透明度 10% 步進 |
| Alt+[ / Alt+] | 下 / 上切換作用圖層 |

---

## 選單結構

### File

- New Window
- Open Image / Open Folder
- Recent（資料夾 + 影像）
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association（Windows）
- **Session** — Save / Load
- **Workspaces…** — 儲存 / 載入 / 重命名命名視窗佈局
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts（可自訂綁定）
- Exit

### Tools（額外工具 — 分為 8 個群組子選單）

- **批次** — 格式轉換 · EXIF 清除 · 影像清洗器 · 影像整理器 · 權杖批次重命名
- **圖庫與元資料** — 圖庫搜尋 · 智慧相簿 · 找相似 / 重複 · 自動標籤 · 階層標籤 · 匯出元資料 · XMP 邊車檔 · GPS 標記
- **檢視** — Timeline · Calendar · Map
- **工作流程** — 挑片 · 暫存盤 · 虛擬副本 · 雙窗格 FM · 巨集
- **匯出** — 聯絡單 PDF · 網頁圖庫 · 幻燈片影片（MP4）· 列印佈局
- **顯影（非破壞）** — 色調曲線 · .cube LUT · 分離色調 · 局部調整遮罩 · 漸層減光 · Velvia · 浮雕 · 去色邊 · 負片轉正 · 電影調色 · 色調 / 細節等化器 · 極座標 · 萬花筒 · 毛玻璃 · 軟校樣
- **修圖與變形** — AI 影像放大 · 雜訊抑制 / 銳化 · 修復筆刷 · 仿製圖章 · 人臉偵測 · 天空 / 背景 · 裁切 / 拉直 · 自動拉直 · 鏡頭校正
- **多影像** — HDR 合成 · 全景拼接 · 焦點堆疊

### 檢視 / 排序 / 過濾 / 語言 / 外掛 / 說明

（標準選單 — 完整選項見應用程式內。）

### 右鍵上下文選單

導航 · 快速動作（顯示 / 複製路徑 / 複製影像）· 變形 · 批次操作 · 刪除 · 桌布 · 比較 / 幻燈片 · 匯出 · 額外工具 · 書籤 · 影像資訊 · 外掛貢獻項目。

---

## 外掛系統

Imervue 支援第三方外掛。完整參考見 [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md)。

### 快速開始

1. 在專案根目錄的 `plugins/` 建立資料夾
2. 定義繼承 `ImervuePlugin` 的類別
3. 在 `__init__.py` 用 `plugin_class = YourPlugin` 註冊
4. 重啟 Imervue

### 鉤子

| 鉤子 | 觸發 |
|------|---------|
| `on_plugin_loaded()` | 外掛實例化後 |
| `on_plugin_unloaded()` | App 關閉時 |
| `on_build_menu_bar(menu_bar)` | 預設選單列建好後 |
| `on_build_main_tabs(tabs)` | 內建 4 個分頁加完之後 |
| `on_build_context_menu(menu, viewer)` | 右鍵選單開啟時 |
| `on_image_loaded(path, viewer)` | 影像在深度縮放載入後 |
| `on_folder_opened(path, images, viewer)` | 資料夾在網格開啟後 |
| `on_image_switched(path, viewer)` | 切換影像時 |
| `on_image_deleted(paths, viewer)` | 影像被軟刪除後 |
| `on_key_press(key, modifiers, viewer)` | 按鍵時（回傳 True 消費事件） |
| `on_app_closing(main_window)` | App 關閉前 |
| `get_translations()` | 提供 i18n 字串 |

### 外掛下載器

**Plugins > Download Plugins** 開啟線上下載器。來源倉庫：[Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins)。

---

## MCP 伺服器

Imervue 內建 [Model Context Protocol](https://modelcontextprotocol.io) 伺服器，讓 AI 助手（Claude Code / Desktop、Cursor、Cline …）能在沒有 GUI 的情況下呼叫專案的純邏輯工具。Qt-free；一個命令啟動：

```sh
python -m Imervue.mcp_server
```

### 工具

精選工具（共 46 個 — 完整清單見文件）。每個工具都會宣告 JSON
`outputSchema` 與唯讀 / 破壞性的 `annotations`，並把結果以
`structuredContent` 回傳；長時間執行的工具會串流 `notifications/progress`。

| 工具 | 用途 |
|------|---------|
| `list_images` | 列出資料夾中的影像（可選遞迴） |
| `read_image_metadata` / `read_xmp_tags` | 尺寸、格式、EXIF、XMP 邊車檔（評等、色標、關鍵字） |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | 無參考分析：各通道統計、colourfulness/entropy/對比、直方圖 + 裁切、模糊分數 |
| `image_thumbnail` / `ocr_text` / `find_similar` | Base64 預覽、Tesseract 文字、perceptual-hash 近重複分組（含進度） |
| `convert_format` | 轉換 PNG / JPEG / WebP / TIFF / BMP（+ 選用 HEIC / AVIF / JXL） |
| `apply_watermark` / `apply_frame` | 燒入文字浮水印，或加 matte / 拍立得相框 + 說明文字 |
| `build_collage` | 把多張圖片合成成網格拼貼（含進度） |
| `crop_image` / `resize_image` / `rotate_image` | 像素裁切、保留長寬比縮放、無損旋轉 / 翻轉 |
| `collection_stats` | 資料夾的評等 / 收藏 / 色標 / 挑片彙整 |
| `search_images` | 以 smart-album 查詢 DSL 篩選資料夾（路徑 / EXIF / 大小 / 尺寸） |
| `extract_gps` / `dominant_colors` | 讀取 EXIF GPS 座標（可接 `reverse_geocode`）；median-cut 調色盤（rgb / hex / 占比） |
| `error_level_analysis` | JPEG 重壓的竄改鑑識圖（PNG data URI） |
| `solarize_image` / `glow_image` | 套用曝色反轉或柔光暈染並存檔 |
| `velvia_image` / `emboss_image` / `defringe_image` | Velvia 飽和度提升、方向光浮雕、邊緣色邊去飽和 |
| `film_negative_image` / `graduated_density_image` | 反轉掃描負片；套用線性漸層減光 |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | 電影調色高光滾降；分區曝光；分頻帶對比 |
| `colormap_image` / `false_color_image` | 以 viridis / magma / jet 感知色彩映射重新上色；偽彩曝光尺標 |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Bayer 有序抖動；陰影／高光分離色調；亮度帶像素排序 |
| `polar_image` / `kaleidoscope_image` | 極座標／反極座標扭曲（小行星）；鏡射成萬花筒楔形 |
| `frosted_glass_image` / `clahe_image` / `local_contrast_image` | 隨機鄰點毛玻璃散射；CLAHE 局部均衡；清晰度＋紋理局部對比 |
| `reverse_geocode` / `extract_video_frame` | 離線 GPS → 城市、把影片一格解碼成靜態影像 |
| `puppet_from_png` / `puppet_inspect` | 從 PNG 建構 `.puppet` rig；開啟一個並回傳清單 |

### Prompts

四個可重用的 prompt：`caption_image`、`suggest_edits`、`analyze_composition`
（以 saliency 為基礎的構圖評析）與 `flag_issues`（銳利度 + 品質 + 裁切的
分流檢查）。prompt 的引數可透過 `completion/complete` 自動補全。

### 配置

倉庫根目錄附帶 `.mcp.json` 供 Claude Code 自動探索。對於 Desktop / 其他客戶端，加入 `claude_desktop_config.json`（或等效）：

```json
{
  "mcpServers": {
    "imervue": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "Imervue.mcp_server"]
    }
  }
}
```

完整協議介面見 [docs/en/index.rst](../docs/en/index.rst) 的 MCP 章節。

---

## 多語言支援

| 語言 | 代碼 |
|----------|------|
| English | `English` |
| 繁體中文 | `Traditional_Chinese` |
| 简体中文 | `Chinese` |
| 한국어 | `Korean` |
| 日本語 | `Japanese` |

從 **Language** 選單切換。需重啟。

外掛可透過 `language_wrapper.register_language()` 註冊全新語言，或透過 `get_translations()` 提供翻譯。詳見 [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n)。

---

## 使用者設定

儲存在工作目錄的 `user_setting.json`。關鍵欄位：

| 設定 | 類型 | 說明 |
|---------|------|-------------|
| `language` | string | 目前語言代碼 |
| `user_recent_folders` / `user_recent_images` | list | 最近開啟 |
| `user_last_folder` | string | 啟動時自動還原 |
| `bookmarks` | list | 書籤路徑（最多 5000） |
| `sort_by` / `sort_ascending` | string / bool | 排序方法 + 順序 |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | 每影像整理 |
| `thumbnail_size` / `tile_padding` | int | 網格配置 |
| `navigation_auto_loop` | bool | 資料夾末端自動循環 |
| `keyboard_shortcuts` | dict | 自訂鍵綁定 |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | 視窗佈局持久化 |
| `stack_raw_jpeg_pairs` | bool | RAW+JPEG 疊合切換 |
| `external_editors` | list | 已配置編輯器 |
| `macros` / `macro_last_name` | list / string | 已儲存巨集 + Alt+M 目標 |

---

## 架構

```
Imervue/
├── __main__.py              # 應用程式進入點
├── Imervue_main_window.py   # 主視窗（QMainWindow）— 掛載 4 個分頁
├── gpu_image_view/          # IMERVUE 分頁 — GPU viewer + 深度縮放
├── gui/                     # 對話框與側邊欄（顯影、EXIF 等）
├── paint/                   # PAINT 分頁 — 本格的なラスター描画 風格點陣編輯器
├── puppet/                  # PUPPET 分頁 — 2D 綁骨偶動畫器
├── export/                  # 匯出產生器（聯絡單、網頁圖庫、MP4）
├── image/                   # 影像工具（金字塔、磁磚管理、資訊）
├── library/                 # 圖庫輔助（RAW+JPEG 疊合、索引）
├── macros/                  # 巨集錄製 / 重放
├── menu/                    # 選單定義
├── mcp_server/              # Model Context Protocol stdio 伺服器
├── multi_language/          # i18n（en / zh-tw / zh-cn / ja / ko）
├── external/                # 外部編輯器整合
├── plugin/                  # 外掛系統（base / manager / downloader）
├── sessions/                # 工作區序列化
├── system/                  # Windows 檔案關聯
└── user_settings/           # 持久使用者設定
```

### 渲染管線（Imervue 分頁）

1. `GPUImageView` 繼承 `QOpenGLWidget`
2. 兩個 GLSL 1.20 程式（textured quads + solid color rectangles）
3. LRU 紋理快取 — 256-磁磚上限、1.5 GB VRAM 預算
4. 多層磁磚金字塔以 LANCZOS 在 512 × 512 磁磚尺寸建構
5. 硬體支援時最高 8× 各向異性過濾
6. 著色器編譯失敗時軟體渲染備援

### 縮圖快取

- **鍵**：`{path}|{mtime_ns}|{file_size}|{thumbnail_size}` 的 MD5
- **格式**：壓縮 PNG（`compress_level=1` — 寫入快、佔用小）
- **位置**：`%LOCALAPPDATA%/Imervue/cache/thumbnails`（Win）或 `~/.cache/imervue/thumbnails`（Linux/macOS）
- **失效**：檔案元資料變動時自動

### Puppet 渲染（Puppet 分頁）

- `QOpenGLWidget` 含 `glDrawElements` + 客戶端 vertex array
- 每 drawable：rest vertices 快取為 float32 numpy；vertex morphs 向量化；topological deformer sort 提升出 per-drawable 迴圈
- 透明度背景是 2×2 GL_REPEAT 平鋪紋理（最佳化前是 100k+ 立即模式 quads）
- Cubism 轉換器同時產生 opacity_keys 曲線與 vertex-morph deltas，所以參數驅動的可見度切換能存活 `.moc3 → .puppet` 轉換

---

## 授權

本專案使用 [MIT License](../LICENSE)。

Copyright (c) 2026 JE-Chen
