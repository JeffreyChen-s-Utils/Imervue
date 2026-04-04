<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  基于 PySide6 和 OpenGL 的 GPU 加速图片浏览器
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-TW.md">繁體中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## 目录

- [概述](#概述)
- [功能特色](#功能特色)
- [支持的图片格式](#支持的图片格式)
- [安装](#安装)
- [使用方式](#使用方式)
- [浏览模式](#浏览模式)
- [键盘与鼠标快捷键](#键盘与鼠标快捷键)
- [菜单结构](#菜单结构)
- [插件系统](#插件系统)
- [多语言支持](#多语言支持)
- [用户设置](#用户设置)
- [架构](#架构)
- [许可证](#许可证)

---

## 概述

Imervue 是一款高性能图片浏览器，专为流畅的浏览体验和大量图片集合的高效处理而设计。通过 OpenGL 的 GPU 加速，为缩略图网格和深度缩放图片查看提供快速渲染。

核心设计原则：

- **性能优先** — 使用现代 GLSL 着色器和 VBO 进行 GPU 加速渲染
- **支持大量集合** — 虚拟化磁贴网格仅加载可见缩略图
- **流畅体验** — 异步多线程图片加载与预取机制
- **可扩展** — 完整的插件系统，支持生命周期、菜单、图片和输入钩子

---

## 功能特色

### 核心功能

- 通过 OpenGL 的 GPU 加速渲染（GLSL 1.20 着色器 + VBO）
- 深度缩放图片查看，使用多层图片金字塔（512×512 磁贴）
- 虚拟化磁贴缩略图网格，支持延迟加载
- 异步多线程图片加载
- 缩略图磁盘缓存系统（NumPy `.npy` 格式，MD5 缓存键）
- 预加载前后各 ±3 张相邻图片
- 撤销/重做系统（QUndoStack 用于编辑，传统堆栈用于删除）

### 导航与查看

- 文件夹浏览和单张图片查看
- 全屏模式，UI 在空闲 2 秒后自动隐藏
- 深度缩放模式下的小地图覆盖层
- RGB 直方图覆盖层
- 图片旋转（包括通过 piexif 的无损 JPEG 旋转）
- 动态 GIF/APNG 播放，支持逐帧控制
- 幻灯片模式，可自定义间隔时间
- 并排图片比较
- 按文件名搜索/筛选图片

### 整理功能

- 书签系统（最多 500 个书签）
- 评分系统（1–5 星）和收藏功能
- 按名称、修改日期、创建日期、文件大小或分辨率排序
- 按扩展名或评分筛选
- 最近文件夹和最近图片追踪
- 启动时自动恢复上次打开的文件夹

### 编辑与导出

- 内置图片编辑器（裁切、亮度、对比度、饱和度、旋转）
- 导出/另存为，支持格式转换（PNG、JPEG、WebP、BMP、TIFF）
- 有损格式质量滑块（JPEG、WebP）
- 批量操作（重命名、移动/复制、旋转选中的图片）
- 设为桌面壁纸
- 复制图片/图片路径到剪贴板

### 元数据

- EXIF 数据显示于可折叠侧边栏
- EXIF 编辑器对话框
- 图片信息对话框（尺寸、文件大小、日期）

### 系统集成

- Windows 右键"用 Imervue 打开"上下文菜单（通过注册表进行文件关联）
- 使用 QFileSystemWatcher 进行文件夹监控（变更时自动刷新）
- 多语言支持（5 种内置语言）
- 插件系统，附带在线插件下载器
- Toast 通知系统（信息、成功、警告、错误级别）

---

## 支持的图片格式

### 位图格式

| 格式 | 扩展名 |
|------|--------|
| PNG | `.png` |
| JPEG | `.jpg`、`.jpeg` |
| BMP | `.bmp` |
| TIFF | `.tiff`、`.tif` |
| WebP | `.webp` |
| GIF | `.gif`（动态） |
| APNG | `.apng`（动态） |

### 矢量图格式

| 格式 | 扩展名 |
|------|--------|
| SVG | `.svg`（通过 QSvgRenderer 渲染，缩略图缩小至最大 512px） |

### RAW 相机格式

| 格式 | 扩展名 | 相机品牌 |
|------|--------|---------|
| CR2 | `.cr2` | Canon |
| NEF | `.nef` | Nikon |
| ARW | `.arw` | Sony |
| DNG | `.dng` | Adobe Digital Negative |
| RAF | `.raf` | Fujifilm |
| ORF | `.orf` | Olympus |

RAW 文件支持嵌入式预览提取，并在无法提取时回退使用半尺寸处理。

---

## 安装

### 系统要求

- Python >= 3.10
- 支持 OpenGL 的 GPU（可使用软件渲染作为后备）

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

### 依赖包

| 包 | 用途 |
|---|------|
| PySide6 | Qt6 GUI 框架 |
| qt-material | Material Design 主题 |
| Pillow | 图片处理 |
| PyOpenGL | OpenGL 绑定 |
| PyOpenGL_accelerate | OpenGL 性能优化 |
| numpy | 数组操作与缩略图缓存 |
| rawpy | RAW 图片解码 |
| imageio | 图片输入/输出 |

---

## 使用方式

### 基本启动

```bash
python -m Imervue
```

### 打开特定图片

```bash
python -m Imervue /path/to/image.jpg
```

### 打开文件夹

```bash
python -m Imervue /path/to/folder
```

### 命令行选项

| 选项 | 说明 |
|------|------|
| `--debug` | 启用调试模式 |
| `--software_opengl` | 使用软件 OpenGL 渲染（设置 `QT_OPENGL=software` 和 `QT_ANGLE_PLATFORM=warp`）。当 GPU 驱动不可用或有问题时使用。 |
| `file` | （位置参数）启动时打开的图片或文件夹 |

---

## 浏览模式

### 网格模式（磁贴网格）

打开文件夹时，图片会以虚拟化缩略图网格显示：

- **延迟加载** — 仅渲染和加载可见的缩略图
- **动态缩略图大小** — 可设置为 128×128、256×256、512×512、1024×1024 或自动
- **滚动和缩放** — 流畅浏览大量集合
- **多选** — 拖拽框选或长按进入选择模式
- **批量操作** — 重命名、移动/复制、旋转或删除选中的图片
- **磁盘缓存** — 缩略图以 `.npy` 文件缓存，使用 MD5 失效机制

### 单张图片模式（深度缩放）

打开单张图片或双击缩略图时：

- **多层图片金字塔** — 512×512 像素磁贴，使用 LANCZOS 下采样
- **LRU 磁贴缓存** — GPU 上最多缓存 256 个磁贴（1.5 GB VRAM 上限）
- **流畅平移和缩放** — GPU 加速，支持各向异性过滤（最高 8x）
- **小地图覆盖层** — 显示当前视口位置
- **RGB 直方图** — 按 `H` 键切换
- **加载时居中** — 默认适应窗口大小
- **相邻图片预加载** — 预加载前后各 ±3 张相邻图片

---

## 键盘与鼠标快捷键

### 导航（两种模式通用）

| 快捷键 | 动作 |
|--------|------|
| 方向键 | 滚动网格 / 切换图片（深度缩放模式下左右切换） |
| Shift + 方向键 | 精细滚动（半步） |
| Home | 重置缩放和平移至原点 |
| Ctrl+F 或 / | 打开搜索对话框 |
| S | 打开幻灯片对话框 |
| Ctrl+Z | 撤销 |
| Ctrl+Shift+Z / Ctrl+Y | 重做 |

### 深度缩放 / 单张图片模式

| 快捷键 | 动作 |
|--------|------|
| F | 切换全屏 |
| R | 顺时针旋转 |
| Shift+R | 逆时针旋转 |
| E | 打开图片编辑器 |
| W | 适应宽度 |
| Shift+W | 适应高度 |
| H | 切换 RGB 直方图覆盖层 |
| B | 切换当前图片的书签 |
| Ctrl+C | 复制图片到剪贴板 |
| Ctrl+V | 从剪贴板粘贴图片 |
| 0 | 切换收藏（爱心） |
| 1–5 | 快速评分（1–5 星） |
| Delete | 将当前图片移至回收站（可撤销） |
| Escape | 退出深度缩放 / 退出全屏 |

### 动画播放（GIF / APNG）

| 快捷键 | 动作 |
|--------|------|
| Space | 播放 / 暂停 |
| ,（逗号） | 上一帧 |
| .（句号） | 下一帧 |
| [ | 降低播放速度 |
| ] | 提高播放速度 |

### 磁贴网格模式

| 快捷键 | 动作 |
|--------|------|
| 方向键 | 滚动网格 |
| Delete | 删除选中的磁贴 |
| Escape | 取消全部选择 |

### 鼠标控制

| 动作 | 行为 |
|------|------|
| 左键点击 | 选择磁贴或打开图片 |
| 左键拖拽 | 网格中框选多张图片 |
| 长按（500ms） | 进入磁贴选择模式 |
| 中键拖拽 | 深度缩放中平移/滚动 |
| 滚轮 | 放大/缩小或滚动 |
| 右键 | 打开上下文菜单 |

---

## 菜单结构

### 文件

- 新窗口
- 打开图片
- 打开文件夹
- 最近（子菜单：最近文件夹和图片）
- 书签（管理已添加书签的图片）
- 确认待处理的删除（确认撤销堆栈）
- 文件关联（仅限 Windows — 注册/取消注册右键上下文菜单）
- 退出

### 查看

- 磁贴大小：128×128 / 256×256 / 512×512 / 1024×1024 / 自动

### 排序

- 按名称 / 按修改日期 / 按创建日期 / 按文件大小 / 按分辨率
- 升序 / 降序

### 筛选

- 按扩展名：全部、JPG、PNG、BMP、TIFF、SVG、RAW
- 按评分：全部、已收藏、1–5 星
- 清除筛选

### 语言

- English / 繁體中文 / 简体中文 / 한국어 / 日本語

### 插件

- 已加载的插件（显示各插件名称和版本）
- 下载插件（打开在线插件下载器）
- 打开插件文件夹

### 说明

- 键盘与鼠标快捷键（详细的快捷键参考对话框）

### 右键菜单

- 导航（上层文件夹、下一张/上一张图片）
- 快速操作（在资源管理器中显示、复制路径、复制图片）
- 变换（顺时针/逆时针旋转、编辑图片）
- 批量操作（批量重命名、移动/复制、全部旋转）
- 删除（删除当前/选中的项目）
- 设为壁纸
- 比较 / 幻灯片
- 导出（另存为，可选择格式）
- 无损 JPEG 旋转
- 书签（添加/移除书签）
- 图片信息
- 最近菜单
- 插件贡献的项目

---

## 插件系统

Imervue 支持插件系统以扩展功能。完整说明请参阅[插件开发指南](../PLUGIN_DEV_GUIDE.md)。

### 快速开始

1. 在项目根目录的 `plugins/` 文件夹中创建一个文件夹
2. 定义一个继承 `ImervuePlugin` 的类
3. 在 `__init__.py` 中以 `plugin_class = YourPlugin` 注册
4. 重新启动 Imervue

### 可用的钩子

| 钩子 | 触发时机 |
|------|---------|
| `on_plugin_loaded()` | 插件实例化后 |
| `on_plugin_unloaded()` | 应用程序关闭时 |
| `on_build_menu_bar(menu_bar)` | 默认菜单栏构建完成后 |
| `on_build_context_menu(menu, viewer)` | 右键菜单打开时 |
| `on_image_loaded(path, viewer)` | 图片在深度缩放中加载后 |
| `on_folder_opened(path, images, viewer)` | 文件夹在网格中打开后 |
| `on_image_switched(path, viewer)` | 在图片间导航时 |
| `on_image_deleted(paths, viewer)` | 图片被软删除后 |
| `on_key_press(key, modifiers, viewer)` | 按键时（返回 True 以消费事件） |
| `on_app_closing(main_window)` | 应用程序关闭前 |
| `get_translations()` | 提供国际化字符串 |

### 插件下载器

可通过 **插件 > 下载插件** 从官方仓库下载插件。下载器从 GitHub 上的 [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins) 获取。

---

## 多语言支持

### 内置语言

| 语言 | 代码 |
|------|------|
| English | `English` |
| 繁體中文 | `Traditional_Chinese` |
| 简体中文 | `Chinese` |
| 한국어 | `Korean` |
| 日本語 | `Japanese` |

可从 **语言** 菜单更改语言。更改后需要重新启动才会生效。

### 通过插件添加语言

插件可以使用 `language_wrapper.register_language()` 注册全新的语言，或通过 `get_translations()` 为现有语言添加翻译。详情请参阅[插件开发指南](../PLUGIN_DEV_GUIDE.md#internationalization-i18n)。

---

## 用户设置

设置存储在工作目录的 `user_setting.json` 中。

| 设置 | 类型 | 说明 |
|------|------|------|
| `language` | 字符串 | 当前语言代码 |
| `user_recent_folders` | 列表 | 最近打开的文件夹 |
| `user_recent_images` | 列表 | 最近打开的图片 |
| `user_last_folder` | 字符串 | 上次打开的文件夹（启动时自动恢复） |
| `bookmarks` | 列表 | 已添加书签的图片路径（最多 500 个） |
| `sort_by` | 字符串 | 排序方式（name/modified/created/size/resolution） |
| `sort_ascending` | 布尔 | 排序顺序 |
| `image_ratings` | 字典 | 图片路径 → 评分（1–5）映射 |
| `image_favorites` | 集合 | 已收藏的图片路径 |
| `thumbnail_size` | 整数/null | 网格缩略图大小（128/256/512/1024/null 为自动） |

---

## 架构

```
Imervue/
├── __main__.py              # 应用程序入口点
├── Imervue_main_window.py   # 主窗口（QMainWindow）
├── gpu_image_view/          # GPU 加速查看器
│   ├── gpu_image_view.py    # 主要查看器组件（QOpenGLWidget）
│   ├── gl_renderer.py       # OpenGL 着色器渲染器
│   ├── actions/             # 查看器操作（缩放、平移、旋转等）
│   └── images/              # 图片加载、金字塔、磁贴管理
├── gui/                     # UI 组件
│   ├── bookmark_dialog.py   # 书签管理对话框
│   ├── exif_editor.py       # EXIF 元数据编辑器
│   ├── exif_sidebar.py      # 可折叠 EXIF 侧边栏
│   ├── export_dialog.py     # 导出/另存为对话框
│   ├── image_editor.py      # 图片编辑器（裁切、调整、旋转）
│   └── toast.py             # Toast 通知系统
├── image/                   # 图片工具
│   ├── info.py              # 图片信息提取
│   ├── pyramid.py           # 深度缩放图片金字塔
│   ├── thumbnail_disk_cache.py  # 缩略图缓存（MD5 + .npy）
│   └── tile_manager.py      # 磁贴网格管理
├── menu/                    # 菜单定义
│   ├── file_menu.py         # 文件菜单
│   ├── filter_menu.py       # 筛选菜单
│   ├── language_menu.py     # 语言菜单
│   ├── plugin_menu.py       # 插件菜单
│   ├── recent_menu.py       # 最近项目子菜单
│   ├── right_click_menu.py  # 右键菜单
│   ├── sort_menu.py         # 排序菜单
│   └── tip_menu.py          # 说明菜单
├── multi_language/          # 国际化
│   ├── language_wrapper.py  # 语言单例管理器
│   ├── english.py           # 英文翻译
│   ├── chinese.py           # 简体中文
│   ├── traditional_chinese.py  # 繁体中文
│   ├── korean.py            # 韩文
│   └── japanese.py          # 日文
├── plugin/                  # 插件系统
│   ├── plugin_base.py       # ImervuePlugin 基类
│   ├── plugin_manager.py    # 插件发现与生命周期
│   └── plugin_downloader.py # 在线插件下载器
├── system/                  # 系统集成
│   └── file_association.py  # Windows 文件关联（注册表）
└── user_settings/           # 用户配置
    ├── user_setting_dict.py # 设置读写（线程安全）
    ├── bookmark.py          # 书签管理
    └── recent_image.py      # 最近图片追踪
```

### 渲染管线

1. **OpenGL 上下文** — `GPUImageView` 继承 `QOpenGLWidget`
2. **着色器程序** — 两个 GLSL 1.20 程序（纹理四边形 + 纯色矩形）
3. **纹理管理** — LRU 缓存，256 磁贴上限，1.5 GB VRAM 预算
4. **深度缩放金字塔** — 多层磁贴金字塔，使用 LANCZOS 重采样，512×512 磁贴大小
5. **各向异性过滤** — 硬件支持时最高 8x
6. **后备** — 着色器编译失败时使用立即模式渲染

### 缩略图缓存

- **键**：`{path}|{mtime_ns}|{file_size}|{thumbnail_size}` 的 MD5 哈希
- **格式**：NumPy `.npy` 二进制（快速 I/O，无压缩开销）
- **位置**：`%LOCALAPPDATA%/Imervue/cache/thumbnails`（Windows）或 `~/.cache/imervue/thumbnails`（Linux/macOS）
- **失效机制**：文件元数据变更时自动失效

---

## 许可证

本项目采用 [MIT 许可证](../LICENSE)。

Copyright (c) 2026 JE-Chen
