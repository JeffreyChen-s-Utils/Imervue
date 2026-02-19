# Imervue

### Image + Immerse + View

Imervue is a GPU-accelerated image viewer built with PySide6.  
It focuses on performance, smooth navigation, and efficient handling of large image collections.

The application supports both folder-based browsing and single image viewing, with optimized thumbnail loading and deep zoom rendering.

---

## Features

- GPU-accelerated rendering
- Deep zoom image viewing
- Tile-based thumbnail grid
- Asynchronous image loading (multi-threaded)
- Thumbnail cache system
- Preloading of adjacent images
- Recent folders and recent images menu
- Automatic restore of last opened folder on startup
- Multi-language support
- Undoable delete system
- Adjustable thumbnail size

---

## Browsing Modes

### Grid Mode

When opening a folder, images are displayed in a virtualized tile grid:

- Only visible thumbnails are loaded
- Scroll and zoom supported
- Efficient memory usage
- Dynamic thumbnail size

### Single Image Mode

When opening a single image:

- Deep zoom rendering
- Smooth pan and zoom
- Centered on load
- Supports switching between images in the same folder

---

### Recent System

Imervue keeps track of:

- Recent Folders
- Recent Images

The recent list:

- Removes duplicates automatically
- Validates file existence
- Can be cleared manually
- Uses system icons for better integration

---

### Startup Behavior

On launch, Imervue:

- Restores the last opened folder
- Automatically loads the image grid
- Preserves user settings

---

