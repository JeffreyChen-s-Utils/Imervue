<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  基于 PySide6 和 OpenGL 的 GPU 加速图像浏览器 / 显影器 / 绘图工作室 / 偶动画编辑器
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <strong>简体中文</strong> ·
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

## 目录

- [概述](#概述)
- [安装](#安装)
- [使用方式](#使用方式)
- [Imervue — 图片浏览与图库](#imervue--图片浏览与图库)
- [Modify — 非破坏显影](#modify--非破坏显影)
- [Paint — 全功能栅格编辑器](#paint--全功能栅格编辑器)
- [Puppet — 2D 绑骨偶动画](#puppet--2d-绑骨偶动画)
- [Desktop Pet — 无边框桌面宠物](#desktop-pet--无边框桌面宠物)
- [键盘与鼠标快捷键](#键盘与鼠标快捷键)
- [菜单结构](#菜单结构)
- [插件系统](#插件系统)
- [MCP 服务器](#mcp-服务器)
- [多语言支持](#多语言支持)
- [用户设置](#用户设置)
- [架构](#架构)
- [许可](#许可)

---

## 概述

Imervue 是一款 GPU 加速的图像工作站，提供 **五个顶层标签**：

| 标签 | 功能 |
|---|---|
| **Imervue** | 浏览、查看、整理、搜索、批量处理你的图库 |
| **Modify** | 非破坏显影管线 — 滑块、曲线、LUT、蒙版、修图、多图合成 |
| **Paint** | 全功能栅格绘图工作室，含笔刷、图层、动画、漫画工具、PSD I/O |
| **Puppet** | 从零打造的 2D 绑骨偶动画器 — 网格、变形器、参数、动作、物理 |
| **Desktop Pet** | 无边框 / 透明背景 / 永远置顶的桌面宠物 overlay；用同一条 puppet runtime 带实时驱动（idle / blink / mic / webcam / drag-track） |

**Puppet** 与 **Desktop Pet** 是可选标签页：在 **File > Preferences > Optional tabs** 关闭其中一个，下次启动起就不会加入那个标签页、也不会加载它的代码，Imervue 启动更快、占用的内存更少。两者默认开启；各自在第一次打开标签页时才创建，若桌面宠物设置为启动时显示，Desktop Pet 标签页会在启动时就创建。

设计原则：

- **性能优先** — 使用现代 GLSL 着色器和 VBO 进行 GPU 加速渲染
- **支持大量集合** — 虚拟化磁砖网格仅加载可见缩图
- **流畅体验** — 异步多线程图片加载与预取机制
- **非破坏显影** — 每次调整都存储在每张图片的 recipe 中，原始文件直到明确导出才会被覆写
- **可扩展** — 完整插件系统（生命周期 / 菜单 / 图片 / 输入钩子）；MCP 服务器将纯逻辑工具暴露给 AI 助手使用

---

取消或关闭正在运行的后台工具时，请求立即返回；对话框显示“正在取消”并暂停操作，待当前无法立即中断的工作和清理完成后，再按原始结果关闭。正常完成时可能短暂显示“正在完成”。重新打开不会收到旧任务的结果。程序最终退出前仍会等待剩余任务安全结束。

在 `Extra Tools` > `Workflow` > `Background Jobs` 查看跨窗口的批量导出、图库扫描、AI 放大／共享插件转换和插件下载。原始对话框关闭后，已完成输出和失败原因仍会保留。取消采用协作方式，当前任务会存活到实际结束。重试建立新任务，只处理失败项并保留成功输出；每次插件下载视为一个完整安装项。面板最多显示 500 条明细，失败优先；“保存完整报告”将全部结果保存为 JSON。“清除已完成”释放已结束任务的记录。

Paint 的 File > `Open Document…`、`Save Document…`、`Save Document As…` 和 `Save All Documents` 使用可继续编辑的 `.imervue` 文件。“保存全部”依次处理已修改标签页，不切换当前标签页；取消或失败即停止，未保存文件保持打开。关闭窗口可保存全部，关闭标签页则保存该页。保存后 Undo／Redo 会重新标记修改。平面图片导出独立处理，不清除修改状态。标签页和状态栏提示显示来源、文件保存位置、平面输出及恢复自动保存状态／时间／错误。打开原生文件和拖放保留已有编辑。现有 PSD 快捷键保持不变；手动原生保存同步执行。

使用 `Extra Tools` > `Workflow` > `Photo Workflow` 串联搜索 → 比较 → 保留／拒绝 → 显影预设 → 批量导出。Library Search 加入高亮结果，未高亮时加入全部结果；重开搜索保留查询和结果。每个窗口在关闭或返回后保留跨文件夹的有序集合、勾选、过滤和预设名称。过滤只改变显示：隐藏但勾选的照片仍是批量目标，计数会明确显示。保留勾选照片，拒绝取消勾选而不删除。比较预览长边最多 800 像素。显影沿用命名预设；Batch Export 接收同一组已勾选且非拒绝来源和导出预设。每页 500 条，应用／导出前同步外部挑片状态；清除流程明确重置。

单张导出、批量导出和批量转换共用原子写入，在 `Background Jobs` 保留已完成路径与错误。批量重名自动改名，同格式转换也另存；单张替换需确认。GUI 保留 metadata 时嵌入正确的 sRGB ICC；转换保留描述信息，导出默认移除位置。CLI 逐张输出支持 `--output-conflict`（`rename`、`skip`、`replace`）、`--export-metadata`（`all`、`no_location`、`none`）和含输出链接的 JSON `--result-report`。默认沿用跳过／`--overwrite` 和编码行为；指定 metadata 可能重新编码。`strip` 始终移除 metadata。Ctrl+C 保留完成输出并报告取消。PDF、MP4 和图库文件原子发布；图库原件副本保留 metadata。

`Manage Plugins` 显示各窗口的加载失败，以及共享依赖、下载、模型和后端状态及原因。已加载表示可选能力在使用时检查；共享工具结果保留所选模型／后端和 CPU 降级原因。下载和重试保留正常安装、模型和素材，同一插件／解释器的并行安装被拒绝。依赖窗口取消不阻塞，导入失败不会误报成功。`Reload Plugins` 重新读取各窗口代码；GPU Develop 保留其他窗口仍使用的后端，要求插件 API 3。下载或重试后，在每个窗口重载或重启。

缩略图磁盘缓存改为后台盘点，浏览可立即读写。写入采用原子替换，前台修改优先于过时盘点；清除包含尚未盘点的文件。后台初始化清理旧 NPY 并调整配额，结束前容量统计为暂定值。可读取信息的锁定文件仍计入，可能阻止配额达标。固定十万文件测量的构造 p95 低于 10 ms，盘点完成时间与额外成本单独记录。

## 安装

### 需求

- Python >= 3.10
- 支持 OpenGL 的 GPU（也提供软件渲染备援）

### 从源码安装

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### 安装为包

```bash
pip install .
```

### 依赖

| 包 | 用途 |
|---------|---------|
| PySide6 | Qt6 GUI 框架 |
| qt-material | Material Design 主题 |
| Pillow | 图片处理 |
| PyOpenGL | OpenGL 绑定 |
| PyOpenGL_accelerate | OpenGL 性能优化 |
| numpy | 数组运算与缩图缓存 |
| rawpy | RAW 图像解码（CR2 / CR3 / NEF / ARW / RAF / ORF / RW2 / PEF / DNG 等） |
| imageio | 图片 I/O |
| imageio-ffmpeg | 幻灯片 MP4 与 Create GIF / Video 的 MP4（H.264 通过 ffmpeg） |
| defusedxml | 安全 XML 解析（XMP 边车文件） |
| watchdog | Watched Folder 自动化与 MCP 服务器的变更通知 |

可选（feature-gated；不装就停用该功能）：

| 包 | 用途 |
|---------|---------|
| onnxruntime + huggingface_hub | CLIP 语义搜索与 CLIP 自动标签（首次使用时提示安装；约 150 MB 的模型只下载一次） |
| onnxruntime | Real-ESRGAN AI 放大 |
| opencv-python<5 | HDR 合成、全景拼接、焦点堆叠、人脸检测、修复笔刷 |
| sounddevice | Puppet 麦克风对嘴 |
| mediapipe | Puppet 摄像头脸部追踪 |

---

## 使用方式

### 基本启动

```bash
python -m Imervue
```

### 打开指定图片或文件夹

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### 命令行选项

| 选项 | 说明 |
|--------|-------------|
| `--debug` | 启用调试模式 |
| `--software_opengl` | 使用软件 OpenGL 渲染（设置 `QT_OPENGL=software` 和 `QT_ANGLE_PLATFORM=warp`） |
| `file` | （位置参数）启动时要打开的图片或文件夹 |

### 无界面批处理 CLI

`Imervue.cli` 可在 shell 中执行纯图像运算，**完全不启动 Qt** —— 适合脚本、CI 步骤，以及没有显示设备的服务器：

```bash
py -m Imervue.cli resize photos/ --max 1600 --out web/
py -m Imervue.cli watermark a.jpg --text "(c) Me" --corner bottom-right
py -m Imervue.cli info *.png --json
py -m Imervue.cli list-ops          # 列出所有可用子命令
```

| 子命令 | 用途 |
|---|---|
| `info` / `stats` | 尺寸与格式；无参考质量指标（`--json` 输出机器可读格式） |
| `convert` / `resize` / `thumbnail` | 格式转换（`--format` JPEG / PNG / WEBP / TIFF / BMP / AVIF / HEIC / JXL、`--quality`）；缩放到指定长边（`--max`）或精确的 `--width` / `--height`；缩略图尺寸 |
| `watermark` / `optimize` | 文字水印（`--text`、`--corner`、`--opacity`、`--font-fraction`、`--color R G B`、`--no-shadow`）；在 `--max-kb` 预算内编码 |
| `dehaze` / `clahe` / `dither` / `distort` | 暗通道去雾、自适应均衡、Bayer 有序抖动、swirl / pinch / ripple |
| `auto-orient` / `strip` | 把 EXIF 方向标记烘焙进像素；重存并移除 EXIF / XMP / ICC |
| `collage` / `anaglyph` | 网格拼贴（`--columns`、`--cell-width` / `--cell-height`、`--gap`、`--margin`、`--background R G B`）；立体对转红蓝 3D（`--method`） |
| `preset` / `pipeline` | 按名称应用已保存的显影预设；执行有序的 JSON 运算管线 |
| `list-ops` | 列出所有子命令（`--json` 输出机器可读格式） |

每个子命令都像查看器一样解码：输出会依 EXIF 方向转正，并从内嵌色彩描述文件转换为 sRGB；AVIF 由 Pillow 自己读取，安装了可选后端时也能读取 HEIC / JPEG XL。相机 RAW 会像查看器一样显像，而不是读成内嵌的小预览；`resize` 与 `strip` 会写成 PNG。无法读取的文件会被报告，其余文件照常处理。中途截断的文件会像查看器一样，读取到能读的位置为止。16 位与浮点灰阶会像查看器一样缩放成 8 位；`resize` 与 `strip` 保留来源的位深度。

接受文件或文件夹的子命令（除 `collage`、`anaglyph`、`list-ops` 外的全部）共用 `--out`（输出目录）、`--recursive`、`--dry-run`（只列出动作、不写入）、`--overwrite` 与 `-j` / `--jobs`（并行任务数；`0` 表示使用全部核心）。`collage` 与 `anaglyph` 写入 `--out` 指定的单个文件。`--version` 显示 CLI 版本。

[MCP 服务器](#mcp-服务器)的每个工具也都是一个子命令。其中十个就是上面的子命令（`convert_format` 即 `convert`、`quality_metrics` 即 `stats`、`build_collage` 即 `collage`，依此类推）；其余 48 个直接执行 MCP 工具自身的代码：

| 类型 | 子命令 |
|---|---|
| 编辑：在每个源文件旁写入 `<stem>_<name>.png`，或在 `--out` 中写入 `<stem>.png` | `frame`、`crop`、`rotate`、`solarize`、`glow`、`velvia`、`emboss`、`film-negative`、`defringe`、`graduated-density`、`filmic-tonemap`、`tone-equalizer`、`detail-equalizer`、`colormap`、`false-color`、`split-toning`、`pixel-sort`、`polar`、`kaleidoscope`、`frosted-glass`、`local-contrast`、`posterize`、`gradient-map`、`film-grain`、`levels`、`auto-color-balance`、`channel-mixer`、`curve`、`lens-correction` |
| 其他输出 | `ela`（错误级别分析图，输出为 PNG）、`video-frame`（视频中的单帧，`--frame-index`）、`puppet-from-png`（`.puppet` 绑骨模型，`--cell-size`） |
| 报告：每张图片一个结果，`--json` 输出机器可读格式 | `metadata`、`xmp`、`gps`、`dominant-colors`、`sharpness`、`statistics`、`histogram`、`ocr`、`puppet-inspect`、`puppet-validate` |
| 执行一次并输出 JSON | `list-images FOLDER`、`search FOLDER --query "..."`、`similar FOLDER`、`collection-stats FOLDER`、`reverse-geocode --latitude .. --longitude ..`、`puppet-schema --name ..` |

每个 MCP 参数都会成为一个选项，默认值与允许的取值都与原参数相同：`zone_gains` 对应 `--zone-gains`，布尔（是 / 否）参数对应 `--grayscale` / `--no-grayscale`，颜色或矩阵的一行则按顺序接受各个值（`--red 1 0 0`）。`py -m Imervue.cli <subcommand> --help` 会列出这些选项。

`pipeline FILE INPUTS…` 按 JSON 文件串接多个运算 —— 文件内容是步骤列表或 `{"pipeline": [...]}`，每个步骤是一个 `"op"` 加上该运算的参数（最多 50 个步骤）。可用的运算有 `dehaze`、`clahe`、`dither`、`distort`、`clarity`、`texture`、`grayscale`、`invert` 与 `watermark`；每个参数及其默认值见文档。

```bash
py -m Imervue.cli film-grain photos/ --intensity 0.4 --seed 7 --out grain/
py -m Imervue.cli crop a.jpg --x 0 --y 0 --width 800 --height 600
py -m Imervue.cli histogram a.jpg --json
py -m Imervue.cli search photos/ --query "ext:jpg width:>1920"
```

---

## Imervue — 图片浏览与图库

缩略图墙加载新的 GPU 纹理前，会先淘汰画面外纹理，保留可见缩略图并遵守内存预算。只有边缘接触画面、实际可见面积为零的纹理不会占住容量。

绘制、缩略图请求和纹理淘汰共享可见网格范围，并在周边保留一行／列缓冲。普通缩略图尺寸按需解码，同时执行的工作不超过缩略图池容量；滚动会替换尚未启动的请求。完整分辨率模式以有限并行工作继续发现超出格子的图片。进度显示当前画面和明确请求的工作；从 Deep Zoom 返回时保留已加载的缓存和网格位置。

相邻图片预取会合计实际金字塔字节与解码中的预留容量。预取共享物理 RAM 的 20%（256 MiB–8 GiB），由打开的查看窗口公平分配；缺少可选内存检测时共享 2 GiB 降级配额。取消的解码实际结束后才释放预留容量；打开被配额拒绝的图片时，仍会走正常前台加载。RAM 配额与 GPU 纹理预算分开，并非整个程序或前台图片的内存上限。

**Imervue** 标签是默认登陆界面，整合图片查看器与文件夹树、EXIF 侧边栏、图库整理工具。

### 查看器

- **GPU 加速渲染** — OpenGL（GLSL 1.20 着色器 + VBO）
- **深度缩放金字塔** — 512×512 瓦片多层 LANCZOS 缩放；瓦片 LRU 保留 256 条（硬上限 512）。VRAM 预算在启动时向 GL 驱动探测，获取失败则回落 1.5 GB，可用 `vram_limit_mb` 设置覆盖（会钳制，不会被静默忽略）。最高 8× 各向异性过滤；远超 Pillow 安全上限（1.79 亿像素）的全景图也能打开（上限依内存而定：16 GB 约 14 亿像素）
- **异步加载** — 多线程解码搭配自适应预取窗口：一般浏览为 ±3 张，一旦持续朝同一方向翻页便扩张为前 5 张 / 后 1 张
- **独立工作线程池** — 缩略图爆量与深度缩放解码分属不同池，打开大文件夹时不会饿死你正在看的那张图
- **虚拟化缩图网格** — 只渲染可见磁砖；缩图尺寸可选（128 / 256 / 512 / 1024 / 自动）
- **磁盘缓存** — MD5 失效检测的压缩 PNG 缩图，存于 `%LOCALAPPDATA%/Imervue/cache/thumbnails`（或 `~/.cache/imervue/thumbnails`）
- **EXIF 方向** — 手机或相机只打了方向标签、没有真正旋转的竖拍照片，在检视器、缩图、列表视图、悬停预览和 Modify 分页中都会摆正显示；之前保存的显影裁剪 / 旋转仍按当初的方向套用
- **色彩管理** — 内嵌色彩描述文件的照片（手机的 Display P3、相机的 Adobe RGB、CMYK，以及 Photoshop 嵌入灰度图像的灰度描述文件，例如 Dot Gain 20%、Gray Gamma 1.8）在检视器与缩图中会转换为 sRGB 显示；没有描述文件或本身是 sRGB 的图像照原样显示
- **不完整的文件** — 中途截断的 JPEG、PNG、TIFF、GIF、BMP（下载或复制中断、从故障存储卡救回的照片）会像浏览器一样显示已读到的部分，而不是完全打不开
- **被其他程序修改的文件** — 其他程序覆盖保存图片时（外部编辑器直接覆盖，或先写副本再改名替换），检视器会显示新版本：深度缩放中打开的图片在最后一次写入后 1 秒内更新，网格缩图与列表的行在几秒内更新
- **16 位与浮点灰阶** — 16 位灰阶 PNG／TIFF（扫描、深度图、科学或天文影像）与浮点 TIFF，在检视器、缩图、预览与工具中都以真实亮度显示，不再几乎全白或全黑
- **隐藏文件** — Windows 标为隐藏的文件（在资源管理器与文件夹树中也不显示），以及以点开头的名称（例如 macOS 在存储卡、网络驱动器上替每张照片写入的 `._photo.jpg`），不会出现在缩图网格、文件夹图标、批量工具的文件夹清单、监视文件夹、图库扫描、CLI 与 MCP 服务器的文件夹工具中；递归扫描会跳过 `$RECYCLE.BIN`、Mac 的 `.Trashes` 等隐藏文件夹。特意打开的隐藏图片仍会打开
- **各种扩展名的 JPEG** — `.jpe`、`.jfif`、`.jif` 和 `.jpg` 一样能打开（Windows 上的 Chrome、Edge 常把下载的照片存成 `.jfif`），检视器、JPG 筛选、批量工具与 CLI 都适用
- **更多格式** — ICO、TGA、DDS、QOI、JPEG 2000（.jp2／.j2k／.jpf／.jpx）、Netpbm（PPM／PGM／PBM／PNM）、PCX、PSD（合并后的图像） 由 Pillow 直接读取，可以检视；原地旋转等写回操作会被拒绝，编辑请用“另存为”／“导出”保存
- **动画播放** — GIF / APNG，含播放 / 暂停 / 逐帧 / 速度控制；解码后超过 512 MB 的动画会边播放边逐帧解码，而不是一开始全部解码；10 ms 以下的帧会和浏览器一样显示 100 ms；多页 TIFF（扫描的文件）不会播放，而是一次显示一页，用 `,` 与 `.` 翻页（显示为“第 2/5 页”）；相机嵌入 JPEG 的预览（MPF）不会被当成第二帧显示，APNG 的默认图像（给不支持 APNG 的程序看的静态图）也不会被当成第一帧

### 浏览模式

- **网格**（默认）— 虚拟化磁砖网格，悬停预览（500 ms 延迟）
- **列表（详细）** — `Ctrl+L` 切换；列：预览 · 标签 · 评分 · 名称 · 分辨率 · 大小 · 类型 · 修改时间；`Delete` 删除选中的行，`Ctrl+Z` 撤销；评分（`1`–`5`）、收藏（`0`）、挑片（`P` / `Shift+X` / `U`）、色彩（`F1`–`F5`）键也作用于选中的行，与网格相同
- **深度缩放** — 双击磁砖；GPU 流畅平移 / 缩放 + 小地图
- **分割视图**（`Shift+S`）— 两张图并列
- **双页阅读**（`Shift+D`、`Ctrl+Shift+D` 为漫画从右至左）— 对页阅读器
- **多屏镜像**（`Ctrl+Shift+M`）— 副屏窗口
- **剧场模式**（`Shift+Tab`）— 隐藏所有外壳
- **对比对话框** — 并排 / 重叠（alpha 滑块）/ 差异（增益滑块）/ A|B 拖曳分隔
- **Timeline / Calendar / Map** 视图 — 按拍摄日期分组、日历浏览、Leaflet + OpenStreetMap 地理坐标

### 屏幕叠加层

- RGB 直方图（`H`）
- F8 OSD（文件名 / 大小 / 类型）、Ctrl+F8 调试 HUD（VRAM / 缓存 / 线程）
- 像素视图（`Shift+P`）— 缩放达 400 % 起显示每像素 RGB / HEX，画面上的像素不超过 40,000 个时再加上像素网格
- 色彩模式（`Shift+M`）— Normal / Grayscale / Invert / Sepia（GLSL）

### 导航

- 方向键、浏览器式历史（`Alt+←/→`）、随机跳转（`X`）
- 跨文件夹导航（`Ctrl+Shift+←/→`）
- 跳到第 N 张（`Ctrl+G`）
- 模糊搜索（`Ctrl+F` / `/`）
- **命令面板**（`Ctrl+Shift+P`）— 模糊搜索所有菜单动作
- 文件夹末端自动循环
- 触控板捏合缩放 + 水平滑动切换图片

### 整理

- **书签** — 最多 5000 个路径
- **评级** — 0-5 星（`1`-`5`）+ 收藏爱心（`0`）；在网格中作用于选中的缩略图，没有就作用于方向键所在的那张，再没有就是鼠标下的那张
- **颜色标签** — 旗标式 红 / 黄 / 绿 / 蓝 / 紫（`F1`-`F5`）
- **挑片**（Culling）— 三状态旗标（`P` = 保留、`Shift+X` = 拒绝、`U` = 取消）；按状态过滤；批量删除拒绝；**自动挑片** 会在每组近重复中挑出最清晰的一张保留、其余标为拒绝
- **层级标签** — 树状路径如 `animal/cat/british`；自动匹配子孙；选中缩略图后右键 **批量操作** > **索引关键字** 会把 Lightroom／darktable 的关键字层级（`Places|Taiwan|Taipei`）归到对应的父标签下
- **Tags & Albums** 含多标签 AND / OR 过滤；新建或重命名时，与另一个名称只差大小写或空格的名称会被拒绝；**清理…** 会移除已不存在文件的记录，并合并只差大小写的名称
- **智能相册** — 保存规则式查询并一键重新应用；过滤条件涵盖扩展名、分辨率与 **长宽比**、**文件大小**、评级 **下限 / 上限**、颜色、挑片、标签（含 **排除**）、**相机 / 镜头**、**文件名正则 / glob** 与 **文件年龄**，并可 **导出 / 导入** 为可移植的 JSON 文件
- **堆叠 RAW+JPEG 对** — 将同档名采集折叠成单一磁砖；RAW 仍可从同级访问
- **每图笔记** — 在 EXIF 侧栏，自动防抖保存，跨会话持久
- **暂存盘** — 跨文件夹篮子，重启后保留；批量移动 / 复制 / 导出
- **双面板文件管理器** — 双窗格的双树视图
- **Session / 工作区布局** — 将标签 / 选择 / 过滤 / 浮动坐标快照成 `.imervue-session.json`；可保存命名布局（Browse / Develop / Export 排列）
- **宏** — 录制 / 重放评级 / 收藏 / 颜色 / 标签动作批次（`Alt+M` 重放上一个宏）
- **缩图徽章 + 密度** — 颜色条 / 收藏 / 书签 / 评级星；Compact / Standard / Relaxed 内边距
- **拖出到外部 App** — 直接把磁砖拖进 Explorer / Chrome / Discord
- **最近文件夹 / 图片** 追踪；上次文件夹启动时自动还原

### 排序与过滤

- 按名称（与资源管理器相同的自然顺序：`img2` 在 `img10` 之前）/ 修改时间 / 创建时间 / 拍摄时间（相机的 EXIF 时间，没有时用修改时间）/ 大小 / 分辨率排序（升 / 降）
- 按扩展名、颜色标签、评级、标签 / 相册、挑片状态过滤
- **高级过滤** — 分辨率 / 文件大小 / 方向 / 修改日期范围
- **多标签过滤** 对话框含 AND / OR

### 搜索

- **模糊文件名搜索** 含子字符串高亮
- **找相似** — pHash（64-bit DCT）含可调 Hamming 距离
- **图库搜索** — SQLite 多根索引，可按文件名、最小宽 / 高与文件大小搜索（最多 2000 条结果；双击即可打开）；重新扫描只读取新增或修改的文件（勾选 **Compute perceptual hash** 时也读取还没有哈希值的文件），多个同时进行
- **查询搜索**（右键）— 以精简的查询语言筛选当前打开的文件夹：关键字、标签（含取反）、评级、颜色、扩展名、地点、挑片、收藏、长宽比、年龄、大小、尺寸、相机 / 镜头，以及文件名正则 / glob；`place:` 可填城市、国家或两者，含空格的值用双引号括起（`place:"Rio de Janeiro"`）
- **找相似（average hash）** — pHash 与 dHash 再加上可选的 average-hash（aHash），提供互补的近重复度量
- **语义搜索（CLIP）** — 自然语言查询（如"雪中的金毛犬"），使用 onnxruntime 上运行的 CLIP ViT-B/32 生成并缓存 embedding，不需要 PyTorch：首次使用时 Imervue 会提示安装 `onnxruntime`，并按固定版本下载约 150 MB 的模型（只下载一次）；有 NVIDIA GPU 时通过 CUDA 运行，否则使用 CPU，从不使用集成显卡
- **自动标签** — 根据颜色、边缘与形状给出启发式标签：document / screenshot / photo / graphic、landscape / portrait；语义搜索下载 CLIP 模型后，改用 CLIP 零样本标签（从 photo、document、screenshot、graphic、illustration、portrait、landscape、animal、food、text 中最多选三个）

### 元数据

- **EXIF 侧栏** 含可折叠组 + 内嵌 0-5 星评级行
- **EXIF 编辑器** 对话框 — 描述、作者、版权、相机与注释（支持 Unicode）无需额外套件即可写入 JPEG / WebP，像素与其他标签不变；**描述** 按钮用本地视觉模型（`localhost:11434` 上的 Ollama 加 `llava`）写一句话填入描述，图片不会离开你的电脑
- **关键字编辑器** — 标题 / 创作者 / 描述 / 关键字，含从标签共现得出的 **相关标签建议**，以及 **受控词汇展开**（输入叶节点关键字会自动套用其祖先＋同义词，词汇为可编辑的层级结构）
- **图像信息** 对话框（尺寸 / 大小 / 日期）
- **XMP 边车文件**（`.xmp` 同伴文件）— 评级 / 标题 / 描述 / 关键字 / 颜色标签与其他支持 XMP 的照片管理软件双向同步（通过 `defusedxml` 安全解析）。保存时会合并进既有的 sidecar：只改这些字段，RAW 显影软件存在里面的显影设置、裁剪与历史记录都会保留，无法解析的 sidecar 不会被覆写。除了 `photo.xmp`（Lightroom、Bridge），darktable 与 digiKam 写的 `photo.jpg.xmp` 在它是唯一的 sidecar 时也会读取并更新；颜色标签看得懂 Lightroom 的写法（`Red` … `Purple`）与 Bridge 的写法（`Select`、`Second`、`Approved`、`Review`、`To Do`），导出时按 Lightroom 的写法写入。被拒绝的照片（Lightroom、Bridge、darktable 的 `xmp:Rating` -1）会成为筛选的「拒绝」，「拒绝」导出时写成 -1。没有 sidecar 的文件会读取并导入文件本身内嵌的 XMP 与 EXIF 评级（JPEG、PNG、WebP、TIFF、CR3、RW2、RWL、ORF、RAF）：Lightroom 就是这样保存 JPEG 的评级与关键字，Windows 文件资源管理器的星级也是。
- **GPS 地理标记编辑器** — 读写 EXIF GPS 经纬度；JPEG / WebP 无需额外套件，像素、其他标签与缩略图都不变
- **从 GPX 轨迹添加地理标记** — 用选中图片的 EXIF 拍摄时间匹配手机或 GPS 记录器的 `.gpx` 记录，可设置相机的时区、时间差上限与轨迹点之间的插值，再把位置写入 JPEG / WebP 文件
- **修改拍摄时间** — 把选中图片的 EXIF 拍摄时间平移若干天 / 小时 / 分钟 / 秒，或直接指定第一张照片的实际拍摄时间；改写 JPEG / WebP 文件中的 DateTimeOriginal、DateTimeDigitized 与 DateTime
- **元数据模板** — 记住一组标题、描述与关键词，可用 `{filename}` / `{name}` / `{folder}` / `{date}` / `{year}` 替换符号，应用到选中的图片：只填写空白字段（关键词为添加），或覆盖原有内容；结果由 XMP 边车与导出元数据写出
- **令牌批量重命名** — 实时预览模板 `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **导出元数据 CSV / JSON** — 每张图一行含挑片 / 评级 / 标签 / 笔记

### 额外工具（Imervue 标签 — 批量处理）

从 **Tools** 菜单访问；分为功能组子菜单：

- **批次** — 格式转换 · EXIF 清除 · 图像清洗器（重新渲染移除所有隐藏数据）· 图像整理器（按日期 / 分辨率 / 类型 / 大小分到子文件夹）· 令牌批量重命名
- **修图与变形** — AI 图像放大（Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU）· 人脸检测（Haar cascade）· 修复、仿制、裁切 / 拉直与镜头校正
- **图库与元数据** — 图库搜索 · 智能相册 · 找相似图片 · 语义搜索 · 找重复图片 · 自动标签 · 层级标签 · 导出元数据 · XMP 边车 · GPS 标记 · 从 GPX 轨迹添加地理标记 · 修改拍摄时间 · 元数据模板

### 系统集成

- Windows 右键 **用 Imervue 打开**（通过注册表）
- 文件夹监控：约每秒检查一次打开的文件夹，在别处新增、删除或重命名的文件一两秒内就会出现；不会一直占用文件夹，所以在 Windows 上仍可重命名或移动它的上层文件夹。文件夹树在按 F5 / **Refresh**、Imervue 回到前台以及打开的文件夹有变更时更新
- Toast 通知系统（info / success / warning / error）
- 插件系统含在线下载器（见 [插件系统](#插件系统)）

---

## Modify — 非破坏显影

Modify 通过较低分辨率的后台预览保持调整时的操作响应，停止调整后再生成完整质量。快速调整或切换照片会丢弃旧结果；标注坐标保持完整图片尺寸。保存或应用破坏性效果时，会先完成完整质量的运算。

**Modify** 标签是显影工作站。每次调整都存储在每张图片的 **recipe** 中 — 原始文件直到你明确 **导出** 或 **另存为** 才会被覆写。例外是 **Apply Crop** 与标注的 **Save**：它们会把结果写回原文件，并保留其 EXIF（相机、拍摄时间、GPS）、XMP 与 DPI。相机 RAW、HEIC 以及动画 / 多页文件永远不会被覆写——裁剪会提示改用导出，标注保存则会询问新文件名。单次处理的工具（CLAHE、HSL 混色器、相框、自动拉直……）会把结果存成原图旁的 `photo_clahe.png`；再执行一次会存成 `photo_clahe_1.png`，不会覆盖上一次的结果。**按 EXIF 自动旋转**、**EXIF 批量清除** 的副本与 **拆分页面…** 也用同样的方式编号。Imervue 无损旋转照片（裁剪框会跟着转）或改写其 EXIF（GPS 地理标记、EXIF 编辑器）时，照片的配方与虚拟副本都会跟着走；带局部蒙版、图层、镜头光晕或人脸标签的配方则留在旋转前的版本上，转回来即可取回。

### 显影滑块

- 白平衡 — 色温 / 色调
- 色调区段 — 高光 / 阴影 / 白色 / 黑色
- 曝光 / 对比 / 饱和度 / 鲜艳度
- 裁切、旋转、水平 / 垂直翻转
- 所有调整通过 recipe 存储，全程非破坏

### 曲线与 LUT

- **色调曲线编辑器** — 可拖曳 RGB 曲线 + 单独 R / G / B 通道，含 monotone cubic 插值
- **应用 .cube LUT** — 加载任何 Adobe LUT（3D 最高 65³，1D 最多 65,536 点，含 DaVinci Resolve 的 `LUT_3D_INPUT_RANGE`），trilinear 插值，混合强度滑块
- **分离色调** — 阴影 / 高光色相 + 饱和度，含平衡枢纽

### 创意效果

- **曝色反转（Solarize）** — 暗房式色调反转（阈值 + 混合）
- **柔光晕染（Diffuse Glow / Orton）** — 柔焦高光晕染（强度 / 半径 / 高光阈值）
- **渐变映射（Gradient Map）** — 亮度 → 调色板，可选 **感知（OkLCH）** 插值模式，让饱和渐变的中点维持鲜艳而不变灰
- **有序抖动（Ordered Dither）** — Bayer 矩阵量化至 N 阶（保留极值）
- **渐变中灰密度（Graduated Density）** — 按角度 / 硬度 / 偏移的线性 ND 渐变，可选染色，用于天空与前景
- **色调均衡器（Tone Equalizer）** — 在平滑蒙版上对每个亮度区段（阴影至高光）独立调整曝光
- **细节均衡器（Detail Equalizer）** — 按频段重新加权对比（细微纹理对粗大对比），超越单一清晰度滑块
- **电影感色调映射（Filmic Tone Map）** — 纯 Reinhard / Hable 高光滚降，含枢纽对比与饱和度还原，用于高对比单张曝光
- **Velvia（Velvia）** — 以亮度加权的饱和度提升，强化沉闷色彩同时保护阴影
- **彩色负片（Film Negative）** — 反转扫描的彩色负片，除去橙色片基，含输出 gamma
- **去紫边（Defringe）** — 在高对比边缘对紫 / 绿色差色边去饱和
- **浮雕（Emboss）** — 由亮度高度场生成的方向光浮雕
- **极坐标（Polar Coordinates）** — 把画面卷成圆盘或展开（小行星 / 极坐标反转）
- **万花筒（Kaleidoscope）** — 将单一角度楔形镜射成 n 重对称
- **磨砂玻璃（Frosted Glass）** — 确定性种子的局部像素散布
- **边框与说明文字（Frame & Caption）** — 任意颜色的衬边、可选的拍立得风格下缘，以及单独设置颜色的说明文字
- **显影预设** — 保存 recipe 后可整份 **套用**，或只 **合并** 其有设定的调整到其他图片（保留各图自身的裁切等）

### 局部调整

- **笔刷 / 径向 / 线性渐变蒙版**，含每蒙版的曝光 / 亮度 / 对比 / 饱和度 / 白平衡偏移 + 羽化滑块
- 蒙版通过显影管线非破坏混合

### 修图与变形

- **修复笔刷** — 圆形点，OpenCV inpainting（Telea 或 Navier-Stokes）
- **仿制图章** — Shift+点击源、羽化贴至目标
- **裁切 / 拉直** — 标准化裁切矩形 + 最多 ±15° 的拉直，自动裁到最大内接矩形
- **自动拉直** — Hough-line 水平线 / 垂直线检测
- **镜头校正** — 纯 numpy 径向畸变（桶形 / 枕形）、暗角提升、各通道色差校正
- **降噪 / 锐化** — 边缘保留双边降噪 + unsharp mask 锐化
- **天空 / 背景** — 检测天空换成渐变或去除背景（透明或白色填色）；可选 `rembg` / U²-Net 升级

### 多图

- **HDR 合成** — 通过 OpenCV Mertens fusion 合并包围曝光（含 AlignMTB 预先对齐）
- **全景拼接** — OpenCV `Stitcher`（panorama 或 scans 模式），黑边自动裁切
- **焦点堆叠** — Laplacian 焦点图 + Gaussian 混合 + 可选 ECC 对齐

### 输出

- **导出预设** — 在批量导出中：Web 1600 px / 4K Web 3840 px / Print 300 DPI PNG / Instagram 1080 × 1080 正方形 / Thumbnail 400 px，或自定义
- **水印** — 在批量导出中：在四角之一或居中加上文字水印，可设置不透明度；只应用于导出的副本
- **GPU 批量显影** — 安装 **GPU 显影** 插件（**Plugins > Download Plugins**）后，批量导出可以在独立显卡上渲染显影 recipe，在 **运算设备** 中选择；**Plugins > GPU 显影…** 首次使用时会安装 `wgpu`，并显示找到的显卡。白平衡、曝光、高光 / 阴影、白色 / 黑色、亮度、对比度、鲜艳度、饱和度与色调曲线在 GPU 上运行（一张 2400 万像素的照片约 0.1 秒，而不是约 7 秒）；recipe 的其余部分仍在 CPU 上处理。从不使用集成显卡；GPU 处理失败的图片改由 CPU 渲染；输出与 CPU 渲染器相比，只有一小部分像素会有几个色阶以内的差异
- **另存为 / 导出** — PNG / JPEG / WebP / BMP / TIFF（Pillow 支持 AVIF 时还有 AVIF，装了 `pillow-heif` 还有 HEIC，装了 `pillow-jxl-plugin` 还有 JPEG XL），有损格式提供质量滑块；保留相机、镜头与拍摄时间的 EXIF，位置可选（**元数据**：全部／位置以外／无）；建议的文件名一定是还没被占用的（`photo.png` 旁边就是 `photo_1.png`），已存在的文件（尤其是原图本身）要确认后才会被替换
- **批量操作** — 重命名、移动 / 复制、旋转选中图片。移动或复制不会覆盖同名文件（会以 `name_1` 存入）；在 Imervue 里重命名或移动的照片（批量重命名、Token 批量重命名、文件夹树、移动 / 复制、双窗格、暂存区、图片整理）会保留评级、收藏、标签、颜色标签、标题、备注与筛选标记，`.xmp` 与标注 sidecar 也会一起带走；文件夹在 Imervue 中打开时，用其他程序重命名的照片也一样；改成另一张选中照片现在的名称（重新编号、互换两个名称）时，会按正确顺序把整批重命名，而不是只改一部分
- **联系表 PDF** — 多页网格含说明（A4 / A3 / Letter / Legal）；**版式** 下拉框可填入预设：默认 4 × 5、紧凑 6 × 8、校样 5 × 6、编辑版式 2 × 3、索引 8 × 10（列 × 行，连同各自的边距与说明设置），手动修改网格就会变成自定义
- **网页画廊 HTML** — 自包含文件夹含 `index.html` + JPEG 缩图 + 内嵌灯箱；**客户审阅** 会在每张图片下方加一个留言框，留言保存在审阅者的浏览器里，可一次下载为一个 JSON 文件
- **幻灯片 MP4** — H.264 视频，FPS / 每张保留秒数 / 淡入淡出 / 溶接 / 滑入 / 抹除转场可设（`imageio-ffmpeg`）
- **打印布局** — 多页 PDF（A4/A3/Letter/Legal）含网格 / 边距 / 装订槽 / 裁切标记
- **软打样** — 加载 ICC profile、模拟目标色域、用洋红色标示超出色域的像素
- **虚拟副本** — 每图命名的 recipe 快照；可切换不同风格而不丢失原图

### 外部编辑器

从 **File > External Editors…** 注册程序（图像编辑器等），再从 **File > Open in External Editor** 启动。用编辑器保存后，检视器会自动显示新版本。

---

## Paint — 全功能栅格编辑器

**Paint** 标签是完整功能的栅格绘图工作室，以独立 `QMainWindow` 嵌入，含菜单、左工具栏、上下文敏感的选项栏、右侧分页式停靠列。多文档编辑 — 同时打开多张图，每张有独立撤销栈。

### 工具（27）

笔刷 · 橡皮擦 · 填色 · 滴管 · 矩形 / 套索 / 魔棒 / 快速选择 · 移动 · 文字 · 渐变 · 模糊 · 涂抹 · 减淡 · 加深 · 海绵 · 钢笔 · 仿制图章 · 对话框 · 矩形 · 椭圆 · 直线 · 多边形 · 裁切 · 变形 · 抓手 · 缩放

**钢笔** 用直线连接你点击的各点，在你拖出控制柄的地方则连成曲线；在它的选项栏勾选 **平滑** 后，会改为穿过每个点画出一条平滑曲线。

暗房调色三件组 — **减淡**（提亮）、**加深**（压暗）与 **海绵**（降低饱和度）— 按笔刷加权绘制局部调整；减淡与加深作用于中间调。三者都没有选项。

**油漆桶** 面板的 **在新图层平涂底色** 会在线稿下方的新图层上，给线稿的每个封闭区域各填一种平涂色（色板面板显示有颜色时就用色板的颜色）— 也就是上阴影前的平涂步骤 — 线条与图稿周围的空间则保持空白。

**渐变** 工具可以绘制前景色 → 背景色，或你自己的渐变：在选项栏的 **颜色** 中选择，旁边的 **编辑…** 会打开渐变编辑器；每个渐变都有名称与色标（每个色标有位置和带不透明度的颜色），色标可以添加、移动、改色和移除。你的渐变会跨会话保留。

单键快捷：`B / E / G / I / M / L / W / V / T / U / R / P / S / C / Z / H`；`Shift+R/E/I/P` 切形状变体。

### 笔刷

六种笔刷类型 — 铅笔 / 钢笔 / 马克笔 / 喷枪 / 水彩 / 水墨 — 以及基于它们的预设（Crayon、Highlight、Sumi calligraphy …）。笔刷停靠设置大小 / 不透明度 / 硬度 / 密度 / 混合模式；选项栏提供大小 / 不透明度 / 硬度。数位板笔压会依 **Settings > Pressure Curve…** 中设置的曲线缩放大小与不透明度；鼠标始终以最大笔压绘制。笔刷停靠中的 **散布** 让每个笔触点偏离笔画，偏移量最多为笔刷大小乘以所设比例；**颜色抖动** 改变每个笔触点的色相、饱和度与亮度；**跟随笔倾斜** 会在与数位笔倾斜方向垂直的方向上收窄笔尖，并让笔尖随倾斜方向转动（Sumi calligraphy 预设已开启此项）；像素画笔刷仍保持方形笔尖。选择捕获笔尖、**File > Import brush preset…**。

### 图层

完整图层面板含缩图、可见性、↑ / ↓ 重排按钮（或 `Ctrl+[` / `Ctrl+]`）、混合模式、不透明度、搜索、矢量图层、1-bit 图层、**图层蒙版**（新建 / 从选择 / 反转 / 应用）、**剪切蒙版**、**图层效果**（投影 / 外发光 / 描边）。按颜色分割图层、渐变映射预设。

### 选择

矩形 / 套索 / 魔棒 / 快选 含 **替换 / 加 / 减 / 交集** 模式；在选项栏勾选 **磁性** 后，松开鼠标时套索的轮廓会吸附到 10 px 范围内图层最强的边缘。**快速蒙版模式**（`Q`）。**描边选择** 对话框。

### 动画与漫画

- **动画** — 帧时间轴停靠：**+ Frame** 为拼合后的画面拍快照，按所选 FPS 播放，洋葱皮显示上一帧；**Export…** 将各帧保存为 GIF、WebP（无损）或 PNG 动画，每帧持续所选 FPS 的一个节拍
- **漫画工具** — 分镜切割（之后笔刷的 **限制在分格内** 会让每一笔都留在它起笔的分格里）· 网点层 · 盖页码 · 速度线（径向 / 平行 / 爆发）· 动作闪光 · 沿选区排文字（把你输入的文字沿选区轮廓排列，放在新图层上）· 对话框工具

### 滤镜与查看辅助

- **滤镜** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone · Match Colour（你选取的参考图像的色彩氛围）· Match Swatches（每个像素换成色板中最接近的颜色）（只有一个滑块的滤镜 — Posterize、Threshold、Halftone、Match Colour — 拖动滑块时会在图层按原尺寸裁出的一块区域上实时预览；其他滤镜打开 OK / Cancel 参数对话框）
- **查看辅助** — 像素格 · 对齐像素 · 对齐边缘 · 洋葱皮 · 出血指引 · 画布旋转（`Ctrl+Shift+H` CCW 旋转）

### 停靠（14 个，分 3 组以分页排列）

| 分组 | 面板 |
|---|---|
| 绘图 | 色彩 · 笔刷 · 油漆桶 · 色板 |
| 画布 | 图层 · 导航 · 历史 · 页面 · 动画 · 直方图 |
| 素材库 | 素材 · 印章 · 姿势 · 参考 |

色彩面板开头是色相环与饱和度 / 亮度三角形：在色环上拖动可选取色相，在三角形内拖动可选取深浅，下方的滑杆与 HEX 输入框会随之更新。素材面板会把你自己的素材列在内置网点与纹理之前：Imervue 程序文件夹下 `materials` 文件夹中的图片（放在名为 `texture`、`tone`、`pattern`、`brush_tip` 或 `pose` 的第一层子文件夹中的图片会归入对应分类），以及你捕获的笔刷笔尖。**Edit > Save Selection as Material…** 会把画面中选取的部分保存到那里，绝不会覆盖之前保存的同名素材。色板面板会显示最近使用的颜色，或一组调色板（内置的 Standard、Pastel、Manga，或你自己的调色板）：**Save as Palette…** 会把最近使用的颜色以一个名称保存下来，**Delete Palette** 则删除一组你自己的调色板；**Filter > Match Swatches…** 使用的就是色板面板显示的颜色。每个面板都可移动 / 浮动，并可在 **Window** 菜单单独开关。**Settings > Workspace Layouts…** 提供内置的 Default / Drawing / Comic / Compact 布局；**Save current…** 以一个名称保存 图层 / 色彩 / 笔刷 / 导航 / 历史 / 参考 这几个面板中哪些处于显示状态，套用布局时会显示或隐藏这些面板。工具选项与面板尺寸不会保存。

### 文件 I/O

- **New Canvas…** 按你选择的尺寸打开一个标签：纸张、漫画或屏幕预设（A4、B5 漫画页、1080p、4K …）、用 **Save as Preset…** 保存的预设，或任意宽度与高度，背景可选白色或透明；**New Tab**（`Ctrl+N`）则保持默认的 1024 × 1024 白色画布
- **Open PSD…** 把文件拼合成一个图层，在新标签中打开；**Save as PSD…** 写出各图层及其混合模式（不含蒙版与图层效果）
- **Export image…** 依所选的文件类型写出 PNG、JPEG、WebP、TIFF 或 BMP（JPEG 与 BMP 不支持透明，会以白底输出）；漫画项目可将页面导出为 **CBZ** 或 **PDF**。**Save Comic Project…** 把整部漫画（每一页及其图层）保存为单个 `.imervue-proj` 文件，**Open Comic Project…** 可将其重新打开。只有 **Save as PSD…** 算作保存该标签：导出之后，关闭时仍会询问它未保存的更改
- **自动保存** — 每 2 分钟为每份已修改文档保存快照，各自保留最近八份。**File > Restore Autosave** 将各文档最新的可读版本打开为新的已修改标签，保留当前编辑；最新快照损坏时会尝试较旧版本。原生快照保留漫画分格裁切信息。状态栏显示当前文档最后自动保存时间，写入失败会提示，关闭标签只删除其自己的快照。 定时保存使用最后完成的编辑版本，在后台任务中重建快照、压缩并写入。每个工作区只有一个写入任务，每份文档只保留最新待存版本；关闭或替换文档会取消尚未送达的输出。历史容量无法保留不可变状态时，会先在 UI 线程复制一致的完整文档，再在后台写入。

### 强化用户体验

- **Tab** 切换所有停靠（无干扰绘图）
- `Ctrl+Tab` 循环 Paint 标签
- `,` / `.` 切换笔刷种类
- `0`-`9` 笔刷不透明度 10 % 步进
- `Alt+[` / `Alt+]` 下 / 上切换作用图层
- 画布右键打开快速 Undo / Redo / 全选 / 取消选 / Fit / 100 %
- 每标签修改星号、撤销 / 重做 toast、启动时还原自动保存对话框

Undo／Redo 可恢复图层的新增、删除、排序与合并，以及图层属性、蒙版、矢量、组、选区和参考图层状态。图层菜单、图层面板、漫画图层和素材插入操作都会建立撤销步骤，每份文档保有独立历史记录。

每份 Paint 文档的历史最多保留 50 个步骤，容量上限为 512 MiB，包括当前基准和 Undo／Redo 分支。未修改的像素共享存储，画笔和橡皮擦只保存变化的区块；达到上限时移除较旧的步骤。如果单份文档快照超过上限，会清除历史，但保留可编辑的文档。

切换到 Paint 会保留文件、图层、未保存的修改与撤销历史；第一次打开时显示空白画布。使用 **File > Open Current Image in Paint** 将查看器图片打开为新文件。Paint 主标签栏的左右键也会将上一张／下一张查看器图片打开为新文件。深度缩放中的 `E` 会打开独立的注释编辑器。

---

## Puppet — 2D 绑骨偶动画

> **完整教程**：[`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md) 涵盖直播（OBS / NDI / 虚拟摄像头）与动画制作（录制 / 时间轴编辑 / MP4 导出）的端到端流程。英文版于 [`puppet_guide.md`](../puppet_guide.md)、繁体中文于 [`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md)。

**Puppet** 标签是从零打造的 2D 绑骨偶动画系统：网格变形绑骨、参数、动作、物理、表情、姿势、对嘴与摄像头脸部追踪，**不依赖任何专有 SDK**、**不使用 `live2d-py`**，采用完全开放的 `.puppet` 文件格式，规格完整记录于 `Imervue/puppet/FORMAT.md`。

### 文件格式

`.puppet` 是 zip 容器：

- `puppet.json` — manifest（drawables、deformers、parameters、motions、pose groups、parts、hit areas）
- `textures/*.png` — atlas 纹理
- `motions/*.json` — keyframe tracks
- `expressions/*.json` — 参数叠加
- `physics.json` — Verlet 物理配置

JSON 为主，人类可 diff，没有专有二进制。格式是开放且可校验的：保存的文件以一个未压缩的 `mimetype` 条目（`application/vnd.imervue.puppet+zip`）开头，每个 JSON 文件都在 `$schema` 中注明自己的 schema；四份 JSON Schema 发布在 [`docs/schemas/`](../docs/schemas/)；`py -m Imervue.cli puppet-validate examples/puppet/imeru.puppet`（MCP `puppet_validate`）可检查文件，`puppet-schema`（MCP `puppet_schema`）则输出某一份 schema；[`docs/examples/read_puppet.py`](../docs/examples/read_puppet.py) 仅用 Python 标准库即可读取 `.puppet`。规格（[`Imervue/puppet/FORMAT.md`](../Imervue/puppet/FORMAT.md)）与 schema 均采用 MIT 许可，任何程序都可以读写 `.puppet` 文件。

### 渲染器

`QOpenGLWidget` 含 vertex-array textured-triangle 绘制（按 draw_order）、每 drawable 混合模式（normal / additive / multiply）、pose-group 互斥、图像空间正交投影、GL_REPEAT 平铺的透明度棋盘背景、滚轮缩放 + 中键拖曳平移。针对大型 rig 优化 — 一个含 307 个 drawable、2965 个 vertex morph 的转换后 Cubism rig 在 CPU 上达 60 FPS。

### 编辑

- **导入 PNG** → 自动生成考虑 alpha 的三角网格
- **添加旋转变形器**（anchor + angle）/ **添加 warp 变形器**（rows × cols 双线性 lattice），位于 **Edit** 菜单
- **添加参数** → 在滑块端点按 **Set Key** 在参数停靠记录关键形状
- **网格编辑器** — 切换 Edit Mesh 拖曳顶点；点击 8 px 内吸附到最近顶点
- **动作时间轴** — **Edit > Edit motion…** 可拖动关键帧与贝塞尔控制手柄；**缓动** 把一条轨道改成 31 种具名缓动曲线之一（elastic 和 bounce 会转成采样出来的关键帧），**精简关键帧** 则删除录制 take 中与前后关键帧连线相差在容差以内的关键帧
- **修复人偶** — **Tools > 修复人偶** 清理每个图元的网格：删除损坏和面积为零的三角形，合并位置与 UV 都相同的重复顶点，移除未被任何三角形使用的顶点（骨骼权重与 vertex morph 会跟随保留下来的顶点），并让每个顶点的骨骼权重总和为 1
- **另存为…** 把整个 rig 写成 `.puppet` zip

### 运行

- **参数绑定** — 每个参数保有 key 列表，将滑块值对应到部分 deformer-form 快照；运行时采样并逐字段线性插值
- **动作播放** — 底部停靠含动作列表 + 播放 / 暂停 / 停止 / 循环 / 拖曳；曲线采样器支持 `linear`、`stepped`、`inverse-stepped`、`cubic-bezier` 段（牛顿迭代 time → param）；每动作淡入 / 淡出
- **表情** — `additive` / `multiply` / `overwrite` 参数叠加堆栈
- **姿势组** — 互斥 drawable 可见性（武器切换、嘴形变体）；**Pose** 停靠栏选择每组显示的成员
- **物理** — Verlet 钟摆链用于头发 / 衣物 / 缎带；输入参数移动链锚点，重力 + 阻尼 + 每粒子弹簧回复静止
- **顶点 morph** — Cubism 式线性混合于 rest 与 ±extreme deltas；每帧向量化 numpy，60 FPS
- **不透明度 keys** — 参数驱动的 alpha 曲线；让替代姿势 mesh 随手势参数淡入 / 淡出

### 实时输入

- Drag-track head — 光标在画布上移动时，头部与眼睛会转向光标
- 自动眨眼，cosine open → close → open 曲线
- 麦克风对嘴 via `sounddevice` RMS → `ParamMouthOpenY`（可选依赖）
- 从音频文件对嘴 — **Live > 从音频文件对嘴…** 把 WAV 转成一个动作，让 `ParamMouthOpenY` 随它的音量张开（每秒 30 次，不产生变化的 key 会被丢弃），并把这个 WAV 作为动作的声音播放；不需要额外依赖
- 摄像头脸部追踪 via OpenCV + MediaPipe Tasks FaceLandmarker → 头部 yaw / pitch / roll + 眼 / 嘴开合（可选依赖）
- 自定义动作录制 — 滑动滑块 / 对摄像头 / 物理运行时以 30 Hz 抓取参数值；停止时烘焙成线性段 Motion

### Cubism 互通

可插入 **Cubism Native SDK**（用户自备 DLL — Live2D 的 Free Material License 禁止重新散布）将任何 `.moc3` 模型转成 `.puppet` zip。转换器执行 sample-and-reconstruct 扫描，同时抓取 vertex-morph delta 与参数驱动的可见度切换，所以手势切换（比耶 / 捂脸 / 拍照 …）能完整保留。

### 输出

- **截取画面…** 只存角色本身的 PNG，保持 rig 本身的尺寸（长边最多 4096 px），背景透明
- **录制…** 切换 30 FPS 帧循环，通过 `imageio` 写成 GIF / WebM / MP4，角色缩放到 1080 px 内、白色背景（这些帧不含 alpha）
- **虚拟摄像头** — 把 puppet canvas 暴露成系统的 webcam
- **NDI 输出** — 在局域网广播 puppet 作为 NDI 源
- **VTube Studio API 服务器** — 可选 WebSocket API，给 VTS 兼容客户端读参数

### OBS 直播整合

两条路：A 是"开箱即用"，B 是低延迟、高画质、需要局域网。

#### A. 虚拟摄像头（最简单）

把 puppet canvas 变成假的 webcam，OBS 用标准"视频捕获设备"源即可拿到。

1. `pip install pyvirtualcam`
2. 各平台对应驱动：
   - **Windows**：装 OBS Studio 26+，自带 *OBS Virtual Camera* 驱动。第一次打开 OBS、右下角点 **Start Virtual Camera** 注册驱动，之后 `pyvirtualcam` 才找得到它。
   - **macOS**：OBS for Mac 自带 system extension，首次运行会要求在"系统设置 → 隐私与安全性"启用。
   - **Linux**：`sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"`（要先 `apt install v4l2loopback-dkms` 之类）。
3. Puppet 标签打开 rig，工具栏 / **Output > Virtual camera** 打勾。状态栏会打印出实际设备名。
4. OBS：**Sources > + > Video Capture Device**，下拉选步骤 3 打印的设备名（通常是 *OBS Virtual Camera*）。

Imervue 会把输出帧的长边强制压到 1080 px，所以 Cubism 原生画布（高度常在 3000–8000 px）不会被 DirectShow 虚拟摄像头驱动拒绝。长宽比保留，OBS 端可以再缩。

每一帧都会用 off-screen framebuffer 重画 — 只渲染角色本身、不含棋盘格背景与编辑器外壳。所以 OBS 看到的就是"角色 + 一张纯洋红色背景"。

##### 为什么是洋红色背景？（以及怎么去掉）

虚拟摄像头走的是 **DirectShow**（Windows）/ **AVFoundation**（macOS）/ **v4l2loopback**（Linux），这三种传输格式**只有 RGB、没有 alpha 通道**。OBS 的"视频捕获设备"源把进来的图像当成不透明 RGB，所以 Imervue 在角色以外填什么颜色，OBS 就显示什么颜色。

选 **洋红色 `#FF00FF`** 是业界标准的 chroma-key 色：它几乎不会出现在自然肤色、发色、瞳色里，去背容差可以开很宽而不误伤角色。

OBS 端去背步骤：

1. 加进来的"视频捕获设备"源右键 → **滤镜（Filters）**
2. 左下角 **效果滤镜（Effect Filters）** 区块 → **+** → **色键（Color Key）**
3. 设置：
   - **Key Color Type**：`Custom Color`
   - **Custom Color**：HEX 输入 `FF00FF`（或 R = 255 / G = 0 / B = 255）
   - **Similarity**：从 `80` 开始，边缘若有残留洋红色拉到 `200–300`。数值越大去得越干净
   - **Smoothness**：`30–50`，让边缘不要太硬、不会像 pixel art
4. 关闭对话框。OBS 把这条滤镜跟源绑在一起，之后启用虚拟摄像头都自动套用

若你的角色配色里刚好有洋红色（罕见、costume / 道具上可能），色键会把那些像素也吃掉。改走下面的 NDI — 带 alpha 通道，不用色键。

**疑难排解：OBS 还是看得到洋红色**

- 确认 Color Key 滤镜是加在**视频捕获设备源本身**，不是加在 Scene 上。加在源上的滤镜跟着走；加在 Scene 的会晚一步、在源绘制完之后才作用。
- HEX 确认是 `FF00FF` 一字不差 — `FF00FE` 之类捕不到全部洋红色像素。
- 角色轮廓边缘若有一圈薄薄的洋红色 halo，把 *Similarity* 拉到 `300`。那一圈是 GL_LINEAR 在角色边缘跟洋红色背景内插出来的，容差放宽就能盖掉。

#### B. NDI（低延迟、专业）

NDI（Newtek 的 Network Device Interface）以 < 50 ms 的延迟在 LAN 上传递 puppet 画面、保留 alpha 通道。

1. 从 <https://ndi.video/tools/> 下载安装 **NDI Tools**（包含 NDI runtime）。
2. `pip install ndi-python`
3. OBS 端安装 **obs-ndi** 插件：<https://github.com/obs-ndi/obs-ndi/releases>
4. Puppet 标签工具栏 / **Output > NDI output** 打勾。状态栏会打印 NDI 源名（默认 *Imervue Puppet*）。
5. OBS：**Sources > + > NDI Source**，下拉选步骤 4 的源名。

NDI 也吃 1080 上限的缩放，但传输 RGBA — off-screen render 把角色外的区域填成完全透明，alpha 通道原样传出去，OBS / vMix 端直接把角色叠到自己的场景上，完全不用做色键。

#### C. 窗口捕获（保底）

OBS **Sources > + > Window Capture** 可以直接抓 Imervue 窗口，零依赖。画质较差、要自己 crop 掉外壳，但在不能装驱动的锁定机器上能跑。

### 示例

内置 rig 是 [`examples/puppet/imeru.puppet`](../examples/puppet/imeru.puppet) — **Imeru**，Imervue 的原创吉祥物：1024 × 1336 画布上的 45 个 drawable，具备所有 Cubism 标准参数外加双关节手臂、Live2D 式视差转头、随她转头背向光源而改变形状的脸部阴影、虹膜被裁切在眼白内的眨眼、头发物理、8 个动作（两个 Idle 循环、TapHead、TapBody 以及包含挥手在内的四个 Gesture）和 7 个表情。从 **File > Examples > Imeru** 或 **打开 puppet…** 打开，点她的头或身体即可看到她的反应。她完全由代码制作，做法与 3D 二次元游戏打造角色相同：头发、身体、服装和手臂在 Blender 中建模，并运用这类游戏的着色技巧（借助平滑代理形体的法线为头发打光、手绘发丝与高光笔触、烘焙遮蔽）以卡通渲染（cel shading）着色，再逐个 puppet 图层渲染出来；脸部以 SDF 脸部阴影图着色；眼睛、眉毛和嘴巴是画上去的，最后为各图层绑定，所以文件不涉及任何第三方权利；`py -3 examples/puppet/imeru/build.py` 可重新生成它（需要 Blender 4.2 或更新版本）。

---

## Desktop Pet — 无边框桌面宠物

第五个标签 — **Desktop Pet** 把任意 `.puppet` 角色以无边框、透明背景的 overlay 形式放上你的桌面。标签本身是控制面板；真正的角色会浮在（或藏在）其他窗口之上。在 Puppet 标签里能对 rig 做的事 — 动作、表情、物理、idle 驱动、摄像头 / 麦克风输入 — 在这里同样适用。

### 你可以做的事

| 功能 | 说明 |
|---|---|
| 无边框 overlay | 无窗口外壳、无 taskbar entry — 只有角色出现在桌面上。 |
| 透明背景 | 角色没盖到的地方都会让桌面透出来。 |
| 拖拽移动 | 左键拖角色到新位置。释放时若靠近屏幕边缘，会自动 **吸附** 贴齐边缘。 |
| 点击穿透模式 | 让宠物忽略鼠标输入，可以继续在它下面工作。 |
| 锁定位置 | 冻结宠物，避免误拖移动。 |
| 永远置底 | 让宠物位于所有其他窗口之后 — 像桌面挂件那样，而不是永远置顶。 |
| 全屏时自动隐藏 | 当其他应用（游戏 / 视频 / 简报）在同一屏幕全屏时自动隐藏宠物；全屏结束后再回来。 |
| 隐藏时暂停 | 宠物不可见时停止重绘；实时驱动的计时器仍会继续运行。 |
| 尺寸预设 | small / medium / large 三档。以中心对齐缩放，调尺寸时角色不会跨屏幕跳。 |
| 不透明度滑杆 | 把宠物淡化到 10% – 100%，可以当作低调的桌面摆件。 |
| 记住你放的位置 | 拖到喜欢的角落后，下次启动时宠物会回到那里。 |
| 全局热键 | 在任何应用中都能显示 / 隐藏宠物、锁定位置、切换点击穿透或让它立即说话（需要 `pynput`）：默认为 Ctrl+Shift+P / L / T / Space，每一个都可以在标签的 **Global hotkeys**（全局热键）分组中重新绑定。已被其他动作占用的按键会被拒绝；两个动作共用的已保存按键会在状态栏中列出。 |

### 点击交互

- **左键点角色身体** — 若 rig 有定义命中区域（例如点头），就播放对应的动作；否则宠物会用对话气泡跟你打招呼。
- **右键任意处** — 打开 context menu：Hide pet、Live drivers、Play motion（rig 内所有动作清单）、Apply expression、Pose（选择每个姿势组显示的成员）、Lock position、Click-through、Always on bottom、Hide on fullscreen、Speech bubble、Size。
- **系统托盘图标** — 左键切换显示 / 隐藏；右键打开 Show/Hide、Click-through、Open puppet、Hide pet。

### 实时驱动

可以从标签或右键菜单挑任意组合。Auto idle、Idle motions 与 Auto-blink 默认开启；其余默认关闭 — 只开你要的就好。

- **Auto idle** — 加上呼吸 + 轻微 drift，让角色看起来活着。
- **Idle motions** — 在 rig 的 idle-group 动作之间随机循环。
- **Auto-blink** — 每隔几秒自然眨眼的循环曲线。
- **Drag-track head** — 光标在宠物上方时，头部与眼睛会转向光标。
- **Mouse gaze** — 眼睛与头部在整个屏幕上跟随光标。
- **Mic lip-sync** — 嘴会跟着你的声音一起开合（需要 `sounddevice`）。
- **Webcam tracking** — 你的头 / 眼 / 嘴会驱动宠物的对应部位（需要 `opencv-python` 和 `mediapipe`）。

### 如何开始

1. 切换到 **Desktop Pet** 标签。
2. 点 **Load bundled Imeru** 用内建的角色，或点 **Open Puppet…** 选自己的 `.puppet` 文件。
3. 勾选 **Show pet on desktop**。
4. 把角色拖到你想要的位置；挑选要启用的驱动；调整不透明度 / 尺寸。
5. 随时右键打开快速操作菜单，或用系统托盘图标在找不到标签时隐藏宠物。

所有设置 — 位置、驱动、不透明度、点击穿透、尺寸 — 都会跨启动保留。

**Desktop Pet Integrations** 插件（**Plugins > Download Plugins**）会新增 **Plugins > Desktop Pet Integrations** 菜单：宠物会响应 OBS（开始直播、录制、切换场景）、Twitch 聊天关键字（出现在消息任意位置即可，或用 `=hi` 匹配整条消息、`!dance*` 匹配开头、`/go+al/` 使用正则表达式）、本地 webhook（`POST http://127.0.0.1:9876/trigger`，内容为 `{"group": "Wave", "speech": "Hi!"}`）以及 Windows 通知。它同时也是基于 `on_pet_created` 编写宠物插件的示例。

### 自定义语音（pet script）

宠物的对话气泡取材自一个你可以自行编写的 JSON 文件。在 Desktop Pet 标签的 **Pet script** 分组中点击 **Load script…**，选择一个 `.petscript.json`。schema 如下：

```json
{
  "version": 1,
  "name": "Friendly pet",
  "greetings": ["Hi!", "Hello!"],
  "time_of_day_greetings": {
    "morning": ["Good morning!"],
    "night": ["Still up?"]
  },
  "hit_responses": {
    "HitAreaHead": ["Don't poke me!", "Stop!"]
  },
  "motion_lines": {
    "wave": ["Hi there!"]
  },
  "scheduled": [
    {"every_seconds": 1800, "messages": ["Stretch break!"]}
  ]
}
```

- **`greetings`** — 当点击没有匹配到更具体的项目时使用。
- **`time_of_day_greetings`** — 按本地时钟时段分组的问候语（`morning` 05–11 时、`afternoon` 12–17 时、`evening` 18–21 时、`night` 22–04 时），优先于 `greetings` 使用；没有台词的时段会退回 `greetings`。
- **`hit_responses`** — 每个 `HitArea` 的台词。键必须与 rig 中定义的命中区域 ID 相符。
- **`motion_lines`** — 每个动作的台词。当点击命中区域而播放同名动作时说出（从 context menu 启动的动作不会）。
- **`scheduled`** — 计时器驱动的提示。每个条目每隔 `every_seconds` 秒触发一次。

每个桶（bucket）内的台词以 round-robin 轮替，使用户不会连续两次看到同一句。**Reset to default** 会丢弃自定义脚本，恢复内建的问候语组。

一个可用的示例位于 [`examples/desktop_pet/imeru.petscript.json`](../examples/desktop_pet/imeru.petscript.json)；其中 head 与 body 的台词会回应对 Imeru 的 `Head` 和 `Body` 命中区域的点击。

---

## 键盘与鼠标快捷键

### 导航（所有模式）

| 快捷键 | 动作 |
|----------|--------|
| 方向键 | 网格：移动焦点框（Enter 打开该图片）/ 深度缩放：左 / 右切换图片 |
| Ctrl+Shift+←/→ | 跳到前 / 下个含图片的同级文件夹 |
| Alt+← / Alt+→ | 历史后退 / 前进 |
| Ctrl+G | 跳到第 N 张 |
| X | 随机跳转 |
| Home | 让图片适应窗口（网格中：滚回顶部） |
| Ctrl+F 或 / | 模糊搜索对话框 |
| T | 打开标签与相册 |
| Ctrl+Shift+P | 打开命令面板 |
| Alt+M | 在当前选择重放上一个宏 |
| S | 打开幻灯片对话框 |
| Ctrl+Z | 撤销 |
| Ctrl+Shift+Z / Ctrl+Y | 重做 |

### 深度缩放 / 单张图片

| 快捷键 | 动作 |
|----------|--------|
| F | 切换全屏 |
| Shift+Tab | 切换剧场模式 |
| R / Shift+R | 顺时针 / 逆时针旋转 |
| E | 在标注编辑器中打开当前图片 |
| W / Shift+W | 适应宽度 / 高度 |
| Shift+F | 适应窗口 |
| - / = | 缩小 / 放大 |
| V | 阅读模式（适应宽度，滚动阅读，到底后前往下一张图片） |
| L | 放大镜：跟随光标的局部放大（缩略图上也可用） |
| H | 切换 RGB 直方图 |
| F8 / Ctrl+F8 | OSD 叠加层 / 调试 HUD |
| Shift+P | 切换像素视图（≥ 400 % 显示 RGB；画面上 ≤ 40,000 像素时再显示网格） |
| Shift+M | 循环色彩模式 |
| B | 切换书签 |
| Ctrl+C / Ctrl+V | 复制 / 粘贴图片至 / 自剪贴板 |
| 0 / 1-5 | 切换收藏 / 快速评级 |
| F1-F5 | 快速颜色标签 |
| P / Shift+X / U | 挑片：保留 / 拒绝 / 取消 |
| Shift+S | 分割视图 |
| Shift+D / Ctrl+Shift+D | 双页（LTR / RTL） |
| Ctrl+Shift+M | 多屏镜像窗口 |
| Delete | 连同 `.xmp` / 标注 sidecar 移到回收站（可撤销）；在没有回收站的磁盘（存储卡、U 盘、网络驱动器）上，文件会留着，直到你确认永久删除 |
| Escape | 退出深度缩放 / 全屏 |

### 动画播放（GIF / APNG）

| 快捷键 | 动作 |
|----------|--------|
| 空格 | 播放 / 暂停 |
| ,（逗号）/ .（句号）| 上一帧 / 下一帧 |
| [ / ] | 降低 / 提高播放速度 |

### 磁砖网格

| 快捷键 | 动作 |
|----------|--------|
| Ctrl+L | 切换网格 ↔ 列表 |
| 悬停（500 ms） | 悬停预览弹窗 |
| Delete | 删除选中磁砖 |
| Escape | 取消全选 |

### 鼠标 / 触控板

| 动作 | 行为 |
|--------|----------|
| 左键单击 | 选中磁砖或打开图片 |
| 左键拖曳 | 网格矩形多选 |
| 长按（500 ms） | 进入磁砖选择模式 |
| 中键拖曳 | 深度缩放中平移 |
| 滚轮 | 缩放或滚动 |
| 右键单击 | 上下文菜单 |
| 捏合 | 深度缩放中缩放 |
| 水平滑动 | 上一张 / 下一张 |

### Paint 标签（额外）

| 快捷键 | 动作 |
|----------|--------|
| B / E / G / I | 笔刷 / 橡皮擦 / 填色 / 滴管 |
| V / T / U / R | 移动 / 文字 / 渐变 / 涂抹 |
| M / L / W | 矩形选择 / 套索 / 魔棒 |
| P / S / C / Z / H | 钢笔 / 仿制 / 裁剪 / 缩放 / 抓手 |
| Q | 切换快速蒙版模式 |
| Tab | 切换所有停靠 |
| Ctrl+Tab / Ctrl+Shift+Tab | 下一个 / 上一个 Paint 标签 |
| , / . | 循环笔刷种类 |
| 0-9 | 笔刷不透明度 10% 步进 |
| Alt+[ / Alt+] | 下 / 上切换作用图层 |
| Ctrl+[ / Ctrl+] | 在堆叠中下移 / 上移作用图层 |
| Ctrl+D | 取消选择 |
| [ / ] | 笔刷大小减小 / 增大 1 px |
| Shift+[ / Shift+] | 笔刷大小减小 / 增大 5 px |
| Ctrl+Shift+N / Ctrl+J / Ctrl+E | 新建图层 / 复制图层 / 向下合并 |
| Ctrl+0 / Ctrl+1 | 适合窗口 / 实际大小（100 %） |
| X | 交换前景色 / 背景色 |
| D | 将颜色重置为黑 / 白 |

---

## 菜单结构

### File

- New Window
- Open File / Open Folder
- Recent（文件夹 + 图片）
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association（Windows）
- **Session** — Save / Load
- **Workspaces…** — 保存 / 加载 / 重命名命名窗口布局
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts（可自定义绑定）
- Exit

### Tools（额外工具 — 分为 8 个组子菜单）

- **批次** — 格式转换 · EXIF 清除 · 图像清洗器 · 图像整理器 · 令牌批量重命名 · 去闪烁（延时摄影）· 文档二值化 · Otsu 阈值 · 编辑动画 · 优化到目标大小 · 梗图字幕 · 隐写术
- **图库与元数据** — 图库搜索 · 智能相册 · 找相似图片 · 语义搜索 · 找重复图片 · 自动标签图片 · 层级标签 · 导出元数据（CSV / JSON）· XMP 边车 · GPS 标记 · 从 GPX 轨迹添加地理标记 · 修改拍摄时间 · 元数据模板 · 缩略图缓存
- **视图** — 时间轴视图（按日 / 月 / 年）· 日历视图 · 地图视图 · 示波器与检测 · 小行星全景（360°）· 图像统计 · 质量报告 · 测试图卡 · 色盲模拟预览（红色盲 / 绿色盲 / 蓝色盲 / 全色盲）
- **工作流** — 挑片 · 暂存盘 · 参考图面板 · 虚拟副本 · 双面板文件管理器 · 宏 · 监视文件夹
- **导出** — 联系表 PDF · 网页画廊 · 幻灯片视频（MP4）· 打印布局 · 拼贴 · 证件照排版
- **显影（非破坏）** — 前后对比 · 显影预设 · 色调曲线 · .cube LUT · 分离色调 · 局部调整蒙版 · 图层 · 色阶 · 通道混合器 · 渐变映射 · 自动色彩平衡 · 清晰度 / 去雾 · HSL / 色彩混合 · CLAHE · 背景平整 · 边框与说明文字 · 有序抖动 · 色彩映射 · 扭曲 · 极坐标 · 万花筒 · 磨砂玻璃 · 像素排序 · 胶片颗粒 · 镜头光晕 · 阈值 / 色调分离 · 曝色反转 · 柔光晕染 · 渐变中灰密度 · Velvia · 浮雕 · 去紫边 · 彩色负片 · 电影感色调映射 · 色调 / 细节均衡器 · 软打样
- **修图与变形** — AI 图像放大 · 降噪 / 锐化 · 修复笔刷 · 仿制图章 · 频率分离 · 智能裁剪 · 人像自动修图 · 人脸检测 · 天空 / 背景 · 裁切 / 拉直 · 自动拉直 · 镜头校正 · 比例尺
- **多图** — HDR 合成 · 全景拼接 · 焦点堆叠 · 图像叠合 · 红青立体 3D

### 视图 / 排序 / 过滤 / 语言 / 插件 / 说明

（标准菜单 — 完整选项见应用内。）

### 右键上下文菜单

导航 · 快速动作（显示 / 复制路径 / 复制图片）· 变形 · 批量操作 · 删除 · 桌面壁纸 · 对比 / 幻灯片 · 导出 · 额外工具 · 书签 · 图像信息 · 插件贡献项目。

---

## 插件系统

Imervue 支持第三方插件。完整参考见 [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md)。

### 快速开始

1. 在项目根目录的 `plugins/` 建文件夹
2. 定义继承 `ImervuePlugin` 的类
3. 在 `__init__.py` 用 `plugin_class = YourPlugin` 注册
4. 重启 Imervue

### 钩子

| 钩子 | 触发 |
|------|---------|
| `on_plugin_loaded()` | 插件实例化后 |
| `on_plugin_unloaded()` | 所属窗口关闭时，以及 Reload Plugins 之前 |
| `on_build_menu_bar(plugin_menu)` | 共用的 Plugins 菜单建好后 |
| `on_build_main_tabs(tabs)` | 内置 5 个标签加完之后 |
| `on_build_context_menu(menu, viewer)` | 右键菜单打开时 |
| `on_image_loaded(path, viewer)` | 图片在深度缩放加载后 |
| `on_folder_opened(path, images, viewer)` | 文件夹在网格打开后 |
| `on_image_switched(path, viewer)` | 切换图片时 |
| `on_image_deleted(paths, viewer)` | 图片被软删除后 |
| `on_key_press(key, modifiers, viewer)` | 按键时（返回 True 消费事件） |
| `on_pet_created(pet)` | 桌面宠物窗口创建时，或插件加载时宠物已存在 |
| `on_app_closing(main_window)` | App 关闭前 |
| `get_translations()` | 提供 i18n 字符串 |
| `register_languages()` | 类方法：注册新语言（每次加载前，以及启动时） |

除了钩子之外，插件还可以为批量导出提供另一个显影 recipe 渲染器：在 `on_plugin_loaded` 中用 `Imervue.image.develop_backends.register` 注册一个 `BackendProvider`。GPU 显影插件就是示例；详见 [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md)。

按下 **OK** 即执行一项图像变换的对话框，可以从 `Imervue.plugin.tool_dialog.ToolDialogMixin` 获得按钮行、可选包安装、后台工作线程与结果 toast。插件如果导入了旧版本发布之后才加入的主程序代码，就在它的 `__init__.py` 旁放一个 `plugin.json`，写明所需的插件 API 版本（`{"min_api_version": 2}`）；版本过旧的 Imervue 会跳过该插件并把原因写入日志，而不是在它的导入过程中出错。

### 插件下载器

**Plugins > Download Plugins** 打开在线下载器。源仓库：[Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins)。需要更新版本 Imervue 的插件不会被安装：状态栏会显示它所需的插件 API 版本，已安装的副本保持原样。请先更新 Imervue，再重新下载。

---

## MCP 服务器

Imervue 内置 [Model Context Protocol](https://modelcontextprotocol.io) 服务器，让 AI 助手（Claude Code / Desktop、Cursor、Cline …）能在没有 GUI 的情况下调用项目的纯逻辑工具。Qt-free；一条命令启动：

```sh
python -m Imervue.mcp_server
```

### 工具

精选工具（共 58 个 — 完整清单见文档）。每个工具都会公布 JSON `outputSchema`
以及只读 / 破坏性 `annotations`，将结果以 `structuredContent` 返回；长时间运行的
工具会流式发送 `notifications/progress`。

| 工具 | 用途 |
|------|---------|
| `list_images` | 列出文件夹中的图片（可选递归） |
| `read_image_metadata` / `read_xmp_tags` | 尺寸、格式、EXIF、XMP：sidecar，没有时读文件内嵌的（评级、标签、关键字） |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | 无参考分析：每通道统计、色彩度 / 熵 / 对比度、直方图 + 裁剪、模糊评分 |
| `image_thumbnail` / `ocr_text` / `find_similar` | Base64 预览、Tesseract 文字、感知哈希近重复分组（带进度） |
| `convert_format` | 转换 PNG / JPEG / WebP / TIFF / BMP / AVIF（+ 可选 HEIC / JXL） |
| `apply_watermark` / `apply_frame` | 烧入文字水印或衬边 / 拍立得相框 + 说明文字 |
| `build_collage` | 将多张图片合成为网格拼贴（带进度） |
| `crop_image` / `resize_image` / `rotate_image` | 像素裁切、缩放（只指定一边时保持长宽比，两边都指定时缩放为精确尺寸）、无损旋转 / 翻转。尺寸与坐标以依 EXIF 方向摆正后的图像为准。 |
| `collection_stats` | 文件夹的评级 / 收藏 / 颜色标签 / 挑片汇总 |
| `search_images` | 以智能相册查询 DSL 筛选文件夹（路径 / EXIF / 大小 / 尺寸） |
| `extract_gps` / `dominant_colors` | 读取 EXIF GPS 坐标（可接 `reverse_geocode`）；median-cut 调色板（rgb / hex / pixel_count） |
| `error_level_analysis` | JPEG 重压的篡改鉴识图（PNG data URI） |
| `solarize_image` / `glow_image` | 套用曝色反转或柔光晕染并存档 |
| `velvia_image` / `emboss_image` / `defringe_image` | Velvia 饱和度提升、方向光浮雕、边缘色边去饱和 |
| `film_negative_image` / `graduated_density_image` | 反转扫描负片；套用线性渐变中灰密度渐变 |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | 电影感高光滚降；逐区段曝光；逐频段对比 |
| `colormap_image` / `false_color_image` | 以 viridis / magma / jet 感知色彩映射重新着色；伪彩曝光标尺 |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Bayer 有序抖动；阴影／高光分离色调；亮度带像素排序 |
| `polar_image` / `kaleidoscope_image` | 极坐标／反极坐标扭曲（小行星）；镜射成万花筒楔形 |
| `frosted_glass_image` / `clahe_image` / `local_contrast_image` | 随机邻点毛玻璃散射；CLAHE 局部均衡；清晰度＋纹理局部对比 |
| `posterize_image` / `gradient_map_image` | 将各通道量化成平坦色阶；以渐变重新映射亮度 |
| `film_grain_image` / `dehaze_image` / `distort_image` | 可调高斯颗粒；暗通道去雾；漩涡／挤压／涟漪扭曲 |
| `levels_image` / `curve_image` | 黑白点＋gamma 色阶；S 曲线／提亮阴影／压缩高光的色调曲线 |
| `auto_color_balance_image` / `channel_mixer_image` | 自动白平衡（4 种方法）；3×3 通道混合器＋黑白转换 |
| `lens_correction_image` | 校正镜头桶形／枕形畸变（k1）、暗角与红／蓝色差 |
| `reverse_geocode` / `extract_video_frame` | 离线 GPS → 城市、把一帧视频解码成静态图 |
| `puppet_from_png` / `puppet_inspect` | 从 PNG 构建 `.puppet` rig；打开 `.puppet` 返回其清单 |
| `puppet_validate` / `puppet_schema` | 按 v1 格式检查 `.puppet`（schema、加载器、rig 检查）；返回它的某一份 JSON Schema |

### 提示词（Prompts）

四个可复用提示词：`caption_image`、`suggest_edits`、`analyze_composition`
（显著性驱动的构图评析）与 `flag_issues`（锐度 + 质量 + 裁剪分流）。
`completion/complete` 会为 `suggest_edits` 的 `style` 与 `analyze_composition` 的 `focus`
提供候选值。

### 配置

仓库根目录附带 `.mcp.json` 供 Claude Code 自动发现。对于 Desktop / 其他客户端，添加到 `claude_desktop_config.json`（或等效）：

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

完整协议接口见 [docs/en/index.rst](../docs/en/index.rst) 的 MCP 章节。

---

## 多语言支持

| 语言 | 代码 |
|----------|------|
| English | `English` |
| 繁體中文 | `Traditional_Chinese` |
| 简体中文 | `Chinese` |
| 한국어 | `Korean` |
| 日本語 | `Japanese` |

从 **Language** 菜单切换。需重启。

插件可通过 `language_wrapper.register_language()` 注册全新语言，或通过 `get_translations()` 为内置语言补充翻译（已有键永远不会被覆盖，所以插件不可能弄坏内置字符串）。插件字符串若为空，或其 `{placeholders}` 与英文版不同，就会被丢弃并写入日志，界面改为显示内置文本，而不会出现空白或错误。**Español** 正是这样提供的 —— 从下载器安装 `spanish_translation` 插件后，它就会与五个内置语言一起出现在语言菜单中。详见 [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n)。

---

## 用户设置

保存在应用程序旁的 `user_setting.json` —— 源码版本为项目根目录，冻结版本则是含 `.exe` 的文件夹（PyInstaller 与 Nuitka 皆同）。

此文件是**多账号容器**：每个 profile 各自持有独立的设置字典，因此同一份安装可以同时保有不同配置（例如 *Work* 与 *Personal*）。在 **File > Profiles…** 可切换、创建、重命名与删除 profile。旧版留下的 v1 单账号文件会在首次读取时自动迁移为 `default` profile。写入会在最后一次变更后延迟数秒才批量落地，且以原子方式写入（`.tmp` 同层文件 + `os.replace`），因此保存中途被中断也不会截断文件。启动时若读不到这个文件（JSON 损坏，或被其他程序占用），Imervue 会以默认设置启动，并在第一次保存前把它另存为旁边的 `user_setting.json.unreadable-<日期>-<时间>`；无法保留副本时绝不覆盖它。启动时会弹出警告，写明是哪个文件以及如何取回原来的设置。

每次会话的日志 `imervue.log` 也写在同一个文件夹（该文件夹为只读时改写到 `%LOCALAPPDATA%\Imervue`，Windows 以外为 `~/.cache/imervue`）。上一次会话的日志会以 `imervue.previous.log` 保留在旁边，因此程序异常退出后再次启动 Imervue，能说明原因的日志依然还在。报告问题时请把两个文件一起附上。

当前 profile 的关键条目：

| 设置 | 类型 | 说明 |
|---------|------|-------------|
| `language` | string | 当前语言代码 |
| `user_recent_folders` / `user_recent_images` | list | 最近打开 |
| `user_last_folder` | string | 启动时自动还原 |
| `bookmarks` | list | 书签路径（最多 5000） |
| `sort_by` / `sort_ascending` | string / bool | 排序方法 + 顺序 |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | 每图整理 |
| `thumbnail_size` / `tile_padding` | int | 网格配置 |
| `navigation_auto_loop` | bool | 文件夹末端自动循环 |
| `keyboard_shortcuts` | dict | 自定义键绑定 |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | 窗口布局持久化 |
| `stack_raw_jpeg_pairs` | bool | RAW+JPEG 堆叠切换 |
| `external_editors` | list | 已配置编辑器 |
| `macros` / `macro_last_name` | list / string | 已保存宏 + Alt+M 目标 |
| `puppet_tab_enabled` / `desktop_pet_tab_enabled` | bool | 可选标签页（默认开启；下次启动生效） |

---

## 架构

```
Imervue/
├── __main__.py              # 应用程序入口点
├── cli.py                   # 无界面批处理 CLI（不含 Qt）
├── Imervue_main_window.py   # 主窗口（QMainWindow）— 挂载 5 个标签页
├── gpu_image_view/          # IMERVUE 标签页 — GPU 查看器、深度缩放、瓦片墙
│   ├── actions/             #   查看器动作（删除 / 选择 / 比对 / 幻灯片）
│   └── images/              #   加载层（解码 worker、文件夹扫描、预取）
├── gui/                     # Qt 外壳 — 对话框、侧边栏、显影面板、画布
├── paint/                   # PAINT 标签页 — 全功能位图编辑器
│   ├── docks/               #   停靠面板（颜色 / 画笔 / 图层 / 素材 / …）
│   └── tools/               #   指针工具处理器
├── puppet/                  # PUPPET 标签页 — 2D 绑骨偶动画器 + Cubism 互通
├── desktop_pet/             # 桌面宠物标签页 — 无边框悬浮窗 + 实时驱动与集成
├── image/                   # 纯图像核心（不含 Qt）— recipe 管线、滤镜、编解码、
│                            #   金字塔 / 瓦片管理、XMP、pHash、元数据
├── library/                 # SQLite 图库索引、智能相册、CLIP 搜索、挑片
├── export/                  # 导出生成器（索引表、网页图库、MP4、快捷键速查表）
├── macros/                  # 宏录制 / 重放
├── menu/                    # 菜单定义（file / tools / filter / 右键 / …）
├── mcp_server/              # Model Context Protocol stdio 服务器
├── multi_language/          # i18n（en / zh-tw / zh-cn / ja / ko）+ 验证
├── external/                # 外部编辑器集成
├── plugin/                  # 插件系统（base / manager / downloader / pip installer）
├── sessions/                # Session 与工作区序列化 + 迁移
├── system/                  # 操作系统集成 — 主题、UI 缩放、文件关联、
│                            #   剪贴板监听、树状监视、批量删除、logging
└── user_settings/           # 持久化多账号设置、标签、评分、书签
```

全树贯穿两条规则：

- **纯运算与 Qt 分离。** 单图工具的标准形状是 `image/<feature>.py`（NumPy / Pillow，可在 worker 线程或无显示设备的测试中导入）加上 `gui/<feature>_dialog.py`（Qt 外壳），再于 `menu/extra_tools_menu.py` 注册一个入口。
- **大型 Qt 类只做委派。** `GPUImageView`、`PetWindow` 与 `PaintWorkspace` 只保留事件覆写与生命周期；行为住在具名的协作者（`InputController`、`OverlayPainter`、`PetInteraction`、`ToolDispatcher`…）中，而它们的数学又被抽成纯模块，可在没有 GL context 的情况下单元测试。

### 渲染管线（Imervue 标签）

1. `GPUImageView` 继承 `QOpenGLWidget`
2. 两个 GLSL 1.20 程序（textured quads + solid color rectangles）
3. LRU 纹理缓存 — 256 瓦片软上限（硬上限 512）；VRAM 预算向 GL 驱动探测，回落 1.5 GB，可由用户覆盖
4. 多层磁砖金字塔以 LANCZOS 在 512 × 512 磁砖尺寸构建
5. 硬件支持时最高 8× 各向异性过滤
6. 着色器编译失败时软件渲染备援

### 缩图缓存

- **键**：`{path}|{mtime_ns}|{file_size}|{thumbnail_size}|{recipe_hash}` 的 MD5 —— recipe hash 让显影编辑能反映到缩略图上，又不必让其他所有缓存失效
- **格式**：压缩 PNG（`compress_level=1` — 写入快、占用小）
- **位置**：`%LOCALAPPDATA%/Imervue/cache/thumbnails`（Win）或 `~/.cache/imervue/thumbnails`（Linux/macOS）
- **失效**：文件元数据变动时自动

### Puppet 渲染（Puppet 标签）

- `QOpenGLWidget` 含 `glDrawElements` + 客户端 vertex array
- 每 drawable：rest vertices 缓存为 float32 numpy；vertex morphs 向量化；topological deformer sort 提升出 per-drawable 循环
- 透明度背景是 2×2 GL_REPEAT 平铺纹理（优化前是 100k+ 立即模式 quads）
- Cubism 转换器同时生成 opacity_keys 曲线与 vertex-morph deltas，所以参数驱动的可见度切换能存活 `.moc3 → .puppet` 转换

---

## 许可

本项目使用 [MIT License](../LICENSE)。

Copyright (c) 2026 JE-Chen
