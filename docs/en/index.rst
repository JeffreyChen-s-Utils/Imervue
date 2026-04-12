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
   * - Select multiple images
     - Left-click and drag to draw a selection rectangle
   * - Pan with keyboard
     - Arrow keys; hold ``Shift`` for fine movement

Deep Zoom Mode
^^^^^^^^^^^^^^

Click a thumbnail to enter Deep Zoom mode for high-quality single-image viewing.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Method
   * - Zoom in/out
     - Mouse wheel
   * - Pan
     - Hold middle mouse button
   * - Previous image
     - ``Left Arrow``
   * - Next image
     - ``Right Arrow``
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
   * - Filter by tag
     - ``Filter`` > ``By Tag``
   * - Filter by album
     - ``Filter`` > ``By Album``

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
   * - Clear filters
     - ``Filter`` > ``Clear Filter``

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

A side-by-side window opens so you can compare composition and colour differences.

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

Results update in real time. Double-click a result to jump straight to that image.

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
   * - Mouse wheel
     - Zoom in / out
   * - Middle-click drag
     - Pan
   * - ``F``
     - Fullscreen
   * - ``Esc``
     - Return to thumbnails / exit fullscreen
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
   * - ``B``
     - Toggle bookmark
   * - ``T``
     - Tags & Albums manager

Tools
^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Action
   * - ``Ctrl + F`` / ``/``
     - Search images
   * - ``Ctrl + C``
     - Copy image to clipboard
   * - ``Ctrl + V``
     - Paste from clipboard
   * - ``H``
     - RGB histogram
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

Command-Line Usage
------------------

::

   imervue                        # Launch normally
   imervue /path/to/image         # Open a specific image
   imervue /path/to/folder        # Open a specific folder
   imervue --debug                # Enable debug mode
   imervue --software_opengl      # Use software rendering (when GPU is unsupported)
