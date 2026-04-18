<p align="center">
  <img src="Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  A GPU-accelerated image viewer built with PySide6 and OpenGL
</p>

<p align="center">
  <a href="README/README_zh-TW.md">繁體中文</a> ·
  <a href="README/README_zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://imervue.readthedocs.io/en/latest/?badge=latest"><img src="https://readthedocs.org/projects/imervue/badge/?version=latest" alt="Documentation Status"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Supported Image Formats](#supported-image-formats)
- [Installation](#installation)
- [Usage](#usage)
- [Browsing Modes](#browsing-modes)
- [Keyboard & Mouse Shortcuts](#keyboard--mouse-shortcuts)
- [Menu Structure](#menu-structure)
- [Plugin System](#plugin-system)
- [Multi-Language Support](#multi-language-support)
- [User Settings](#user-settings)
- [Architecture](#architecture)
- [License](#license)

---

## Overview

Imervue is a high-performance image viewer designed for smooth navigation and efficient handling of large image collections. It leverages GPU acceleration through OpenGL to deliver fast rendering for both thumbnail grids and deep zoom image viewing.

Key design principles:

- **Performance first** — GPU-accelerated rendering with modern GLSL shaders and VBO
- **Large collection support** — Virtualized tile grid loads only visible thumbnails
- **Smooth experience** — Asynchronous multi-threaded image loading with prefetching
- **Extensible** — Full plugin system with lifecycle, menu, image, and input hooks

---

## Features

### Core

- GPU-accelerated rendering via OpenGL (GLSL 1.20 shaders with VBO)
- Deep zoom image viewing with multi-level image pyramid (512×512 tiles)
- Virtualized tile-based thumbnail grid with lazy loading
- Asynchronous multi-threaded image loading
- Thumbnail disk cache system (NumPy `.npy` format with MD5-based cache keys)
- Prefetching of ±3 adjacent images for smooth browsing
- Undo/Redo system (QUndoStack for edits, legacy stack for deletions)

### Navigation & Viewing

- Folder-based browsing and single image viewing
- **Grid / List (detail) browse modes** — toggle with Ctrl+L
- **Breadcrumb path bar** — clickable segments above the viewer
- Fullscreen + **Theater mode** (Shift+Tab hides all chrome)
- Minimap overlay in deep zoom mode
- RGB histogram overlay
- **F8 OSD** (file info overlay) / **Ctrl+F8 Debug HUD** (VRAM / cache / threads)
- **Pixel view** (Shift+P) — zoom ≥ 400% shows grid + per-pixel RGB/HEX
- **Color modes** (Shift+M) — Normal / Grayscale / Invert / Sepia via GLSL
- Image rotation (including lossless JPEG rotation via piexif)
- Animated GIF/APNG playback with frame-by-frame controls
- Slideshow mode with configurable interval
- **Enhanced compare dialog** — Side-by-side / Overlay (alpha slider) / Difference (gain slider)
- **Split view** (Shift+S) / **Dual-page reading** (Shift+D, Ctrl+Shift+D for RTL/manga)
- **Multi-monitor window** (Ctrl+Shift+M) mirrors current image on secondary display
- **Hover preview popup** — larger preview on tile hover (500 ms delay)
- **Touchpad gestures** — pinch-to-zoom, horizontal swipe to navigate
- **Browsing history** (Alt+←/→) + **Random image** (X)
- **Cross-folder navigation** (Ctrl+Shift+←/→) — jump to next/prev sibling folder
- Fuzzy search with substring highlighting (Ctrl+F / `/`)
- **Go to image** dialog (Ctrl+G) — jump by index
- Auto-loop at folder ends

### Organization

- Bookmark system (up to 5000 bookmarks)
- Rating system (1–5 stars) and favorites
- **Color labels** (F1–F5 → red/yellow/green/blue/purple) — Lightroom-style flags independent of star rating
- Tags & Albums with **multi-tag filter** (AND/OR boolean logic)
- Sort by name, modified date, created date, file size, or resolution
- Filter by file extension, rating, color label, or tag/album
- **Advanced filter** — resolution / file size / orientation / modified date range
- Recent folders and recent images tracking
- Automatic restore of last opened folder on startup
- **Thumbnail status badges** — left-edge colour strip, favorite heart, bookmark star, rating stars
- **Thumbnail density** — Compact / Standard / Relaxed padding
- **File tree extras** — F5 refresh, New Folder, Expand/Collapse All

### Editing & Export

- Built-in image editor (crop, brightness, contrast, saturation, exposure, rotation, flip) with non-destructive preview — edits are previewed live on canvas and only written to disk on explicit Save
- Export/Save As with format conversion (PNG, JPEG, WebP, BMP, TIFF)
- Quality slider for lossy formats (JPEG, WebP)
- Batch operations (rename, move/copy, rotate selected images)
- Set image as desktop wallpaper
- Copy image / image path to clipboard

### Metadata

- EXIF data display in collapsible sidebar
- EXIF editor dialog
- Image info dialog (dimensions, file size, dates)

### Extra Tools

- **Image Sanitizer** — Re-render images from raw pixels to strip ALL hidden data (EXIF, metadata, steganographic content, trailing bytes); rename with date + random string; optionally upscale to common resolutions (1080p / 2K / 4K / 5K / 8K) using traditional methods (Lanczos, Bicubic, Nearest Neighbor) or AI (Real-ESRGAN) while preserving aspect ratio
- **Batch Format Conversion** — Convert images between PNG, JPEG, WebP, BMP, TIFF with quality control
- **AI Image Upscale** — Super-resolution via Real-ESRGAN (x2 / x4 general, x4 anime) with ONNX Runtime (CUDA/DML/CPU), plus traditional lossless methods (Lanczos, Bicubic, Nearest Neighbor); supports folder selection with recursive scanning
- **Duplicate Detection** — Find duplicate images by exact hash or perceptual similarity
- **Image Organizer** — Sort images into subfolders by date, resolution, type, size, or fixed count
- **Batch EXIF Strip** — Remove EXIF, GPS, and metadata from all images in a folder
- **Crop Tool** — Interactive crop with aspect ratio presets (Free / 1:1 / 4:3 / 3:2 / 16:9 / 9:16), rule-of-thirds overlay, and drag handles

### System Integration

- Windows right-click "Open with Imervue" context menu (file association via registry)
- Folder monitoring with QFileSystemWatcher (auto-refresh on changes)
- Multi-language support (5 built-in languages)
- Plugin system with online plugin downloader
- Toast notification system (info, success, warning, error levels)

---

## Supported Image Formats

### Raster Formats

| Format | Extensions |
|--------|-----------|
| PNG | `.png` |
| JPEG | `.jpg`, `.jpeg` |
| BMP | `.bmp` |
| TIFF | `.tiff`, `.tif` |
| WebP | `.webp` |
| GIF | `.gif` (animated) |
| APNG | `.apng` (animated) |

### Vector Formats

| Format | Extensions |
|--------|-----------|
| SVG | `.svg` (rendered via QSvgRenderer, thumbnails downscaled to max 512px) |

### RAW Camera Formats

| Format | Extensions | Camera |
|--------|-----------|--------|
| CR2 | `.cr2` | Canon |
| NEF | `.nef` | Nikon |
| ARW | `.arw` | Sony |
| DNG | `.dng` | Adobe Digital Negative |
| RAF | `.raf` | Fujifilm |
| ORF | `.orf` | Olympus |

RAW files support embedded preview extraction with fallback to half-size processing.

---

## Installation

### Requirements

- Python >= 3.10
- GPU with OpenGL support (software rendering fallback available)

### Install from source

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### Install as package

```bash
pip install .
```

### Dependencies

| Package | Purpose |
|---------|---------|
| PySide6 | Qt6 GUI framework |
| qt-material | Material Design theme |
| Pillow | Image processing |
| PyOpenGL | OpenGL bindings |
| PyOpenGL_accelerate | OpenGL performance optimization |
| numpy | Array operations and thumbnail cache |
| rawpy | RAW image decoding |
| imageio | Image I/O |

---

## Usage

### Basic Launch

```bash
python -m Imervue
```

### Open a specific image

```bash
python -m Imervue /path/to/image.jpg
```

### Open a folder

```bash
python -m Imervue /path/to/folder
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug mode |
| `--software_opengl` | Use software OpenGL rendering (sets `QT_OPENGL=software` and `QT_ANGLE_PLATFORM=warp`). Useful when GPU drivers are unavailable or problematic. |
| `file` | (positional) Image file or folder to open at startup |

---

## Browsing Modes

### Grid Mode (Tile Grid)

When opening a folder, images are displayed in a virtualized thumbnail grid:

- **Lazy loading** — Only visible thumbnails are rendered and loaded
- **Dynamic thumbnail size** — Configurable at 128×128, 256×256, 512×512, 1024×1024, or auto
- **Scroll and zoom** — Navigate large collections smoothly
- **Multi-select** — Click-drag rectangle selection or long-press to enter selection mode
- **Batch operations** — Rename, move/copy, rotate, or delete selected images
- **Disk cache** — Thumbnails cached as `.npy` files with MD5-based invalidation

### Single Image Mode (Deep Zoom)

When opening a single image or double-clicking a thumbnail:

- **Multi-level image pyramid** — Tiles at 512×512 pixels with LANCZOS downsampling
- **LRU tile cache** — Up to 256 tiles cached on GPU (1.5 GB VRAM limit)
- **Smooth pan and zoom** — GPU-accelerated with anisotropic filtering (up to 8x)
- **Minimap overlay** — Shows current viewport position
- **RGB histogram** — Toggle with `H` key
- **Pixel view** (Shift+P) — at ≥ 400 % zoom shows pixel grid and per-pixel RGB / HEX under the cursor
- **Color modes** (Shift+M) — Normal / Grayscale / Invert / Sepia (GLSL, non-destructive)
- **Centered on load** — Fit-to-window by default
- **Adjacent image prefetch** — Preloads ±3 neighboring images

### List Mode (Detail)

Toggle with **Ctrl+L**. Replaces the tile grid with a sortable table:

- Columns: Preview · Label · Name · Resolution · Size · Type · Modified
- Sortable by any column (including colour label)
- Double-click a row to open deep zoom; Esc returns to the list
- Thumbnail / metadata loaded lazily off the UI thread

### Split View & Dual-Page Reading

- **Split View** (Shift+S) — displays two images side by side in the main window
- **Dual Page** (Shift+D) — shows consecutive images as facing pages; arrow keys advance by 2
- **Manga (RTL)** (Ctrl+Shift+D) — dual-page with right-to-left reading order
- Esc returns to the previous mode (Grid or List)

### Multi-Monitor Window

**Ctrl+Shift+M** opens a frameless second top-level window that maximizes onto your
secondary screen and mirrors whichever image the main viewer is showing. The main
window keeps browsing independently.

---

## Keyboard & Mouse Shortcuts

### Navigation (Both Modes)

| Shortcut | Action |
|----------|--------|
| Arrow Keys | Scroll grid / Switch images (Left/Right in deep zoom) |
| Shift + Arrow | Fine-grained scrolling (half step) |
| Ctrl+Shift+←/→ | Jump to previous / next sibling folder with images |
| Alt+← / Alt+→ | History back / forward (browser-style) |
| Ctrl+G | Go to image by index |
| X | Jump to a random image |
| Home | Reset zoom and pan to origin |
| Ctrl+F or / | Open fuzzy search dialog |
| S | Open slideshow dialog |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z / Ctrl+Y | Redo |

### Deep Zoom / Single Image Mode

| Shortcut | Action |
|----------|--------|
| F | Toggle fullscreen |
| Shift+Tab | Toggle **theater mode** (hide all chrome) |
| R | Rotate clockwise |
| Shift+R | Rotate counter-clockwise |
| E | Open image editor |
| W | Fit to width |
| Shift+W | Fit to height |
| H | Toggle RGB histogram overlay |
| F8 | Toggle OSD info overlay (filename / size / type) |
| Ctrl+F8 | Toggle debug HUD (VRAM / cache / threads) |
| Shift+P | Toggle pixel view (≥ 400 % zoom shows grid + RGB) |
| Shift+M | Cycle color modes (Normal / Grayscale / Invert / Sepia) |
| B | Toggle bookmark for current image |
| Ctrl+C | Copy image to clipboard |
| Ctrl+V | Paste image from clipboard |
| 0 | Toggle favorite (heart) |
| 1–5 | Quick rating (1–5 stars) |
| F1–F5 | Quick **color label** (red / yellow / green / blue / purple) |
| Shift+S | Open split view (two images side-by-side) |
| Shift+D | Open dual-page reading (manga/comic) |
| Ctrl+Shift+D | Open dual-page reading in right-to-left order |
| Ctrl+Shift+M | Toggle secondary-display mirror window |
| Delete | Move current image to trash (undoable) |
| Escape | Exit deep zoom / Exit fullscreen / Close dual/list mode |

### Animation Playback (GIF / APNG)

| Shortcut | Action |
|----------|--------|
| Space | Play / Pause |
| , (comma) | Previous frame |
| . (period) | Next frame |
| [ | Decrease playback speed |
| ] | Increase playback speed |

### Tile Grid Mode

| Shortcut | Action |
|----------|--------|
| Arrow Keys | Scroll grid |
| Ctrl+L | Toggle Grid ↔ List (detail) browse mode |
| Hover (500 ms) | Show larger hover preview popup |
| Delete | Delete selected tiles |
| Escape | Deselect all |

### Mouse Controls

| Action | Behavior |
|--------|----------|
| Left Click | Select tile or open image |
| Left Drag | Rectangle multi-select in grid |
| Long Press (500ms) | Enter tile selection mode |
| Middle Mouse Drag | Pan/scroll in deep zoom |
| Scroll Wheel | Zoom in/out or scroll |
| Right Click | Open context menu |

### Touchpad Gestures

| Gesture | Action |
|---------|--------|
| Pinch | Zoom in / out in deep zoom (anchored at pinch centre) |
| Horizontal Swipe | Previous / next image |

---

## Menu Structure

### File

- New Window
- Open Image
- Open Folder
- Recent (submenu: recent folders and images)
- Bookmarks (manage bookmarked images)
- Commit Pending Deletions (finalize undo stack)
- Keyboard Shortcuts (customizable key bindings)
- File Association (Windows only — register/unregister right-click context menu)
- Exit

### Extra Tools

- Batch Format Conversion
- AI Image Upscale
- Find Duplicate Images
- Image Organizer
- Batch EXIF Strip
- Image Sanitizer

### View

- Tile Size: 128×128 / 256×256 / 512×512 / 1024×1024 / Auto
- **Browse Mode**: Grid / List (toggle with Ctrl+L)
- **Thumbnail Density**: Compact / Standard / Relaxed

### Sort

- By Name / By Modified Date / By Created Date / By File Size / By Resolution
- Ascending / Descending

### Filter

- By Extension: All, JPG, PNG, BMP, TIFF, SVG, RAW
- **By Color Label**: All / Any label / No label / Red / Yellow / Green / Blue / Purple
- By Rating: All, Favorited, 1–5 stars
- By Tag (single) / By Album (single)
- **Multi-Tag Filter…** — multi-select tags or albums with AND / OR boolean logic
- **Advanced Filter…** — resolution / file size / orientation / modified-date range
- Clear Filter

### Language

- English / 繁體中文 / 简体中文 / 한국어 / 日本語

### Plugins

- Loaded Plugins (shows each plugin name and version)
- Download Plugins (opens online plugin downloader)
- Open Plugin Folder

### Instructions

- Keyboard & Mouse Shortcuts (detailed shortcut reference dialog)

### Right-Click Context Menu

- Navigation (parent folder, next/previous image)
- Quick actions (show in explorer, copy path, copy image)
- Transformations (rotate CW/CCW, edit image)
- Batch operations (batch rename, move/copy, rotate all)
- Deletion (delete current/selected)
- Set as wallpaper
- Compare / Slideshow
- Export (Save As with format selection)
- Lossless JPEG rotate
- Extra Tools (batch convert, AI upscale, duplicate detection, image organizer, EXIF strip, image sanitizer)
- Bookmarks (add/remove)
- Image info
- Recent menu
- Plugin-contributed items

---

## Plugin System

Imervue supports a plugin system for extending functionality. See the full [Plugin Development Guide](PLUGIN_DEV_GUIDE.md) for details.

### Quick Start

1. Create a folder inside `plugins/` at the project root
2. Define a class extending `ImervuePlugin`
3. Register it in `__init__.py` with `plugin_class = YourPlugin`
4. Restart Imervue

### Available Hooks

| Hook | Trigger |
|------|---------|
| `on_plugin_loaded()` | After plugin is instantiated |
| `on_plugin_unloaded()` | At app shutdown |
| `on_build_menu_bar(menu_bar)` | After default menu bar is built |
| `on_build_context_menu(menu, viewer)` | When right-click menu opens |
| `on_image_loaded(path, viewer)` | After image loads in deep zoom |
| `on_folder_opened(path, images, viewer)` | After folder opens in grid |
| `on_image_switched(path, viewer)` | When navigating between images |
| `on_image_deleted(paths, viewer)` | After image(s) are soft-deleted |
| `on_key_press(key, modifiers, viewer)` | On key press (return True to consume) |
| `on_app_closing(main_window)` | Before application closes |
| `get_translations()` | Provide i18n strings |

### Plugin Downloader

Plugins can be downloaded from the official repository via **Plugins > Download Plugins**. The downloader fetches from [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins) on GitHub.

---

## Multi-Language Support

### Built-In Languages

| Language | Code |
|----------|------|
| English | `English` |
| 繁體中文 (Traditional Chinese) | `Traditional_Chinese` |
| 简体中文 (Simplified Chinese) | `Chinese` |
| 한국어 (Korean) | `Korean` |
| 日本語 (Japanese) | `Japanese` |

Language can be changed from the **Language** menu. A restart is required for the change to take effect.

### Adding Languages via Plugins

Plugins can register entirely new languages using `language_wrapper.register_language()`, or add translations for existing languages via `get_translations()`. See the [Plugin Development Guide](PLUGIN_DEV_GUIDE.md#internationalization-i18n) for details.

---

## User Settings

Settings are stored in `user_setting.json` in the working directory.

| Setting | Type | Description |
|---------|------|-------------|
| `language` | string | Current language code |
| `user_recent_folders` | list | Recently opened folders |
| `user_recent_images` | list | Recently opened images |
| `user_last_folder` | string | Last opened folder (auto-restored on startup) |
| `bookmarks` | list | Bookmarked image paths (max 5000) |
| `sort_by` | string | Sort method (name/modified/created/size/resolution) |
| `sort_ascending` | bool | Sort order |
| `image_ratings` | dict | Image path → rating (1–5) mapping |
| `image_favorites` | set | Favorited image paths |
| `image_color_labels` | dict | Image path → color name (`red`/`yellow`/`green`/`blue`/`purple`) |
| `thumbnail_size` | int/null | Grid thumbnail size (128/256/512/1024/null for auto) |
| `tile_padding` | int | Thumbnail grid padding in px (0 compact / 8 standard / 16 relaxed) |
| `navigation_auto_loop` | bool | Wrap around when pressing Right/Left at folder ends (default `true`) |
| `keyboard_shortcuts` | dict | Custom `action_id → [key, modifiers]` overrides |
| `window_geometry` | string | Base64-encoded window geometry (saved on close) |
| `window_state` | string | Base64-encoded window state (dock / toolbar layout) |
| `window_maximized` | bool | Whether the window was maximized on last close |

---

## Architecture

```
Imervue/
├── __main__.py              # Application entry point
├── Imervue_main_window.py   # Main window (QMainWindow)
├── gpu_image_view/          # GPU-accelerated viewer
│   ├── gpu_image_view.py    # Main viewer widget (QOpenGLWidget)
│   ├── gl_renderer.py       # OpenGL shader-based renderer
│   ├── actions/             # Viewer actions (zoom, pan, rotate, etc.)
│   └── images/              # Image loading, pyramid, tile management
├── gui/                     # UI components
│   ├── ai_upscale_dialog.py # AI super-resolution (Real-ESRGAN)
│   ├── annotation_dialog.py # Annotation canvas + crop tool
│   ├── batch_convert_dialog.py # Batch format conversion
│   ├── bookmark_dialog.py   # Bookmark manager dialog
│   ├── develop_panel.py     # Edit/develop panel
│   ├── duplicate_detection_dialog.py # Duplicate image finder
│   ├── exif_editor.py       # EXIF metadata editor
│   ├── exif_sidebar.py      # Collapsible EXIF sidebar
│   ├── exif_strip_dialog.py # Batch EXIF strip
│   ├── export_dialog.py     # Export/Save As dialog
│   ├── image_editor.py      # Image editor (crop, adjust, rotate)
│   ├── image_organizer_dialog.py # Image sorter/organizer
│   ├── image_sanitize_dialog.py  # Image sanitizer + AI upscale
│   ├── shortcut_settings_dialog.py # Custom keyboard shortcuts
│   └── toast.py             # Toast notification system
├── image/                   # Image utilities
│   ├── info.py              # Image info extraction
│   ├── pyramid.py           # Deep zoom image pyramid
│   ├── thumbnail_disk_cache.py  # Thumbnail cache (MD5 + .npy)
│   └── tile_manager.py      # Tile grid management
├── menu/                    # Menu definitions
│   ├── extra_tools_menu.py  # Extra Tools menu
│   ├── file_menu.py         # File menu
│   ├── filter_menu.py       # Filter menu
│   ├── language_menu.py     # Language menu
│   ├── plugin_menu.py       # Plugins menu
│   ├── recent_menu.py       # Recent items submenu
│   ├── right_click_menu.py  # Context menu
│   ├── sort_menu.py         # Sort menu
│   └── tip_menu.py          # Instructions menu
├── multi_language/          # i18n
│   ├── language_wrapper.py  # Language singleton manager
│   ├── english.py           # English translations
│   ├── chinese.py           # Simplified Chinese
│   ├── traditional_chinese.py  # Traditional Chinese
│   ├── korean.py            # Korean
│   └── japanese.py          # Japanese
├── plugin/                  # Plugin system
│   ├── plugin_base.py       # ImervuePlugin base class
│   ├── plugin_manager.py    # Plugin discovery and lifecycle
│   └── plugin_downloader.py # Online plugin downloader
├── system/                  # System integration
│   └── file_association.py  # Windows file association (registry)
└── user_settings/           # User configuration
    ├── user_setting_dict.py # Settings I/O (thread-safe)
    ├── bookmark.py          # Bookmark management
    └── recent_image.py      # Recent images tracking
```

### Rendering Pipeline

1. **OpenGL Context** — `GPUImageView` extends `QOpenGLWidget`
2. **Shader Programs** — Two GLSL 1.20 programs (textured quads + solid color rectangles)
3. **Texture Management** — LRU cache with 256-tile limit and 1.5 GB VRAM budget
4. **Deep Zoom Pyramid** — Multi-level tile pyramid built with LANCZOS resampling at 512×512 tile size
5. **Anisotropic Filtering** — Up to 8x when hardware supports it
6. **Fallback** — Immediate mode rendering if shader compilation fails

### Thumbnail Cache

- **Key**: MD5 hash of `{path}|{mtime_ns}|{file_size}|{thumbnail_size}`
- **Format**: NumPy `.npy` binary (fast I/O, no compression overhead)
- **Location**: `%LOCALAPPDATA%/Imervue/cache/thumbnails` (Windows) or `~/.cache/imervue/thumbnails` (Linux/macOS)
- **Invalidation**: Automatic when file metadata changes

---

## License

This project is licensed under the [MIT License](LICENSE).

Copyright (c) 2026 JE-Chen
