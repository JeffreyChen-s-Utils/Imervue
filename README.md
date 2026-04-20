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
- Thumbnail disk cache system (compressed PNG with MD5-based cache keys)
- Prefetching of ±3 adjacent images for smooth browsing
- Undo/Redo system (QUndoStack for edits, legacy stack for deletions)

### Navigation & Viewing

- Folder-based browsing and single image viewing
- **Grid / List (detail) browse modes** — toggle with Ctrl+L; the list view shows name, size, modified date, dimensions, and a dedicated star-rating column
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
- **Enhanced compare dialog** — Side-by-side / Overlay (alpha slider) / Difference (gain slider) / **A|B Split** before/after tab with a draggable divider
- **Split view** (Shift+S) / **Dual-page reading** (Shift+D, Ctrl+Shift+D for RTL/manga)
- **Multi-monitor window** (Ctrl+Shift+M) mirrors current image on secondary display
- **Hover preview popup** — larger preview on tile hover (500 ms delay)
- **Touchpad gestures** — pinch-to-zoom, horizontal swipe to navigate
- **Browsing history** (Alt+←/→) + **Random image** (X)
- **Cross-folder navigation** (Ctrl+Shift+←/→) — jump to next/prev sibling folder
- Fuzzy search with substring highlighting (Ctrl+F / `/`)
- **Go to image** dialog (Ctrl+G) — jump by index
- **Command Palette** (Ctrl+Shift+P) — fuzzy-search every menu action in one dialog
- Auto-loop at folder ends

### Organization

- Bookmark system (up to 5000 bookmarks)
- Rating system (1–5 stars) and favorites
- **Color labels** (F1–F5 → red/yellow/green/blue/purple) — Lightroom-style flags independent of star rating
- **Culling workflow** (P / Shift+X / U → Pick / Reject / Unflag) — Lightroom-style 3-state flag with Filter > By Cull State and bulk delete-rejects
- **Hierarchical tags** — tree-structured paths like `animal/cat/british`, descendants searched automatically
- Tags & Albums with **multi-tag filter** (AND/OR boolean logic)
- **Smart Albums** — save rule-based filter queries (extensions, min resolution, rating, color, cull, tags…) and reapply them in one click
- **Timeline view** — Google-Photos-style grouping by day / month / year (EXIF DateTimeOriginal falling back to mtime)
- **Similar-image search** via 64-bit DCT pHash with Hamming distance threshold
- **Per-image notes** in the EXIF sidebar — free-text, debounced save, persisted across sessions
- **Staging tray** — cross-folder basket that survives restarts; bulk move/copy/export
- **Dual-pane file manager** — Total Commander-style two-tree view with move/copy between panes
- Sort by name, modified date, created date, file size, or resolution
- Filter by file extension, rating, color label, cull state, or tag/album
- **Advanced filter** — resolution / file size / orientation / modified date range
- **Stack RAW+JPEG pairs** — collapse shoot-in-RAW+JPEG captures into one tile; the preview is shown while the RAW stays accessible as a sibling
- **Session / Workspace save & restore** — snapshot current tabs, active image, selection, and filter state to a `.imervue-session.json` file and reload later
- **Workspace layout presets** — save named window layouts (geometry, dock / toolbar state, splitter sizes, active folder) via File > Workspaces… and flip between Browse / Develop / Export arrangements without rearranging panels every time
- **Macro record / replay** — capture rating / favorite / color / tag actions and reapply them to any selection (Alt+M replays the last macro)
- Recent folders and recent images tracking
- Automatic restore of last opened folder on startup
- **Thumbnail status badges** — left-edge colour strip, favorite heart, bookmark star, rating stars
- **Thumbnail density** — Compact / Standard / Relaxed padding
- **File tree extras** — F5 refresh, New Folder, Expand/Collapse All
- **Drag-out to external apps** — press and drag a selected tile into Explorer / Chrome / Discord

### Editing & Export

- Built-in image editor (crop, brightness, contrast, saturation, exposure, rotation, flip) with non-destructive preview — edits are previewed live on canvas and only written to disk on explicit Save
- **Develop panel sliders** — white balance (temperature / tint), tonal regions (shadows / midtones / highlights), and vibrance in addition to the classic exposure / contrast / saturation controls; every edit remains non-destructive via per-image recipes
- **Watermark overlay** — place a text or image watermark with configurable position (9 anchors), opacity, and scale; applied on export without touching the original pixels
- **Export presets** — one-click pipelines for common targets: Web 1600 (long-edge 1600 px JPEG), Print 300 dpi (full-resolution, color-managed), Instagram 1080 (square / portrait crop at 1080 px)
- Export/Save As with format conversion (PNG, JPEG, WebP, BMP, TIFF)
- Quality slider for lossy formats (JPEG, WebP)
- Batch operations (rename, move/copy, rotate selected images)
- **Contact Sheet PDF** — grid of thumbnails with captions, configurable rows/columns and page size (A4 / A3 / Letter / Legal)
- **Web Gallery HTML** — self-contained folder with `index.html`, JPEG thumbnails, inline lightbox; optional copy-originals for portability
- **Slideshow MP4** — render image sequences to H.264 video with configurable FPS, hold-per-image, and fade transitions (requires `imageio-ffmpeg`)
- **External editor integration** — register programs (e.g. GIMP, Photoshop) and launch them on the current image from File > Open in External Editor
- Set image as desktop wallpaper
- Copy image / image path to clipboard

### Metadata

- EXIF data display in collapsible sidebar, including a **star-rating strip** that edits the image's 0–5 rating in place
- EXIF editor dialog
- Image info dialog (dimensions, file size, dates)
- **XMP sidecar** (`.xmp` companion files) — import / export ratings, title, description, keywords, and color labels for round-trip interop with Adobe Lightroom and Capture One (safe XML parsing via `defusedxml`)

### Extra Tools

- **Image Sanitizer** — Re-render images from raw pixels to strip ALL hidden data (EXIF, metadata, steganographic content, trailing bytes); rename with date + random string; optionally upscale to common resolutions (1080p / 2K / 4K / 5K / 8K) using traditional methods (Lanczos, Bicubic, Nearest Neighbor) or AI (Real-ESRGAN) while preserving aspect ratio
- **Batch Format Conversion** — Convert images between PNG, JPEG, WebP, BMP, TIFF with quality control
- **AI Image Upscale** — Super-resolution via Real-ESRGAN (x2 / x4 general, x4 anime) with ONNX Runtime (CUDA/DML/CPU), plus traditional lossless methods (Lanczos, Bicubic, Nearest Neighbor); supports folder selection with recursive scanning
- **Duplicate Detection** — Find duplicate images by exact hash or perceptual similarity
- **Image Organizer** — Sort images into subfolders by date, resolution, type, size, or fixed count
- **Batch EXIF Strip** — Remove EXIF, GPS, and metadata from all images in a folder
- **Crop Tool** — Interactive crop with aspect ratio presets (Free / 1:1 / 4:3 / 3:2 / 16:9 / 9:16), rule-of-thirds overlay, and drag handles
- **Library Search** — SQLite index with multi-root scanning; query by extension, size, dimensions, filename
- **Smart Albums** — save & reapply rule-based filter queries
- **Find Similar Images** — pHash-based search with adjustable Hamming distance
- **Semantic Search (CLIP)** — query the library with natural language ("golden retriever in snow", "neon street at night") via a CLIP text/image embedding index; embeddings are cached to an `.npz` archive and queried with an O(N) cosine scan. Requires optional dependencies `open_clip_torch` + `torch`; the feature degrades gracefully when they are absent.
- **Auto-Tag Images** — heuristic (photo / document / screenshot / landscape / portrait) with optional CLIP ONNX upgrade
- **Hierarchical Tags** manager — tree-structured tag paths with bulk assign/untag
- **Token Batch Rename** — live-preview templates like `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **Export Metadata (CSV / JSON)** — one row per image with EXIF, cull, rating, tags, notes
- **Culling** dialog — filter by Pick / Reject / Unflagged, bulk delete all rejects
- **Staging Tray** — cross-folder basket for batch move/copy/export
- **Dual-Pane File Manager** — Total Commander-style two-tree view
- **Timeline View** — day / month / year groupings of the current image set
- **Macros** — record/replay batches of rating / favorite / color-label / tag actions across selections
- **Contact Sheet PDF** — multi-page PDF with grid layout and filename captions
- **Web Gallery** — static HTML gallery with thumbnails + lightbox
- **Slideshow Video** — MP4 export with fade transitions
- **Tone Curve editor** — draggable-points RGB and per-channel (R/G/B) curves with monotone cubic interpolation; stored on the recipe so curves apply non-destructively
- **Apply .cube LUT** — pick any Adobe 3D LUT (up to 64³), trilinear-interpolate, and blend with an intensity slider; results persist on the recipe
- **Virtual Copies** — named recipe snapshots per image. Try a look, snap it, continue editing, and swap back any time — all variants live in the recipe store alongside the master
- **HDR Merge** — combine 2+ bracketed exposures via OpenCV's Mertens exposure fusion (with optional AlignMTB pre-alignment); writes a single merged image
- **Panorama Stitch** — stitch overlapping frames via OpenCV's `Stitcher` in panorama or scans mode, with black-border auto-crop
- **Focus Stacking** — fuse shots at different focus distances (Laplacian-variance focus map + Gaussian blending) for macro / product work, with optional ECC alignment
- **Healing Brush** — click-to-add circular spots over the image; applies OpenCV inpainting (Telea or Navier-Stokes) and saves a cleaned copy
- **Lens Correction** — pure-numpy radial distortion (barrel / pincushion), vignette lift, and per-channel chromatic-aberration correction with a 4-slider preview
- **Map View** — plot geotagged images on an interactive Leaflet + OpenStreetMap map (QtWebEngine); falls back to a coordinate list when WebEngine is absent
- **Calendar View** — browse the library by capture date; days with photos are highlighted on a `QCalendarWidget`, selecting a day lists its shots
- **Face Detection** — OpenCV Haar frontal-face cascade surfaces faces in the current image; naming each face persists into the recipe's `extra` blob
- **Local Adjustment Masks** — brush / radial / linear gradient masks with per-mask exposure, brightness, contrast, saturation, white-balance deltas and a feather slider; stored on the recipe and blended non-destructively
- **Split Toning** — Lightroom-style shadow/highlight hue + saturation with a balance pivot; writes to recipe.extra and applies in the develop pipeline
- **Clone Stamp** — shift+click source, click destination with a feathered source-to-destination blit (complements the healing brush)
- **Crop / Straighten** — normalised crop rectangle plus arbitrary-angle straighten that auto-crops to the largest inner rect (no black corners)
- **Auto-Straighten** — Hough-line horizon/vertical detection computes the rotation to level tilted horizons or buildings, with one click to apply
- **Noise Reduction / Sharpening** — edge-preserving bilateral denoise (optionally luminance-only) plus unsharp-mask sharpening with amount/radius/threshold
- **Sky / Background** — replace detected sky with a gradient or remove the background (transparent or white fill); optional rembg/U²-Net when installed
- **Soft Proof** — load an ICC profile, simulate the destination gamut, and highlight out-of-gamut pixels in magenta
- **GPS Geotag editor** — read existing EXIF GPS coordinates and write new lat/lon back via piexif (JPEG)
- **Print Layout** — compose multiple images onto a multi-page PDF sheet with configurable page size (A4/A3/Letter/Legal), orientation, grid, margins, gutter, and crop marks

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
| imageio-ffmpeg | Slideshow MP4 export (H.264 via ffmpeg) |

Optional (feature-gated; omit to disable the feature cleanly):

| Package | Purpose |
|---------|---------|
| open_clip_torch + torch | CLIP semantic search (natural-language image queries) |
| onnxruntime | Real-ESRGAN AI upscale / CLIP ONNX auto-tag |

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
| Ctrl+Shift+P | Open **Command Palette** (fuzzy-search menu actions) |
| Alt+M | Replay last macro on current selection |
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
| P | **Cull: Pick** (flag for keep) |
| Shift+X | **Cull: Reject** |
| U | **Cull: Unflag** |
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
- Tags & Albums
- Commit Pending Deletions (finalize undo stack)
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association (Windows only — register/unregister right-click context menu)
- **Session** (submenu: Save Session… / Load Session…)
- **Workspaces…** — save / load / rename / delete named window layouts
- **External Editors…** — configure executables (name, path, arguments)
- **Open in External Editor** — submenu listing configured editors
- Keyboard Shortcuts (customizable key bindings)
- Exit

### Extra Tools

Organised into 8 function-grouped submenus:

- **Batch** — Batch Format Conversion · Batch EXIF Strip · Image Sanitizer · Image Organizer · Token Batch Rename
- **Library & Metadata** — Library Search (SQLite multi-root index) · Smart Albums · Find Similar Images (pHash) · Find Duplicate Images · Auto-Tag Images (heuristic + optional CLIP ONNX) · Hierarchical Tags · Export Metadata (CSV / JSON) · XMP Sidecars · GPS Geotag
- **Views** — Timeline View ▸ (by day / month / year) · Calendar View · Map View
- **Workflow** — Culling · Staging Tray · Virtual Copies · Dual-Pane File Manager · Macros
- **Export** — Contact Sheet PDF · Web Gallery · Slideshow Video (MP4) · Print Layout
- **Develop (Non-Destructive)** — Tone Curve · Apply .cube LUT · Split Toning · Local Adjustment Masks · Soft Proof
- **Retouch & Transform** — AI Image Upscale · Noise Reduction / Sharpening · Healing Brush · Clone Stamp · Face Detection · Sky / Background · Crop / Straighten · Auto-Straighten · Lens Correction
- **Multi-Image** — HDR Merge · Panorama Stitch · Focus Stacking

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
- **By Cull State**: All / Picks only / Rejects only / Unflagged only
- **Stack RAW+JPEG pairs** (toggle) — collapse same-stem RAW/preview captures into one tile
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
| `stack_raw_jpeg_pairs` | bool | Collapse RAW+JPEG pairs sharing a filename stem into one tile |
| `external_editors` | list | Configured editors (`[{name, executable, arguments}]`) |
| `macros` | list | Saved macros (`[{name, steps[], created_at}]`) |
| `macro_last_name` | string | Name of the most recently saved macro (used by Alt+M) |

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
│   ├── command_palette.py   # Ctrl+Shift+P fuzzy action finder
│   ├── contact_sheet_dialog.py # Contact sheet PDF export dialog
│   ├── develop_panel.py     # Edit/develop panel
│   ├── duplicate_detection_dialog.py # Duplicate image finder
│   ├── exif_editor.py       # EXIF metadata editor
│   ├── exif_sidebar.py      # Collapsible EXIF sidebar
│   ├── exif_strip_dialog.py # Batch EXIF strip
│   ├── export_dialog.py     # Export/Save As dialog
│   ├── external_editors_settings.py # External editor config dialog
│   ├── image_editor.py      # Image editor (crop, adjust, rotate)
│   ├── image_organizer_dialog.py # Image sorter/organizer
│   ├── image_sanitize_dialog.py  # Image sanitizer + AI upscale
│   ├── macro_manager_dialog.py # Macro record/compose/replay dialog
│   ├── shortcut_settings_dialog.py # Custom keyboard shortcuts
│   ├── slideshow_mp4_dialog.py # Slideshow MP4 export dialog
│   ├── web_gallery_dialog.py # Web gallery HTML export dialog
│   └── toast.py             # Toast notification system
├── external/                # External tool integration
│   └── editors.py           # Editor config + subprocess launcher
├── export/                  # Export generators (non-Qt logic)
│   ├── contact_sheet.py     # PDF contact sheet (QPdfWriter + QPainter)
│   ├── web_gallery.py       # Static HTML gallery + thumbnails
│   └── slideshow_mp4.py     # MP4 slideshow via imageio-ffmpeg
├── macros/                  # Macro record / replay
│   └── macro_manager.py     # Singleton manager + action registry
├── sessions/                # Workspace serialization
│   └── session_manager.py   # Capture / save / restore session snapshot
├── library/                 # Library helpers
│   └── stacks.py            # RAW+JPEG stack grouping
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
- **Format**: Compressed PNG (`compress_level=1` — fast write, small footprint, migrated from legacy `.npy` which is cleaned up on first access)
- **Location**: `%LOCALAPPDATA%/Imervue/cache/thumbnails` (Windows) or `~/.cache/imervue/thumbnails` (Linux/macOS)
- **Invalidation**: Automatic when file metadata changes

---

## License

This project is licensed under the [MIT License](LICENSE).

Copyright (c) 2026 JE-Chen
