# Imervue Plugin Development Guide

## Overview

Imervue supports a plugin system that allows developers to extend the application with custom functionality. Plugins can add menu items and top-level tabs, respond to image events, handle keyboard shortcuts, add languages, and more.

Working examples are the plugins published in the distribution repository [Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins), for instance `plugins/png_to_icon/` for a small plugin and `languages/spanish_translation/` for a language plugin. **Plugins → Download Plugins** installs them.

## Quick Start

1. Create a folder inside the `plugins/` directory. In a source checkout that is the directory next to the `Imervue/` package; in a packaged build it is the `plugins/` directory next to the executable (**Plugins → Open Plugin Folder** opens it):

```
plugins/
    my_plugin/
        __init__.py
        my_plugin.py
```

2. Define your plugin class in `my_plugin.py`:

```python
import logging

from Imervue.plugin.plugin_base import ImervuePlugin

logger = logging.getLogger("Imervue.plugin.my_plugin")


class MyPlugin(ImervuePlugin):
    plugin_name = "My Plugin"
    plugin_version = "1.0.0"
    plugin_description = "A short description of what this plugin does."
    plugin_author = "Your Name"

    def on_plugin_loaded(self):
        logger.info("%s loaded", self.plugin_name)
```

3. Register it in `__init__.py`:

```python
from my_plugin.my_plugin import MyPlugin

plugin_class = MyPlugin
```

4. Restart Imervue (or use **Plugins → Reload Plugins**). Your plugin is discovered and loaded automatically.

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

- `self.main_window`: the `ImervueMainWindow` instance (menus, file tree, labels, etc.)
- `self.viewer`: the `GPUImageView` instance (images, zoom state, tile grid, etc.)

## Available Hooks

### Lifecycle Hooks

#### `on_plugin_loaded()`

Called once after the plugin is instantiated and registered. Use for initialization.

```python
def on_plugin_loaded(self):
    self.my_data = {}
    logger.info("Plugin ready")
```

#### `on_plugin_unloaded()`

Called when the plugin is being unloaded (usually at app shutdown). Clean up resources here.

```python
def on_plugin_unloaded(self):
    self.my_data.clear()
```

### Menu Hooks

#### `on_build_menu_bar(plugin_menu: QMenu)`

Called once after the shared **Plugins** menu is built. Despite the hook's name, the argument is that `QMenu`, not the `QMenuBar`: add a submenu or actions to it rather than a new top-level menu.

```python
from PySide6.QtWidgets import QMessageBox

def on_build_menu_bar(self, plugin_menu):
    my_menu = plugin_menu.addMenu("My Plugin")
    action = my_menu.addAction("Say Hello")
    action.triggered.connect(
        lambda: QMessageBox.information(self.main_window, "Hello", "Hello from my plugin!")
    )
```

To put an entry into one of the **Extra Tools** submenus instead, look the submenu up by its object name, `extra_tools.<key>`, and fall back to the Plugins menu so the entry still appears on an Imervue version that predates the names. The keys are `batch_submenu`, `library_submenu`, `views_submenu`, `workflow_submenu`, `export_submenu`, `develop_submenu`, `retouch_submenu` and `multi_image_submenu`. Match by object name, never by the visible title: titles are translated.

```python
from PySide6.QtWidgets import QMenu

def on_build_menu_bar(self, plugin_menu):
    target = self.main_window.findChild(QMenu, "extra_tools.retouch_submenu")
    entry = (target if target is not None else plugin_menu).addAction("My Filter")
    entry.triggered.connect(self.open_dialog)
```

Qt keeps only a weak reference to a bound-method slot. That is fine for hooks, because the plugin manager holds every plugin instance, but a helper object created inside a hook must be stored on `self` or its slots silently stop firing.

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

### Tab Hooks

#### `on_build_main_tabs(tabs: QTabWidget)`

Called once after the five built-in tabs (Imervue / Modify / Paint / Puppet / Desktop Pet) are added to the main window's top-level `QTabWidget`, before `on_build_menu_bar`. Append your own tab with `tabs.addTab(widget, label)`; plugin tabs follow the built-in ones in plugin discovery order. An exception raised here is logged and skipped, so one plugin cannot abort startup.

```python
from PySide6.QtWidgets import QLabel

def on_build_main_tabs(self, tabs):
    tabs.addTab(QLabel("Hello from My Plugin"), "My Plugin")
```

### Image Hooks

#### `on_image_loaded(image_path: str, viewer: GPUImageView)`

Called after a single image is loaded in deep zoom mode.

```python
def on_image_loaded(self, image_path, viewer):
    logger.debug("Viewing: %s", image_path)
```

#### `on_folder_opened(folder_path: str, image_paths: list[str], viewer: GPUImageView)`

Called after a folder is opened and images are listed in tile grid mode.

```python
def on_folder_opened(self, folder_path, image_paths, viewer):
    logger.debug("Opened folder with %d images", len(image_paths))
```

#### `on_image_switched(image_path: str, viewer: GPUImageView)`

Called when the user navigates to the next/previous image.

```python
def on_image_switched(self, image_path, viewer):
    logger.debug("Switched to: %s", image_path)
```

#### `on_image_deleted(deleted_paths: list[str], viewer: GPUImageView)`

Called after image(s) are soft-deleted (added to the undo stack).

```python
def on_image_deleted(self, deleted_paths, viewer):
    logger.debug("Deleted %d image(s)", len(deleted_paths))
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
self.main_window.tree            # The folder tree view
self.main_window.model           # The folder tree's sort proxy model
self.main_window.plugin_manager  # The PluginManager (loaded plugins, hook dispatch)
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

The `plugins/` directory is put on `sys.path`, so a package plugin imports its own modules by package name (`from my_plugin.helpers import ...`). Single-file plugins work locally, but the plugin downloader only distributes package plugins.

## Dependencies

A plugin may use Imervue's default dependency set (PySide6, numpy, Pillow, imageio, defusedxml, watchdog) directly. Anything heavier (onnxruntime, rembg, opencv-python, torch, ...) must be requested through `ensure_dependencies`, which checks the imports and offers to pip-install whatever is missing before it calls your callback. In a packaged build the packages go into the application's own `lib/site-packages`.

```python
from Imervue.plugin.pip_installer import ensure_dependencies

REQUIRED_PACKAGES = [("onnxruntime", "onnxruntime")]  # (import name, pip name)

def _run_guarded(self):
    ensure_dependencies(self.main_window, REQUIRED_PACKAGES, self._run)
```

Import the heavy package inside the code that `_run` calls, not at module level, so the plugin still loads while the package is missing.

## Background Work

Never block the GUI thread in a hook. Run long work in a `QThread` subclass and report back through signals.

A dialog that owns a running worker must stop it on **Cancel** as well as on window close; Cancel calls `reject()`, which does not deliver a `closeEvent`. Derive the dialog from `WorkerHostMixin` (`Imervue/plugin/worker_host.py`, listed before `QDialog` in the bases) and keep the worker on `self._worker`: the mixin stops and joins it before the dialog is destroyed. A `QThread` destroyed while it is still running aborts the whole process.

## Distributing a Plugin

Plugins reach users through the [Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins) repository. **Plugins → Download Plugins** reads its `main` branch:

- A plugin lives under a category directory: `plugins/<name>/`, or `languages/<name>/` for a language plugin.
- **Only the files directly inside the plugin directory are downloaded.** Subdirectories (`models/`, `assets/`, ...) are not, so keep every file the plugin needs to run flat, and discover optional files such as model weights at runtime.
- A download replaces the installed copy of the plugin as a whole, so do not keep user data inside the plugin directory if it has to survive an update.

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

    def on_build_menu_bar(self, plugin_menu):
        lang = language_wrapper.language_word_dict
        my_menu = plugin_menu.addMenu(lang.get("my_plugin_action", "Do Something"))
        my_menu.addAction(lang.get("my_plugin_greeting", "Hello!"))
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

The new language will automatically appear in the **Language** menu (below a separator). When the user selects it and restarts, the application will use the plugin-provided translations. A built-in language code cannot be registered this way; use `get_translations()` to extend a built-in language.

> **Tip:** Copy all keys from `Imervue/multi_language/english.py` as a starting template for your language plugin. Any missing keys will fall back to `None` via `dict.get()`, so make sure to translate all keys for a complete experience.

## Error Handling

All plugin hooks are wrapped in try/except by the plugin manager. If your plugin raises an exception, it is logged with its traceback but won't crash the application; look for messages prefixed with your plugin name in the console and in `imervue.log`.

This only covers exceptions raised inside a hook. A crash in native code (a GPU driver, an ONNX runtime) or a `QThread` destroyed while running still takes the process down, which is why heavy work belongs in a worker (see *Background Work*).

## Tips

- Log through `logging.getLogger("Imervue.plugin.<your_plugin>")` rather than `print()`: log records reach the console and `imervue.log`, and a packaged build has no console.
- Keep the plugin's pure logic (image maths, file handling) in plain functions that take arrays or paths, separate from the Qt classes, so it can be unit-tested without a display.
- Store plugin state in your plugin instance (`self.my_data = ...`). For state that must persist across sessions, write a JSON file outside the plugin directory (see *Distributing a Plugin*).
- Don't modify internal Imervue data structures directly unless you know what you're doing. Use the provided hooks and the public API.
