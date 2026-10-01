<p align="center">
  <img src="Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  A GPU-accelerated image viewer / developer / paint studio / puppet animator built with PySide6 and OpenGL
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="README/README_zh-TW.md">繁體中文</a> ·
  <a href="README/README_zh-CN.md">简体中文</a> ·
  <a href="README/README_ja.md">日本語</a> ·
  <a href="README/README_ko.md">한국어</a> ·
  <a href="README/README_es.md">Español</a> ·
  <a href="README/README_fr.md">Français</a> ·
  <a href="README/README_de.md">Deutsch</a> ·
  <a href="README/README_pt-BR.md">Português (BR)</a> ·
  <a href="README/README_ru.md">Русский</a>
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
- [Paint — full-featured raster editor](#paint--full-featured-raster-editor)
- [Puppet — 2D rigged animation](#puppet--2d-rigged-animation)
- [Desktop Pet — frameless overlay](#desktop-pet--frameless-overlay)
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

Imervue is a GPU-accelerated image workstation that ships **five top-level tabs**:

| Tab | What it does |
|---|---|
| **Imervue** | Browse, view, organize, search, and batch-process your image library |
| **Modify** | Non-destructive develop pipeline — sliders, curves, LUTs, masks, retouch, multi-image |
| **Paint** | full-featured raster paint studio with brushes, layers, animation, manga tools, PSD I/O |
| **Puppet** | From-scratch 2D rigged-puppet animator — meshes, deformers, parameters, motions, physics |
| **Desktop Pet** | Frameless / transparent / always-on-top overlay that runs the same puppet rigs on your desktop with live drivers (idle / blink / mic / webcam / drag-track) |

**Puppet** and **Desktop Pet** are optional: turn either off under **File > Preferences > Optional tabs** and, from the next start, its tab is not added and its code is not loaded, so Imervue starts faster and uses less memory. Both are on by default; each one is built the first time you open its tab, and the Desktop Pet tab at startup when its pet is set to show on launch.

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
| rawpy | Camera RAW decoding (CR2 / CR3 / NEF / ARW / RAF / ORF / RW2 / PEF / DNG and more) |
| imageio | Image I/O |
| imageio-ffmpeg | Slideshow MP4 and Create GIF / Video MP4 (H.264 via ffmpeg) |
| defusedxml | Safe XML parsing (XMP sidecars) |
| watchdog | Watched Folder automation and the MCP server's change notifications |

Optional (feature-gated; omit to disable the feature cleanly):

| Package | Purpose |
|---------|---------|
| onnxruntime + huggingface_hub | CLIP semantic search and CLIP auto-tag labels (offered for install on first use; the ~150 MB model downloads once) |
| onnxruntime | Real-ESRGAN AI upscale |
| opencv-python<5 | HDR merge, panorama stitch, focus stacking, face detection, healing brush |
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

### Headless batch CLI

`Imervue.cli` runs the pure image operations from a shell **without starting Qt** — useful for
scripts, CI steps, and servers with no display:

```bash
py -m Imervue.cli resize photos/ --max 1600 --out web/
py -m Imervue.cli watermark a.jpg --text "(c) Me" --corner bottom-right
py -m Imervue.cli info *.png --json
py -m Imervue.cli list-ops          # print every available subcommand
```

| Subcommand | Purpose |
|---|---|
| `info` / `stats` | Dimensions & format; no-reference quality metrics (`--json` for machine output) |
| `convert` / `resize` / `thumbnail` | Format conversion (`--format` JPEG / PNG / WEBP / TIFF / BMP / AVIF / HEIC / JXL, `--quality`); resize to a long edge (`--max`) or an exact `--width` / `--height`; thumbnail box |
| `watermark` / `optimize` | Text watermark (`--text`, `--corner`, `--opacity`, `--font-fraction`, `--color R G B`, `--no-shadow`); encode under a `--max-kb` budget |
| `dehaze` / `clahe` / `dither` / `distort` | Dark-channel dehaze, adaptive equalization, ordered Bayer dither, swirl / pinch / ripple |
| `auto-orient` / `strip` | Bake the EXIF orientation flag into pixels; re-save without EXIF / XMP / ICC |
| `collage` / `anaglyph` | Grid montage (`--columns`, `--cell-width` / `--cell-height`, `--gap`, `--margin`, `--background R G B`); red-cyan 3D from a stereo pair (`--method`) |
| `preset` / `pipeline` | Apply a saved develop preset by name; run an ordered JSON pipeline of ops |
| `list-ops` | List every subcommand (`--json` for machine output) |

Every subcommand decodes like the viewer: outputs are turned upright by the EXIF orientation and converted to sRGB from an embedded colour profile, AVIF inputs are read by Pillow itself, and HEIC / JPEG XL inputs when their optional backend is installed. A camera RAW is developed as in the viewer instead of being read as its small embedded preview; `resize` and `strip` write it as PNG. A file that can't be read is reported and the rest still run. A file cut short is read as far as it goes, as in the viewer. 16-bit and floating-point greyscale is scaled to 8 bits as in the viewer; `resize` and `strip` keep the source's bit depth.

The subcommands that take files or folders (all but `collage`, `anaglyph` and `list-ops`) share `--out`
(output directory), `--recursive`, `--dry-run` (list actions, write nothing), `--overwrite` and `-j` /
`--jobs` (parallel workers; `0` uses every core). `collage` and `anaglyph` write the one file `--out`
names. `--version` prints the CLI version.

Every tool of the [MCP server](#mcp-server) is a subcommand too. Ten of them are the subcommands above
(`convert_format` is `convert`, `quality_metrics` is `stats`, `build_collage` is `collage`, and so on);
the other 48 run the MCP tool's own code:

| Kind | Subcommands |
|---|---|
| Edits: write `<stem>_<name>.png` beside each source, or `<stem>.png` in `--out` | `frame`, `crop`, `rotate`, `solarize`, `glow`, `velvia`, `emboss`, `film-negative`, `defringe`, `graduated-density`, `filmic-tonemap`, `tone-equalizer`, `detail-equalizer`, `colormap`, `false-color`, `split-toning`, `pixel-sort`, `polar`, `kaleidoscope`, `frosted-glass`, `local-contrast`, `posterize`, `gradient-map`, `film-grain`, `levels`, `auto-color-balance`, `channel-mixer`, `curve`, `lens-correction` |
| Other outputs | `ela` (Error Level Analysis map as PNG), `video-frame` (one frame of a video, `--frame-index`), `puppet-from-png` (a `.puppet` rig, `--cell-size`) |
| Reports: one result per image, `--json` for machine output | `metadata`, `xmp`, `gps`, `dominant-colors`, `sharpness`, `statistics`, `histogram`, `ocr`, `puppet-inspect`, `puppet-validate` |
| Run once and print JSON | `list-images FOLDER`, `search FOLDER --query "..."`, `similar FOLDER`, `collection-stats FOLDER`, `reverse-geocode --latitude .. --longitude ..`, `puppet-schema --name ..` |

Each MCP parameter becomes an option with the same default and allowed values: `zone_gains` is
`--zone-gains`, a yes/no parameter is `--grayscale` / `--no-grayscale`, and a colour or a matrix row
takes its values in order (`--red 1 0 0`). `py -m Imervue.cli <subcommand> --help` lists them.

`pipeline FILE INPUTS…` chains operations from a JSON file — a list of steps, or
`{"pipeline": [...]}`, each step an `"op"` plus its parameters (at most 50 steps). The ops are
`dehaze`, `clahe`, `dither`, `distort`, `clarity`, `texture`, `grayscale`, `invert` and
`watermark`; the docs list every parameter and default.

```bash
py -m Imervue.cli film-grain photos/ --intensity 0.4 --seed 7 --out grain/
py -m Imervue.cli crop a.jpg --x 0 --y 0 --width 800 --height 600
py -m Imervue.cli histogram a.jpg --json
py -m Imervue.cli search photos/ --query "ext:jpg width:>1920"
```

---

## Imervue — Image viewer & library

The **Imervue** tab is the default landing surface. It pairs the image viewer with the folder tree, EXIF sidebar, and library/organization tools.

### Viewer

- **GPU-accelerated rendering** via OpenGL (GLSL 1.20 shaders with VBO)
- **Deep-zoom pyramid** — multi-level tiles at 512×512 with LANCZOS resampling; tile LRU holds 256 entries (hard ceiling 512). The VRAM budget is probed from the GL driver at startup and falls back to 1.5 GB, overridable via the `vram_limit_mb` setting (clamped, never silently dropped). Anisotropic filtering up to 8×; panoramas far past Pillow's 179 MP safety limit open too (the limit follows the computer's memory: about 1.4 gigapixels with 16 GB)
- **Asynchronous loading** — multi-threaded decode with an adaptive prefetch window: ±3 images while browsing, widening to 5 ahead / 1 behind once you page consistently in one direction
- **Separate worker pools** — thumbnail bursts and deep-zoom decodes run on different pools, so opening a large folder never starves the image you are actually looking at
- **Virtualized thumbnail grid** — only visible tiles are rendered; thumbnail size is configurable (128 / 256 / 512 / 1024 / auto)
- **Disk cache** — compressed PNG thumbnails with MD5-based invalidation under `%LOCALAPPDATA%/Imervue/cache/thumbnails` (or `~/.cache/imervue/thumbnails`)
- **EXIF orientation** — portrait shots that a phone or camera tagged instead of turning are shown upright in the viewer, thumbnails, list view, hover preview and Modify tab; a develop crop / rotate saved before this keeps applying to the orientation it was drawn on
- **Colour management** — photos with an embedded colour profile (Display P3 from phones, Adobe RGB from cameras, CMYK, and the grey profiles Photoshop embeds in greyscale images such as Dot Gain 20% or Gray Gamma 1.8) are converted to sRGB for the viewer and thumbnails; untagged and sRGB images are shown as stored
- **Files cut short** — a JPEG, PNG, TIFF, GIF or BMP that ends early (an interrupted download or copy, a photo recovered from a failing memory card) opens with the part that was read, as in a browser, instead of not opening at all
- **Files changed by other programs** — when another program saves over a picture (an external editor, in place or by renaming a copy over it), the viewer shows the new version: the picture open in Deep Zoom within a second of the last write, grid thumbnails and the rows of the List view within a few seconds
- **16-bit and floating-point greyscale** — a 16-bit grey PNG or TIFF (a scan, a depth map, a scientific or astronomy frame) and a floating-point TIFF show their real brightness in the viewer, thumbnails, previews and tools, instead of almost white or black
- **Hidden files** — files Windows marks hidden (hidden in Explorer and the folder tree too) and names starting with a dot, such as the `._photo.jpg` companion macOS writes beside every photo on a memory card or network drive, are left out of the thumbnail wall, folder icons, the batch tools' folder lists, watch folders, library scans, the CLI and the MCP server's folder tools; recursive scans skip hidden folders such as `$RECYCLE.BIN` and a Mac's `.Trashes`. A hidden picture opened on purpose still opens
- **JPEG under every name** — `.jpe`, `.jfif` and `.jif` open like `.jpg` (Chrome and Edge on Windows often save a downloaded photo as `.jfif`): in the viewer, the JPG filter, the batch tools and the CLI
- **More formats** — ICO, TGA, DDS, QOI, JPEG 2000 (.jp2 / .j2k / .jpf / .jpx), Netpbm (PPM / PGM / PBM / PNM), PCX, PSD (the merged picture) open for viewing, read by Pillow itself; rotating one in place and other write-backs are refused, so an edit goes out through Save As / Export
- **Animation playback** — GIF / APNG with play / pause / frame-step / speed controls; an animation too large to hold decoded (over 512 MB) decodes each frame as it plays instead of all up front; a frame of 10 ms or less plays for 100 ms, as in browsers; a multi-page TIFF (a scanned document) shows one page at a time, turned with `,` and `.` ("Page 2/5"), and a camera JPEG's embedded preview (MPF) is never shown as a second frame, nor an APNG's default image (the still for programs without APNG support) as the first

### Browsing modes

- **Grid** (default) — virtualized tile grid with hover-preview popup (500 ms delay)
- **List (detail)** — toggle with `Ctrl+L`; columns: Preview · Label · Rating · Name · Resolution · Size · Type · Modified; `Delete` removes the selected rows and `Ctrl+Z` brings them back, and the rating (`1`–`5`), favourite (`0`), cull (`P` / `Shift+X` / `U`) and colour (`F1`–`F5`) keys mark them, as on the thumbnail wall
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
- Pixel view (`Shift+P`) — from 400 % zoom shows the per-pixel RGB / HEX, plus a pixel grid once no more than 40,000 pixels are on screen
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
- **Ratings** — 0-5 stars (`1`–`5`) + favorite heart (`0`); on the wall they apply to the selected thumbnails, else the one the arrow keys are on, else the one under the mouse
- **Color labels** — flag-based red/yellow/green/blue/purple (`F1`–`F5`)
- **Culling** — three-state flag (`P` = pick, `Shift+X` = reject, `U` = unflag); filter by state; bulk delete-rejects; **auto-cull** picks the sharpest frame per near-duplicate group and rejects the rest
- **Hierarchical tags** — tree paths like `animal/cat/british`; descendants matched automatically; right-click **Batch Operations** > **Index Keywords** (thumbnails selected) files a Lightroom / darktable keyword hierarchy (`Places|Taiwan|Taipei`) under its parents
- **Tags & Albums** with multi-tag AND/OR filtering; a new or renamed name that differs from another only in case or spaces is refused, and **Clean Up…** forgets files that no longer exist and merges names that differ only in case
- **Smart Albums** — save rule-based queries and reapply with one click; filters span extension, resolution & **aspect**, **file size**, rating **floor / ceiling**, colour, cull, tags (incl. **exclusion**), **camera / lens**, **filename regex / glob** and **file age**, plus **export / import** to a portable JSON file
- **Stack RAW+JPEG pairs** — collapse same-stem captures into one tile; RAW stays accessible as a sibling
- **Per-image notes** in the EXIF sidebar — debounced save, persists across sessions
- **Staging Tray** — cross-folder basket that survives restarts; bulk move / copy / export
- **Dual-Pane File Manager** — dual-pane two-tree view
- **Sessions / Workspace Layouts** — snapshot tabs / selection / filter / dock geometry to `.imervue-session.json`; save named layouts for Browse / Develop / Export arrangements
- **Macros** — record / replay batches of rating / favorite / color / tag actions (`Alt+M` replays the last macro)
- **Thumbnail badges + density** — colour strip, favorite, bookmark, rating stars; Compact / Standard / Relaxed padding
- **Drag-out to external apps** — drag a tile straight into Explorer / Chrome / Discord
- **Recent folders / images** tracked; last folder auto-restored on startup

### Sort & filter

- Sort by name (natural order, like Explorer: `img2` before `img10`) / modified / created / date taken (the camera's EXIF time, else modified) / size / resolution (asc or desc)
- Filter by extension, color label, rating, tag/album, cull state
- **Advanced filter** — resolution / file size / orientation / modified-date range
- **Multi-tag filter** dialog with AND / OR boolean logic

### Search

- **Fuzzy filename search** with substring highlighting
- **Find Similar Images** — pHash (64-bit DCT) with adjustable Hamming distance
- **Library Search** — SQLite multi-root index, searched by file name, minimum width / height and file size (up to 2000 results; double-click one to open it); a rescan reads only new or changed files (and, with **Compute perceptual hash** ticked, files still without a hash), several at once
- **Search by Query** (right-click) — a compact query language over the open folder: keywords, tags (incl. negation), ratings, colour, extension, place, cull, favourites, aspect, age, size, dimensions, camera / lens, and filename regex / glob; `place:` matches a city, a country or both, and a value with spaces goes in double quotes (`place:"Rio de Janeiro"`)
- **Find Similar (average hash)** — pHash and dHash are joined by an optional average-hash (aHash) for a complementary near-duplicate metric
- **Semantic Search (CLIP)** — natural-language queries ("golden retriever in snow") via cached embeddings from CLIP ViT-B/32 on onnxruntime, no PyTorch: Imervue offers to install `onnxruntime` on first use and downloads the ~150 MB model once, at a pinned revision; it runs on an NVIDIA GPU through CUDA when available, otherwise on the CPU, never on an integrated GPU
- **Auto-Tag** — heuristic tags from colour, edges and shape: document / screenshot / photo / graphic, landscape / portrait; once Semantic Search has downloaded the CLIP model, zero-shot CLIP labels instead (up to three of photo, document, screenshot, graphic, illustration, portrait, landscape, animal, food, text)

### Metadata

- **EXIF sidebar** with collapsible groups + inline 0-5 star strip
- **EXIF editor** dialog — description, artist, copyright, camera and comment (Unicode included) written into a JPEG or WebP with no extra package, pixels and other tags untouched; **Describe** fills the description with one sentence from a local vision model (Ollama with `llava` on `localhost:11434`), so the image never leaves your computer
- **Keyword editor** — title / creator / description / keywords, with **related-tag suggestions** drawn from tag co-occurrence and **controlled-vocabulary expansion** (a leaf keyword auto-applies its ancestors + synonyms from an editable hierarchical vocabulary)
- **Image info** dialog (dimensions / size / dates)
- **XMP sidecars** (`.xmp` companions) — rating / title / description / keywords / color label round-trip with other XMP-aware photo managers (safe XML via `defusedxml`). Saving merges into an existing sidecar: only these fields change, so a raw developer's settings, crop and history stored there are kept, and a sidecar that can't be parsed is never overwritten. Besides `photo.xmp` (Lightroom, Bridge), the `photo.jpg.xmp` that darktable and digiKam write is read and updated when it is the only sidecar; colour labels are understood in Lightroom's words (`Red` … `Purple`) and Bridge's (`Select`, `Second`, `Approved`, `Review`, `To Do`), and exported as Lightroom writes them. A rejected photo (`xmp:Rating` -1 in Lightroom, Bridge and darktable) becomes a culling Reject, and a Reject is exported as -1. A file without a sidecar is read and imported from the XMP and EXIF rating embedded in it (JPEG, PNG, WebP, TIFF, CR3, RW2, ORF, RAF) — how Lightroom stores a JPEG's rating and keywords, and how Windows Explorer stores its stars.
- **GPS Geotag editor** — read existing EXIF GPS, write new lat/lon into a JPEG or WebP with no extra package, leaving its pixels, other tags and thumbnail untouched
- **Geotag from GPX Track** — match the selection's EXIF capture times against a `.gpx` log from a phone or GPS logger, with the camera's time zone, a gap limit and interpolation between points, then write the positions into the JPEG / WebP files
- **Edit Capture Time** — shift the EXIF capture time of the selection by days / hours / minutes / seconds, or by naming when the first photo was really taken; DateTimeOriginal, DateTimeDigitized and DateTime are rewritten in JPEG / WebP files
- **Metadata Template** — a remembered title, description and keywords with `{filename}` / `{name}` / `{folder}` / `{date}` / `{year}` tokens, stamped on the selection either into empty fields only (keywords added) or over what is there; XMP Sidecars and Export Metadata write the result out
- **Token Batch Rename** — live-preview templates like `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **Export Metadata CSV / JSON** — one row per image including cull / rating / tags / notes

### Extra Tools (Imervue tab — batch processing)

Accessed from **Tools** menu; organised into function-grouped submenus:

- **Batch** — Format Conversion · EXIF Strip · Image Sanitizer (re-render to strip hidden data) · Image Organizer (sort into subfolders by date / resolution / type / size) · Token Batch Rename
- **Retouch & Transform** — AI Image Upscale (Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU) · Face Detection (Haar cascade) · healing, cloning, crop / straighten and lens correction
- **Library & Metadata** — Library Search · Smart Albums · Find Similar Images · Semantic Search · Find Duplicate Images · Auto-Tag · Hierarchical Tags · Export Metadata · XMP Sidecars · GPS Geotag · Geotag from GPX Track · Edit Capture Time · Metadata Template

### System integration

- Windows right-click **Open with Imervue** context menu (registry-based file association)
- Folder monitoring: the open folder is checked about once a second, so files added, removed or renamed elsewhere show within a second or two; nothing holds the folder open, so on Windows the folders above it can still be renamed or moved. The folder tree catches up on F5 / **Refresh**, when Imervue comes back to the front and when the open folder changes
- Toast notification system (info / success / warning / error)
- Plugin system with online plugin downloader (see [Plugin System](#plugin-system))

---

## Modify — Non-destructive develop

The **Modify** tab is the develop workstation. Every adjustment lives on a per-image **recipe** stored alongside the file — the original pixels on disk are never overwritten until you explicitly **Export** or **Save As**. **Apply Crop** and the annotation **Save** are the two exceptions: they write the result back over the file, keeping its EXIF (camera, capture date, GPS), XMP and DPI. A camera RAW, HEIC or animated / multi-page file is never overwritten — the crop asks you to export instead, and the annotation save asks for a new file. The one-shot tools (CLAHE, HSL Mixer, Photo Frame, Auto Straighten …) save their result beside the original as `photo_clahe.png`; running one again saves `photo_clahe_1.png` rather than replacing the last result. **Auto-Rotate by EXIF**, the copies from **Batch EXIF Strip** and **Split Pages…** number their files the same way. A photo's recipe and virtual copies stay with it when Imervue rotates it losslessly (the crop turns with the photo) or rewrites its EXIF (GPS Geotag, the EXIF editor); a recipe with local masks, layers, a lens flare or face tags stays with the unrotated version until it is turned back.

### Develop sliders

- White balance — temperature / tint
- Tonal regions — highlights / shadows / whites / blacks
- Exposure / contrast / saturation / vibrance
- Crop, rotation, horizontal / vertical flip
- All edits remain non-destructive and round-trip through the recipe store

### Curves & LUTs

- **Tone Curve editor** — draggable RGB curve plus per-channel R / G / B with monotone cubic interpolation
- **Apply .cube LUT** — load any Adobe LUT (3D up to 65³, 1D up to 65,536 points; DaVinci Resolve's `LUT_3D_INPUT_RANGE` included), trilinear-interpolate, blend with an intensity slider
- **Split Toning** — shadow / highlight hue + saturation with a balance pivot

### Creative effects

- **Solarize** — darkroom-style tone reversal (threshold + mix)
- **Diffuse Glow / Orton** — soft-focus highlight bloom (amount / radius / highlight-threshold)
- **Gradient Map** — luminance → palette, with an optional **perceptual (OkLCH)** interpolation mode that keeps saturated gradients vivid through the midpoint instead of greying
- **Ordered Dither** — Bayer-matrix quantisation to N levels (extremes preserved)
- **Graduated Density** — linear ND gradient by angle / hardness / offset with an optional tint, for skies and foregrounds
- **Tone Equalizer** — independent exposure per luminance zone (shadows → highlights) over a smoothed mask
- **Detail Equalizer** — re-weight contrast per frequency band (fine texture vs coarse contrast), beyond a single clarity slider
- **Filmic Tone Map** — pure Reinhard / Hable highlight rolloff with pivoted contrast + saturation restore, for high-contrast single exposures
- **Velvia** — luminance-weighted saturation boost that intensifies muted colours while sparing the shadows
- **Film Negative** — invert a scanned colour negative, dividing out the orange film base, with output gamma
- **Defringe** — desaturate purple / green chromatic-aberration fringes on high-contrast edges
- **Emboss** — directional-light relief from a luminance height field
- **Polar Coordinates** — wrap a frame into a disc or unroll it (tiny-planet / polar inversion)
- **Kaleidoscope** — mirror one angular wedge into n-fold symmetry
- **Frosted Glass** — deterministic seeded local pixel scatter
- **Frame & Caption** — a matte border in any colour, an optional Polaroid-style bottom band and a caption in its own colour
- **Develop Presets** — save a recipe, then **apply** it wholesale or **merge** just its active adjustments onto other images (keeping each image's own crop, etc.)

### Local adjustments

- **Brush / radial / linear gradient masks** with per-mask exposure / brightness / contrast / saturation / white-balance deltas + feather slider
- Masks blend non-destructively through the develop pipeline

### Retouch & transform

- **Healing Brush** — circular spots, OpenCV inpainting (Telea or Navier-Stokes)
- **Clone Stamp** — Shift+click source, feathered blit to destination
- **Crop / Straighten** — normalised crop rectangle plus a straighten of up to ±15° that auto-crops to the largest inner rect
- **Auto-Straighten** — Hough-line horizon / vertical detection
- **Lens Correction** — pure-numpy radial distortion (barrel / pincushion), vignette lift, per-channel chromatic-aberration
- **Noise Reduction / Sharpening** — edge-preserving bilateral denoise + unsharp-mask sharpening
- **Sky / Background** — replace detected sky with gradient or remove background (transparent or white fill); optional `rembg` / U²-Net upgrade

### Multi-image

- **HDR Merge** — combine bracketed exposures via OpenCV Mertens fusion (with AlignMTB pre-alignment)
- **Panorama Stitch** — OpenCV `Stitcher` in panorama or scans mode, black-border auto-crop
- **Focus Stacking** — Laplacian-variance focus map + Gaussian blend with optional ECC alignment

### Output

- **Export presets** — in Batch Export: Web 1600 px / 4K Web 3840 px / Print 300 DPI PNG / Instagram 1080 × 1080 square / Thumbnail 400 px, or Custom
- **Watermark** — in Batch Export: a text watermark in a corner or the centre, with its opacity; applied to the exported copies only
- **GPU batch develop** — with the **GPU Develop** plugin (**Plugins > Download Plugins**), Batch Export renders Develop recipes on a discrete GPU, chosen under **Render on**; **Plugins > GPU Develop…** installs `wgpu` on first use and names the GPU it found. White balance, exposure, highlights / shadows, whites / blacks, brightness, contrast, vibrance, saturation and the tone curve run on the GPU (a 24 MP photo in about 0.1 s instead of about 7 s); the rest of a recipe stays on the CPU. Integrated GPUs are never used, an image the GPU fails on is rendered on the CPU, and the output matches the CPU renderer to within a few levels on a small share of pixels
- **Save As / Export** — PNG / JPEG / WebP / BMP / TIFF (plus AVIF when Pillow has AVIF support, HEIC with `pillow-heif` and JPEG XL with `pillow-jxl-plugin`) with quality slider for lossy formats; keeps camera, lens and capture-date EXIF, with the location optional (**Metadata**: all / all but location / none); the suggested file name is one not yet taken (`photo_1.png` beside `photo.png`), and an existing file — above all the photo itself — is replaced only after you confirm
- **Batch operations** — rename, move/copy, rotate selected images. A move or copy never overwrites a file of the same name (it arrives as `name_1`), and a photo renamed or moved in Imervue (Batch Rename, Token Batch Rename, the folder tree, Move / Copy, Dual Pane, Staging Tray, Image Organizer) keeps its rating, favourite, tags, colour label, title, notes and cull flag; its `.xmp` and annotation sidecars go with it; so does a photo renamed in another program while its folder is open in Imervue. Renaming to a name another selected photo has now (renumbering a folder, swapping two names) renames the whole selection in the right order instead of only part of it
- **Contact Sheet PDF** — multi-page grid with captions (A4 / A3 / Letter / Legal); the **Layout** box fills in a preset — Default 4 × 5, Compact 6 × 8, Proof 5 × 6, Editorial 2 × 3, Index 8 × 10 (columns × rows, with their margin and captions) — and editing the grid by hand makes it Custom
- **Web Gallery HTML** — self-contained folder with `index.html` + JPEG thumbs + inline lightbox; **Client review** adds a comment box under each picture, kept in the reviewer's browser and downloaded as one JSON file
- **Slideshow MP4** — H.264 video with configurable FPS / hold-per-image / fade / dissolve / slide / wipe transitions (`imageio-ffmpeg`)
- **Print Layout** — multi-page PDF sheet with configurable page size / orientation / grid / margins / gutter / crop marks
- **Soft Proof** — load an ICC profile, simulate destination gamut, highlight out-of-gamut pixels in magenta
- **Virtual Copies** — named recipe snapshots per image; flip between looks without losing the master

### External editors

Register programs (an image editor, for example) under **File > External Editors…** and launch them on the current image via **File > Open in External Editor**. When the editor saves, the viewer shows the new version by itself.

---

## Paint — full-featured raster editor

The **Paint** tab is a full-featured raster paint studio embedded as its own `QMainWindow` with menus, left tool strip, context-sensitive options bar, and a tabbed right-side dock column. Multi-tab document editing — open many drawings at once, each with its own undo stack.

### Tools (27)

Brush · Eraser · Fill · Eyedropper · Rect / Lasso / Wand / Quick Select · Move · Text · Gradient · Blur · Smudge · Dodge · Burn · Sponge · Pen · Clone Stamp · Speech Bubble · Rectangle · Ellipse · Line · Polygon · Crop · Transform · Hand · Zoom

The **Pen** joins the points you click with straight lines, or curves where you drag out handles; with **Smooth** ticked in its Options bar, it runs one smooth curve through every point instead.

The darkroom-toning trio — **Dodge** (lighten), **Burn** (darken) and **Sponge** (desaturate) — paint local adjustments weighted by the brush; Dodge and Burn work on the midtones. None of the three has options.

The **Bucket** dock's **Base colours on a new layer** gives every closed region of the line art its own flat colour (the Swatches colours, when the dock shows any) on a new layer under it — the flatting step before shading — and leaves the lines and the space around the drawing empty.

The **Gradient** tool paints foreground → background, or a gradient of your own: pick it under **Colours** in the Options bar, and **Edit…** there opens the gradient editor, where each gradient has a name and colour stops (each with a position and a colour with opacity) that you add, move, recolour and remove. Your gradients are kept between sessions.

Single-letter shortcuts: `B / E / G / I / M / L / W / V / T / U / R / P / S / C / Z / H`; `Shift+R/E/I/P` for shape variants.

### Brushes

Six brush kinds — Pencil / Pen / Marker / Airbrush / Watercolour / Sumi — plus presets built on them (Crayon, Highlight, Sumi calligraphy …). The Brush dock sets Size / Opacity / Hardness / Density / Blend mode; the Options bar carries Size / Opacity / Hardness. Tablet pen pressure scales size and opacity through the curve set in **Settings > Pressure Curve…**; a mouse draws at full pressure. The Brush dock's **Scatter** moves each dab off the stroke by up to that share of the brush size, **Colour jitter** shifts each dab's hue, saturation and brightness, and **Follow pen tilt** narrows the tip across the direction a tablet pen leans and turns it to follow (the Sumi calligraphy preset has it on); a pixel-art brush keeps its square tip. Brush-tip capture from a selection, **File > Import brush preset…**.

### Layers

Full layer panel with thumbnails, visibility toggles, ↑ / ↓ reorder buttons (or `Ctrl+[` / `Ctrl+]`), blend modes, opacity, search, vector layers, 1-bit layers, **layer masks** (add / from selection / invert / apply), **clipping masks**, **layer effects** (drop shadow / outer glow / stroke). Divide-layer-by-colour, gradient-map presets.

### Selection

Rect / Lasso / Wand / Quick-select with **Replace / Add / Subtract / Intersect** modes; with **Magnetic** ticked in the Options bar, the Lasso's outline snaps onto the strongest edge of the layer within 10 px when you let go. **Quick Mask Mode** (`Q`) for paint-the-mask workflows. **Stroke Selection** dialog.

### Animation & manga

- **Animation** — frame timeline dock: **+ Frame** snapshots the flattened picture, playback at a chosen FPS, onion skin shows the previous frame; **Export…** saves the frames as an animated GIF, WebP (lossless) or PNG, each frame lasting one tick of the chosen FPS
- **Manga tools** — Panel Cutter · Tone Layers · Stamp Page Numbers · Speedlines (Radial / Parallel / Burst) · Action Flash · Text Along Selection (lays text you type along the outline of the selection, on a new layer) · Speech Bubble tool

### Filters & view aids

- **Filters** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone · Match Colour (the colour mood of a reference image you pick) · Match Swatches (each pixel in its nearest Swatches colour) (the one-slider filters — Posterize, Threshold, Halftone, Match Colour — preview live on a full-size crop of the layer as you drag; the others open an OK / Cancel parameter dialog)
- **View aids** — Pixel Grid · Snap to Pixel · Snap to Edges · Onion Skin · Bleed Guides · Canvas Rotation (`Ctrl+Shift+H` rotates CCW)

### Docks (14, tabbed in 3 clusters)

| Cluster | Docks |
|---|---|
| Drawing | Color · Brush · Bucket · Swatches |
| Canvas | Layers · Navigator · History · Pages · Animation · Histogram |
| Library | Materials · Stamps · Pose · Reference |

The Color dock opens with a hue ring and saturation / brightness triangle: drag on the ring to pick the hue and in the triangle to pick the shade, and the sliders and hex field below follow. The Materials dock lists your own materials ahead of the built-in tones and textures: images in the `materials` folder of Imervue's program folder (a first-level folder named `texture`, `tone`, `pattern`, `brush_tip` or `pose` files them under that category) and your captured brush tips. **Edit > Save Selection as Material…** saves the selected part of the picture there, never over an earlier one. The Swatches dock shows your recent colours or a palette — the built-in Standard, Pastel and Manga, or your own: **Save as Palette…** keeps the recent colours under a name and **Delete Palette** removes one of yours — and **Filter > Match Swatches…** uses the colours it shows. Each dock is movable / floatable and individually toggleable from the **Window** menu. **Settings > Workspace Layouts…** offers the built-in Default / Drawing / Comic / Compact layouts; **Save current…** stores which of the Layers / Color / Brush / Navigator / History / Reference docks are shown under a name, and applying a layout shows or hides those docks. Tool options and dock sizes are not stored.

### File I/O

- **New Canvas…** opens a tab of the size you pick — a paper, manga or screen preset (A4, B5 manga page, 1080p, 4K …), one you saved with **Save as Preset…**, or any width and height — on a white or transparent background; **New Tab** (`Ctrl+N`) keeps the 1024 × 1024 white default
- **Open PSD…** flattens the file into one layer in a new tab; **Save as PSD…** writes the layers with their blend modes (no masks or layer effects)
- **Export image…** writes PNG, JPEG, WebP, TIFF or BMP, by the file type you pick (JPEG and BMP, which have no transparency, on white); comic projects export their pages to **CBZ** or **PDF**. **Save Comic Project…** keeps a whole comic, every page with its layers, in one `.imervue-proj` file, and **Open Comic Project…** brings it back. Only **Save as PSD…** counts as saving the tab: after an export, closing still asks about its unsaved changes
- **Autosave** — a snapshot every 2 minutes while the active tab has unsaved edits; on the next launch a toast offers the snapshots and **File > Restore Autosave** loads the newest into the active tab, and the status bar shows when the last one was taken. Closing Imervue asks about Paint tabs with unsaved changes.

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

The **Puppet** tab is a from-scratch 2D rigged-puppet animation system: mesh-deformation rigs, parameters, motions, physics, expressions, pose, lip-sync and webcam face tracking, with **no proprietary SDK**, **no `live2d-py`**, and a fully open `.puppet` file format documented at `Imervue/puppet/FORMAT.md`.

> **Full walkthrough**: [`puppet_guide.md`](puppet_guide.md) covers the
> end-to-end flow for both live streaming (OBS / NDI / virtual camera)
> and animation production (recording / timeline editing / MP4
> export). Chinese versions at
> [`puppet_guide.zh-TW.md`](puppet_guide.zh-TW.md) and
> [`puppet_guide.zh-CN.md`](puppet_guide.zh-CN.md).

### File format

`.puppet` is a zip container:

- `puppet.json` — manifest (drawables, deformers, parameters, motions, pose groups, parts, hit areas)
- `textures/*.png` — atlas textures
- `motions/*.json` — keyframe tracks
- `expressions/*.json` — parameter overlays
- `physics.json` — Verlet rig configuration

JSON-based, humanly diffable, no proprietary binary. The format is open and checkable: a saved file starts with an uncompressed `mimetype` entry (`application/vnd.imervue.puppet+zip`) and every JSON file names its schema in `$schema`; the four JSON Schemas are published in [`docs/schemas/`](docs/schemas/); `py -m Imervue.cli puppet-validate character.puppet` (MCP `puppet_validate`) checks a file and `puppet-schema` (MCP `puppet_schema`) prints a schema; [`docs/examples/read_puppet.py`](docs/examples/read_puppet.py) reads one with the Python standard library alone. The specification ([`Imervue/puppet/FORMAT.md`](Imervue/puppet/FORMAT.md)) and schemas are MIT-licensed, so any program may read or write `.puppet` files.

### Renderer

`QOpenGLWidget` with vertex-array textured-triangle drawing in draw_order, per-drawable blend modes (normal / additive / multiply), pose-group exclusivity, ortho projection in image-space, GL_REPEAT-tiled transparency-checker backdrop, wheel zoom + middle-drag pan. Optimised for large rigs — a converted Cubism rig with 307 drawables and 2965 vertex morphs runs at 60 FPS on CPU.

### Authoring

- **Import PNG** → auto-generate a triangulated grid mesh that respects alpha
- **Add Rotation Deformer** (anchor + angle) / **Add Warp Deformer** (rows × cols bilinear lattice) in the **Edit** menu
- **Add Parameter** → set key forms at slider extremes via **Set Key** in the parameter dock
- **Mesh editor** — toggle Edit Mesh to drag vertices; clicks within 8 px snap to the nearest
- **Motion timeline** — **Edit > Edit motion…** drags keys and bezier handles; **Ease** reshapes a track to one of 31 named easings (elastic and bounce become sampled keys) and **Simplify Keys** drops the keys of a recorded take that sit within a tolerance of the line through their neighbours
- **Repair Rig** — **Tools > Repair Rig** cleans every drawable's mesh (broken and zero-area triangles, duplicate vertices that share position and UV, unused vertices — bone weights and vertex morphs follow the vertices that stay) and makes each vertex's bone weights sum to 1
- **Save As…** writes the whole rig to a `.puppet` zip

### Runtime

- **Parameter rig** — each parameter holds a key list mapping a slider value to a partial deformer-form snapshot; runtime samples and per-field-lerps
- **Motion playback** — bottom dock with motion list + Play / Pause / Stop / Loop / scrub; curve sampler honours `linear`, `stepped`, `inverse-stepped`, `cubic-bezier` segments (Newton-iterated time → param solve); per-motion fade-in / fade-out
- **Expressions** — stack of `additive` / `multiply` / `overwrite` parameter overlays
- **Pose groups** — mutually-exclusive drawable visibility (weapon swaps, mouth-shape variants); the **Pose** dock picks which member each group shows
- **Physics** — Verlet pendulum chains for hair / cloth / ribbons; input param moves chain anchor, gravity + damping + per-particle springs pull back to rest
- **Vertex morphs** — Cubism-style linear blend between rest and ±extreme deltas; vectorised numpy per-frame at 60 FPS
- **Opacity keys** — parameter-driven alpha curves; lets alternate-pose meshes fade in / out as a gesture parameter fires

### Live input

- Drag-track head — the head and eyes turn toward the cursor as it moves over the canvas
- Auto-blink on a cosine open → close → open curve
- Mic lip-sync via `sounddevice` RMS → `ParamMouthOpenY` (optional dep)
- Lip-sync from an audio file — **Live > Lip-sync from Audio File…** turns a WAV into a motion that opens `ParamMouthOpenY` with its loudness (30 times a second, keys that add nothing dropped) and plays the WAV as its sound; no extra dependency
- Webcam face tracking via OpenCV + the MediaPipe Tasks FaceLandmarker → head yaw / pitch / roll + eye / mouth open (optional deps)
- Custom motion recording — captures parameter values at 30 Hz while you wiggle sliders / face the webcam / let physics run; bakes into a linear-segment Motion ready to play / loop / save

### Cubism interop

The **Cubism Native SDK** can be plugged in (user-supplied DLL — Live2D's Free Material License forbids redistribution) to convert any `.moc3` model into a `.puppet` zip. The converter runs a sample-and-reconstruct sweep that captures both vertex-morph deltas and parameter-driven visibility transitions, so gesture toggles (peace sign / face cover / photo …) survive the conversion intact.

### Output

- **Capture frame…** saves a PNG of the character alone at the rig's own size (long side at most 4096 px) on a transparent background
- **Record…** toggles a 30 FPS frame loop into GIF / WebM / MP4 via `imageio`, the character fitted into 1080 px on white (these frames carry no alpha)
- **Virtual camera** — exposes the puppet canvas as a system webcam
- **NDI output** — broadcasts the puppet as an NDI source on the LAN
- **VTube Studio API server** — opt-in WebSocket API for VTS-compatible clients

### Live streaming to OBS

Two supported paths. Pick A for "just works", B if you want the
lowest latency and best quality on a fast LAN.

#### A. Virtual camera (easiest)

The puppet canvas appears as a webcam OBS picks up via its standard
Video Capture Device source.

1. `pip install pyvirtualcam`
2. Install the platform driver:
   - **Windows**: OBS Studio 26+ ships the *OBS Virtual Camera*
     driver. After installing OBS, open it once and click **Start
     Virtual Camera** in the bottom-right panel — that registers
     the driver system-wide so `pyvirtualcam` can find it.
   - **macOS**: OBS for Mac ships an OBS Virtual Camera system
     extension. First run will prompt to enable it under
     System Settings → Privacy & Security.
   - **Linux**: `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"` (install `v4l2loopback-dkms` first).
3. In the Puppet tab, open your rig, then toggle **Output > Virtual
   camera**. The status bar shows the exact device name to pick.
4. In OBS: **Sources > + > Video Capture Device**, pick the device
   named in step 3 (typically *OBS Virtual Camera*).

Imervue caps the streaming output's longest side at 1080 px so
Cubism-native canvases (often 3000–8000 px tall) don't get rejected
by the DirectShow virtual-camera driver. Aspect ratio is
preserved; OBS can scale further if needed.

##### Why is the background magenta? (and how to remove it)

Virtual cameras run over **DirectShow** (Windows) / **AVFoundation**
(macOS) / **v4l2loopback** (Linux). All three transports are
**RGB-only — no alpha channel**. OBS's *Video Capture Device*
source treats whatever the camera sends as opaque RGB, so whatever
colour Imervue puts behind the character is what OBS displays.

Imervue picks **magenta `#FF00FF`** as that background because
it's the industry-standard chroma-key colour: it almost never
appears in skin tones, hair, or eye colours, so the chroma-key
threshold can be wide open without eating into the character.

To drop the magenta in OBS:

1. Right-click the *Video Capture Device* source you added → **Filters**
2. In the bottom-left **Effect Filters** panel → **+** → **Color Key**
3. Configure:
   - **Key Color Type**: `Custom Color`
   - **Custom Color**: HEX `FF00FF` (or R = 255 / G = 0 / B = 255)
   - **Similarity**: start at `80`, raise toward `200–300` if any
     magenta edges still show. Higher = more aggressive removal.
   - **Smoothness**: `30–50` softens the edge so the cut doesn't
     look hard / pixelated.
4. Close the dialog. OBS attaches the filter to the source, so
   the next time you enable the virtual camera the chroma-key
   is automatically applied.

If the character has magenta in its palette (unusual but possible
on costume / prop art), the chroma key will eat those pixels too.
Switch to the NDI path below — NDI carries the alpha channel
directly so no chroma-keying is needed.

**Troubleshooting: I still see magenta in OBS**

- Verify the Color Key filter is attached to the **Video Capture
  Device** source, not to a Scene. Filters on the source travel
  with it; filters on the Scene apply on top after the source
  rendered.
- Check the hex is `FF00FF` exactly — `FF00FE` or similar won't
  catch all the magenta pixels.
- Bump *Similarity* up to `300` if there's a thin halo of magenta
  pixels at the character's outline. The edges come from
  GL_LINEAR interpolation against the magenta backdrop; a wider
  similarity tolerance eats them.

#### B. NDI (lowest latency, pro-grade)

NDI (Newtek's Network Device Interface) carries the puppet over
the LAN at sub-50 ms latency with the alpha channel intact.

1. Download and install **NDI Tools** from
   <https://ndi.video/tools/> (includes the NDI runtime).
2. `pip install ndi-python`
3. Install the **obs-ndi** plugin into OBS:
   <https://github.com/obs-ndi/obs-ndi/releases>
4. In the Puppet tab, toggle **Output > NDI output**. The status
   bar reports the NDI source name (default *Imervue Puppet*).
5. In OBS: **Sources > + > NDI Source**, pick the source from
   step 4.

NDI broadcasts at the same 1080-capped resolution as path A, but
delivers RGBA — the off-screen render produces a transparent
background outside the character, NDI ships the alpha channel
intact, and OBS / vMix composite the puppet directly over your
scene without any chroma-key pass.

#### C. Window capture (fallback)

OBS **Sources > + > Window Capture** can grab the Imervue window
directly, no extra dependencies needed. Lower quality and you have
to crop the chrome out yourself, but it works on locked-down
machines where you can't install drivers.

### Demo

The bundled rig is [`examples/puppet/imeru.puppet`](examples/puppet/imeru.puppet) — **Imeru**, Imervue's original mascot: 40 drawables on a 1024 × 1336 canvas, every Cubism-standard parameter plus two-joint arms, Live2D-style parallax head turns, blinking with the irises clipped to the eye whites, hair physics, 8 motions (two Idle loops, TapHead, TapBody and four Gestures including a wave) and 7 expressions. Open it via **File > Examples > Imeru** or **Open Puppet…**, and click her head or body to see her react. She is drawn and rigged entirely by code, so the file carries no third-party rights; `py -3 examples/puppet/imeru/build.py` rebuilds it.

---

## Desktop Pet — frameless overlay

Tab 5 — the **Desktop Pet** puts any `.puppet` character on your desktop as a frameless, transparent overlay. The tab itself is the control panel; the actual character floats on top of (or behind) your other windows. Everything you can do with a rig in the Puppet tab — motions, expressions, physics, idle drivers, webcam / mic input — works here too.

### What you can do

| Feature | What it does |
|---|---|
| Frameless overlay | No window chrome, no taskbar entry — just the character on your desktop. |
| Transparent background | Anything the character doesn't cover shows the desktop through. |
| Drag to move | Left-drag the character to a new spot. Release near a screen edge to **snap** flush against it. |
| Click-through mode | Make the pet ignore your mouse so you can keep working under it. |
| Lock position | Freeze the pet so accidental drags can't move it. |
| Always on bottom | Sit the pet behind every other window — a desktop-widget feel instead of always-on-top. |
| Hide on fullscreen | Auto-hide while another app (game / video / presentation) is fullscreen on the same monitor; come back when fullscreen ends. |
| Pauses when hidden | The pet stops repainting while invisible; the live drivers' timers keep running. |
| Size presets | Small / medium / large. Resizes around the centre so the pet doesn't jump across the screen. |
| Opacity slider | Fade the pet from 10% to 100% so it can be a subtle desktop ornament. |
| Remembers where you put it | Drag the pet to your favourite corner; it returns there on the next launch. |
| Global hotkeys | Show / hide the pet, lock it, toggle click-through or make it speak from any app (needs `pynput`): Ctrl+Shift+P / L / T / Space by default, each rebindable in the tab's **Global hotkeys** group. A key another action already uses is refused, and saved keys that two actions share are named in the status line. |

### Click interactions

- **Left-click the body** — if the rig defines a hit area (e.g. tap the head), the matching motion plays. Otherwise the pet greets you with a speech bubble.
- **Right-click anywhere** — opens a context menu with: Hide pet, Live drivers, Play motion (list of every motion in the rig), Apply expression, Pose (pick each pose group's shown member), Lock position, Click-through, Always on bottom, Hide on fullscreen, Speech bubble, Size.
- **System tray icon** — left-click to toggle visibility, right-click for Show/Hide, Click-through, Open puppet, Hide pet.

### Live drivers

Pick any combination from the tab or the right-click menu. Auto idle, Idle motions and Auto-blink are on by default; the rest are off — turn on only what you want.

- **Auto idle** — breath + subtle drift so the character feels alive.
- **Idle motions** — randomly cycle through the rig's idle-group motions.
- **Auto-blink** — natural cyclic eye-close every few seconds.
- **Drag-track head** — the head and eyes turn toward your cursor while it is over the pet.
- **Mouse gaze** — the eyes and head follow your cursor anywhere on screen.
- **Mic lip-sync** — the mouth opens with your voice (needs `sounddevice`).
- **Webcam tracking** — your head / eyes / mouth drive the puppet's (needs `opencv-python` and `mediapipe`).

### How to start

1. Switch to the **Desktop Pet** tab.
2. Click **Load bundled Imeru** to use the included character, or **Open Puppet…** to pick your own `.puppet` file.
3. Tick **Show pet on desktop**.
4. Drag the character to where you want it; pick the drivers you want; adjust opacity / size.
5. Right-click any time for the quick-action menu, or use the system tray icon to hide the pet without finding the tab.

Everything you set — position, drivers, opacity, click-through, size — is remembered between launches.

The **Desktop Pet Integrations** plugin (**Plugins > Download Plugins**) adds **Plugins > Desktop Pet Integrations**: the pet reacts to OBS (streaming, recording, scene changes), to Twitch chat keywords (anywhere in a message, or `=hi` for the whole message, `!dance*` for its start, `/go+al/` for a regular expression), to a local webhook (`POST http://127.0.0.1:9876/trigger` with `{"group": "Wave", "speech": "Hi!"}`) and to Windows notifications. It is also the example of a pet plugin built on `on_pet_created`.

### Custom voice (pet script)

The pet's speech bubble draws from a JSON file you can author yourself. Click **Load script…** in the **Pet script** group of the Desktop Pet tab and pick a `.petscript.json`. The schema:

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

- **`greetings`** — used when nothing more specific matches a click.
- **`time_of_day_greetings`** — greetings per local clock band (`morning` 05–11 h, `afternoon` 12–17 h, `evening` 18–21 h, `night` 22–04 h), used before `greetings`; a band without lines falls back to `greetings`.
- **`hit_responses`** — per-`HitArea` lines. Keys must match the hit-area IDs defined in the rig.
- **`motion_lines`** — per-motion lines. Spoken when a hit-area click plays a motion with that name (not when a motion is started from the context menu).
- **`scheduled`** — timer-driven chimes. Each entry fires every `every_seconds` seconds.

Lines cycle round-robin per bucket so the user doesn't hear the same line twice in a row. **Reset to default** drops the custom script and brings back the built-in greeting set.

A working sample lives at [`examples/desktop_pet/imeru.petscript.json`](examples/desktop_pet/imeru.petscript.json); its head and body lines answer clicks on Imeru's `Head` and `Body` hit areas.

---

## Keyboard & Mouse Shortcuts

### Navigation (all modes)

| Shortcut | Action |
|----------|--------|
| Arrow Keys | Grid: move the focus ring (Enter opens it) / Deep zoom: Left/Right switch images |
| Ctrl+Shift+←/→ | Jump to previous / next sibling folder with images |
| Alt+← / Alt+→ | History back / forward |
| Ctrl+G | Go to image by index |
| X | Jump to a random image |
| Home | Fit the image to the window (on the thumbnail wall: scroll back to the top) |
| Ctrl+F or / | Open fuzzy search dialog |
| T | Open Tags & Albums |
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
| E | Open the current image in the annotation editor |
| W / Shift+W | Fit to width / height |
| Shift+F | Fit to window |
| - / = | Zoom out / in |
| V | Reading mode (fit to width, scroll to read, go on to the next image at the end) |
| L | Loupe: a magnifier that follows the cursor (also over the thumbnails) |
| H | Toggle RGB histogram overlay |
| F8 / Ctrl+F8 | OSD overlay / debug HUD |
| Shift+P | Toggle pixel view (≥ 400 % zoom shows RGB; the grid once ≤ 40,000 pixels are on screen) |
| Shift+M | Cycle color modes (Normal / Grayscale / Invert / Sepia) |
| B | Toggle bookmark |
| Ctrl+C / Ctrl+V | Copy / paste image to/from clipboard |
| 0 / 1-5 | Toggle favorite / quick rating |
| F1-F5 | Quick color label (red / yellow / green / blue / purple) |
| P / Shift+X / U | Cull: Pick / Reject / Unflag |
| Shift+S | Split view |
| Shift+D / Ctrl+Shift+D | Dual-page (LTR / RTL) |
| Ctrl+Shift+M | Multi-monitor mirror window |
| Delete | Move to trash with its `.xmp` / annotation sidecars (undoable); on a drive without a Recycle Bin (memory card, USB stick, network share) the file stays until you choose to delete it for good |
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
| V / T / U / R | Move / Text / Gradient / Smudge |
| M / L / W | Rectangle / Lasso / Magic Wand select |
| P / S / C / Z / H | Pen / Clone / Crop / Zoom / Hand |
| Q | Toggle Quick Mask Mode |
| Tab | Toggle all docks |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous Paint tab |
| , / . | Cycle brush kinds |
| 0-9 | Brush opacity 10% steps |
| Alt+[ / Alt+] | Step active layer down / up |
| Ctrl+[ / Ctrl+] | Move active layer down / up the stack |
| Ctrl+D | Deselect |
| [ / ] | Decrease / increase brush size by 1 px |
| Shift+[ / Shift+] | Decrease / increase brush size by 5 px |
| Ctrl+Shift+N / Ctrl+J / Ctrl+E | Add layer / Duplicate layer / Merge down |
| Ctrl+0 / Ctrl+1 | Fit to window / Actual size (100 %) |
| X | Swap foreground / background colors |
| D | Reset colors to black / white |

---

## Menu Structure

### File

- New Window
- Open File / Open Folder
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

- **Batch** — Format Conversion · EXIF Strip · Image Sanitizer · Image Organizer · Token Batch Rename · Deflicker (Time-lapse) · Document Binarize · Otsu Threshold · Edit Animation · Optimize to Target Size · Meme Caption · Steganography
- **Library & Metadata** — Library Search · Smart Albums · Find Similar Images · Semantic Search · Find Duplicate Images · Auto-Tag Images · Hierarchical Tags · Export Metadata (CSV / JSON) · XMP Sidecars · GPS Geotag · Geotag from GPX Track · Edit Capture Time · Metadata Template · Thumbnail Cache
- **Views** — Timeline View (by day / month / year) · Calendar View · Map View · Scopes & Inspector · Tiny Planet (360°) · Image Statistics · Quality Report · Test Chart · Color blindness preview (protanopia / deuteranopia / tritanopia / achromatopsia)
- **Workflow** — Culling · Staging Tray · Reference Panel · Virtual Copies · Dual-Pane File Manager · Macros · Watched Folder
- **Export** — Contact Sheet PDF · Web Gallery · Slideshow Video (MP4) · Print Layout · Collage · ID Photo Sheet
- **Develop (Non-Destructive)** — Before / After Compare · Develop Presets · Tone Curve · .cube LUT · Split Toning · Local Adjustment Masks · Layers · Levels · Channel Mixer · Gradient Map · Auto Color Balance · Clarity / Dehaze · HSL / Color Mixer · CLAHE · Flatten Background · Frame & Caption · Ordered Dither · Color Map · Distort · Polar Coordinates · Kaleidoscope · Frosted Glass · Pixel Sort · Film Grain · Lens Flare · Threshold / Posterize · Solarize · Diffuse Glow · Graduated Density · Velvia · Emboss · Defringe · Film Negative · Filmic Tone Map · Tone / Detail Equalizer · Soft Proof
- **Retouch & Transform** — AI Image Upscale · Noise Reduction / Sharpening · Healing Brush · Clone Stamp · Frequency Separation · Smart Crop · Portrait Auto-Retouch · Face Detection · Sky / Background · Crop / Straighten · Auto-Straighten · Lens Correction · Scale Bar
- **Multi-Image** — HDR Merge · Panorama Stitch · Focus Stacking · Image Stack · Anaglyph 3D

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
| `on_plugin_unloaded()` | When its window closes, and before Reload Plugins |
| `on_build_menu_bar(plugin_menu)` | After the shared Plugins menu is built |
| `on_build_main_tabs(tabs)` | After the five built-in tabs are added |
| `on_build_context_menu(menu, viewer)` | When right-click menu opens |
| `on_image_loaded(path, viewer)` | After image loads in deep zoom |
| `on_folder_opened(path, images, viewer)` | After folder opens in grid |
| `on_image_switched(path, viewer)` | When navigating between images |
| `on_image_deleted(paths, viewer)` | After image(s) are soft-deleted |
| `on_key_press(key, modifiers, viewer)` | On key press (return True to consume) |
| `on_pet_created(pet)` | When the desktop pet window is created, or already exists when the plugin loads |
| `on_app_closing(main_window)` | Before application closes |
| `get_translations()` | Provide i18n strings |
| `register_languages()` | Class method: register new languages (before each load, and at startup) |

Besides hooks, a plugin can give Batch Export another renderer for Develop recipes: register a `BackendProvider` with `Imervue.image.develop_backends.register` in `on_plugin_loaded`. The GPU Develop plugin is the example; [PLUGIN_DEV_GUIDE.md](PLUGIN_DEV_GUIDE.md) has the details.

A dialog that runs one image transform on **OK** can take the button row, the optional-package install, the worker and the result toast from `Imervue.plugin.tool_dialog.ToolDialogMixin`. A plugin that imports main-program code added after older releases names the plugin API version it needs in a `plugin.json` beside its `__init__.py` (`{"min_api_version": 2}`); an Imervue that is too old skips it with the reason in the log instead of failing inside its imports.

### Plugin Downloader

**Plugins > Download Plugins** opens the online downloader. Source repo: [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins). A plugin that needs a newer Imervue is not installed: the status line names the plugin API version it needs, and any installed copy stays as it was. Update Imervue, then download it again.

---

## MCP Server

Imervue ships a built-in [Model Context Protocol](https://modelcontextprotocol.io) server so AI assistants (Claude Code / Desktop, Cursor, Cline, …) can call into the project's pure-logic helpers without a running GUI. Qt-free; one command:

```sh
python -m Imervue.mcp_server
```

### Tools

Selected tools (58 in total — full list in the docs). Every tool advertises a
JSON `outputSchema` and read-only / destructive `annotations`, returns its
result as `structuredContent`, and long-running tools stream
`notifications/progress`.

| Tool | Purpose |
|------|---------|
| `list_images` | List image files in a folder (recursive optional) |
| `read_image_metadata` / `read_xmp_tags` | Dimensions, format, EXIF, XMP — the sidecar, else what the file embeds (rating, label, keywords) |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | No-reference analysis: per-channel stats, colourfulness/entropy/contrast, histogram + clipping, blur score |
| `image_thumbnail` / `ocr_text` / `find_similar` | Base64 preview, Tesseract text, perceptual-hash near-duplicate groups (with progress) |
| `convert_format` | Convert between PNG / JPEG / WebP / TIFF / BMP / AVIF (+ optional HEIC / JXL) |
| `apply_watermark` / `apply_frame` | Burn in a text watermark or a matte / Polaroid frame + caption |
| `build_collage` | Composite images into a grid montage (with progress) |
| `crop_image` / `resize_image` / `rotate_image` | Pixel crop, resize (one edge keeps the aspect ratio, both give an exact size), lossless rotate / flip. Sizes and coordinates refer to the EXIF-upright image. |
| `collection_stats` | Folder rating / favourite / colour-label / cull summary |
| `search_images` | Filter a folder with the smart-album query DSL (path / EXIF / size / dimensions) |
| `extract_gps` / `dominant_colors` | Read EXIF GPS coordinates (chains into `reverse_geocode`); median-cut colour palette (rgb / hex / pixel_count) |
| `error_level_analysis` | JPEG-recompression tamper map as a PNG data URI |
| `solarize_image` / `glow_image` | Apply a solarize tone reversal or diffuse-glow bloom and save |
| `velvia_image` / `emboss_image` / `defringe_image` | Velvia saturation boost, directional-light emboss, edge-fringe desaturation |
| `film_negative_image` / `graduated_density_image` | Invert a scanned negative; apply a linear graduated-density gradient |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | Filmic highlight rolloff; per-zone exposure; per-band contrast |
| `colormap_image` / `false_color_image` | Recolour luminance through viridis / magma / jet; false-colour exposure scale |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Ordered Bayer dither; shadow/highlight split-tone; brightness-band pixel sort |
| `polar_image` / `kaleidoscope_image` | Warp to / from polar (tiny-planet); mirror into kaleidoscope wedges |
| `frosted_glass_image` / `clahe_image` / `local_contrast_image` | Random-neighbour frosted scatter; CLAHE local equalization; clarity + texture local contrast |
| `posterize_image` / `gradient_map_image` | Quantize channels to flat bands; remap luminance through a gradient |
| `film_grain_image` / `dehaze_image` / `distort_image` | Tunable Gaussian grain; dark-channel dehaze; swirl / pinch / ripple warp |
| `levels_image` / `curve_image` | Black/white point + gamma levels; S-curve / lift-shadows / compress-highlights tone curve |
| `auto_color_balance_image` / `channel_mixer_image` | Auto white-balance (4 methods); 3×3 channel mixer + mono conversion |
| `lens_correction_image` | Correct distortion (k1), vignette and red/blue chromatic aberration |
| `reverse_geocode` / `extract_video_frame` | Offline GPS → city, decode one video frame to a still |
| `puppet_from_png` / `puppet_inspect` | Build a `.puppet` rig from a PNG; open one and return its inventory |
| `puppet_validate` / `puppet_schema` | Check a `.puppet` against the v1 format (schemas, loader, rig checks); return one of its JSON Schemas |

### Prompts

Four reusable prompts: `caption_image`, `suggest_edits`, `analyze_composition`
(saliency-driven composition critique) and `flag_issues` (sharpness + quality +
clipping triage). `completion/complete` suggests values for `suggest_edits`' `style` and
`analyze_composition`'s `focus`.

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

Plugins can register entirely new languages via `language_wrapper.register_language()`, or contribute translations to the built-in ones via `get_translations()` (existing keys are never overwritten, so a plugin can't break a shipped string). A plugin string that is empty, or whose `{placeholders}` differ from the English one, is dropped and logged, so the built-in text shows instead of a blank or an error. **Español** is available exactly this way — install the `spanish_translation` plugin from the downloader and it appears in the Language menu alongside the five built-ins. See [PLUGIN_DEV_GUIDE.md](PLUGIN_DEV_GUIDE.md#internationalization-i18n).

---

## User Settings

Stored in `user_setting.json` next to the application — the project root in a source checkout,
the folder containing the `.exe` in a frozen build (PyInstaller **or** Nuitka).

The file is a **multi-profile container**: each profile holds an independent settings dict, so one
install can carry separate setups (e.g. *Work* and *Personal*). Switch, create, rename and delete
profiles under **File > Profiles…**. A v1 single-profile file left over from an older release is
migrated to the `default` profile automatically on first read. Writes are debounced a few seconds
after the last change and land atomically (`.tmp` sibling + `os.replace`), so an interrupted save
never truncates the file. If the file can't be read at start-up (broken JSON, or another program
holding it), Imervue starts with default settings and, before its first save, keeps the file next
to it as `user_setting.json.unreadable-<date>-<time>`; it never saves over a file it could not
keep that copy of. A warning at start-up names the file and how to get the
earlier settings back.

Each session's log, `imervue.log`, is written to the same folder (to `%LOCALAPPDATA%\Imervue`, or
`~/.cache/imervue` outside Windows, when that folder is read-only). The previous session's log is
kept beside it as `imervue.previous.log`, so after a crash the log that explains it is still there
once Imervue is running again — attach both when reporting a problem.

Key entries in the active profile:

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
| `puppet_tab_enabled` / `desktop_pet_tab_enabled` | bool | Optional tabs (on by default; applied at the next start) |

---

## Architecture

```
Imervue/
├── __main__.py              # Application entry point
├── cli.py                   # Headless batch CLI (no Qt)
├── Imervue_main_window.py   # Main window (QMainWindow) — mounts the 5 tabs
├── gpu_image_view/          # IMERVUE TAB — GPU viewer, deep zoom, tile wall
│   ├── actions/             #   viewer verbs (delete / select / compare / slideshow)
│   └── images/              #   loading layer (decode workers, folder scan, prefetch)
├── gui/                     # Qt shells — dialogs, side panels, develop panel, canvases
├── paint/                   # PAINT TAB — full-featured raster editor
│   ├── docks/               #   dock panels (colour / brush / layer / material / …)
│   └── tools/               #   pointer-tool handlers
├── puppet/                  # PUPPET TAB — 2D rigged-puppet animator + Cubism interop
├── desktop_pet/             # DESKTOP PET TAB — frameless overlay + live drivers & hooks
├── image/                   # Pure image core (no Qt) — recipe pipeline, filters, codecs,
│                            #   pyramid / tile manager, XMP, pHash, metadata
├── library/                 # SQLite library index, smart albums, CLIP search, culling
├── export/                  # Export generators (contact sheet, web gallery, MP4, cheat sheet)
├── macros/                  # Macro record / replay
├── menu/                    # Menu definitions (file / tools / filter / right-click / …)
├── mcp_server/              # Model Context Protocol stdio server
├── multi_language/          # i18n (en / zh-tw / zh-cn / ja / ko) + validation
├── external/                # External editor integration
├── plugin/                  # Plugin system (base / manager / downloader / pip installer)
├── sessions/                # Session & workspace serialization + migration
├── system/                  # OS integration — themes, UI scale, file association,
│                            #   clipboard monitor, tree watcher, batch trash, logging
└── user_settings/           # Persistent multi-profile config, tags, ratings, bookmarks
```

Two rules hold across the tree:

- **Pure logic is separated from Qt.** A single-image tool is normally `image/<feature>.py`
  (NumPy / Pillow, importable from a worker thread or a test with no display) plus
  `gui/<feature>_dialog.py` (the Qt shell) and one entry in `menu/extra_tools_menu.py`.
- **Big Qt classes delegate.** `GPUImageView`, `PetWindow` and `PaintWorkspace` keep only the
  event overrides and lifecycle; behaviour lives in named collaborators (`InputController`,
  `OverlayPainter`, `PetInteraction`, `ToolDispatcher`, …), whose maths is again extracted into
  pure modules that unit-test without a GL context.

### Rendering pipeline (Imervue tab)

1. `GPUImageView` extends `QOpenGLWidget`
2. Two GLSL 1.20 programs (textured quads + solid color rectangles)
3. LRU texture cache — 256-tile soft limit (512 hard ceiling); VRAM budget probed from the GL driver, 1.5 GB fallback, user-overridable
4. Multi-level tile pyramid built with LANCZOS at 512 × 512 tile size
5. Anisotropic filtering up to 8× when hardware supports it
6. Software-rendering fallback if shader compilation fails

### Thumbnail cache

- **Key**: MD5 of `{path}|{mtime_ns}|{file_size}|{thumbnail_size}|{recipe_hash}` — the recipe hash is what makes a develop edit show up on the thumbnail without invalidating every other entry
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
