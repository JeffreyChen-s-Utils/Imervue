Imervue User Guide
==================

A lightweight, GPU-accelerated image viewer with browsing, editing, annotation, and batch processing.

.. contents:: Table of Contents
   :depth: 2
   :local:

----

Getting Started
---------------

When you open Imervue, you will see three areas:

::

   +------------+----------------------+----------+
   |  Folder    |                      |   EXIF   |
   |  Tree      |   Image Viewer       |  Sidebar |
   |            |                      |          |
   +------------+----------------------+----------+

- **Left**: Folder tree. Click a folder to browse the images inside.
- **Center**: Image display area. Shows all images as a thumbnail grid.
- **Right**: EXIF sidebar. Displays shooting information for the selected image.

----

Opening Images
--------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - How
   * - Open Folder
     - ``File`` > ``Open Folder``, then choose a directory
   * - Open Single Image
     - ``File`` > ``Open Image``, then choose a file
   * - Drag & Drop
     - Drag an image or folder directly into the window
   * - Open from Explorer
     - Right-click an image > ``Open with Imervue`` (requires file association)
   * - Recent Files
     - ``File`` > ``Recent``, quickly reopen a previously visited folder

Supported Formats
^^^^^^^^^^^^^^^^^

- **Standard**: PNG, JPEG, BMP, TIFF, WebP, GIF, APNG, SVG
- **RAW**: CR2 (Canon), NEF (Nikon), ARW (Sony), DNG (Adobe), RAF (Fujifilm), ORF (Olympus)

----

Browsing Images
---------------

Thumbnail Grid Mode
^^^^^^^^^^^^^^^^^^^^

After opening a folder, all images are displayed as thumbnails.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Method
   * - Scroll
     - Mouse wheel
   * - Pan
     - Hold middle mouse button and drag
   * - Enter full-size view
     - Left-click any thumbnail
   * - Change thumbnail size
     - Menu ``Thumbnail Size`` > choose 128 / 256 / 512 / 1024
   * - Thumbnail density
     - ``Thumbnail Size`` > ``Thumbnail Density`` > Compact / Standard / Relaxed
   * - Hover preview popup
     - Rest the cursor on a thumbnail for 500 ms to see a larger preview
   * - Select multiple images
     - Left-click and drag to draw a selection rectangle
   * - Pan with keyboard
     - Arrow keys; hold ``Shift`` for fine movement

Each thumbnail shows status badges: a coloured strip on the left edge (colour label),
a heart at the top-left (favourite), a star at the top-right (bookmark), and rating stars
at the bottom-left. A spinner placeholder is drawn for thumbnails that are still loading.

List (Detail) Mode
^^^^^^^^^^^^^^^^^^

Press ``Ctrl + L`` to toggle between thumbnail grid and a sortable list view with these columns:
Preview · Label · Name · Resolution · Size · Type · Modified. Double-click a row (or press ``Enter``) to enter
Deep Zoom; press ``Esc`` to return to the list. Thumbnails and metadata are loaded lazily on a worker thread
so very large folders stay responsive.

Deep Zoom Mode
^^^^^^^^^^^^^^

Click a thumbnail to enter Deep Zoom mode for high-quality single-image viewing.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Method
   * - Zoom in/out
     - Mouse wheel or touchpad pinch
   * - Pan
     - Hold middle mouse button
   * - Previous image
     - ``Left Arrow`` (or swipe right on touchpad)
   * - Next image
     - ``Right Arrow`` (or swipe left on touchpad)
   * - Cross-folder jump
     - ``Ctrl + Shift + Left`` / ``Right`` to previous/next sibling folder with images
   * - History back / forward
     - ``Alt + Left`` / ``Alt + Right`` (browser-style)
   * - Jump to image by number
     - ``Ctrl + G``
   * - Random image
     - ``X``
   * - Fit to width
     - ``W``
   * - Fit to height
     - ``Shift + W``
   * - Reset zoom
     - ``Home``
   * - Return to thumbnails
     - ``Esc``
   * - Fullscreen
     - ``F`` (press again to exit)
   * - Theater mode
     - ``Shift + Tab`` hides menu / status / tree / tabs for distraction-free viewing
   * - OSD info overlay
     - ``F8`` shows filename / size / type; ``Ctrl + F8`` shows a debug HUD (VRAM / cache / threads)
   * - Pixel view
     - ``Shift + P`` — at ≥ 400 % zoom overlays a pixel grid and shows RGB / HEX under the cursor
   * - Colour modes
     - ``Shift + M`` cycles Normal / Grayscale / Invert / Sepia (GLSL, non-destructive)

Split View & Dual-Page Reading
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Display two images side by side directly in the main window without opening the Compare dialog:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Action
     - Shortcut
   * - Split view (two images)
     - ``Shift + S``
   * - Dual page (current + next)
     - ``Shift + D``
   * - Dual page, right-to-left (manga)
     - ``Ctrl + Shift + D``
   * - Return to previous mode
     - ``Esc``

In dual-page mode, arrow keys advance by two images at a time. The RTL variant swaps the two panels
so page 1 appears on the right.

Multi-Monitor Window
^^^^^^^^^^^^^^^^^^^^

Press ``Ctrl + Shift + M`` to open a frameless second window on your secondary display that mirrors
the image currently shown in the main viewer. The main window keeps browsing independently — useful
for exhibitions, dual-screen editing workflows, or client presentations. Press ``Ctrl + Shift + M`` again
to close, or use ``Esc`` inside the second window.

----

Organising Images
-----------------

Rating & Favourites
^^^^^^^^^^^^^^^^^^^

In Deep Zoom mode you can quickly rate images:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Key
   * - Toggle favourite
     - ``0``
   * - Rate 1 -- 5 stars
     - ``1`` ``2`` ``3`` ``4`` ``5`` (press again to clear)

Colour Labels (F1 -- F5)
^^^^^^^^^^^^^^^^^^^^^^^^

Independent Lightroom-style colour flags, stored separately from the 1 -- 5 star rating. Useful for
quick categorisation (e.g. red = reject candidates, green = selects, blue = to retouch).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Key
   * - Red / Yellow / Green / Blue / Purple
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5`` (press the same key again to clear)
   * - Batch apply to selection
     - Select multiple thumbnails, then press the corresponding F key
   * - Filter by colour
     - ``Filter`` > ``By Color Label`` > pick a colour / Any label / No label

The status bar shows a coloured chip for the current image. Thumbnails display a coloured strip on
the left edge. The List view has a dedicated Label column you can sort by.

Bookmarks
^^^^^^^^^

Save frequently used images as bookmarks for quick access later.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Method
   * - Add / remove bookmark
     - Press ``B`` in Deep Zoom mode
   * - Manage bookmarks
     - ``File`` > ``Bookmarks``

Tags & Albums
^^^^^^^^^^^^^

Categorise your images with tags and albums.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Method
   * - Open manager
     - Press ``T`` or ``File`` > ``Tags & Albums``
   * - Tag an image
     - Right-click image > ``Add to Tag``
   * - Add to album
     - Right-click image > ``Add to Album``
   * - Filter by a single tag / album
     - ``Filter`` > ``By Tag`` / ``By Album``
   * - Multi-tag filter (AND / OR)
     - ``Filter`` > ``Multi-Tag Filter…`` — check multiple tags or albums, choose Any (OR) or All (AND)

Sorting & Filtering
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Feature
     - Menu Location
   * - Sort by name
     - ``Sort`` > ``By Name``
   * - Sort by date modified
     - ``Sort`` > ``By Modified Date``
   * - Sort by file size
     - ``Sort`` > ``By File Size``
   * - Sort by resolution
     - ``Sort`` > ``By Resolution``
   * - Ascending / Descending
     - ``Sort`` > ``Ascending`` / ``Descending``
   * - Filter by extension
     - ``Filter`` > ``JPEG`` / ``PNG`` / ``RAW`` etc.
   * - Filter by rating
     - ``Filter`` > ``By Rating``
   * - Filter by colour label
     - ``Filter`` > ``By Color Label`` (All / Any label / No label / Red / Yellow / Green / Blue / Purple)
   * - Advanced filter
     - ``Filter`` > ``Advanced Filter…`` — resolution range, file size range, orientation (landscape / portrait / square), modified-date range
   * - Clear filters
     - ``Filter`` > ``Clear Filter``

Browse Mode (Grid / List)
^^^^^^^^^^^^^^^^^^^^^^^^^

Switch the image browser between the tile grid and a sortable detail list:

- ``Ctrl + L`` — toggle Grid ↔ List
- Menu: ``Thumbnail Size`` > ``Browse Mode`` > Grid / List
- In List mode, any column (including Label) is sortable; double-click a row or press ``Enter`` to open Deep Zoom.

----

Editing Images (Modify Tab)
---------------------------

Switch to the **Modify** tab at the top of the window to enter editing mode.
You can also press ``E`` or right-click > ``Modify`` in Deep Zoom mode.

::

   +--------+----------------------+------------+
   | Tools  |                      | Properties |
   | Strip  |   Canvas (draw here) | Brushes    |
   |        |                      | Develop    |
   +--------+----------------------+------------+

Annotation Tools (Left Panel)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Tool
     - Icon
     - Description
   * - Select
     - |select|
     - Select existing annotations; drag to move
   * - Rectangle
     - |rect|
     - Draw rectangles
   * - Ellipse
     - |ellipse|
     - Draw ellipses or circles
   * - Line
     - |line|
     - Draw straight lines
   * - Arrow
     - |arrow|
     - Draw arrows
   * - Freehand
     - |freehand|
     - Free-form drawing
   * - Text
     - T
     - Add text to the image
   * - Mosaic
     - |mosaic|
     - Pixelate a selected region
   * - Blur
     - |blur|
     - Gaussian-blur a selected region

.. |select| unicode:: U+2B1A
.. |rect| unicode:: U+25A2
.. |ellipse| unicode:: U+25EF
.. |line| unicode:: U+2571
.. |arrow| unicode:: U+2192
.. |freehand| unicode:: U+270E
.. |mosaic| unicode:: U+25A6
.. |blur| unicode:: U+25CC

.. tip::
   Press ``Left Arrow`` / ``Right Arrow`` while in the Modify tab to switch between images without leaving the editor.

Brush Types (Right Panel)
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Brush
     - Effect
   * - Pen
     - Standard thin line, the most common brush
   * - Marker
     - Thicker, semi-transparent strokes
   * - Pencil
     - Thin, slightly faded line
   * - Highlighter
     - Wide and highly transparent, like a real highlighter
   * - Spray
     - Scattered dot effect
   * - Calligraphy
     - Stroke width varies with direction
   * - Watercolor
     - Soft, blended wet-edge effect
   * - Charcoal
     - Rough, textured stroke
   * - Crayon
     - Waxy, crayon-like texture

Drawing Properties (Right Panel)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Property
     - Description
   * - Colour
     - Click the colour swatch to pick a drawing colour
   * - Stroke Width
     - Drag the slider to adjust line thickness (1 -- 40)
   * - Opacity
     - Adjust transparency (0 % -- 100 %)
   * - Font
     - Choose the font for the Text tool
   * - Font Size
     - Adjust text size (6 -- 200 px)

Image Adjustments (Right Panel, Lower)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Slider
     - Function
   * - Exposure
     - Adjust overall brightness
   * - Brightness
     - Fine-tune light and dark areas
   * - Contrast
     - Adjust the difference between lights and darks
   * - Saturation
     - Adjust colour vividness

These adjustments are **non-destructive**. Press ``Reset`` at any time to restore the original.

Save & Undo
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Button
     - Description
   * - Save
     - Write annotations and adjustments to the original file
   * - Undo
     - Undo the last operation
   * - Redo
     - Redo an undone operation
   * - Reset
     - Clear all image adjustments

----

Rotation & Flipping
--------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Action
     - Shortcut
     - Menu
   * - Rotate 90 ° clockwise
     - ``R``
     - Right-click > Modify > Rotate CW
   * - Rotate 90 ° counter-clockwise
     - ``Shift + R``
     - Right-click > Modify > Rotate CCW
   * - Flip horizontal
     - --
     - Right-click > Modify > Flip Horizontal
   * - Flip vertical
     - --
     - Right-click > Modify > Flip Vertical
   * - Lossless rotate (JPEG)
     - --
     - Right-click > Lossless Rotate

----

Exporting Images
----------------

Single Export
^^^^^^^^^^^^^

Right-click an image > ``Export / Save As``.

- Choose format: PNG, JPEG, WebP, BMP, TIFF
- Adjust quality (for lossy formats)
- Preview estimated file size
- Pick a save location

Batch Export
^^^^^^^^^^^^

Select multiple images, then right-click > ``Batch Export``.

- Uniform format conversion
- Set maximum width / height (auto aspect-ratio scaling)
- Quality control
- Real-time progress bar

Create GIF / Video
^^^^^^^^^^^^^^^^^^^

Select multiple images, then right-click > ``Create GIF / Video``.

- GIF and MP4 output
- Drag to reorder frames
- Set frames per second (FPS)
- Custom dimensions
- Loop option

----

Animation Playback
------------------

When opening GIF, APNG, or animated WebP files, animation plays automatically.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``Space``
     - Play / Pause
   * - ``,``
     - Previous frame
   * - ``.``
     - Next frame
   * - ``]``
     - Speed up
   * - ``[``
     - Slow down

----

Image Comparison
----------------

In thumbnail mode, select 2 -- 4 images, then right-click > ``Compare Images``.

The dialog has three tabs:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Tab
     - Purpose
   * - **Side-by-side**
     - Display 2 or 4 images simultaneously; each auto-scales in its pane.
   * - **Overlay**
     - Blend two images with an alpha slider (0 → A only, 100 → B only). Requires exactly 2 selected.
   * - **Difference**
     - Per-pixel ``|A − B|`` visualisation with a gain slider (0.10× – 20×) to amplify subtle changes.

When the two images have different sizes, ``B`` is resampled to ``A``'s dimensions with Lanczos. Very large
images are capped at 2048 px on the long edge internally so overlay / difference stay interactive.

.. seealso::
   For inline comparison without opening a dialog, use **Split View** (``Shift + S``) or
   **Dual-Page Reading** (``Shift + D`` / ``Ctrl + Shift + D``) described in the Browsing section.

----

Slideshow
---------

Press ``S`` or right-click > ``Slideshow`` to start an automatic slideshow.

- Adjustable interval per image
- Optional fade transition between images

----

Search
------

Press ``Ctrl + F`` or ``/`` and type a keyword to search images in the current folder by filename.

Search uses **fuzzy matching** with a three-tier rank (prefix > substring > subsequence) and
**substring highlighting** in the results. Press ``Enter`` or double-click to jump to an image.

To jump by **image index** rather than name, press ``Ctrl + G`` for the Go-to dialog.

----

Copy & Paste
------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Action
     - Method
   * - Copy image to clipboard
     - ``Ctrl + C`` in Deep Zoom mode
   * - Paste clipboard image
     - ``File`` > ``Paste from Clipboard``, or ``Ctrl + V``
   * - Auto-monitor clipboard
     - ``File`` > ``Auto-annotate Clipboard Images`` (toggle)

.. note::
   When auto-monitor is enabled, every time a new image appears on the clipboard (e.g. from a screenshot tool), the annotation editor opens automatically.

----

Deleting Images
---------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Action
     - Method
   * - Delete current image
     - Press ``Delete``
   * - Delete selected images
     - Select multiple, then ``Delete`` or right-click > ``Delete Selected``

Images are moved to the system Recycle Bin / Trash and can be recovered from there.

----

Batch Operations
----------------

In thumbnail mode, select multiple images then right-click:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Feature
     - Description
   * - Batch Rename
     - Rename using templates: ``{name}``, ``{n}``, ``{ext}``
   * - Move / Copy
     - Move or copy images to another folder
   * - Rotate All
     - Rotate all selected images at once
   * - Batch Export
     - Convert format and resize in bulk
   * - Add to Tag
     - Apply the same tag to all selected images
   * - Add to Album
     - Place all selected images into an album

----

RGB Histogram
-------------

Press ``H`` in Deep Zoom mode to overlay an RGB histogram on the image. Press again to hide.

----

Set as Wallpaper
----------------

Right-click in Deep Zoom mode > ``Set as Wallpaper`` to set the current image as your desktop wallpaper.

Supported on Windows, macOS, and Linux (GNOME).

----

Multi-Window
------------

``File`` > ``New Window`` opens another independent Imervue window. Each window can browse a different folder.

Workspace Layout Presets
------------------------

``File`` > ``Workspaces…`` captures the current window geometry, dock / toolbar
arrangement, splitter sizes, and active root folder under a name — then lets
you flip between saved layouts the same way Lightroom switches *Library* /
*Develop* / *Export* or Adobe Bridge switches *Metadata* / *Filmstrip*. The
dialog supports Save Current, Load, Rename, and Delete. Workspaces persist in
``user_settings.json`` (under the ``workspaces`` key) and survive across
sessions.

.. tip::
   Build a **Browse** workspace with the tree and thumbnail grid visible, and a
   separate **Develop** workspace with the develop panel maximised and the tree
   collapsed. One click moves your whole window to the right shape for each
   task.

Touchpad Gestures
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Gesture
     - Action
   * - Pinch
     - Zoom in / out in Deep Zoom (anchored at pinch centre)
   * - Horizontal swipe
     - Previous / next image

----

File Association (Windows)
--------------------------

Register Imervue as an image viewer in Windows Explorer:

1. ``File`` > ``File Association`` > ``Register 'Open with Imervue'``
2. Administrator privileges are required.
3. After registration, right-click any image in Explorer to see the ``Open with Imervue`` option.

To remove: ``File`` > ``File Association`` > ``Remove file association``.

----

Plugin System
-------------

Imervue supports plugins for extended functionality.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Action
     - Menu Location
   * - View installed plugins
     - ``Plugins`` > ``Manage Plugins``
   * - Download new plugins
     - ``Plugins`` > ``Download Plugins``
   * - Open plugins folder
     - ``Plugins`` > ``Open Plugin Folder``
   * - Reload plugins
     - ``Plugins`` > ``Reload Plugins``

----

Language
--------

Switch the interface language from the ``Language`` menu:

- English
- Traditional Chinese (繁體中文)
- Simplified Chinese (简体中文)
- Korean (한국어)
- Japanese (日本語)

A restart is required after switching.

----

Keyboard Shortcuts Reference
-----------------------------

Browsing
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``Left`` / ``Right``
     - Previous / next image
   * - Arrow keys
     - Pan in thumbnail mode
   * - ``Shift + Arrow``
     - Fine pan
   * - ``Ctrl + Shift + Left`` / ``Right``
     - Jump to previous / next sibling folder with images
   * - ``Alt + Left`` / ``Alt + Right``
     - History back / forward (browser-style)
   * - ``Ctrl + G``
     - Jump to image by number
   * - ``X``
     - Jump to a random image
   * - Mouse wheel / Pinch
     - Zoom in / out
   * - Horizontal swipe
     - Previous / next image
   * - Middle-click drag
     - Pan
   * - ``F``
     - Fullscreen
   * - ``Shift + Tab``
     - Theater mode (hide all chrome)
   * - ``Ctrl + L``
     - Toggle Grid ↔ List (detail) browse mode
   * - ``Shift + S``
     - Split view (two images side by side)
   * - ``Shift + D`` / ``Ctrl + Shift + D``
     - Dual-page reading / RTL (manga)
   * - ``Ctrl + Shift + M``
     - Mirror current image on a second monitor
   * - ``Esc``
     - Return to thumbnails / exit fullscreen / close dual or list mode
   * - ``W``
     - Fit to width
   * - ``Shift + W``
     - Fit to height
   * - ``Home``
     - Reset zoom

Editing
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``E``
     - Open Modify tab
   * - ``R``
     - Rotate clockwise
   * - ``Shift + R``
     - Rotate counter-clockwise
   * - ``Ctrl + Z``
     - Undo
   * - ``Ctrl + Shift + Z``
     - Redo
   * - ``Delete``
     - Delete image

Organising
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``0``
     - Toggle favourite
   * - ``1`` -- ``5``
     - Rate (press again to clear)
   * - ``F1`` -- ``F5``
     - Colour label: red / yellow / green / blue / purple (press same key to clear)
   * - ``P``
     - Cull: Pick (flag for keep)
   * - ``Shift + X``
     - Cull: Reject
   * - ``U``
     - Cull: Unflag
   * - ``B``
     - Toggle bookmark
   * - ``T``
     - Tags & Albums manager

Tools & Overlays
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``Ctrl + F`` / ``/``
     - Fuzzy search with substring highlighting
   * - ``Ctrl + C``
     - Copy image to clipboard
   * - ``Ctrl + V``
     - Paste from clipboard
   * - ``H``
     - RGB histogram
   * - ``F8`` / ``Ctrl + F8``
     - OSD info overlay / Debug HUD (VRAM, cache, threads)
   * - ``Shift + P``
     - Pixel view (≥ 400 % shows pixel grid and RGB value under cursor)
   * - ``Shift + M``
     - Cycle colour modes (Normal / Grayscale / Invert / Sepia)
   * - ``S``
     - Slideshow

Animation
^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``Space``
     - Play / Pause
   * - ``,``
     - Previous frame
   * - ``.``
     - Next frame
   * - ``[``
     - Slow down
   * - ``]``
     - Speed up

----

Library & Metadata Management
-----------------------------

Imervue keeps a SQLite-backed index at ``%LOCALAPPDATA%/Imervue/library.db``
(Windows) or ``~/.cache/imervue/library.db`` (POSIX) for cross-folder search,
hierarchical tags, smart albums, perceptual hashes, notes, and cull flags.
Everything below lives under ``Extra Tools`` unless noted.

Library Search
^^^^^^^^^^^^^^

``Extra Tools`` > ``Library Search`` lets you add one or more **root folders**
to a global index that is crawled in a background thread. Once a root is
indexed you can query it by extension, min width/height, size range, or name
substring and drop the results into the viewer as a virtual album.

Smart Albums
^^^^^^^^^^^^

``Extra Tools`` > ``Smart Albums`` persists filter rules (extensions, minimum
dimensions, colour labels, rating, favourites, cull state, hierarchical tags,
name substring) under a friendly name. Reapplying an album filters the active
folder by the saved rules.

Similar-Image Search
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Find Similar Images`` runs a 64-bit DCT pHash on the
current deep-zoom image (or the first selected tile) and lists near matches
from the index sorted by Hamming distance. Adjust the ``Max distance`` spin to
widen or tighten the net.

Semantic Search (CLIP)
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Semantic Search`` lets you type a natural-language phrase
(for example *"golden retriever in snow"* or *"neon street at night"*) and
returns ranked images from the indexed library. Each image is embedded with a
CLIP vision/language encoder and stored alongside its path; a text query is
embedded into the same vector space and compared by cosine similarity.

Embeddings are cached to ``%LOCALAPPDATA%/Imervue/clip_cache.npz`` (Windows) or
``~/.cache/imervue/clip_cache.npz`` (POSIX) as a single compact ``.npz`` archive
so the next launch skips re-encoding. Only the paths you have scanned are
queryable — use ``Scan Folder…`` inside the dialog to extend the index.

.. note::
   Semantic Search requires the optional ``open_clip_torch`` and ``torch``
   packages. If they are not installed the menu entry explains what is missing
   and other features continue to work.

Auto-Tag
^^^^^^^^

``Extra Tools`` > ``Auto-Tag Images`` applies heuristic tags under
``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``landscape`` /
``portrait``). If ``onnxruntime`` and a CLIP model at
``models/clip_vit_b32.onnx`` are available, it also adds CLIP-based content
labels. Runs on a worker thread with a live progress bar.

Hierarchical Tags
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Hierarchical Tags`` manages tree-structured tags such as
``animal/cat/british``. Select a tag to see every image beneath that branch
(descendants included). Tag or untag the current selection with one click.
Hierarchical tags live in the library index and are complementary to the flat
tag system in the right-click menu.

Token Batch Rename
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Token Batch Rename`` opens a live-preview table where you
type a template like ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` and see
exactly what every file will be renamed to. Conflicts are highlighted so
nothing is overwritten. Supported tokens: ``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``.

Metadata Export
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Export Metadata (CSV / JSON)`` writes a row per image in
the current view covering EXIF, dimensions, color label, rating, favourite,
hierarchical tags, cull state, and notes. Useful for feeding cull decisions
into a spreadsheet or external workflow.

Culling (Pick / Reject)
^^^^^^^^^^^^^^^^^^^^^^^

Lightroom-style three-state cull flag. Press ``P`` to pick the current image
or every selected tile, ``Shift + X`` to reject, ``U`` to unflag. ``Filter`` >
``By Cull State`` shows only picks, rejects, or unflagged. ``Extra Tools`` >
``Culling`` applies the filter via a dialog and also exposes a **Delete all
rejects** button that permanently removes the flagged files from disk.

Staging Tray
^^^^^^^^^^^^

``Extra Tools`` > ``Staging Tray`` is a cross-folder basket. Add any set of
tiles to the tray (the list survives restarts), then move or copy the entire
tray into a destination folder in one click. Useful for gathering picks from
many shoots before export.

Dual-Pane File Manager
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Dual-Pane File Manager`` opens a Total Commander-style
two-tree view. Choose a folder in each pane and move/copy the selection
between them without leaving Imervue.

Timeline View
^^^^^^^^^^^^^

``Extra Tools`` > ``Timeline View`` groups the current image set by day,
month, or year (Google Photos style). Date is taken from EXIF
``DateTimeOriginal`` when present, otherwise from the file modification time.
Double-click any image to open it in Deep Zoom.

Drag-out to External Apps
^^^^^^^^^^^^^^^^^^^^^^^^^

Press and drag from a **selected** tile to drop the file into Explorer,
Chrome, Discord, or any app that accepts file URLs. The drag preview is the
tile thumbnail.

Per-Image Notes
^^^^^^^^^^^^^^^

The EXIF sidebar includes a free-text **Notes** box. Typing auto-saves to the
library index after a short debounce. Notes travel with the image path, so
they survive folder re-scans.

----

Command-Line Usage
------------------

::

   imervue                        # Launch normally
   imervue /path/to/image         # Open a specific image
   imervue /path/to/folder        # Open a specific folder
   imervue --debug                # Enable debug mode
   imervue --software_opengl      # Use software rendering (when GPU is unsupported)
