Imervue User Guide
==================

A GPU-accelerated image workstation that ships **four top-level tabs**.
Most of this guide is organised around those four sections.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Tab
     - What it does
   * - **Imervue**
     - Browse, view, organise, search, and batch-process your image library.
       See *Imervue Tab — Image Viewer & Library*.
   * - **Modify**
     - Non-destructive develop pipeline — sliders, curves, LUTs, masks,
       retouch, multi-image. See *Modify Tab — Non-destructive Develop*.
   * - **Paint**
     - full-featured raster paint studio with brushes, layers, animation,
       manga tools, PSD I/O. See *Paint Tab — full-featured Raster Editor*.
   * - **Puppet**
     - From-scratch 2D rigged-puppet animator — meshes, deformers, parameters,
       motions, physics. See *Puppet Tab — 2D Rigged Animation*.

The *Getting Started*, *Reference*, *Plugin System*, and *MCP Server* sections
that follow are cross-cutting — they apply across all four tabs.

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

Independent flag-based colour flags, stored separately from the 1 -- 5 star rating. Useful for
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
the left edge. The **List view** has dedicated **Label** and **Star Rating** columns that you can
sort by — click any cell in the star column to set the rating without leaving the list.

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
   * - White Balance — Temperature
     - Warm / cool shift (blue → yellow); useful for mixed-light or indoor shots
   * - White Balance — Tint
     - Magenta / green shift; corrects fluorescent casts
   * - Shadows
     - Lift or crush detail in dark tonal regions
   * - Midtones
     - Adjust the middle tonal range without affecting blacks and whites
   * - Highlights
     - Recover blown highlights or push bright areas further
   * - Vibrance
     - Saturation-aware boost — protects skin tones and already-saturated colours

These adjustments are **non-destructive**. Every slider writes into an edit recipe stored
per-image; press ``Reset`` at any time to restore the original, or ``Ctrl + Z`` to step
backwards through individual changes. Recipes survive restarts and can be exported / synced
via the XMP sidecar flow described in the Metadata section.

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

Paint Workspace (Paint Tab)
---------------------------

The third top-level tab — **Paint** — is a full-featured painting workspace
with multi-tab documents, vector and raster layers, manga tools, animation
frames, and PSD import/export. Switch to it from the tab bar or press ``E``
from Deep Zoom mode to send the current image straight into a new Paint tab.

UX-affordance highlights — the Paint workspace ships with a full-featured
brush-size cursor that scales with zoom, distinct cursor icons per tool,
a transparency-checker pattern under the canvas, drag-drop highlight
overlay, per-tab modified asterisk, undo / redo toast confirmations, an
autosave status segment in the status bar, and an autosave-recovery
prompt on launch that surfaces snapshots from a previous crashed session.

Power-user hotkeys: ``Tab`` toggles all docks for distraction-free
painting, ``Ctrl+Tab`` cycles tabs, ``,`` / ``.`` cycle brush kinds,
``0–9`` set brush opacity in 10 % steps, ``Alt+[`` / ``Alt+]`` step
the active layer, and right-clicking the canvas opens a quick
Undo / Redo / Select-All / Deselect / Fit / 100 % menu.

The colour dock now exposes a "transparent / no colour" slot (default
BG = transparent), and fill + magic-wand both respect alpha boundaries
so erased pixels stop bleeding into a re-paint.

::

   +------+----------------------+----------------+
   | Tool |                      | Color · Brush  |
   | Bar  |   Canvas (paint)     | Layer · Nav.   |
   |      |                      | Material · …   |
   +------+----------------------+----------------+

The right-side docks (Color, Brush, Layer, Navigator, Material library,
History, Swatch, Reference, Histogram, Animation) are tabbed into a single
column so the canvas keeps the full visible height. Drag any dock title to
re-arrange or float a panel, then save the result via
``Settings`` > ``Workspace Layouts…``.

Tool Palette (Left Strip)
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Tool
     - Shortcut
     - Purpose
   * - Brush
     - ``B``
     - Paint with the active brush kind
   * - Eraser
     - ``E``
     - Alpha-erase the active layer
   * - Fill (bucket)
     - ``G``
     - Flood-fill with tolerance / contiguous / sample-all-layers
   * - Eyedropper
     - ``I``
     - Pick foreground colour from canvas
   * - Move
     - ``V``
     - Translate the active layer or selection
   * - Rect / Lasso / Wand / Quick Select
     - ``M`` / ``L`` / ``W``
     - Selection tools with Replace / Add / Subtract / Intersect modes
   * - Text
     - ``T``
     - Inline text editor with font / size / bold / italic
   * - Gradient
     - ``U``
     - Linear / Radial / Angle / Diamond gradient fill
   * - Blur / Smudge
     - ``R``
     - Local pixel manipulation
   * - Dodge / Burn / Sponge
     -
     - Darkroom toning — locally lighten, darken, or saturate /
       desaturate, weighted by the brush and a tonal-range mask
   * - Pen (Bezier)
     - ``P``
     - Vector path with anchor / handle editing
   * - Clone Stamp
     - ``S``
     - Shift+click sets source, click stamps with feather
   * - Speech Bubble
     - ``Ctrl + B``
     - Comic / manga balloon with auto-tail
   * - Rectangle / Ellipse / Line / Polygon
     - ``Shift + R/E/I/P``
     - Vector shape primitives with stroke + fill
   * - Crop
     - ``C``
     - Interactive crop with aspect-ratio presets
   * - Transform
     - ``Ctrl + T``
     - Free / scale / rotate / skew transform handles
   * - Hand
     - ``H``
     - Pan the canvas with cursor drag
   * - Zoom
     - ``Z``
     - Click to zoom in, Alt-click to zoom out

Brushes
^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Brush
     - Effect
   * - Pen
     - Crisp anti-aliased line, the everyday brush
   * - Marker / Highlighter
     - Wide, semi-transparent strokes that build up
   * - Pencil
     - Thin slightly textured graphite line
   * - Spray
     - Scattered dots driven by density and flow
   * - Calligraphy
     - Width varies with stroke direction
   * - Watercolor
     - Wet-edge bleed and soft blending
   * - Charcoal / Crayon
     - Rough textured strokes with pressure tilt

Each brush exposes Size / Opacity / Hardness / Density / Blend-mode in the
**Brush dock** and the top **Options bar**. Use ``Settings`` >
``Pressure Curve…`` to remap tablet pressure to width or opacity, and
``Edit`` > ``Capture Brush Tip…`` to turn a marquee selection into a custom
brush tip.

Layers
^^^^^^

The **Layer dock** offers thumbnails, visibility toggles, inline rename,
drag-to-reorder, and the active-layer blend mode + opacity. The
``Layer`` menu adds:

- **New / Vector / Duplicate / Merge Down** (``Ctrl + Shift + N`` /
  ``Ctrl + Shift + V`` / ``Ctrl + J`` / ``Ctrl + E``)
- **Masks** — Add Mask / From Selection / Invert / Apply / Delete
  (``Ctrl + Shift + M`` adds; ``Ctrl + Alt + Shift + M`` adds from selection)
- **Clipping Mask** — clip the layer above to the current alpha
  (``Ctrl + Alt + G``)
- **Layer Effects** — Drop Shadow · Outer Glow · Stroke; clear effects
- **Reference Layer** — pin one layer as the eyedropper source
- **1-bit Layer** — toggle the active layer to a binary line-art layer
- **Divide Layer by Colour** — split a flat colour layer into one layer
  per colour for easy bucket re-fills
- **Gradient Map** — submenu of presets (sepia / sunset / cyanotype …)

Selections
^^^^^^^^^^

Use the rect / lasso / wand / quick-select tools, then the **Edit** menu's
**Stroke Selection…** to outline the marquee with the current brush.
``Q`` toggles **Quick Mask Mode** — paint with any brush to refine the
selection edge in red, then press ``Q`` again to convert it back to a
marquee.

Animation
^^^^^^^^^

The **Animation dock** turns the document into a frame strip:

- ``Add Frame`` snapshots the current layer state into a new keyframe.
- Click a frame thumbnail to jump to it.
- ``Onion Skin`` (View menu) overlays neighbouring frames at low alpha.
- Export the strip via **File > Export pages** (CBZ for comic readers,
  PDF for print) or **Animation Export** for MP4 / GIF.

Manga Menu
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Action
     - Description
   * - Panel Cutter
     - ``Ctrl + Shift + P`` — split the canvas into a grid of comic panels with configurable rows / columns / gutter / border / margin
   * - Toggle Tone Layer
     - Convert active layer to a screentone (halftone dot) layer
   * - Stamp Page Numbers
     - Add page numbers across multi-page documents
   * - Speedlines
     - Radial / Parallel / Burst speedline generators
   * - Action Flash
     - Manga-style explosion / impact burst overlay
   * - Speech Bubble tool
     - Drag a balloon, drop the tail toward the speaker

Filters
^^^^^^^

``Filter`` opens a live-preview dialog for each effect:

- **Levels** — black / gamma / white sliders, per-channel
- **Curves** — draggable points (RGB / R / G / B) with monotone cubic interpolation
- **Posterize** — quantise colour into N steps
- **Threshold** — convert to pure black / white at a cut-off
- **Auto Color Balance** — neutralise casts via grey-world / white-patch
- **Film Grain** — luminance noise with adjustable size and amount
- **Convert to Halftone** — newspaper-style dot screen

View Aids
^^^^^^^^^

- **Pixel Grid** (``Ctrl + Shift + '``) — overlay a one-pixel grid at high zoom
- **Snap to Pixel / Edges** — sub-pixel placement clamped to integer coordinates
- **Onion Skin** — animation neighbour overlay
- **Bleed Guides** — print bleed / safe-zone guides
- **Rotate Canvas** (``Ctrl + Shift + H``) — view rotation without rasterising

File I/O
^^^^^^^^

- **Open PSD…** (``Ctrl + O``) and **Save as PSD…** (``Ctrl + S``) — Photoshop layered round-trip with masks, blend modes, and layer effects
- **Export image…** — flatten and save as PNG / JPEG / WebP / BMP / TIFF
- **Export pages → CBZ** / **→ PDF** — multi-frame document export for comics
- **Import / Export brush presets**, **Import palette** — share resources between installs
- **Autosave snapshots** — periodic background snapshots with restore-latest from the File menu

Workspace Layouts
^^^^^^^^^^^^^^^^^

``Settings`` > ``Workspace Layouts…`` saves the dock arrangement, tool-options
state, and active panels under a name, then flips between them with one
click — for example a "Drawing" layout with the Brush + Color docks
prominent and a "Compositing" layout with the Layer + History docks expanded.

----

Puppet Workspace (Puppet Tab)
-----------------------------

The fourth top-level tab — **Puppet** — is a from-scratch 2D rigged-puppet
animation system. It does what Live2D do (mesh-deformation rigs,
parameters, motions, physics, expressions, pose groups, lip-sync, webcam
tracking) but with **no proprietary SDK**, **no `live2d-py`**, and a fully
open ``.puppet`` file format.

.. note::

   The full end-to-end tutorial — going from a fresh install to either
   a live OBS stream or a baked MP4 — lives at ``puppet_guide.md`` at
   the repo root (with ``puppet_guide.zh-TW.md`` and
   ``puppet_guide.zh-CN.md`` mirrors). This section is the reference;
   the guide is the walkthrough.

::

   +-----------+----------------------+----------------+
   |  Toolbar  |                      |  Parameters    |
   +-----------+   GL Canvas          |    dock        |
   |           |                      |                |
   +-----------+----------------------+                |
   |               Motions dock                        |
   +---------------------------------------------------+

End-to-end workflow
^^^^^^^^^^^^^^^^^^^

1. **Import a PNG** — toolbar ``Import PNG…`` runs
   ``puppet.auto_mesh.puppet_from_png``: alpha-bounded triangulated grid,
   one drawable, ready to render.
2. **Add a deformer** — ``Add Rotation Deformer`` (anchor + angle) or
   ``Add Warp Deformer`` (rows × cols Bezier lattice; vertices outside the
   bounds pass through unchanged).
3. **Add a parameter** — ``Add Parameter`` adds a slider to the right-hand
   **Parameters** dock with auto-named id (``Param1``, ``Param2``, …).
4. **Set keys** — drag the slider to one extreme, edit the deformer's form
   in code or via mesh edit, press **Set key**. Repeat at neutral and the
   opposite extreme. The runtime now lerps deformer fields between adjacent
   keys whenever the slider moves.
5. **Save** — ``Save As…`` writes the rig + textures + motions + expressions
   + physics into a single ``.puppet`` zip you can share or open later via
   ``Open Puppet…``.

Try a worked example
^^^^^^^^^^^^^^^^^^^^

The repository ships a fully-rigged demo at
``examples/puppet/march_7th.puppet`` — a 307-drawable Cubism Live2D
rig converted in-tree. Textures and per-parameter vertex morphs are
baked into the ``.puppet`` zip, so the demo opens on the default
``requirements.txt`` without redistributing the Cubism SDK.

The rig carries 203 Cubism-standard parameters (``ParamAngleX/Y/Z``,
``ParamEyeLOpen/ROpen``, ``ParamBreath``, ``ParamMouthOpenY``, …), so
every standard input driver (webcam, blink, lip-sync, cursor look-at)
drives it without per-rig configuration. Nine looping motions ship in
the bundle — author-converted Cubism idle loops plus reference
gesture loops in the ``Idle`` and ``TapHead`` groups.

Open the Puppet tab, click **Open Puppet…**, point at
``march_7th.puppet`` — the figure appears centred. Drag any parameter
slider to drive a joint, or click one of the motions in the Motions
dock — single-click binds the motion and starts playback immediately.

**Running the bundled example, step by step:**

1. Launch Imervue. From source: ``python -m Imervue``. From the
   packaged build: run the ``Imervue`` executable / app bundle. The
   ``examples/`` directory is bundled into both the wheel and the
   Nuitka EXE, so the rig is on disk wherever you installed.
2. Click the **Puppet** tab at the top of the window.
3. Toolbar → **File > Examples > March 7Th** (or the toolbar's
   **Examples ▾** dropdown). The 307-drawable rig loads centred and
   the parameter dock fills with the 203 Cubism-standard sliders.
4. In the bottom **Motions** dock, single-click any motion entry
   (``zhaiyan``, ``zhaoxiang``, ``idle_breath``, ``tap_head`` …).
   Playback starts immediately; click again to stop, or pick a
   different motion to cross-fade into it.
5. Toggle the live-input switches on the toolbar to drive the rig
   from your own inputs — **Drag-track head** for cursor look-at,
   **Auto-blink** for cyclic eye-close, **Auto idle** + **Idle
   motions** for breath + random Idle clips, **Mic lip-sync** for
   mouth-open from microphone RMS, **Webcam tracking** for full
   head + eyes + mouth from MediaPipe FaceLandmarker.
6. **Reset to rest** on the toolbar stops every motion, untoggles
   every live driver, clears expressions / pose overrides, and snaps
   every parameter back to its default — the canonical "start over"
   action.
7. To open a different rig later: **File > Open Puppet…** picks any
   ``.puppet`` zip from disk; **File > Examples ▾** stays bound to
   the bundled list.

``.puppet`` file format (v1)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A ``.puppet`` file is a zip archive:

::

   my_character.puppet
   ├── puppet.json              # required — manifest, drawables, deformers, parameters
   ├── textures/
   │   ├── face.png             # referenced by drawables[].texture
   │   └── body.png
   ├── motions/                 # optional
   │   ├── idle.json
   │   └── wave.json
   ├── expressions/             # optional
   │   └── smile.json
   └── physics.json             # optional

Top-level ``puppet.json`` example::

   {
     "version": 1,
     "size": [2048, 2048],
     "drawables": [ ... ],
     "deformers": [ ... ],
     "parameters": [ ... ],
     "motions": ["idle", "wave"],
     "expressions": ["smile"],
     "pose": {"groups": [ ... ]},
     "physics": "physics.json"
   }

The full schema (drawables, deformers, parameters, motions, expressions,
pose, physics) lives at ``Imervue/puppet/FORMAT.md`` in the repo. JSON +
PNG only — no proprietary binary, fully diffable through git.

Toolbar reference
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Purpose
   * - Open Puppet… / Examples ▾
     - Load a ``.puppet`` from disk, or pick one of the rigs
       bundled under ``examples/puppet/`` directly from the toolbar
   * - Import PNG… / Import PSD… / Import Cubism…
     - Auto-mesh a PNG, layer-split a PSD, or sample-and-reconstruct
       a Cubism rig. The Cubism picker accepts both ``.moc3`` and
       ``.model3.json``; with no rig open either path runs the full
       ``.moc3 → .puppet`` conversion (user-supplied Cubism Native
       SDK). Picking ``.model3.json`` while a rig is loaded merges
       its JSON-only metadata (motions / expressions / physics) onto
       the active document instead.
   * - Recent
     - Quickly reopen a recently-opened puppet
   * - Save As…
     - Write the current rig out as a ``.puppet`` zip
   * - Add Rotation Deformer / Add Warp Deformer / Add Parameter
     - Author the rig from the toolbar
   * - Drag-track head
     - Cursor offset → ``ParamAngleX`` / ``ParamAngleY`` +
       ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - Cosine close→open cycle on ``ParamEyeLOpen`` / ``ParamEyeROpen``
       every ~4.5 s (force-write path bypasses canvas no-change-skip
       so competing drivers can't stall the blink)
   * - Mic lip-sync
     - Microphone RMS → ``ParamMouthOpenY`` (requires ``sounddevice``)
   * - Webcam tracking
     - MediaPipe Tasks API FaceLandmarker → head yaw / pitch / roll +
       eye + mouth (requires ``opencv-python`` + ``mediapipe``;
       opens a live preview dialog with detected landmarks)
   * - Auto idle / Idle motions
     - Breath cycle + drift on standard params, plus optional random
       cycler through Idle-group motions
   * - Edit mesh
     - Click-and-drag canvas vertices to refine the mesh
   * - Record motion
     - Capture parameter changes into a new ``Motion`` and add it to the
       document — bake-from-take, no manual key authoring
   * - Capture frame… / Record… / Export all motions…
     - Save a single PNG, toggle a GIF / WebM / MP4 recording, or
       batch-render every motion in the rig to its own file (all via
       the same character-only off-screen render path used for streaming)
   * - Output > Virtual camera / NDI output
     - Live streaming surfaces — see *Live streaming to OBS* above
   * - Reset to rest
     - Snap-stop the motion player, untoggle every live driver,
       clear expressions / pose groups, restore parameter defaults
   * - Fit to Window
     - Re-centre + re-scale the puppet in the canvas

Recording your own motions
^^^^^^^^^^^^^^^^^^^^^^^^^^

To capture a custom take rather than authoring keyframes by hand:

1. Toggle **Record motion** in the toolbar — a name dialog appears.
2. While recording, drag sliders, enable **Webcam tracking**, let physics
   run, anything that writes parameter values.
3. Toggle **Record motion** off — the recorder bakes the captured 30 Hz
   stream into a ``Motion`` with one linear-segment track per parameter
   that actually moved (parameters that stayed flat are dropped). The
   new motion appears in the bottom **Motions** dock immediately, ready
   to play / loop / save.

Custom motions saved this way round-trip through the same JSON
``motions/<name>.json`` payload as authored ones.

Live streaming to OBS
^^^^^^^^^^^^^^^^^^^^^

Two output paths, both rendering the puppet alone (no checker
backdrop, no editor chrome) into an off-screen framebuffer before
handing it to the streaming surface. Output longest side caps at
1080 px so Cubism-native canvases (March 7th is 3503×7777) don't
get rejected by DirectShow virtual-camera drivers.

**A. Virtual Camera** — appears as a webcam in OBS's *Video Capture
Device* source list. ``pip install pyvirtualcam`` plus the
platform driver: OBS Studio 26+ ships the *OBS Virtual Camera*
driver on Windows / macOS (click *Start Virtual Camera* in OBS
once to register it); Linux uses ``v4l2loopback-dkms`` +
``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``.
Toolbar **Output > Virtual camera** opens the stream.

DirectShow / AVFoundation / v4l2loopback are RGB-only — no alpha
channel — so Imervue fills the area outside the character with
**magenta `#FF00FF`** as a chroma key. Remove it in OBS via the
Color Key filter:

1. Right-click the Video Capture Device source > **Filters**
2. **Effect Filters > + > Color Key**
3. Set **Key Color Type** = ``Custom Color``,
   **Custom Color** = HEX ``FF00FF``,
   **Similarity** = ``80–300``,
   **Smoothness** = ``30–50``

The filter sticks to the source so the chroma key automatically
re-applies whenever the virtual camera resumes.

**B. NDI output** — sub-50 ms LAN broadcast carrying RGBA, so
OBS / vMix composite directly over their own scenes with no
chroma-key pass. ``pip install ndi-python`` + the
`NDI Tools <https://ndi.video/tools/>`_ runtime + the
`obs-ndi <https://github.com/obs-ndi/obs-ndi/releases>`_ plugin.
Toolbar **Output > NDI output** broadcasts the source (default
name *Imervue Puppet*).

``ndi-python`` ships only a source distribution; pip builds it
from C++ at install time. Windows users need Visual Studio Build
Tools 2022 (with C++ workload), CMake on PATH, and the NDI SDK
from <https://ndi.video/for-developers/ndi-sdk/> installed at the
default location with ``NDI_SDK_DIR`` env var pointing at it.

See ``puppet_guide.md`` § 1.2 for the full step-by-step plus the
troubleshooting list (camera shows magenta, ndi-python cmake
failure, virtual camera stretch, etc.).

Optional dependencies
^^^^^^^^^^^^^^^^^^^^^

* ``sounddevice`` — microphone capture for lip-sync
* ``opencv-python`` + ``mediapipe`` — webcam face tracking
* ``imageio-ffmpeg`` — MP4 / WebM recording (already shipped for
  Slideshow Video)
* ``pyvirtualcam`` — virtual-camera output (see *Live streaming*)
* ``ndi-python`` — NDI output (see *Live streaming*)
* User-supplied Cubism Native SDK DLL — ``.moc3 → .puppet``
  conversion (Live2D's Free Material License forbids
  redistribution; users drop the SDK under ``<cwd>/sdk/`` or set
  ``CUBISM_CORE_DLL`` env var)

The plugin degrades gracefully when any of these are missing — the
matching toolbar toggle bounces back off and shows an "install
<package>" hint. ``File > Install dependencies…`` batch-installs
every Python optional package in one go.

----

Desktop Pet Workspace (Desktop Pet Tab)
---------------------------------------

Tab 5 — the **Desktop Pet** puts any ``.puppet`` character on
your desktop as a frameless, transparent overlay. The tab itself
is a control panel; the actual character is a separate top-level
window that shares the entire Puppet runtime (motions,
expressions, physics, idle drivers, mic / webcam input). The
pet can react to clicks, run timer-driven animations, follow
your cursor, hide while another app is fullscreen, and speak
custom lines you author in a JSON file.

This chapter is a complete reference for the tab. The
chapter is organised as:

#. **Quick start** — five-step path from "I just opened Imervue"
   to "there's a puppet on my desktop".
#. **Loading a rig** — file picker, bundled example, restoration
   across launches.
#. **The overlay window** — every window-level behaviour
   (drag-to-move, edge snap, click-through, anchor lock,
   always-on-bottom, hide-on-fullscreen, pause-when-hidden,
   opacity, size, multi-monitor restoration).
#. **Interaction model** — left-click hit areas, the full
   right-click context menu, system tray.
#. **Live drivers** — six opt-in input drivers and their
   optional dependencies.
#. **Pet script** — the JSON file that lets you replace the
   pet's voice with your own lines, schedule reminders, and
   bind per-hit-area / per-motion responses.
#. **Persistence** — what gets remembered between launches and
   the exact settings schema.
#. **Authoring a new pet** — pointer at the Puppet tab + the
   ``.puppet`` file format.
#. **Troubleshooting** — common surprises and what to do about
   them.

Quick start
^^^^^^^^^^^

1. Switch to the **Desktop Pet** tab.
2. Click **Load bundled March 7th** to use the included character,
   or **Open Puppet…** to pick your own ``.puppet`` file.
3. The overlay appears on your desktop and the **Show pet on
   desktop** checkbox is ticked automatically. (If you ever want
   to hide the pet without closing Imervue, untick the box or
   use the system tray icon.)
4. Drag the character to where you want it. Release near a screen
   edge to snap flush.
5. Pick the **Live drivers** you want — idle breathing, blink,
   cursor-following, mic lip-sync, webcam tracking — from either
   the workspace tab or the pet's right-click menu.

Everything you set survives the next launch, so step 5 is a
one-time decision per rig / persona.

Loading a rig
^^^^^^^^^^^^^

The tab exposes three load paths:

* **Open Puppet…** — pick any ``.puppet`` file from disk.
* **Load bundled March 7th** — opens the rig shipped under
  ``examples/puppet/march_7th.puppet``. The resolver searches
  ``examples_dir()`` first (frozen-safe for packaged Nuitka /
  pip-installed builds) and falls back to a repo-root-relative
  lookup so the button works from both run-modes.
* **Last rig** — the previously loaded rig auto-restores on
  Imervue startup from the ``last_rig_path`` settings field; the
  Desktop Pet tab re-instantiates the overlay invisibly so the
  pet is one click away from the same state you left it in.

A successful load auto-ticks **Show pet on desktop** so the pet
appears immediately. The failure path leaves the checkbox alone
and writes the error to the tab's status label.

The overlay window
^^^^^^^^^^^^^^^^^^

The character lives in a top-level window separate from the
Imervue main window. The window is frameless, has no taskbar
entry, and (by default) stays on top of every other window.

.. list-table:: Window behaviours
   :header-rows: 1
   :widths: 28 72

   * - Behaviour
     - Detail
   * - Frameless overlay
     - No window chrome, no minimise / close buttons, no taskbar
       entry. The character is the entire visible surface.
   * - Transparent background
     - Anything the character doesn't cover is fully transparent.
       The desktop / app behind the pet shows through pixel-
       perfectly.
   * - Drag-to-move
     - Left-press anywhere on the body, drag, release. The drag
       is recognised as a click only if the cursor moved less
       than six pixels — moving farther turns the gesture into a
       move and the click handler doesn't fire.
   * - Edge snap
     - Release near a screen edge (default: within 24 px) and
       the pet "clicks" flush against that edge. The threshold
       is configurable from 0 (off) to 200 (very sticky). Snap
       runs independently on each axis so dragging into a corner
       docks against both edges at once.
   * - Overshoot clamp
     - A drag that ends past a screen edge clamps back inside.
       You can't strand the pet off-screen where you couldn't
       grab it again.
   * - Click-through mode
     - When enabled, every mouse event passes through the pet to
       whatever's behind it. The character is still visible but
       it can't be dragged, right-clicked, or used to trigger
       motions. Turn it on when the pet is purely decorative.
   * - Lock position
     - Disables drag-to-move without affecting click-through.
       Useful when you've placed the pet exactly where you want
       it and don't want accidental drags to move it.
   * - Always on bottom
     - Flips the pet from always-on-top to always-on-bottom.
       The pet sits behind every other window as a desktop
       widget. Also unsets the focus-accept flag so clicking the
       pet doesn't raise it.
   * - Hide on fullscreen
     - A 1 Hz background poll watches the foreground window on
       the pet's monitor. When that window covers ≥ 99 % of the
       screen with a per-edge tolerance ≤ 4 px (catching both
       real fullscreen and borderless-windowed games), the pet
       auto-hides. When fullscreen ends, the pet reappears at
       its previous position. The detector uses the Win32
       ``GetWindowRect`` API on Windows; on macOS / Linux it
       no-ops gracefully (the pet stays visible).
   * - Pauses when hidden
     - The ~30 FPS paint tick and the 1 Hz script tick both
       stop on ``hideEvent`` so a hidden pet costs zero CPU.
       They restart on the next ``showEvent``.
   * - Size presets
     - Small (200 × 300), medium (320 × 480), large (480 × 720).
       The pet resizes around its current centre so a size
       change doesn't relocate it. Snap re-runs after resize.
   * - Opacity slider
     - 10 – 100 %. Acts at the window level (via
       ``setWindowOpacity``) so the entire pet fades, not just
       the texture. The minimum 10 % floor exists so you can
       always still see and grab the pet — fully invisible
       would let you lose it.
   * - Position memory
     - The post-snap ``(x, y)`` after every release is persisted.
       On the next launch the pet returns to that screen
       coordinate. If the saved position no longer falls inside
       any connected screen (you unplugged a monitor since last
       launch), the pet falls back to the bottom-right corner
       of the primary screen.

Interaction model
^^^^^^^^^^^^^^^^^

The pet responds to mouse input via three independent channels.

**Left-click on the body**

The click position is mapped back into puppet-canvas
coordinates (undoing the canvas pan / zoom) and run through the
existing ``hit_test`` pipeline. The result drives behaviour as
follows:

#. If a ``HitArea`` covers the clicked drawable AND that area
   has an attached motion, the motion plays.
#. Whether or not a motion played, the pet may pop a speech
   bubble — see the *Pet script* section for the line-pick
   priority.
#. If no hit area covers the click, the pet falls back to a
   greeting (from the script's ``greetings`` list or the
   built-in fallback).

A drag-to-move gesture suppresses the click handler, so moving
the pet doesn't trigger a motion / speech.

**Right-click anywhere on the body**

Opens a context menu with the following structure:

* **Hide pet** — top-level action that closes the overlay.
* **Live drivers** submenu — six checkable toggles (Auto idle,
  Idle motions, Auto-blink, Drag-track head, Mic lip-sync,
  Webcam tracking). Check-state mirrors the live driver state,
  so the menu shows what's currently running.
* **Play motion** submenu — populated from the active rig's
  ``document.motions`` list. Selecting an entry plays that
  motion (and may trigger the pet's voice if the script binds a
  line to it).
* **Apply expression** submenu — populated from the rig's
  ``document.expressions``. Selecting toggles the expression's
  parameter overlay.
* Five top-level checkable toggles: **Lock position**,
  **Click-through**, **Always on bottom**, **Hide on fullscreen**,
  **Speech bubble** — quick access to the same toggles in the
  workspace tab.
* **Size** submenu — Small / Medium / Large; current preset is
  checked.

The motion / expression submenus are disabled when no rig is
loaded.

**System tray icon**

A tray icon (instantiated only on platforms reporting tray
support) provides a fourth surface for the most common actions:

* Left-click toggles pet visibility.
* Right-click opens a menu with **Show pet** (checkable),
  **Click-through**, **Open puppet…**, **Hide pet**.
* The checkable Show / Click-through items mirror the
  workspace's check state via ``sync_visibility`` /
  ``sync_click_through``, so they stay in sync wherever the
  user toggles the corresponding switch.

Live drivers
^^^^^^^^^^^^

Each live driver is lazy-created on first enable, so a dormant
pet pays zero timer / thread cost for drivers you never turn
on. The state of each driver is persisted; toggling on, closing
Imervue, and re-launching reopens the pet with the same
drivers running.

.. list-table::
   :header-rows: 1
   :widths: 22 50 28

   * - Driver
     - What it does
     - Optional dependency
   * - **Auto idle**
     - Breath + subtle drift on standard parameters
       (``ParamBreath`` etc.) so the character looks alive when
       nothing else is animating.
     - none
   * - **Idle motions**
     - Randomly picks a motion from the rig's ``Idle`` group
       every few seconds and plays it. Stops if no motion is
       currently in flight.
     - none
   * - **Auto-blink**
     - Closes and reopens the eyes on a smooth cosine curve
       every ~4.5 s. The driver force-writes the parameter so
       other drivers that touch eye-open values don't suppress
       the blink.
     - none
   * - **Drag-track head**
     - The head + eyes turn toward the global cursor position
       even when the cursor is off the pet. Drives
       ``ParamAngleX`` / ``ParamAngleY`` / ``ParamEyeBallX`` /
       ``ParamEyeBallY``.
     - none
   * - **Mic lip-sync**
     - Microphone RMS amplitude drives ``ParamMouthOpenY``. The
       mouth opens proportional to your voice volume so the
       character looks like it's speaking when you are.
     - ``sounddevice``
   * - **Webcam tracking**
     - MediaPipe FaceLandmarker reads your webcam at ~30 FPS
       and drives the head pose + eye-open + mouth-open params.
       Opens a small live-preview window so you can verify the
       camera sees your face.
     - ``opencv-python`` + ``mediapipe``

The two optional-dep drivers degrade gracefully: if the
required package isn't installed, toggling the checkbox bounces
back off and the workspace's status label shows an "install
sounddevice" / "install opencv-python + mediapipe" hint.

Pet script — custom voice and scheduled events
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The pet's speech bubble draws from a JSON file you can author
and load from the **Pet script** group on the tab. The script
governs four things:

* **Greetings** — default click lines when nothing more
  specific matches.
* **Hit-area responses** — per-``HitArea.id`` line buckets.
* **Motion lines** — per-motion-name line buckets, fired when
  the pet starts that motion (either from a hit area or from
  the context menu).
* **Scheduled chimes** — timer-driven lines that fire every
  ``every_seconds`` of monotonic wall-clock time.

Schema (versioned — future fields are forward-compatible):

.. code-block:: json

   {
     "version": 1,
     "name": "March 7th — playful voice",
     "greetings": [
       "Hi!", "Hello hello!", "Need a break?"
     ],
     "hit_responses": {
       "HitAreaHead": ["Hey, my head!", "Stop poking!"],
       "HitAreaBody": ["Hehe~", "Pat pat?"]
     },
     "motion_lines": {
       "wave": ["Hi!", "Hello!"],
       "curtsy": ["Cheers!"]
     },
     "scheduled": [
       {"every_seconds": 1800, "messages": ["Stretch break!"]}
     ]
   }

Loading rules:

* Lists are sampled round-robin per bucket so the user doesn't
  see the same line twice in a row.
* Unknown top-level keys are ignored (forward-compat — a future
  v2 file still loads on a v1 runtime).
* Garbage list entries (wrong type, malformed scheduled entries,
  zero / negative ``every_seconds``) are skipped — one bad row
  doesn't fail the whole load. Only outright-unparseable JSON
  raises an error and surfaces the path in the status label.
* The hit-area / motion / greeting cascade is layered: a left-
  click consults ``hit_responses[area.id]`` first, then
  ``motion_lines[area.motion]``, then ``greetings``, then the
  built-in default greeting set as the floor.
* Time tracking uses ``time.monotonic`` so suspending the laptop
  or jumping the system clock can't binge-fire queued events.

**Reset to default** drops the user script and reverts to the
built-in greeting set; the persisted script path is cleared so
the next launch doesn't reload it.

A working sample lives at
``examples/desktop_pet/march_7th.petscript.json`` — six
greetings, two hit-area buckets (head / body), three motion
lines (wave / curtsy / cheer), and a 30-minute stretch
reminder.

Persistence
^^^^^^^^^^^

All Desktop Pet state round-trips through
``user_setting_dict["desktop_pet"]`` (a slot in the standard
Imervue user-settings file). Each field has a default + range
clamp on load so a corrupted settings file can't crash launch.

.. list-table:: Persisted fields
   :header-rows: 1
   :widths: 28 18 54

   * - Field
     - Default
     - Notes
   * - ``last_rig_path``
     - ``""``
     - Auto-restored on launch if the file still exists.
   * - ``script_path``
     - ``""``
     - Auto-restored on launch if the script still parses;
       an unreadable script reverts to defaults silently.
   * - ``position``
     - ``[-1, -1]``
     - Screen-coord ``(x, y)`` from the last drag release.
       ``-1, -1`` means "use bottom-right of primary screen".
       Multi-monitor unplug between sessions falls back the
       same way.
   * - ``size_preset``
     - ``"medium"``
     - One of ``small`` / ``medium`` / ``large``.
   * - ``opacity``
     - ``1.0``
     - Clamped to ``[0.1, 1.0]``. Out-of-range values reset
       to default.
   * - ``click_through``
     - ``false``
     -
   * - ``anchor_locked``
     - ``false``
     -
   * - ``always_on_bottom``
     - ``false``
     - Mutually exclusive with always-on-top.
   * - ``hide_on_fullscreen``
     - ``true``
     - Set ``false`` to keep the pet visible during fullscreen.
   * - ``snap_threshold``
     - ``24``
     - Clamped to ``[0, 200]`` px.
   * - ``drivers``
     - all ``false``
     - Sub-dict keyed by driver id (``auto_idle``,
       ``idle_motion``, ``auto_blink``, ``drag_track``,
       ``mic_lipsync``, ``webcam_tracking``). Unknown keys
       round-trip untouched for forward-compat.
   * - ``show_on_launch``
     - ``false``
     - Auto-show the overlay when Imervue starts.
   * - ``speech_enabled``
     - ``true``
     - When false the speech bubble never pops.

The settings dict's merge behaviour is one level deep: older
settings files missing newer keys still produce a complete
state dict on load (defaults fill the gaps); newer keys you've
saved survive a downgrade to an older runtime that doesn't
know about them.

Authoring a new pet
^^^^^^^^^^^^^^^^^^^

Any ``.puppet`` file works as a Desktop Pet character — the
Desktop Pet tab is purely a renderer + interaction shell; rig
authoring happens in the Puppet tab (see
*Puppet Workspace (Puppet Tab)*).

To create your own pet rig:

#. Switch to the Puppet tab and import an artwork via
   **File > Import PNG…** or **File > Import PSD…**, or pull in
   a Cubism model via **File > Import Cubism…**.
#. Author rotation / warp deformers, parameters, motions,
   expressions, and (optionally) hit areas tied to body parts
   so the Desktop Pet's left-click handler can fire motions.
#. Save the rig via **File > Save As…** to a ``.puppet`` zip.
#. Switch back to the Desktop Pet tab and load the new file
   via **Open Puppet…**.

If your rig defines ``HitArea`` entries, you can author per-
hit-area speech-bubble lines in a ``.petscript.json`` whose
``hit_responses`` keys match the area ids.

Troubleshooting
^^^^^^^^^^^^^^^

**The pet appears inside a grey rectangle instead of being
fully transparent.** The OS-level translucent-background
attribute requires an alpha-aware GL surface plus matching
attributes on the embedded GL widget. Make sure no third-party
window-management tool is overriding the
``WA_TranslucentBackground`` attribute on the overlay window
(some custom window managers on Linux do this). On Windows /
macOS this should "just work".

**"Load bundled March 7th" reports the file isn't found.** The
resolver consults ``examples_dir()`` first (the frozen-safe
location used by packaged builds) and falls back to a CWD-
relative path. If neither contains the rig, the status label
surfaces the expected path. Verify the ``examples/`` directory
shipped with your install — for source checkouts, launch
Imervue from the repository root.

**The pet doesn't speak when clicked.** Three checks:

#. Make sure the **Speech bubble on click** toggle is on (in the
   tab or the right-click menu).
#. If you loaded a custom script, verify the JSON parses — the
   tab's status label shows the load error.
#. If a hit-area click did nothing, the area probably has no
   matching motion AND the script has no ``hit_responses`` entry
   for that area id. Either bind a motion to the area in the
   Puppet tab or add the area id to the script's
   ``hit_responses``.

**The webcam tracking checkbox bounces back off.** Webcam
tracking needs ``opencv-python`` and ``mediapipe`` installed
in the same Python environment Imervue is running in. Install
with ``pip install opencv-python mediapipe``. After install,
toggling the checkbox should bring up a small preview window
showing the detected face landmarks.

**The pet doesn't auto-hide during fullscreen apps.** The
fullscreen detector polls the foreground window at 1 Hz. On
Windows it uses the ``GetWindowRect`` Win32 API; on macOS /
Linux it doesn't have a reliable cross-platform equivalent
and no-ops (the pet stays visible). For Windows: make sure
**Hide when other app is fullscreen** is checked, and verify
the fullscreen window actually covers ≥ 99 % of the same
monitor as the pet.

**The pet's position drifts off-screen between launches.** This
happens when the screen the pet was on is no longer connected
on the next launch (laptop dock, second monitor unplugged).
The pet auto-falls-back to the bottom-right corner of the
primary screen in this case — drag it to where you want and
the next save will overwrite the stale position.

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

Export Presets
^^^^^^^^^^^^^^

For the common delivery targets you don't want to retune every time, use
``File`` > ``Export with Preset``. One click applies the right resize, format,
and quality pipeline:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Preset
     - Pipeline
   * - **Web 1600**
     - Fit long edge to 1600 px, JPEG quality 85, sRGB; for blog / forum uploads where visual quality matters more than pixel count.
   * - **Print 300 dpi**
     - Full-resolution TIFF / high-quality JPEG with 300 dpi metadata, color-managed output for labs and print shops.
   * - **Instagram 1080**
     - Square (1080 × 1080) or portrait (1080 × 1350) crop with the original aspect ratio preserved inside, quality 90 JPEG.

Presets compose with the watermark overlay (below) — enable the watermark once and
every preset output carries it.

Watermark Overlay
^^^^^^^^^^^^^^^^^

``File`` > ``Watermark…`` opens a non-destructive overlay configurator. Settings
apply on export only — the original pixels on disk are never touched.

- **Mode**: text or image. Image watermarks support PNG with alpha.
- **Position**: 9-anchor grid (corners, edges, centre).
- **Opacity**: 0 – 100 %.
- **Scale**: percent of the exported long edge; the watermark rescales automatically
  as you resize for different presets.

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

The dialog has four tabs:

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
   * - **A | B Split**
     - Before / after split view with a draggable vertical divider. Drag the handle to sweep between the two
       images; ideal for showing develop-recipe adjustments or comparing exports. Requires exactly 2 selected.

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
you flip between saved layouts the same way other XMP-aware photo managers switches *Library* /
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
Everything below lives under ``Extra Tools`` unless noted. As of the latest
version, the menu is organised into eight function-grouped submenus —
``Batch``, ``Library & Metadata``, ``Views``, ``Workflow``, ``Export``,
``Develop (Non-Destructive)``, ``Retouch & Transform``, and ``Multi-Image`` —
so each path below is shown as ``Extra Tools`` > ``<submenu>`` > ``<tool>``.

Library Search
^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Library Search`` lets you add one or more **root folders**
to a global index that is crawled in a background thread. Once a root is
indexed you can query it by extension, min width/height, size range, or name
substring and drop the results into the viewer as a virtual album.

Smart Albums
^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Smart Albums`` persists filter rules (extensions, minimum
dimensions, colour labels, rating, favourites, cull state, hierarchical tags,
name substring) under a friendly name. Reapplying an album filters the active
folder by the saved rules.

Similar-Image Search
^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Find Similar Images`` runs a 64-bit DCT pHash on the
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

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` applies heuristic tags under
``auto/...`` (``photo`` / ``document`` / ``screenshot`` / ``landscape`` /
``portrait``). If ``onnxruntime`` and a CLIP model at
``models/clip_vit_b32.onnx`` are available, it also adds CLIP-based content
labels. Runs on a worker thread with a live progress bar.

Hierarchical Tags
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` manages tree-structured tags such as
``animal/cat/british``. Select a tag to see every image beneath that branch
(descendants included). Tag or untag the current selection with one click.
Hierarchical tags live in the library index and are complementary to the flat
tag system in the right-click menu.

Token Batch Rename
^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` opens a live-preview table where you
type a template like ``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` and see
exactly what every file will be renamed to. Conflicts are highlighted so
nothing is overwritten. Supported tokens: ``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``.

Metadata Export
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` writes a row per image in
the current view covering EXIF, dimensions, color label, rating, favourite,
hierarchical tags, cull state, and notes. Useful for feeding cull decisions
into a spreadsheet or external workflow.

XMP Sidecar (other XMP-aware photo managers Interop)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Imervue can read and write Adobe XMP sidecar files (``photo.jpg`` ↔
``photo.xmp``) so that ratings, titles, descriptions, keywords, and color
labels round-trip cleanly with other XMP-aware photo managers, other XMP-aware photo managers, Bridge, and other
XMP-aware tools.

- **Import XMP for current image** — pulls rating / title / keywords /
  color label from the sidecar into the internal database.
- **Export XMP for current image** — writes the current rating / title /
  keywords / color label into a sidecar next to the image.
- **Batch import / export** — applies the same operation to the active
  selection or the whole folder.

XML parsing uses ``defusedxml`` so malformed or malicious sidecars cannot
trigger XXE / billion-laughs attacks. If ``defusedxml`` is not installed
the XMP menu entries are hidden and no sidecars are written.

The **EXIF sidebar** also exposes a clickable **star-rating strip** — the
rating it sets is what XMP export will write.

Culling (Pick / Reject)
^^^^^^^^^^^^^^^^^^^^^^^

flag-based three-state cull flag. Press ``P`` to pick the current image
or every selected tile, ``Shift + X`` to reject, ``U`` to unflag. ``Filter`` >
``By Cull State`` shows only picks, rejects, or unflagged. ``Extra Tools`` >
``Culling`` applies the filter via a dialog and also exposes a **Delete all
rejects** button that permanently removes the flagged files from disk. The same
dialog's **Pick sharpest per similar group** button groups the folder's
near-duplicates by perceptual hash, scores each by sharpness, and marks the
sharpest frame of every group as a pick and the rest as rejects.

Staging Tray
^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Staging Tray`` is a cross-folder basket. Add any set of
tiles to the tray (the list survives restarts), then move or copy the entire
tray into a destination folder in one click. Useful for gathering picks from
many shoots before export.

Dual-Pane File Manager
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Dual-Pane File Manager`` opens a dual-pane
two-tree view. Choose a folder in each pane and move/copy the selection
between them without leaving Imervue.

Timeline View
^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Timeline View`` groups the current image set by day,
month, or year (date-grouped). Date is taken from EXIF
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

Advanced Develop & Compositing
------------------------------

Tone Curve
^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Tone Curve`` opens a draggable-points curve editor with
four channels (RGB, R, G, B). Left-click on empty canvas to add a point;
drag to move; right-click to delete. Points are interpolated with a
monotone cubic spline and stored on the image's recipe, so the curve applies
non-destructively at render time.

Apply .cube LUT
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Apply .cube LUT`` lets you pick any Adobe ``.cube`` file
(1D or 3D, up to 64³). The LUT is parsed with an ``lru_cache`` keyed by
path + mtime, evaluated with trilinear interpolation, and blended against
the original via an intensity slider. The LUT path and intensity live on
the recipe.

Virtual Copies
^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Virtual Copies`` gives each image named recipe
snapshots. Snap the current edit, continue experimenting, and swap back to
any earlier variant later. Variants sit alongside the master recipe in the
recipe store and survive resetting the master to identity.

HDR Merge
^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``HDR Merge`` combines two or more bracketed exposures
into a single image via OpenCV's Mertens exposure fusion. The optional
"Align exposures" checkbox runs ``cv2.AlignMTB`` first to compensate for
hand-held shake. Output is saved to a user-chosen file — it does not touch
any source image.

Panorama Stitch
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Panorama Stitch`` wraps OpenCV's high-level
``Stitcher`` API. Choose **Panorama** mode for landscapes / cityscapes or
**Scans** mode for flat documents and artwork. Black edges produced by the
warp can be auto-cropped.

Focus Stacking
^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Focus Stacking`` fuses multiple shots taken at
different focus distances. For each pixel the algorithm picks whichever
input frame has the highest local sharpness (Laplacian variance), then
smooths the selection mask with a gaussian blend to avoid seams. ECC
alignment is on by default for slight hand-held offsets.

Healing Brush
^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Healing Brush`` shows the current image at up to
720 px longest side. Left-click adds a circular spot; right-click on an
existing spot removes it; the radius slider sets new-spot size. On apply,
OpenCV inpainting (Telea for speed, Navier-Stokes for smoother blending)
fills each masked region from surrounding pixels and the result is saved
to a new file.

Lens Correction
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Lens Correction`` exposes four pure-numpy sliders:
radial distortion ``k1`` (barrel / pincushion), vignette lift, and
per-channel chromatic-aberration radial scale for red and blue. The
corrected image is saved as a new file — lens correction is not part of
the recipe because the output shape can change.

Map View
^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` plots every geotagged image in the current
library on an interactive Leaflet + OpenStreetMap map (requires
``PySide6.QtWebEngineWidgets``). Without WebEngine, the dialog falls back
to a plain list of ``(path, lat, lon)`` entries so the feature remains
usable on minimal installs.

Calendar View
^^^^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` shows a ``QCalendarWidget`` with days
highlighted when photos were taken that day (EXIF ``DateTimeOriginal`` →
``DateTimeDigitized`` → file mtime). Selecting a date lists its images;
double-click to open one in the main viewer.

Face Detection
^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` runs OpenCV's Haar frontal-face
cascade on the current image and draws each detection as a rectangle.
Double-click a row in the list to type a person name; on Save, the tags
are written into the recipe's ``extra['face_tags']`` blob. Detection is a
classical technique — accuracy is adequate for "show me the faces" but
not a replacement for modern CNN-based recognition.

Local Adjustment Masks
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Local Adjustment Masks`` layers brush, radial, or
linear gradient masks over the image. Each mask carries its own exposure,
brightness, contrast, saturation, temperature, tint deltas plus a feather
slider. Masks are saved on ``recipe.extra['masks']`` and applied
non-destructively at load time, so the underlying file is never touched.

Split Toning
^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Split Toning`` applies distinct hues to shadows and
highlights with per-region saturation and a balance pivot. Stored on
``recipe.extra['split_toning']`` and applied after the tone curve in the
develop pipeline.

Clone Stamp
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Clone Stamp`` copies a feathered source patch onto a
destination — the hard-edge complement to the healing brush. Shift+click
sets the source, a normal click stamps, right-click undoes. The result is
written to a new file so the original stays intact.

Crop / Straighten
^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Crop / Straighten`` combines a normalised (0..1)
crop rectangle with an arbitrary straighten angle. The output is
auto-cropped to the largest inner rectangle so rotated photos have no
black corners.

Auto-Straighten
^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Auto-Straighten`` detects the dominant horizon or
vertical lines via Hough line detection and proposes a rotation. One
click applies the straighten; you can tweak the angle first if the
auto-detection picks the wrong reference.

Noise Reduction / Sharpening
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Noise Reduction / Sharpening`` applies a bilateral
(edge-preserving) denoise followed by an unsharp-mask sharpen.
"Luminance only" keeps colour noise intact but flattens grain without
smearing chroma edges.

Sky / Background
^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Sky / Background`` replaces detected sky with a
gradient or removes the background to transparent / white. When
``rembg`` (U²-Net) is installed, the foreground mask comes from the
segmentation network; otherwise the heuristic HSV rule is used.

Soft Proof
^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Soft Proof`` loads an ICC profile, converts the
image through it and back, and highlights pixels that clipped during
the round-trip in magenta — a quick out-of-gamut check before printing.

Tonal & Creative Effects
^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` gathers a set of one-shot,
apply-and-save effects, each a thin slider dialog over a pure-NumPy transform
(the same logic is also exposed as an MCP tool):

- **Graduated Density** — a linear neutral-density gradient defined by angle,
  hardness and offset, optionally tinted; darkens a sky or foreground without a
  manual mask.
- **Tone Equalizer** — independent exposure per luminance zone (one slider each
  for blacks → whites) over a smoothed mask, so the adjustment follows the
  scene's tones.
- **Detail Equalizer** — a gain slider per frequency band (fine texture →
  coarse contrast), the multi-scale alternative to a single clarity slider.
- **Filmic Tone Map** — a Reinhard or Hable highlight rolloff with pivoted
  contrast and a saturation restore, for high-contrast single exposures.
- **Velvia** — a luminance-weighted saturation boost that intensifies muted
  colours while sparing already-saturated ones and the shadows.
- **Film Negative** — invert a scanned colour negative, dividing out the
  auto-estimated orange film base, with an output-gamma slider.
- **Defringe** — desaturate purple/green chromatic-aberration fringes along
  high-contrast edges, leaving flat colour untouched.
- **Emboss** — a directional-light relief from the luminance height field
  (azimuth / elevation / depth + a greyscale toggle).
- **Polar Coordinates** — wrap the frame into a disc or unroll it (the
  tiny-planet / polar-inversion look).
- **Kaleidoscope** — mirror one angular wedge into ``n``-fold symmetry.
- **Frosted Glass** — a deterministic, seed-reproducible local pixel scatter.

GPS Geotag
^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` reads any existing EXIF GPS tags and
lets you edit or set new decimal-degree coordinates. Requires ``piexif``
to be installed; writes to JPEG in place.

Print Layout
^^^^^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` composes multiple images onto a
multi-page PDF with configurable page size, orientation, grid, margins,
gutter, and crop marks. Requires ``reportlab``.

----

Command-Line Usage
------------------

::

   imervue                        # Launch normally
   imervue /path/to/image         # Open a specific image
   imervue /path/to/folder        # Open a specific folder
   imervue --debug                # Enable debug mode
   imervue --software_opengl      # Use software rendering (when GPU is unsupported)

----

MCP Server
----------

Imervue ships a built-in `Model Context Protocol <https://modelcontextprotocol.io>`_
server that lets AI assistants (Claude Code, Claude Desktop, Cursor,
Cline, …) call into the project's pure-logic helpers without a
running GUI. Start it with::

   python -m Imervue.mcp_server

The server is Qt-free and only loads what each tool needs at call
time.

Available Tools
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Tool
     - Purpose
   * - ``list_images``
     - List image files in a folder (path, size, mtime). Pass
       ``recursive=true`` to walk subfolders.
   * - ``read_image_metadata``
     - Dimensions, format, EXIF tags and XMP sidecar fields for one
       image. Missing data is reported as the appropriate empty value
       rather than raising.
   * - ``read_xmp_tags``
     - Fast path that only reads the XMP sidecar — rating, color
       label, keywords, title, description.
   * - ``convert_format``
     - Convert one image to another format. Destination format is
       inferred from the destination suffix (``png`` / ``jpg`` /
       ``jpeg`` / ``webp`` / ``tiff`` / ``bmp``). Optional
       ``quality`` (1–100) applies to JPEG/WebP.
   * - ``puppet_from_png``
     - Build a ``.puppet`` rig from a PNG using the puppet plugin's
       auto-mesh. Seeds the Cubism-standard parameter catalogue so
       the rig is immediately drivable.
   * - ``puppet_inspect``
     - Open a ``.puppet`` archive and return a structured inventory:
       drawables, deformers, parameters, motions, expressions, hit
       areas, parts, parameter blends and physics rigs.
   * - ``image_statistics`` / ``quality_metrics`` / ``read_histogram``
     - Per-channel mean/min/max/std/median, no-reference quality
       metrics (colourfulness, entropy, contrast, edge density, noise),
       and the 256-bin histogram with over/under clipping fractions.
   * - ``sharpness_score`` / ``ocr_text`` / ``image_thumbnail``
     - Laplacian-variance blur score, Tesseract OCR text (graceful when
       absent), and a bounded base64 PNG preview.
   * - ``find_similar``
     - Group near-duplicate images by perceptual hash (Hamming
       threshold). Reports per-file progress when a progress token is
       supplied.
   * - ``apply_watermark`` / ``apply_frame``
     - Burn in a text watermark, or wrap the image in a matte /
       Polaroid frame with an optional caption.
   * - ``build_collage``
     - Composite several images into a grid montage (configurable
       columns, cell size, gap, margin, background). Reports progress.
   * - ``crop_image`` / ``resize_image`` / ``rotate_image``
     - Pixel-box crop, aspect-preserving resize, and lossless 90/180/270
       rotation or horizontal/vertical flip.
   * - ``collection_stats``
     - Summarise a folder's ratings, favourites, colour labels and cull
       states (counts, 0–5 star distribution and average).
   * - ``reverse_geocode`` / ``extract_video_frame``
     - Resolve GPS coordinates to the nearest city offline, and decode
       one frame of a video to a still image.
   * - ``extract_gps`` / ``dominant_colors``
     - Read EXIF GPS latitude/longitude (chains into ``reverse_geocode``);
       extract a median-cut colour palette (rgb / hex / pixel share).
   * - ``error_level_analysis``
     - JPEG-recompression Error-Level-Analysis tamper map as a PNG data
       URI (edited regions light up against the background).
   * - ``search_images``
     - Filter a folder with the smart-album query DSL (extension / name /
       size / dimensions / aspect / EXIF camera / lens / place).
   * - ``solarize_image`` / ``glow_image``
     - Apply a solarize tone reversal or a diffuse-glow / Orton bloom and
       save the result.
   * - ``velvia_image`` / ``emboss_image`` / ``defringe_image``
     - Velvia luminance-weighted saturation boost, directional-light emboss
       relief, and purple/green edge-fringe desaturation.
   * - ``film_negative_image`` / ``graduated_density_image``
     - Invert a scanned colour negative (auto film base), and apply a linear
       graduated neutral-density gradient.
   * - ``filmic_tonemap_image`` / ``tone_equalizer_image`` / ``detail_equalizer_image``
     - Filmic Reinhard/Hable highlight rolloff, per-luminance-zone exposure,
       and per-frequency-band contrast.
   * - ``colormap_image`` / ``false_color_image``
     - Recolour luminance through a viridis/magma/jet perceptual map, or map
       it to a false-colour exposure scale.
   * - ``dither_image`` / ``split_toning_image`` / ``pixel_sort_image``
     - Ordered (Bayer) dither to a few tones per channel, shadow/highlight
       split-toning, and brightness-band pixel sorting.
   * - ``polar_image`` / ``kaleidoscope_image``
     - Warp between rectangular and polar coordinates (tiny-planet), or mirror
       the frame into a number of kaleidoscope wedges.
   * - ``frosted_glass_image`` / ``clahe_image`` / ``local_contrast_image``
     - Random-neighbour frosted-glass scatter, contrast-limited adaptive
       histogram equalization, and midtone clarity + fine-detail texture.
   * - ``posterize_image`` / ``gradient_map_image``
     - Quantize each channel to a few flat bands, or remap luminance through a
       black-to-white gradient blended by intensity.
   * - ``film_grain_image`` / ``dehaze_image`` / ``distort_image``
     - Tunable Gaussian film grain, dark-channel-prior dehaze, and swirl /
       pinch / ripple geometric distortion.
   * - ``levels_image`` / ``curve_image``
     - Black/white-point and gamma levels, and a master tone-curve preset
       (S-curve, lift shadows, compress highlights).
   * - ``auto_color_balance_image`` / ``channel_mixer_image``
     - Automatic white balance (gray-world, white-patch, percentile-stretch,
       retinex) and a 3x3 channel mixer with mono conversion.
   * - ``lens_correction_image``
     - Correct barrel/pincushion distortion (k1), lift or deepen the corner
       vignette, and cancel red/blue chromatic aberration.

Every tool advertises a JSON ``outputSchema`` and read-only /
destructive ``annotations``, and returns its result as
``structuredContent`` alongside the text envelope (per MCP 2025-11-25),
so clients consume typed payloads without re-parsing. Long-running
tools stream ``notifications/progress`` when the caller passes a
progress token.

Prompts
^^^^^^^

The server exposes four prompts via ``prompts/list`` / ``prompts/get``:
``caption_image``, ``suggest_edits``, ``analyze_composition`` (a
saliency-driven composition critique) and ``flag_issues`` (a sharpness
+ quality + clipping triage). Prompt arguments are completable through
``completion/complete``.

Claude Code (Project-Level)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The repository ships a project-level ``.mcp.json`` at the repo root:

.. code-block:: json

   {
     "mcpServers": {
       "imervue": {
         "type": "stdio",
         "command": "python",
         "args": ["-m", "Imervue.mcp_server"]
       }
     }
   }

Opening any subdirectory of the repo in Claude Code auto-discovers
this server. Claude Code prompts before enabling project servers the
first time — accept the prompt to use it.

Claude Desktop
^^^^^^^^^^^^^^

Add the same entry to your Claude Desktop config:

* macOS: ``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows: ``%APPDATA%\Claude\claude_desktop_config.json``

Use an absolute working directory or activate a virtualenv in which
Imervue is installed; the ``python`` invocation must resolve to an
interpreter that can ``import Imervue``.

Protocol Surface
^^^^^^^^^^^^^^^^

The server implements the stdio JSON-RPC 2.0 transport of MCP
version ``2025-03-26``:

* ``initialize`` — handshake; advertises ``capabilities.tools``.
* ``tools/list`` — enumerate the registered tools with their
  JSON-Schema input definitions.
* ``tools/call`` — invoke a tool with ``{"name", "arguments"}``;
  results come back inside the ``content`` array.
* ``notifications/*`` — silently accepted (no response).

The implementation lives in ``Imervue/mcp_server/``:

* ``server.py`` — protocol loop + tool registry.
* ``tools.py`` — handler functions and the default tool definitions.
* ``__main__.py`` — ``python -m Imervue.mcp_server`` entry point.

Custom tools can be registered by constructing :class:`MCPServer`
manually, calling :meth:`MCPServer.register`, and feeding messages
through :meth:`MCPServer.handle_message` (or driving the stdio loop
with the built-in :func:`run` helper).
