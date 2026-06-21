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
- [Paint — 本格的なラスター描画 风格绘图](#paint--本格的なラスター描画-风格绘图)
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
| **Paint** | 本格的なラスター描画 风格的栅格绘图工作室，含笔刷、图层、动画、漫画工具、PSD I/O |
| **Puppet** | 从零打造的 2D 绑骨偶动画器 — 网格、变形器、参数、动作、物理 |
| **Desktop Pet** | 无边框 / 透明背景 / 永远置顶的桌面宠物 overlay；用同一条 puppet runtime 带实时驱动（idle / blink / mic / webcam / drag-track） |

设计原则：

- **性能优先** — 使用现代 GLSL 着色器和 VBO 进行 GPU 加速渲染
- **支持大量集合** — 虚拟化磁砖网格仅加载可见缩图
- **流畅体验** — 异步多线程图片加载与预取机制
- **非破坏显影** — 每次调整都存储在每张图片的 recipe 中，原始文件直到明确导出才会被覆写
- **可扩展** — 完整插件系统（生命周期 / 菜单 / 图片 / 输入钩子）；MCP 服务器将纯逻辑工具暴露给 AI 助手使用

---

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
| rawpy | RAW 图像解码 |
| imageio | 图片 I/O |
| imageio-ffmpeg | 幻灯片 MP4 导出（H.264 通过 ffmpeg） |
| defusedxml | 安全 XML 解析（XMP 边车文件） |

可选（feature-gated；不装就停用该功能）：

| 包 | 用途 |
|---------|---------|
| open_clip_torch + torch | CLIP 语义搜索 |
| onnxruntime | Real-ESRGAN AI 放大 / CLIP ONNX 自动标签 |
| opencv-python | HDR 合成、全景拼接、焦点堆叠、人脸检测、修复笔刷 |
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

---

## Imervue — 图片浏览与图库

**Imervue** 标签是默认登陆界面，整合图片查看器与文件夹树、EXIF 侧边栏、图库整理工具。

### 查看器

- **GPU 加速渲染** — OpenGL（GLSL 1.20 着色器 + VBO）
- **深度缩放金字塔** — 512×512 磁砖多层 LANCZOS 缩放，LRU 缓存上限 256 磁砖 / 1.5 GB VRAM 预算，最高 8× 各向异性过滤
- **异步加载** — 多线程解码 + ±3 张预取
- **虚拟化缩图网格** — 只渲染可见磁砖；缩图尺寸可选（128 / 256 / 512 / 1024 / 自动）
- **磁盘缓存** — MD5 失效检测的压缩 PNG 缩图，存于 `%LOCALAPPDATA%/Imervue/cache/thumbnails`（或 `~/.cache/imervue/thumbnails`）
- **动画播放** — GIF / APNG，含播放 / 暂停 / 逐帧 / 速度控制

### 浏览模式

- **网格**（默认）— 虚拟化磁砖网格，悬停预览（500 ms 延迟）
- **列表（详细）** — `Ctrl+L` 切换；列：预览 · 标签 · 名称 · 分辨率 · 大小 · 类型 · 修改时间
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
- 像素视图（`Shift+P`）— ≥ 400 % 缩放显示网格 + 每像素 RGB / HEX
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
- **评级** — 0-5 星（`1`-`5`）+ 收藏爱心（`0`）
- **颜色标签** — other XMP-aware photo managers 式 红 / 黄 / 绿 / 蓝 / 紫（`F1`-`F5`）
- **挑片**（Culling）— other XMP-aware photo managers 三状态旗标（`P` = 保留、`Shift+X` = 拒绝、`U` = 取消）；按状态过滤；批量删除拒绝
- **层级标签** — 树状路径如 `animal/cat/british`；自动匹配子孙
- **Tags & Albums** 含多标签 AND / OR 过滤
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

- 按名称 / 修改时间 / 创建时间 / 大小 / 分辨率排序（升 / 降）
- 按扩展名、颜色标签、评级、标签 / 相册、挑片状态过滤
- **高级过滤** — 分辨率 / 文件大小 / 方向 / 修改日期范围
- **多标签过滤** 对话框含 AND / OR

### 搜索

- **模糊文件名搜索** 含子字符串高亮
- **找相似** — pHash（64-bit DCT）含可调 Hamming 距离
- **图库搜索** — SQLite 多根索引，含紧凑的查询 DSL：关键字、标签（含取反）、评级、颜色、扩展名、地点、挑片、收藏、长宽比、年龄、大小、尺寸、相机 / 镜头，以及文件名正则 / glob
- **找相似（average hash）** — pHash 与 dHash 再加上可选的 average-hash（aHash），提供互补的近重复度量
- **语义搜索（CLIP）** — 自然语言查询（如"雪中的金毛犬"）通过缓存的 embedding；`open_clip_torch` + `torch` 未安装时优雅停用
- **自动标签** — 启发式分类 + 可选 CLIP ONNX 升级

### 元数据

- **EXIF 侧栏** 含可折叠组 + 内嵌 0-5 星评级行
- **EXIF 编辑器** 对话框
- **关键字编辑器** — 标题 / 创作者 / 描述 / 关键字，含从标签共现得出的 **相关标签建议**
- **图像信息** 对话框（尺寸 / 大小 / 日期）
- **XMP 边车文件**（`.xmp` 同伴文件）— 评级 / 标题 / 描述 / 关键字 / 颜色标签双向同步 other XMP-aware photo managers（通过 `defusedxml` 安全解析）
- **GPS 地理标记编辑器** — 读写 EXIF GPS 经纬度（JPEG）
- **令牌批量重命名** — 实时预览模板 `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **导出元数据 CSV / JSON** — 每张图一行含挑片 / 评级 / 标签 / 笔记

### 额外工具（Imervue 标签 — 批量处理）

从 **Tools** 菜单访问；分为功能组子菜单：

- **批次** — 格式转换 · EXIF 清除 · 图像清洗器（重新渲染移除所有隐藏数据）· 图像整理器 · 令牌批量重命名
- **AI / 启发式** — AI 图像放大（Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU）· 找重复 · 找相似 · 自动标签 · 人脸检测
- **图库与元数据** — 图库搜索 · 智能相册 · 层级标签 · 导出元数据 · XMP 边车 · GPS 标记

### 系统集成

- Windows 右键 **用 Imervue 打开**（通过注册表）
- 文件夹监控（`QFileSystemWatcher` 自动刷新）
- Toast 通知系统（info / success / warning / error）
- 插件系统含在线下载器（见 [插件系统](#插件系统)）

---

## Modify — 非破坏显影

**Modify** 标签是显影工作站。每次调整都存储在每张图片的 **recipe** 中 — 原始文件直到你明确 **导出** 或 **另存为** 才会被覆写。

### 显影滑块

- 白平衡 — 色温 / 色调
- 色调区段 — 阴影 / 中间调 / 高光
- 曝光 / 对比 / 饱和度 / 鲜艳度
- 裁切、旋转、水平 / 垂直翻转
- 所有调整通过 recipe 存储，全程非破坏

### 曲线与 LUT

- **色调曲线编辑器** — 可拖曳 RGB 曲线 + 单独 R / G / B 通道，含 monotone cubic 插值
- **应用 .cube LUT** — 加载任何 Adobe 3D LUT（最高 64³），trilinear 插值，混合强度滑块
- **分离色调** — 旗标式阴影 / 高光色相 + 饱和度，含平衡枢纽

### 局部调整

- **笔刷 / 径向 / 线性渐变蒙版**，含每蒙版的曝光 / 亮度 / 对比 / 饱和度 / 白平衡偏移 + 羽化滑块
- 蒙版通过显影管线非破坏混合

### 修图与变形

- **修复笔刷** — 圆形点，OpenCV inpainting（Telea 或 Navier-Stokes）
- **仿制图章** — Shift+点击源、羽化贴至目标
- **裁切 / 拉直** — 标准化裁切矩形 + 任意角度拉直，自动裁到最大内接矩形
- **自动拉直** — Hough-line 水平线 / 垂直线检测
- **镜头校正** — 纯 numpy 径向畸变（桶形 / 枕形）、暗角提升、各通道色差校正
- **降噪 / 锐化** — 边缘保留双边降噪 + unsharp mask 锐化
- **天空 / 背景** — 检测天空换成渐变或去除背景（透明或白色填色）；可选 `rembg` / U²-Net 升级

### 多图

- **HDR 合成** — 通过 OpenCV Mertens fusion 合并包围曝光（含 AlignMTB 预先对齐）
- **全景拼接** — OpenCV `Stitcher`（panorama 或 scans 模式），黑边自动裁切
- **焦点堆叠** — Laplacian 焦点图 + Gaussian 混合 + 可选 ECC 对齐

### 输出

- **水印叠加** — 文字或图片，9 个锚点、不透明度、缩放；只在导出时套用
- **导出预设** — Web 1600 / Print 300 dpi / Instagram 1080 一键流水线
- **另存为 / 导出** — PNG / JPEG / WebP / BMP / TIFF，有损格式提供质量滑块
- **批量操作** — 重命名、移动 / 复制、旋转选中图片
- **联系表 PDF** — 多页网格含说明（A4 / A3 / Letter / Legal）
- **网页画廊 HTML** — 自包含文件夹含 `index.html` + JPEG 缩图 + 内嵌灯箱
- **幻灯片 MP4** — H.264 视频，FPS / 每张保留秒数 / 淡入淡出可设（`imageio-ffmpeg`）
- **打印布局** — 多页 PDF（A4/A3/Letter/Legal）含网格 / 边距 / 装订槽 / 裁切标记
- **软打样** — 加载 ICC profile、模拟目标色域、用洋红色标示超出色域的像素
- **虚拟副本** — 每图命名的 recipe 快照；可切换不同风格而不丢失原图

### 外部编辑器

从 **File > External Editors…** 注册程序（your image editor /  / …），再从 **File > Open in External Editor** 启动。

---

## Paint — 本格的なラスター描画 风格绘图

**Paint** 标签是完整功能的栅格绘图工作室，以独立 `QMainWindow` 嵌入，含菜单、左工具栏、上下文敏感的选项栏、右侧分页式停靠列。多文档编辑 — 同时打开多张图，每张有独立撤销栈。

### 工具（27）

笔刷 · 橡皮擦 · 填色 · 滴管 · 矩形 / 套索 / 魔棒 / 快速选择 · 移动 · 文字 · 渐变 · 模糊 · 涂抹 · 减淡 · 加深 · 海绵 · 钢笔 · 仿制图章 · 对话框 · 矩形 · 椭圆 · 直线 · 多边形 · 裁切 · 变形 · 抓手 · 缩放

暗房调色三件组 — **减淡**（提亮）、**加深**（压暗）与 **海绵**（增 / 减饱和度）— 按笔刷以及阴影 / 中间调 / 高光蒙版加权，对局部做色调与色度调整。

单键快捷：`B / E / G / I / V / T / U / R / P / S / C / Z / H`；`Shift+R/E/I/P` 切形状变体。

### 笔刷

钢笔 / 马克笔 / 铅笔 / 荧光笔 / 喷漆 / 书法 / 水彩 / 木炭 / 蜡笔，含大小 / 不透明度 / 硬度 / 密度 / 混合模式。压感曲线编辑器、选择捕获笔尖、笔刷预设导入 / 导出。

### 图层

完整图层面板含缩图、可见性、拖曳重排、混合模式、不透明度、搜索、矢量图层、1-bit 图层、**图层蒙版**（新建 / 从选择 / 反转 / 应用）、**剪切蒙版**、**图层效果**（投影 / 外发光 / 描边）。按颜色分割图层、渐变映射预设。

### 选择

矩形 / 套索 / 魔棒 / 快选 含 **替换 / 加 / 减 / 交集** 模式 + 羽化。**快速蒙版模式**（`Q`）。**描边选择** 对话框。

### 动画与漫画

- **动画** — 帧时间轴停靠含快照、播放、洋葱皮、MP4 / GIF 导出
- **漫画工具** — 分镜切割 · 网点层 · 盖页码 · 速度线（径向 / 平行 / 爆发）· 动作闪光 · 对话框工具

### 滤镜与查看辅助

- **滤镜** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone（每个含实时预览对话框）
- **查看辅助** — 像素格 · 对齐像素 · 对齐边缘 · 洋葱皮 · 出血指引 · 画布旋转（`Ctrl+Shift+H` CCW 旋转）

### 停靠（10 个，分页式）

色彩 · 笔刷 · 图层 · 导航 · 素材库 · 历史 · 色板 · 参考 · 直方图 · 动画。每个停靠可移动 / 浮动。**Settings > Workspace Layouts** 保存与召回命名排列。

### 文件 I/O

- 打开 / 保存 **PSD**（Photoshop）含完整图层往返
- 导出 PNG / JPEG / WebP，多页漫画导出 **CBZ** 或 **PDF**
- 自动保存快照 + 还原最新

### 强化用户体验

- **Tab** 切换所有停靠（无干扰绘图）
- `Ctrl+Tab` 循环 Paint 标签
- `,` / `.` 切换笔刷种类
- `0`-`9` 笔刷不透明度 10 % 步进
- `Alt+[` / `Alt+]` 下 / 上切换作用图层
- 画布右键打开快速 Undo / Redo / 全选 / 取消选 / Fit / 100 %
- 每标签修改星号、撤销 / 重做 toast、启动时还原自动保存对话框

从深度缩放按 `E` 把当前图片直接送入新的 Paint 标签。

---

## Puppet — 2D 绑骨偶动画

> **完整教程**：[`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md) 涵盖直播（OBS / NDI / 虚拟摄像头）与动画制作（录制 / 时间轴编辑 / MP4 导出）的端到端流程。英文版于 [`puppet_guide.md`](../puppet_guide.md)、繁体中文于 [`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md)。

**Puppet** 标签是从零打造的 2D 绑骨偶动画系统。功能对标 Live2D（网格变形绑骨、参数、动作、物理、表情、姿势、对嘴、摄像头脸部追踪），但**不依赖任何专利 SDK**、**不使用 `live2d-py`**，采用完全开放的 `.puppet` 文件格式，规格完整记录于 `Imervue/puppet/FORMAT.md`。

### 文件格式

`.puppet` 是 zip 容器：

- `puppet.json` — manifest（drawables、deformers、parameters、motions、pose groups、parts、hit areas）
- `textures/*.png` — atlas 纹理
- `motions/*.json` — keyframe tracks
- `expressions/*.json` — 参数叠加
- `physics.json` — Verlet 物理配置

JSON 为主，人类可 diff，没有专利二进制。

### 渲染器

`QOpenGLWidget` 含 vertex-array textured-triangle 绘制（按 draw_order）、每 drawable 混合模式（normal / additive / multiply）、pose-group 互斥、图像空间正交投影、GL_REPEAT 平铺的透明度棋盘背景、滚轮缩放 + 中键拖曳平移。针对大型 rig 优化 — March 7th（307 drawables / 2965 vertex morphs）在 CPU 上达 60 FPS。

### 编辑

- **导入 PNG** → 自动生成考虑 alpha 的三角网格
- **添加旋转变形器**（anchor + angle）/ **添加 warp 变形器**（rows × cols bezier lattice）工具栏动作
- **添加参数** → 在滑块端点按 **Set Key** 在参数停靠记录关键形状
- **网格编辑器** — 切换 Edit Mesh 拖曳顶点；点击 8 px 内吸附到最近顶点
- **另存为…** 把整个 rig 写成 `.puppet` zip

### 运行

- **参数绑定** — 每个参数保有 key 列表，将滑块值对应到部分 deformer-form 快照；运行时采样并逐字段线性插值
- **动作播放** — 底部停靠含动作列表 + 播放 / 暂停 / 停止 / 循环 / 拖曳；曲线采样器支持 `linear`、`stepped`、`inverse-stepped`、`cubic-bezier` 段（牛顿迭代 time → param）；每动作淡入 / 淡出
- **表情** — `additive` / `multiply` / `overwrite` 参数叠加堆栈
- **姿势组** — 互斥 drawable 可见性（武器切换、嘴形变体）
- **物理** — Verlet 钟摆链用于头发 / 衣物 / 缎带；输入参数移动链锚点，重力 + 阻尼 + 每粒子弹簧回复静止
- **顶点 morph** — Cubism 式线性混合于 rest 与 ±extreme deltas；每帧向量化 numpy，60 FPS
- **不透明度 keys** — 参数驱动的 alpha 曲线；让替代姿势 mesh 随手势参数淡入 / 淡出

### 实时输入

- 鼠标拖曳 → 头部角度参数
- 自动眨眼，cosine open → close → open 曲线
- 麦克风对嘴 via `sounddevice` RMS → `ParamMouthOpenY`（可选依赖）
- 摄像头脸部追踪 via OpenCV + MediaPipe FaceMesh → 头部 yaw / pitch / roll + 眼 / 嘴开合（可选依赖）
- 自定义动作录制 — 滑动滑块 / 对摄像头 / 物理运行时以 30 Hz 抓取参数值；停止时烘焙成线性段 Motion

### Cubism 互通

可插入 **Cubism Native SDK**（用户自备 DLL — Live2D 的 Free Material License 禁止重新散布）将任何 `.moc3` 模型转成 `.puppet` zip。转换器执行 sample-and-reconstruct 扫描，同时抓取 vertex-morph delta 与参数驱动的可见度切换，所以手势切换（比耶 / 捂脸 / 拍照 …）能完整保留。

### 输出

- **截取画面…** 通过 `glReadPixels` 存 PNG
- **录制…** 切换 30 FPS 帧循环，通过 `imageio` 写成 GIF / WebM / MP4
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

Imervue 会把输出帧的长边强制压到 1080 px，所以 Cubism 原生画布（March 7th 是 3503×7777）不会被 DirectShow 虚拟摄像头驱动拒绝。长宽比保留，OBS 端可以再缩。

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

示例 rig 在 [`examples/puppet/march_7th.puppet`](../examples/puppet/march_7th.puppet) — 307 drawable 的 Cubism Live2D 角色仓库内转换。从 **打开 puppet…** 打开，rig 居中加载；点击 18 个动作（Idle 组 + Gesture 组）任意一个即播放。手势涵盖比耶、捂脸、拍照、脸红、黑脸、哭、流汗、星星、流星 — rig 定义的所有命名手势。

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
| 隐藏时暂停 | 宠物不可见时停止动画 — 离开画面零 CPU。 |
| 尺寸预设 | small / medium / large 三档。以中心对齐缩放，调尺寸时角色不会跨屏幕跳。 |
| 不透明度滑杆 | 把宠物淡化到 10% – 100%，可以当作低调的桌面摆件。 |
| 记住你放的位置 | 拖到喜欢的角落后，下次启动时宠物会回到那里。 |

### 点击交互

- **左键点角色身体** — 若 rig 有定义命中区域（例如点头），就播放对应的动作；否则宠物会用对话气泡跟你打招呼。
- **右键任意处** — 打开 context menu：Hide pet、Live drivers、Play motion（rig 内所有动作清单）、Apply expression、Lock position、Click-through、Always on bottom、Hide on fullscreen、Speech bubble、Size。
- **系统托盘图标** — 左键切换显示 / 隐藏；右键打开 Show/Hide、Click-through、Open puppet、Hide pet。

### 实时驱动

可以从标签或右键菜单挑任意组合。每个驱动默认关闭 — 只开你要的就好。

- **Auto idle** — 加上呼吸 + 轻微 drift，让角色看起来活着。
- **Idle motions** — 在 rig 的 idle-group 动作之间随机循环。
- **Auto-blink** — 每隔几秒自然眨眼的循环曲线。
- **Drag-track head** — 头部跟着光标转动。
- **Mic lip-sync** — 嘴会跟着你的声音一起开合（需要 `sounddevice`）。
- **Webcam tracking** — 你的头 / 眼 / 嘴会驱动宠物的对应部位（需要 `opencv-python` 和 `mediapipe`）。

### 如何开始

1. 切换到 **Desktop Pet** 标签。
2. 点 **Load bundled March 7th** 用内建的角色，或点 **Open Puppet…** 选自己的 `.puppet` 文件。
3. 勾选 **Show pet on desktop**。
4. 把角色拖到你想要的位置；挑选要启用的驱动；调整不透明度 / 尺寸。
5. 随时右键打开快速操作菜单，或用系统托盘图标在找不到标签时隐藏宠物。

所有设置 — 位置、驱动、不透明度、点击穿透、尺寸 — 都会跨启动保留。

---

## 键盘与鼠标快捷键

### 导航（所有模式）

| 快捷键 | 动作 |
|----------|--------|
| 方向键 | 滚动网格 / 切换图片（深度缩放中左 / 右） |
| Shift + 方向 | 细微滚动（半步） |
| Ctrl+Shift+←/→ | 跳到前 / 下个含图片的同级文件夹 |
| Alt+← / Alt+→ | 历史后退 / 前进 |
| Ctrl+G | 跳到第 N 张 |
| X | 随机跳转 |
| Home | 重置缩放与平移 |
| Ctrl+F 或 / | 模糊搜索对话框 |
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
| E | 打开图像编辑器（Modify 标签） |
| W / Shift+W | 适合宽度 / 高度 |
| H | 切换 RGB 直方图 |
| F8 / Ctrl+F8 | OSD 叠加层 / 调试 HUD |
| Shift+P | 切换像素视图（≥ 400 % 显示网格 + RGB） |
| Shift+M | 循环色彩模式 |
| B | 切换书签 |
| Ctrl+C / Ctrl+V | 复制 / 粘贴图片至 / 自剪贴板 |
| 0 / 1-5 | 切换收藏 / 快速评级 |
| F1-F5 | 快速颜色标签 |
| P / Shift+X / U | 挑片：保留 / 拒绝 / 取消 |
| Shift+S | 分割视图 |
| Shift+D / Ctrl+Shift+D | 双页（LTR / RTL） |
| Ctrl+Shift+M | 多屏镜像窗口 |
| Delete | 移到回收站（可撤销） |
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
| V / T / U / R | 移动 / 文字 / 渐变 / 矩形选择 |
| P / S / C / Z / H | 钢笔 / 涂抹 / 仿制 / 缩放 / 抓手 |
| Q | 切换快速蒙版模式 |
| Tab | 切换所有停靠 |
| Ctrl+Tab | 循环 Paint 标签 |
| , / . | 循环笔刷种类 |
| 0-9 | 笔刷不透明度 10% 步进 |
| Alt+[ / Alt+] | 下 / 上切换作用图层 |

---

## 菜单结构

### File

- New Window
- Open Image / Open Folder
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

- **批次** — 格式转换 · EXIF 清除 · 图像清洗器 · 图像整理器 · 令牌批量重命名
- **图库与元数据** — 图库搜索 · 智能相册 · 找相似 / 重复 · 自动标签 · 层级标签 · 导出元数据 · XMP 边车 · GPS 标记
- **视图** — Timeline · Calendar · Map
- **工作流** — 挑片 · 暂存盘 · 虚拟副本 · 双面板 FM · 宏
- **导出** — 联系表 PDF · 网页画廊 · 幻灯片视频（MP4）· 打印布局
- **显影（非破坏）** — 色调曲线 · .cube LUT · 分离色调 · 局部调整蒙版 · 软打样
- **修图与变形** — AI 图像放大 · 降噪 / 锐化 · 修复笔刷 · 仿制图章 · 人脸检测 · 天空 / 背景 · 裁切 / 拉直 · 自动拉直 · 镜头校正
- **多图** — HDR 合成 · 全景拼接 · 焦点堆叠

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
| `on_plugin_unloaded()` | App 关闭时 |
| `on_build_menu_bar(menu_bar)` | 默认菜单栏建好后 |
| `on_build_main_tabs(tabs)` | 内置 4 个标签加完之后 |
| `on_build_context_menu(menu, viewer)` | 右键菜单打开时 |
| `on_image_loaded(path, viewer)` | 图片在深度缩放加载后 |
| `on_folder_opened(path, images, viewer)` | 文件夹在网格打开后 |
| `on_image_switched(path, viewer)` | 切换图片时 |
| `on_image_deleted(paths, viewer)` | 图片被软删除后 |
| `on_key_press(key, modifiers, viewer)` | 按键时（返回 True 消费事件） |
| `on_app_closing(main_window)` | App 关闭前 |
| `get_translations()` | 提供 i18n 字符串 |

### 插件下载器

**Plugins > Download Plugins** 打开在线下载器。源仓库：[Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins)。

---

## MCP 服务器

Imervue 内置 [Model Context Protocol](https://modelcontextprotocol.io) 服务器，让 AI 助手（Claude Code / Desktop、Cursor、Cline …）能在没有 GUI 的情况下调用项目的纯逻辑工具。Qt-free；一条命令启动：

```sh
python -m Imervue.mcp_server
```

### 工具

精选工具（共 22 个 — 完整清单见文档）。每个工具都会公布 JSON `outputSchema`
以及只读 / 破坏性 `annotations`，将结果以 `structuredContent` 返回；长时间运行的
工具会流式发送 `notifications/progress`。

| 工具 | 用途 |
|------|---------|
| `list_images` | 列出文件夹中的图片（可选递归） |
| `read_image_metadata` / `read_xmp_tags` | 尺寸、格式、EXIF、XMP 边车（评级、标签、关键字） |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | 无参考分析：每通道统计、色彩度 / 熵 / 对比度、直方图 + 裁剪、模糊评分 |
| `image_thumbnail` / `ocr_text` / `find_similar` | Base64 预览、Tesseract 文字、感知哈希近重复分组（带进度） |
| `convert_format` | 转换 PNG / JPEG / WebP / TIFF / BMP（+ 可选 HEIC / AVIF / JXL） |
| `apply_watermark` / `apply_frame` | 烧入文字水印或衬边 / 拍立得相框 + 说明文字 |
| `build_collage` | 将多张图片合成为网格拼贴（带进度） |
| `crop_image` / `resize_image` / `rotate_image` | 像素裁切、保持长宽比的缩放、无损旋转 / 翻转 |
| `collection_stats` | 文件夹的评级 / 收藏 / 颜色标签 / 挑片汇总 |
| `reverse_geocode` / `extract_video_frame` | 离线 GPS → 城市、把一帧视频解码成静态图 |
| `puppet_from_png` / `puppet_inspect` | 从 PNG 构建 `.puppet` rig；打开 `.puppet` 返回其清单 |

### 提示词（Prompts）

四个可复用提示词：`caption_image`、`suggest_edits`、`analyze_composition`
（显著性驱动的构图评析）与 `flag_issues`（锐度 + 质量 + 裁剪分流）。
提示词参数可通过 `completion/complete` 自动补全。

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

插件可通过 `language_wrapper.register_language()` 注册全新语言，或通过 `get_translations()` 提供翻译。详见 [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n)。

---

## 用户设置

存储在工作目录的 `user_setting.json`。关键字段：

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

---

## 架构

```
Imervue/
├── __main__.py              # 应用程序入口
├── Imervue_main_window.py   # 主窗口（QMainWindow）— 挂载 4 个标签
├── gpu_image_view/          # IMERVUE 标签 — GPU viewer + 深度缩放
├── gui/                     # 对话框与侧栏（显影、EXIF 等）
├── paint/                   # PAINT 标签 — 本格的なラスター描画 风格栅格编辑器
├── puppet/                  # PUPPET 标签 — 2D 绑骨偶动画器
├── export/                  # 导出生成器（联系表、网页画廊、MP4）
├── image/                   # 图像工具（金字塔、磁砖管理、信息）
├── library/                 # 图库辅助（RAW+JPEG 堆叠、索引）
├── macros/                  # 宏录制 / 重放
├── menu/                    # 菜单定义
├── mcp_server/              # Model Context Protocol stdio 服务器
├── multi_language/          # i18n（en / zh-tw / zh-cn / ja / ko）
├── external/                # 外部编辑器集成
├── plugin/                  # 插件系统（base / manager / downloader）
├── sessions/                # 工作区序列化
├── system/                  # Windows 文件关联
└── user_settings/           # 持久用户配置
```

### 渲染管线（Imervue 标签）

1. `GPUImageView` 继承 `QOpenGLWidget`
2. 两个 GLSL 1.20 程序（textured quads + solid color rectangles）
3. LRU 纹理缓存 — 256-磁砖上限、1.5 GB VRAM 预算
4. 多层磁砖金字塔以 LANCZOS 在 512 × 512 磁砖尺寸构建
5. 硬件支持时最高 8× 各向异性过滤
6. 着色器编译失败时软件渲染备援

### 缩图缓存

- **键**：`{path}|{mtime_ns}|{file_size}|{thumbnail_size}` 的 MD5
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
