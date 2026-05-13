<p align="center">
  <img src="Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  A GPU-accelerated image viewer / developer / paint studio / puppet animator built with PySide6 and OpenGL
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
- [Installation](#installation)
- [Usage](#usage)
- [Imervue — Image viewer & library](#imervue--image-viewer--library)
- [Modify — Non-destructive develop](#modify--non-destructive-develop)
- [Paint — MediBang-style raster editor](#paint--medibang-style-raster-editor)
- [Puppet — 2D rigged animation](#puppet--2d-rigged-animation)
- [Keyboard & Mouse Shortcuts](#keyboard--mouse-shortcuts)
- [Menu Structure](#menu-structure)
- [Plugin System](#plugin-system)
- [MCP Server](#mcp-server)
- [Multi-Language Support](#multi-language-support)
- [User Settings](#user-settings)
- [Architecture](#architecture)
- [License](#license)

---

## Overview

Imervue is a GPU-accelerated image workstation that ships **four top-level tabs**:

| Tab | What it does |
|---|---|
| **Imervue** | Browse, view, organize, search, and batch-process your image library |
| **Modify** | Non-destructive develop pipeline — sliders, curves, LUTs, masks, retouch, multi-image |
| **Paint** | MediBang-style raster paint studio with brushes, layers, animation, manga tools, PSD I/O |
| **Puppet** | From-scratch 2D rigged-puppet animator — meshes, deformers, parameters, motions, physics |

Design principles:

- **Performance first** — GPU-accelerated rendering with modern GLSL shaders and VBO
- **Large collection support** — Virtualized tile grid loads only visible thumbnails
- **Smooth experience** — Asynchronous multi-threaded image loading with prefetching
- **Non-destructive develop** — Every adjustment lives on a per-image recipe; the file on disk is never overwritten until you explicitly export
- **Extensible** — Full plugin system with lifecycle / menu / image / input hooks; MCP server exposes Qt-free pure-logic tools to AI assistants

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
| defusedxml | Safe XML parsing (XMP sidecars) |

Optional (feature-gated; omit to disable the feature cleanly):

| Package | Purpose |
|---------|---------|
| open_clip_torch + torch | CLIP semantic search (natural-language image queries) |
| onnxruntime | Real-ESRGAN AI upscale / CLIP ONNX auto-tag |
| opencv-python | HDR merge, panorama stitch, focus stacking, face detection, healing brush |
| sounddevice | Puppet lip-sync from microphone |
| mediapipe | Puppet webcam face tracking |

---

## Usage

### Basic launch

```bash
python -m Imervue
```

### Open a specific image or folder

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### Command-line options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug mode |
| `--software_opengl` | Use software OpenGL rendering (sets `QT_OPENGL=software` and `QT_ANGLE_PLATFORM=warp`) |
| `file` | (positional) Image file or folder to open at startup |

---

## Imervue — Image viewer & library

The **Imervue** tab is the default landing surface. It pairs the image viewer with the folder tree, EXIF sidebar, and library/organization tools.

### Viewer

- **GPU-accelerated rendering** via OpenGL (GLSL 1.20 shaders with VBO)
- **Deep-zoom pyramid** — multi-level tiles at 512×512 with LANCZOS resampling, LRU cache up to 256 tiles / 1.5 GB VRAM budget, anisotropic filtering up to 8×
- **Asynchronous loading** — multi-threaded decode with ±3-image prefetch
- **Virtualized thumbnail grid** — only visible tiles are rendered; thumbnail size is configurable (128 / 256 / 512 / 1024 / auto)
- **Disk cache** — compressed PNG thumbnails with MD5-based invalidation under `%LOCALAPPDATA%/Imervue/cache/thumbnails` (or `~/.cache/imervue/thumbnails`)
- **Animation playback** — GIF / APNG with play / pause / frame-step / speed controls

### Browsing modes

- **Grid** (default) — virtualized tile grid with hover-preview popup (500 ms delay)
- **List (detail)** — toggle with `Ctrl+L`; columns: Preview · Label · Name · Resolution · Size · Type · Modified
- **Deep Zoom** — double-click a tile; smooth GPU pan/zoom with minimap overlay
- **Split View** (`Shift+S`) — two images side by side
- **Dual-Page Reading** (`Shift+D`, `Ctrl+Shift+D` for right-to-left manga) — facing-page reader
- **Multi-Monitor mirror** (`Ctrl+Shift+M`) — secondary-display window
- **Theater Mode** (`Shift+Tab`) — hide all chrome
- **Compare dialog** — Side-by-side / Overlay (alpha slider) / Difference (gain slider) / A|B split with draggable divider
- **Timeline / Calendar / Map** views — group library by capture date, browse on a calendar, plot geotagged shots on Leaflet + OpenStreetMap

### On-screen overlays

- RGB histogram (`H`)
- F8 OSD (filename / size / type), Ctrl+F8 debug HUD (VRAM / cache / threads)
- Pixel view (`Shift+P`) — ≥ 400 % zoom shows pixel grid + per-pixel RGB / HEX
- Color modes (`Shift+M`) — Normal / Grayscale / Invert / Sepia via GLSL

### Navigation

- Arrow keys, browser-style history (`Alt+←/→`), random jump (`X`)
- Cross-folder navigation (`Ctrl+Shift+←/→`)
- Go-to-image-by-index (`Ctrl+G`)
- Fuzzy search (`Ctrl+F` / `/`)
- **Command Palette** (`Ctrl+Shift+P`) — fuzzy-search every menu action
- Auto-loop at folder ends
- Touchpad pinch-zoom + horizontal-swipe-to-navigate

### Organization

- **Bookmarks** — up to 5000 paths
- **Ratings** — 0-5 stars (`1`–`5`) + favorite heart (`0`)
- **Color labels** — Lightroom-style red/yellow/green/blue/purple (`F1`–`F5`)
- **Culling** — Lightroom 3-state flag (`P` = pick, `Shift+X` = reject, `U` = unflag); filter by state; bulk delete-rejects
- **Hierarchical tags** — tree paths like `animal/cat/british`; descendants matched automatically
- **Tags & Albums** with multi-tag AND/OR filtering
- **Smart Albums** — save rule-based queries (extension / resolution / rating / color / cull / tags) and reapply with one click
- **Stack RAW+JPEG pairs** — collapse same-stem captures into one tile; RAW stays accessible as a sibling
- **Per-image notes** in the EXIF sidebar — debounced save, persists across sessions
- **Staging Tray** — cross-folder basket that survives restarts; bulk move / copy / export
- **Dual-Pane File Manager** — Total Commander-style two-tree view
- **Sessions / Workspace Layouts** — snapshot tabs / selection / filter / dock geometry to `.imervue-session.json`; save named layouts for Browse / Develop / Export arrangements
- **Macros** — record / replay batches of rating / favorite / color / tag actions (`Alt+M` replays the last macro)
- **Thumbnail badges + density** — colour strip, favorite, bookmark, rating stars; Compact / Standard / Relaxed padding
- **Drag-out to external apps** — drag a tile straight into Explorer / Chrome / Discord
- **Recent folders / images** tracked; last folder auto-restored on startup

### Sort & filter

- Sort by name / modified / created / size / resolution (asc or desc)
- Filter by extension, color label, rating, tag/album, cull state
- **Advanced filter** — resolution / file size / orientation / modified-date range
- **Multi-tag filter** dialog with AND / OR boolean logic

### Search

- **Fuzzy filename search** with substring highlighting
- **Find Similar Images** — pHash (64-bit DCT) with adjustable Hamming distance
- **Library Search** — SQLite multi-root index queryable by extension / size / dimensions / filename
- **Semantic Search (CLIP)** — natural-language queries ("golden retriever in snow") via cached embeddings; gracefully unavailable when `open_clip_torch` + `torch` aren't installed
- **Auto-Tag** — heuristic classification with optional CLIP ONNX upgrade

### Metadata

- **EXIF sidebar** with collapsible groups + inline 0-5 star strip
- **EXIF editor** dialog
- **Image info** dialog (dimensions / size / dates)
- **XMP sidecars** (`.xmp` companions) — rating / title / description / keywords / color label round-trip for Lightroom / Capture One interop (safe XML via `defusedxml`)
- **GPS Geotag editor** — read existing EXIF GPS, write new lat/lon via piexif (JPEG)
- **Token Batch Rename** — live-preview templates like `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **Export Metadata CSV / JSON** — one row per image including cull / rating / tags / notes

### Extra Tools (Imervue tab — batch processing)

Accessed from **Tools** menu; organised into function-grouped submenus:

- **Batch** — Format Conversion · EXIF Strip · Image Sanitizer (re-render to strip hidden data) · Image Organizer (sort into subfolders by date / resolution / type / size) · Token Batch Rename
- **AI / Heuristic** — AI Image Upscale (Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU) · Find Duplicate Images · Find Similar Images · Auto-Tag · Face Detection (Haar cascade)
- **Library & Metadata** — Library Search · Smart Albums · Hierarchical Tags · Export Metadata · XMP Sidecars · GPS Geotag

### System integration

- Windows right-click **Open with Imervue** context menu (registry-based file association)
- Folder monitoring with `QFileSystemWatcher` (auto-refresh on change)
- Toast notification system (info / success / warning / error)
- Plugin system with online plugin downloader (see [Plugin System](#plugin-system))

---

## Modify — Non-destructive develop

The **Modify** tab is the develop workstation. Every adjustment lives on a per-image **recipe** stored alongside the file — the original pixels on disk are never overwritten until you explicitly **Export** or **Save As**.

### Develop sliders

- White balance — temperature / tint
- Tonal regions — shadows / midtones / highlights
- Exposure / contrast / saturation / vibrance
- Crop, rotation, horizontal / vertical flip
- All edits remain non-destructive and round-trip through the recipe store

### Curves & LUTs

- **Tone Curve editor** — draggable RGB curve plus per-channel R / G / B with monotone cubic interpolation
- **Apply .cube LUT** — load any Adobe 3D LUT (up to 64³), trilinear-interpolate, blend with an intensity slider
- **Split Toning** — Lightroom-style shadow / highlight hue + saturation with a balance pivot

### Local adjustments

- **Brush / radial / linear gradient masks** with per-mask exposure / brightness / contrast / saturation / white-balance deltas + feather slider
- Masks blend non-destructively through the develop pipeline

### Retouch & transform

- **Healing Brush** — circular spots, OpenCV inpainting (Telea or Navier-Stokes)
- **Clone Stamp** — Shift+click source, feathered blit to destination
- **Crop / Straighten** — normalised crop rectangle plus arbitrary-angle straighten that auto-crops to the largest inner rect
- **Auto-Straighten** — Hough-line horizon / vertical detection
- **Lens Correction** — pure-numpy radial distortion (barrel / pincushion), vignette lift, per-channel chromatic-aberration
- **Noise Reduction / Sharpening** — edge-preserving bilateral denoise + unsharp-mask sharpening
- **Sky / Background** — replace detected sky with gradient or remove background (transparent or white fill); optional `rembg` / U²-Net upgrade

### Multi-image

- **HDR Merge** — combine bracketed exposures via OpenCV Mertens fusion (with AlignMTB pre-alignment)
- **Panorama Stitch** — OpenCV `Stitcher` in panorama or scans mode, black-border auto-crop
- **Focus Stacking** — Laplacian-variance focus map + Gaussian blend with optional ECC alignment

### Output

- **Watermark overlay** — text or image, 9 anchor positions, opacity, scale; applied on export only
- **Export presets** — Web 1600 / Print 300 dpi / Instagram 1080 one-click pipelines
- **Save As / Export** — PNG / JPEG / WebP / BMP / TIFF with quality slider for lossy formats
- **Batch operations** — rename, move/copy, rotate selected images
- **Contact Sheet PDF** — multi-page grid with captions (A4 / A3 / Letter / Legal)
- **Web Gallery HTML** — self-contained folder with `index.html` + JPEG thumbs + inline lightbox
- **Slideshow MP4** — H.264 video with configurable FPS / hold-per-image / fade transitions (`imageio-ffmpeg`)
- **Print Layout** — multi-page PDF sheet with configurable page size / orientation / grid / margins / gutter / crop marks
- **Soft Proof** — load an ICC profile, simulate destination gamut, highlight out-of-gamut pixels in magenta
- **Virtual Copies** — named recipe snapshots per image; flip between looks without losing the master

### External editors

Register programs (GIMP / Photoshop / Affinity / …) under **File > External Editors…** and launch them on the current image via **File > Open in External Editor**.

---

## Paint — MediBang-style raster editor

The **Paint** tab is a full-featured raster paint studio embedded as its own `QMainWindow` with menus, left tool strip, context-sensitive options bar, and a tabbed right-side dock column. Multi-tab document editing — open many drawings at once, each with its own undo stack.

### Tools (24)

Brush · Eraser · Fill · Eyedropper · Rect / Lasso / Wand / Quick Select · Move · Text · Gradient · Blur · Smudge · Pen · Clone Stamp · Speech Bubble · Rectangle · Ellipse · Line · Polygon · Crop · Transform · Hand · Zoom

Single-letter shortcuts: `B / E / G / I / V / T / U / R / P / S / C / Z / H`; `Shift+R/E/I/P` for shape variants.

### Brushes

Pen / marker / pencil / highlighter / spray / calligraphy / watercolor / charcoal / crayon, with Size / Opacity / Hardness / Density / Blend-mode controls. Pressure-curve editor, brush-tip capture from a selection, import / export brush presets.

### Layers

Full layer panel with thumbnails, visibility toggles, drag-to-reorder, blend modes, opacity, search, vector layers, 1-bit layers, **layer masks** (add / from selection / invert / apply), **clipping masks**, **layer effects** (drop shadow / outer glow / stroke). Divide-layer-by-colour, gradient-map presets.

### Selection

Rect / Lasso / Wand / Quick-select with **Replace / Add / Subtract / Intersect** modes and Feather. **Quick Mask Mode** (`Q`) for paint-the-mask workflows. **Stroke Selection** dialog.

### Animation & manga

- **Animation** — frame timeline dock with snapshots, playback, onion-skin overlay, MP4 / GIF export
- **Manga tools** — Panel Cutter · Tone Layers · Stamp Page Numbers · Speedlines (Radial / Parallel / Burst) · Action Flash · Speech Bubble tool

### Filters & view aids

- **Filters** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone (each with a live-preview dialog)
- **View aids** — Pixel Grid · Snap to Pixel · Snap to Edges · Onion Skin · Bleed Guides · Canvas Rotation (`Ctrl+Shift+H` rotates CCW)

### Docks (10, tabbed)

Color · Brush · Layer · Navigator · Material library · History · Swatch · Reference · Histogram · Animation. Each dock is movable / floatable. **Settings > Workspace Layouts** saves and recalls named arrangements.

### File I/O

- Open / save **PSD** (Photoshop) with full layer round-trip
- Export PNG / JPEG / WebP, plus multi-page comic export to **CBZ** or **PDF**
- Autosave snapshots with restore-latest

### Power-user UX

- **Tab** toggles all docks for distraction-free painting
- `Ctrl+Tab` cycles tabs
- `,` / `.` cycles brush kinds
- `0`-`9` set brush opacity in 10 % steps
- `Alt+[` / `Alt+]` step the active layer
- Right-click on canvas opens a quick Undo / Redo / Select All / Deselect / Fit / 100 % menu
- Per-tab modified asterisk, undo / redo toast confirmations, autosave-recovery prompt on launch

Press `E` from Deep Zoom to send the current image straight into a new Paint tab.

---

## Puppet — 2D rigged animation

The **Puppet** tab is a from-scratch 2D rigged-puppet animation system. It does what Live2D / Inochi2D do (mesh-deformation rigs, parameters, motions, physics, expressions, pose, lip-sync, webcam face tracking) but with **no proprietary SDK**, **no `live2d-py`**, and a fully open `.puppet` file format documented at `Imervue/puppet/FORMAT.md`.

### File format

`.puppet` is a zip container:

- `puppet.json` — manifest (drawables, deformers, parameters, motions, pose groups, parts, hit areas)
- `textures/*.png` — atlas textures
- `motions/*.json` — keyframe tracks
- `expressions/*.json` — parameter overlays
- `physics.json` — Verlet rig configuration

JSON-based, humanly diffable, no proprietary binary.

### Renderer

`QOpenGLWidget` with vertex-array textured-triangle drawing in draw_order, per-drawable blend modes (normal / additive / multiply), pose-group exclusivity, ortho projection in image-space, GL_REPEAT-tiled transparency-checker backdrop, wheel zoom + middle-drag pan. Optimised for large rigs — March 7th (307 drawables / 2965 vertex morphs) runs at 60 FPS on CPU.

### Authoring

- **Import PNG** → auto-generate a triangulated grid mesh that respects alpha
- **Add Rotation Deformer** (anchor + angle) / **Add Warp Deformer** (rows × cols bezier lattice) toolbar actions
- **Add Parameter** → set key forms at slider extremes via **Set Key** in the parameter dock
- **Mesh editor** — toggle Edit Mesh to drag vertices; clicks within 8 px snap to the nearest
- **Save As…** writes the whole rig to a `.puppet` zip

### Runtime

- **Parameter rig** — each parameter holds a key list mapping a slider value to a partial deformer-form snapshot; runtime samples and per-field-lerps
- **Motion playback** — bottom dock with motion list + Play / Pause / Stop / Loop / scrub; curve sampler honours `linear`, `stepped`, `inverse-stepped`, `cubic-bezier` segments (Newton-iterated time → param solve); per-motion fade-in / fade-out
- **Expressions** — stack of `additive` / `multiply` / `overwrite` parameter overlays
- **Pose groups** — mutually-exclusive drawable visibility (weapon swaps, mouth-shape variants)
- **Physics** — Verlet pendulum chains for hair / cloth / ribbons; input param moves chain anchor, gravity + damping + per-particle springs pull back to rest
- **Vertex morphs** — Cubism-style linear blend between rest and ±extreme deltas; vectorised numpy per-frame at 60 FPS
- **Opacity keys** — parameter-driven alpha curves; lets alternate-pose meshes fade in / out as a gesture parameter fires

### Live input

- Cursor drag → head-angle parameters
- Auto-blink on a cosine open → close → open curve
- Mic lip-sync via `sounddevice` RMS → `ParamMouthOpenY` (optional dep)
- Webcam face tracking via OpenCV + MediaPipe FaceMesh → head yaw / pitch / roll + eye / mouth open (optional deps)
- Custom motion recording — captures parameter values at 30 Hz while you wiggle sliders / face the webcam / let physics run; bakes into a linear-segment Motion ready to play / loop / save

### Cubism interop

The **Cubism Native SDK** can be plugged in (user-supplied DLL — Live2D's Free Material License forbids redistribution) to convert any `.moc3` model into a `.puppet` zip. The converter runs a sample-and-reconstruct sweep that captures both vertex-morph deltas and parameter-driven visibility transitions, so gesture toggles (peace sign / face cover / photo …) survive the conversion intact.

### Output

- **Capture frame…** saves a PNG of the current canvas via `glReadPixels`
- **Record…** toggles a 30 FPS frame loop into GIF / WebM / MP4 via `imageio`
- **NDI output** for streaming into OBS / Zoom (optional `ndi-python` dep)
- **VTube Studio API server** — opt-in OBS-friendly remote control
- **Virtual camera** stream

### Demo

A drop-in rig lives at [`examples/puppet/march_7th.puppet`](examples/puppet/march_7th.puppet) — a 307-drawable Cubism Live2D character converted in-tree. Open via **Open Puppet…** to see the rig come up centred; click any of the 18 motions (Idle group + Gesture group) to play. Gestures cover peace sign, face cover, photo, blush, dark face, cry, sweat, stars, shooting star — every named gesture the rig defines.

---

## Keyboard & Mouse Shortcuts

### Navigation (all modes)

| Shortcut | Action |
|----------|--------|
| Arrow Keys | Scroll grid / Switch images (Left/Right in deep zoom) |
| Shift + Arrow | Fine-grained scrolling (half step) |
| Ctrl+Shift+←/→ | Jump to previous / next sibling folder with images |
| Alt+← / Alt+→ | History back / forward |
| Ctrl+G | Go to image by index |
| X | Jump to a random image |
| Home | Reset zoom and pan to origin |
| Ctrl+F or / | Open fuzzy search dialog |
| Ctrl+Shift+P | Open Command Palette |
| Alt+M | Replay last macro on current selection |
| S | Open slideshow dialog |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z / Ctrl+Y | Redo |

### Deep Zoom / single image

| Shortcut | Action |
|----------|--------|
| F | Toggle fullscreen |
| Shift+Tab | Toggle theater mode (hide all chrome) |
| R / Shift+R | Rotate CW / CCW |
| E | Open image editor (Modify tab) |
| W / Shift+W | Fit to width / height |
| H | Toggle RGB histogram overlay |
| F8 / Ctrl+F8 | OSD overlay / debug HUD |
| Shift+P | Toggle pixel view (≥ 400 % zoom shows grid + RGB) |
| Shift+M | Cycle color modes (Normal / Grayscale / Invert / Sepia) |
| B | Toggle bookmark |
| Ctrl+C / Ctrl+V | Copy / paste image to/from clipboard |
| 0 / 1-5 | Toggle favorite / quick rating |
| F1-F5 | Quick color label (red / yellow / green / blue / purple) |
| P / Shift+X / U | Cull: Pick / Reject / Unflag |
| Shift+S | Split view |
| Shift+D / Ctrl+Shift+D | Dual-page (LTR / RTL) |
| Ctrl+Shift+M | Multi-monitor mirror window |
| Delete | Move to trash (undoable) |
| Escape | Exit deep zoom / Exit fullscreen |

### Animation playback (GIF / APNG)

| Shortcut | Action |
|----------|--------|
| Space | Play / Pause |
| , (comma) / . (period) | Previous / next frame |
| [ / ] | Decrease / increase playback speed |

### Tile Grid

| Shortcut | Action |
|----------|--------|
| Ctrl+L | Toggle Grid ↔ List |
| Hover (500 ms) | Hover preview popup |
| Delete | Delete selected tiles |
| Escape | Deselect all |

### Mouse / touchpad

| Action | Behavior |
|--------|----------|
| Left Click | Select tile or open image |
| Left Drag | Rectangle multi-select in grid |
| Long Press (500 ms) | Enter tile selection mode |
| Middle Drag | Pan in deep zoom |
| Scroll Wheel | Zoom in/out or scroll |
| Right Click | Context menu |
| Pinch | Zoom in/out in deep zoom |
| Horizontal Swipe | Previous / next image |

### Paint tab (in addition to the above)

| Shortcut | Action |
|----------|--------|
| B / E / G / I | Brush / Eraser / Fill / Eyedropper |
| V / T / U / R | Move / Text / Gradient / Rectangle select |
| P / S / C / Z / H | Pen / Smudge / Clone / Zoom / Hand |
| Q | Toggle Quick Mask Mode |
| Tab | Toggle all docks |
| Ctrl+Tab | Cycle Paint tabs |
| , / . | Cycle brush kinds |
| 0-9 | Brush opacity 10% steps |
| Alt+[ / Alt+] | Step active layer down / up |

---

## Menu Structure

### File

- New Window
- Open Image / Open Folder
- Recent (folders + images)
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association (Windows)
- **Session** — Save / Load
- **Workspaces…** — save / load / rename named window layouts
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts (customisable bindings)
- Exit

### Tools (extra tools — organised into 8 grouped submenus)

- **Batch** — Format Conversion · EXIF Strip · Image Sanitizer · Image Organizer · Token Batch Rename
- **Library & Metadata** — Library Search · Smart Albums · Find Similar / Duplicate · Auto-Tag · Hierarchical Tags · Export Metadata · XMP Sidecars · GPS Geotag
- **Views** — Timeline · Calendar · Map
- **Workflow** — Culling · Staging Tray · Virtual Copies · Dual-Pane File Manager · Macros
- **Export** — Contact Sheet PDF · Web Gallery · Slideshow Video (MP4) · Print Layout
- **Develop (Non-Destructive)** — Tone Curve · .cube LUT · Split Toning · Local Adjustment Masks · Soft Proof
- **Retouch & Transform** — AI Image Upscale · Noise Reduction / Sharpening · Healing Brush · Clone Stamp · Face Detection · Sky / Background · Crop / Straighten · Auto-Straighten · Lens Correction
- **Multi-Image** — HDR Merge · Panorama Stitch · Focus Stacking

### View / Sort / Filter / Language / Plugins / Instructions

(Standard menus — see in-app for full options.)

### Right-Click Context Menu

Navigation · Quick actions (reveal / copy path / copy image) · Transformations · Batch ops · Delete · Wallpaper · Compare / Slideshow · Export · Extra tools · Bookmarks · Image info · Plugin-contributed items.

---

## Plugin System

Imervue supports third-party plugins. See [PLUGIN_DEV_GUIDE.md](PLUGIN_DEV_GUIDE.md) for the full reference.

### Quick start

1. Create a folder inside `plugins/` at the project root
2. Define a class extending `ImervuePlugin`
3. Register it in `__init__.py` with `plugin_class = YourPlugin`
4. Restart Imervue

### Hooks

| Hook | Trigger |
|------|---------|
| `on_plugin_loaded()` | After plugin is instantiated |
| `on_plugin_unloaded()` | At app shutdown |
| `on_build_menu_bar(menu_bar)` | After default menu bar is built |
| `on_build_main_tabs(tabs)` | After the four built-in tabs are added |
| `on_build_context_menu(menu, viewer)` | When right-click menu opens |
| `on_image_loaded(path, viewer)` | After image loads in deep zoom |
| `on_folder_opened(path, images, viewer)` | After folder opens in grid |
| `on_image_switched(path, viewer)` | When navigating between images |
| `on_image_deleted(paths, viewer)` | After image(s) are soft-deleted |
| `on_key_press(key, modifiers, viewer)` | On key press (return True to consume) |
| `on_app_closing(main_window)` | Before application closes |
| `get_translations()` | Provide i18n strings |

### Plugin Downloader

**Plugins > Download Plugins** opens the online downloader. Source repo: [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins).

---

## MCP Server

Imervue ships a built-in [Model Context Protocol](https://modelcontextprotocol.io) server so AI assistants (Claude Code / Desktop, Cursor, Cline, …) can call into the project's pure-logic helpers without a running GUI. Qt-free; one command:

```sh
python -m Imervue.mcp_server
```

### Tools

| Tool | Purpose |
|------|---------|
| `list_images` | List image files in a folder (recursive optional) |
| `read_image_metadata` | Dimensions, format, EXIF, and XMP sidecar |
| `read_xmp_tags` | XMP-only fast path: rating, label, keywords |
| `convert_format` | Convert between PNG / JPEG / WebP / TIFF / BMP |
| `puppet_from_png` | Build a `.puppet` rig from a PNG (auto-mesh + standard parameters) |
| `puppet_inspect` | Open a `.puppet` and return its inventory |

### Wiring

The repository ships a `.mcp.json` at the root for Claude Code auto-discovery. For Desktop / other clients, add this to `claude_desktop_config.json` (or equivalent):

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

Full protocol surface in the MCP section of [docs/en/index.rst](docs/en/index.rst).

---

## Multi-Language Support

| Language | Code |
|----------|------|
| English | `English` |
| 繁體中文 (Traditional Chinese) | `Traditional_Chinese` |
| 简体中文 (Simplified Chinese) | `Chinese` |
| 한국어 (Korean) | `Korean` |
| 日本語 (Japanese) | `Japanese` |

Change via the **Language** menu. Restart required.

Plugins can register entirely new languages via `language_wrapper.register_language()`, or contribute translations via `get_translations()`. See [PLUGIN_DEV_GUIDE.md](PLUGIN_DEV_GUIDE.md#internationalization-i18n).

---

## User Settings

Stored in `user_setting.json` in the working directory. Key entries:

| Setting | Type | Description |
|---------|------|-------------|
| `language` | string | Current language code |
| `user_recent_folders` / `user_recent_images` | list | Recently opened |
| `user_last_folder` | string | Auto-restored on startup |
| `bookmarks` | list | Bookmarked image paths (max 5000) |
| `sort_by` / `sort_ascending` | string / bool | Sort method + order |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | Per-image organization |
| `thumbnail_size` / `tile_padding` | int | Grid configuration |
| `navigation_auto_loop` | bool | Wrap at folder ends |
| `keyboard_shortcuts` | dict | Custom key bindings |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | Layout persistence |
| `stack_raw_jpeg_pairs` | bool | RAW+JPEG stack toggle |
| `external_editors` | list | Configured editors |
| `macros` / `macro_last_name` | list / string | Saved macros + Alt+M target |

---

## Architecture

```
Imervue/
├── __main__.py              # Application entry point
├── Imervue_main_window.py   # Main window (QMainWindow) — mounts the 4 tabs
├── gpu_image_view/          # IMERVUE TAB — GPU viewer + deep zoom
├── gui/                     # Dialogs and side panels (develop, EXIF, etc.)
├── paint/                   # PAINT TAB — MediBang-style raster editor
├── puppet/                  # PUPPET TAB — 2D rigged-puppet animator
├── export/                  # Export generators (contact sheet, web gallery, MP4)
├── image/                   # Image utilities (pyramid, tile manager, info)
├── library/                 # Library helpers (RAW+JPEG stacks, indexing)
├── macros/                  # Macro record / replay
├── menu/                    # Menu definitions (file / tools / filter / …)
├── mcp_server/              # Model Context Protocol stdio server
├── multi_language/          # i18n (en / zh-tw / zh-cn / ja / ko)
├── external/                # External editor integration
├── plugin/                  # Plugin system (base / manager / downloader)
├── sessions/                # Workspace serialization
├── system/                  # Windows file association
└── user_settings/           # Persistent user config
```

### Rendering pipeline (Imervue tab)

1. `GPUImageView` extends `QOpenGLWidget`
2. Two GLSL 1.20 programs (textured quads + solid color rectangles)
3. LRU texture cache — 256-tile limit, 1.5 GB VRAM budget
4. Multi-level tile pyramid built with LANCZOS at 512 × 512 tile size
5. Anisotropic filtering up to 8× when hardware supports it
6. Software-rendering fallback if shader compilation fails

### Thumbnail cache

- **Key**: MD5 of `{path}|{mtime_ns}|{file_size}|{thumbnail_size}`
- **Format**: Compressed PNG (`compress_level=1` — fast write, small footprint)
- **Location**: `%LOCALAPPDATA%/Imervue/cache/thumbnails` (Win) or `~/.cache/imervue/thumbnails` (Linux/macOS)
- **Invalidation**: Automatic on file metadata change

### Puppet rendering (Puppet tab)

- `QOpenGLWidget` with `glDrawElements` + client-side vertex arrays
- Per-drawable: rest vertices cached as float32 numpy; vertex morphs vectorised; topological deformer sort hoisted out of the per-drawable loop
- Transparency backdrop is a 2×2 GL_REPEAT-tiled texture (was 100k+ immediate-mode quads pre-optimisation)
- Cubism converter produces opacity_keys curves alongside vertex-morph deltas so parameter-driven visibility transitions survive the `.moc3 → .puppet` conversion

---

## License

This project is licensed under the [MIT License](LICENSE).

Copyright (c) 2026 JE-Chen
