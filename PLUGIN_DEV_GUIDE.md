# Imervue Plugin Development Guide

## Overview

Imervue supports a plugin system that allows developers to extend the application with custom functionality. Plugins can add menu items, respond to image events, handle keyboard shortcuts, and more.

## Quick Start

1. Create a folder inside the `plugins/` directory (next to the `Imervue/` package):

```
plugins/
    my_plugin/
        __init__.py
        my_plugin.py
```

2. Define your plugin class in `my_plugin.py`:

```python
from Imervue.plugin.plugin_base import ImervuePlugin


class MyPlugin(ImervuePlugin):
    plugin_name = "My Plugin"
    plugin_version = "1.0.0"
    plugin_description = "A short description of what this plugin does."
    plugin_author = "Your Name"

    def on_plugin_loaded(self):
        print(f"{self.plugin_name} loaded!")
```

3. Register it in `__init__.py`:

```python
from my_plugin.my_plugin import MyPlugin

plugin_class = MyPlugin
```

4. Restart Imervue — your plugin will be automatically discovered and loaded.

## Plugin Structure

### Required Class Attributes

| Attribute            | Type  | Description                        |
|----------------------|-------|------------------------------------|
| `plugin_name`        | `str` | Display name shown in the UI       |
| `plugin_version`     | `str` | Version string (e.g. `"1.0.0"`)   |
| `plugin_description` | `str` | Short description of the plugin    |
| `plugin_author`      | `str` | Author name or contact             |

### Built-in Properties

Every plugin instance automatically has:

- `self.main_window` — The `ImervueMainWindow` instance (access menus, file tree, labels, etc.)
- `self.viewer` — The `GPUImageView` instance (access images, zoom state, tile grid, etc.)

## Available Hooks

### Lifecycle Hooks

#### `on_plugin_loaded()`

Called once after the plugin is instantiated and registered. Use for initialization.

```python
def on_plugin_loaded(self):
    self.my_data = {}
    print("Plugin ready!")
```

#### `on_plugin_unloaded()`

Called when the plugin is being unloaded (usually at app shutdown). Clean up resources here.

```python
def on_plugin_unloaded(self):
    self.my_data.clear()
```

### Menu Hooks

#### `on_build_menu_bar(menu_bar: QMenuBar)`

Called after the default menu bar is built. Add your own menus here.

```python
from PySide6.QtWidgets import QMessageBox

def on_build_menu_bar(self, menu_bar):
    my_menu = menu_bar.addMenu("My Plugin")
    action = my_menu.addAction("Say Hello")
    action.triggered.connect(
        lambda: QMessageBox.information(self.main_window, "Hello", "Hello from my plugin!")
    )
```

#### `on_build_context_menu(menu: QMenu, viewer: GPUImageView)`

Called when the right-click context menu is being built. Add items conditionally based on viewer state.

```python
def on_build_context_menu(self, menu, viewer):
    if viewer.deep_zoom:
        action = menu.addAction("My Deep Zoom Action")
        action.triggered.connect(self.do_something)
    elif viewer.tile_grid_mode:
        action = menu.addAction("My Tile Grid Action")
        action.triggered.connect(self.do_something_else)
```

### Image Hooks

#### `on_image_loaded(image_path: str, viewer: GPUImageView)`

Called after a single image is loaded in deep zoom mode.

```python
def on_image_loaded(self, image_path, viewer):
    print(f"Viewing: {image_path}")
```

#### `on_folder_opened(folder_path: str, image_paths: list[str], viewer: GPUImageView)`

Called after a folder is opened and images are listed in tile grid mode.

```python
def on_folder_opened(self, folder_path, image_paths, viewer):
    print(f"Opened folder with {len(image_paths)} images")
```

#### `on_image_switched(image_path: str, viewer: GPUImageView)`

Called when the user navigates to the next/previous image.

```python
def on_image_switched(self, image_path, viewer):
    print(f"Switched to: {image_path}")
```

#### `on_image_deleted(deleted_paths: list[str], viewer: GPUImageView)`

Called after image(s) are soft-deleted (added to the undo stack).

```python
def on_image_deleted(self, deleted_paths, viewer):
    print(f"Deleted {len(deleted_paths)} image(s)")
```

### Input Hooks

#### `on_key_press(key: int, modifiers: int, viewer: GPUImageView) -> bool`

Called when a key is pressed in the viewer. Return `True` to consume the event and prevent default handling. Return `False` to let the default handler run.

```python
from PySide6.QtCore import Qt

def on_key_press(self, key, modifiers, viewer):
    if key == Qt.Key.Key_F2:
        self.my_custom_action()
        return True  # Event consumed
    return False  # Let default handling continue
```

> **Important:** Be careful about consuming common keys. Only return `True` for keys your plugin specifically handles.

### Application Hooks

#### `on_app_closing(main_window: ImervueMainWindow)`

Called when the application is about to close. Use for final cleanup or saving state.

```python
def on_app_closing(self, main_window):
    self.save_plugin_state()
```

## Accessing Application State

### Viewer State

```python
# Current mode
viewer.tile_grid_mode   # True if in thumbnail grid view
viewer.deep_zoom        # DeepZoomImage object if in deep zoom mode (None otherwise)

# Images
viewer.model.images     # List of all image paths
viewer.current_index    # Index of current image in deep zoom mode

# Selection (tile grid mode)
viewer.tile_selection_mode  # True if selection mode is active
viewer.selected_tiles       # Set of selected image paths

# Zoom (deep zoom mode)
viewer.zoom             # Current zoom level
viewer.dz_offset_x      # Pan offset X
viewer.dz_offset_y      # Pan offset Y
```

### Main Window

```python
self.main_window.menuBar()       # Access the menu bar
self.main_window.filename_label  # The filename display label
self.main_window.tree            # The file system tree view
self.main_window.model           # The QFileSystemModel
```

## Plugin Discovery

The plugin manager scans the `plugins/` directory at startup. It supports two formats:

### Package Plugin (recommended)

```
plugins/
    my_plugin/
        __init__.py      # Must define: plugin_class = MyPlugin
        my_plugin.py     # Contains the plugin class
        helpers.py       # Optional additional modules
```

### Single-File Plugin

```
plugins/
    simple_plugin.py     # Contains a class that extends ImervuePlugin
```

For single-file plugins, the manager will automatically find your `ImervuePlugin` subclass. For package plugins, you should explicitly set `plugin_class` in `__init__.py`.

## Internationalization (i18n)

Plugins can provide multi-language support in two ways:

### 1. Adding translations for your plugin's UI strings

Override `get_translations()` to provide localized strings for your plugin. These strings are merged into the global language dictionaries, so you can use `language_wrapper.language_word_dict.get("your_key")` in your plugin just like built-in code does.

```python
from Imervue.multi_language.language_wrapper import language_wrapper

class MyPlugin(ImervuePlugin):
    plugin_name = "My Plugin"
    plugin_version = "1.0.0"
    plugin_description = "Example plugin with i18n"
    plugin_author = "Your Name"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "my_plugin_action": "Do Something",
                "my_plugin_greeting": "Hello from My Plugin!",
            },
            "Chinese": {
                "my_plugin_action": "执行操作",
                "my_plugin_greeting": "来自我的插件的问候！",
            },
            "Traditional_Chinese": {
                "my_plugin_action": "執行操作",
                "my_plugin_greeting": "來自我的插件的問候！",
            },
            "Japanese": {
                "my_plugin_action": "何かを実行",
                "my_plugin_greeting": "プラグインからこんにちは！",
            },
            "Korean": {
                "my_plugin_action": "작업 실행",
                "my_plugin_greeting": "플러그인에서 인사드립니다!",
            },
        }

    def on_build_menu_bar(self, menu_bar):
        lang = language_wrapper.language_word_dict
        my_menu = menu_bar.addMenu(lang.get("my_plugin_action", "Do Something"))
        action = my_menu.addAction(lang.get("my_plugin_greeting", "Hello!"))
```

Built-in language codes: `"English"`, `"Traditional_Chinese"`, `"Chinese"`, `"Korean"`, `"Japanese"`.

> **Note:** Plugin translations cannot overwrite existing built-in keys. Only new keys are added.

### 2. Creating a language plugin (adding an entirely new language)

You can create a plugin that registers a new language for the entire application. Use `language_wrapper.register_language()` in `on_plugin_loaded()`:

```python
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.multi_language.language_wrapper import language_wrapper


class SpanishLanguagePlugin(ImervuePlugin):
    plugin_name = "Spanish Language"
    plugin_version = "1.0.0"
    plugin_description = "Adds Spanish language support to Imervue"
    plugin_author = "Your Name"

    def on_plugin_loaded(self):
        language_wrapper.register_language(
            language_code="Spanish",
            display_name="Español",
            word_dict={
                "main_window_current_filename_format": "Nombre de archivo actual: {name}",
                "main_window_open_image": "Abrir archivo",
                "main_window_current_filename": "Nombre de archivo actual:",
                "main_window_current_file": "Archivo",
                "main_window_open_folder": "Abrir carpeta",
                "main_window_exit": "Salir",
                # ... all keys from english_word_dict should be translated
                "menu_bar_language": "Idioma",
                "language_menu_bar_please_restart_messagebox": "Por favor reinicie",
                # ... etc.
            }
        )
```

The new language will automatically appear in the **Language** menu (below a separator). When the user selects it and restarts, the application will use the plugin-provided translations.

> **Tip:** Copy all keys from `Imervue/multi_language/english.py` as a starting template for your language plugin. Any missing keys will fall back to `None` via `dict.get()`, so make sure to translate all keys for a complete experience.

## Error Handling

All plugin hooks are wrapped in try/except by the plugin manager. If your plugin raises an exception, it will be logged but won't crash the application. Check the console for error messages prefixed with your plugin name.

## Tips

- Check the `plugins/example_plugin/` for a complete working example.
- Use `print()` for debugging — output appears in the console.
- Avoid blocking the main thread in hooks. For heavy work, use `QThreadPool` or `QRunnable`.
- Store plugin state in your plugin instance (`self.my_data = ...`). For persistent state across sessions, save to a JSON file in your plugin directory.
- Don't modify internal Imervue data structures directly unless you know what you're doing. Use the provided hooks and the public API.
