# Imervue Architecture

> Short overview of how Imervue is put together: what lives where, how it starts, and where to
> extend it. The detailed per-module map (every package and module, cross-cutting patterns in §10,
> persisted files in §11, known traps in §12) is [`architecture_explore.md`](architecture_explore.md),
> written in Traditional Chinese. This file does not repeat its tables.
>
> Last verified: 2026-09-23 against `5fc068d` on `dev`.

## 1. Purpose

Imervue is a PySide6 + OpenGL desktop application (Python >= 3.10; Windows, macOS, Linux) that
puts five workspaces behind one main window: a GPU-accelerated image browser and photo library,
a non-destructive "develop" editor (Modify tab), a raster paint / comic workspace, a 2D rigged
puppet animator compatible with Live2D Cubism, and a desktop-pet overlay driven by the puppet
runtime. Two non-GUI surfaces reuse the same image algorithms: a headless batch CLI and a Model
Context Protocol (MCP) stdio server. Heavy or crash-prone optional dependencies (ONNX runtime,
rembg, OpenCV, downloaded model weights) are kept out of the main program and shipped as plugins.

## 2. Layers and directories

The tree follows one layering rule: **pure logic and Qt shells are separate**. Menus call dialogs
and workspaces; dialogs and workspaces call pure NumPy / Pillow / SQLite code that never imports Qt
and can run on worker threads, from the CLI, the MCP server, or plugins.

```
menu/                      builds QActions, opens dialogs
gui/  gpu_image_view/      Qt shells, OpenGL viewer
paint/ puppet/ desktop_pet/  self-contained tab workspaces
image/  library/  export/  pure logic (no Qt)
system/ user_settings/ multi_language/ plugin/   infrastructure
```

| Path | Responsibility |
| --- | --- |
| `Imervue/__main__.py` | Process entry: frozen-build fixes, UTF-8 I/O, settings/theme/UI-scale before any widget, main window |
| `Imervue/Imervue_main_window.py` | `ImervueMainWindow`: owns the tab widget and coordinates the five workspaces; its filter row, missing-file handling, folder watching, folder tabs, screen handling, view modes, status bar and browse modes come from the `Imervue/gui/main_window_*.py` mixins |
| `Imervue/menu/` | Menu construction only; `extra_tools_menu.py` holds the `_open_<feature>()` entry points |
| `Imervue/gui/` | Qt dialogs and main-window widgets (develop panel, file tree, list/dual views, EXIF sidebar); most dialogs are shells over `Imervue/image/` |
| `Imervue/gpu_image_view/` | `GPUImageView` (tile wall + deep zoom) and its collaborators; `images/` is the load path, `actions/` the viewer actions |
| `Imervue/image/` | Pure image algorithms: develop `Recipe`, tone/colour, geometry, effects, I/O, metadata, caches |
| `Imervue/library/` | SQLite library index and organising algorithms (smart albums, dedupe, culling, events) |
| `Imervue/export/` | Contact-sheet PDF, static web gallery, slideshow MP4 |
| `Imervue/paint/` | Paint tab: document model, canvas, brush engine, `tools/`, `docks/`, comic and animation features |
| `Imervue/puppet/` | Puppet tab: `.puppet` model and I/O, Cubism import, runtime (deformers, physics), GL canvas, live input drivers, outputs |
| `Imervue/desktop_pet/` | Desktop Pet tab (control panel) plus the separate top-level `PetWindow`; reuses the puppet runtime |
| `Imervue/system/` | App/OS infrastructure: frozen-safe paths (`app_paths.py`), logging, themes, UI scale, file association, batched trash |
| `Imervue/user_settings/` | Global settings dict (profiles, migration, debounced atomic save), tags, bookmarks, colour labels |
| `Imervue/multi_language/` | `language_wrapper` singleton and built-in dictionaries (`english.py` is the canonical key set) |
| `Imervue/sessions/`, `Imervue/macros/`, `Imervue/external/` | Session/workspace save-restore, macro record/replay, external-editor launcher |
| `Imervue/plugin/` | Plugin base class, manager, downloader, pip installer, `WorkerHostMixin` |
| `Imervue/mcp_server/` | MCP JSON-RPC 2.0 stdio server; no Qt, no optional dependencies |
| `Imervue/cli.py` | Headless batch CLI (NumPy + Pillow paths only, never starts Qt) |
| `plugins/` | Plugin sources (gitignored; tracked files need `git add -f`), mirrored to Imervue_Plugins |
| `tests/` | pytest suite; shared fixtures in `tests/conftest.py`, GL skip marker in `tests/_qt_skip.py` |
| `examples/` | Sample `.puppet` rigs and a desktop-pet script |
| `docs/`, `README.md`, `README/` | Sphinx docs and translated READMEs; `README.md` and `docs/en` are canonical |
| `Imervue.spec`, `Imervue_mac.spec`, `packaging/`, `exe/` | PyInstaller specs, AppImage / auto-py-to-exe config, frozen launch shim (`nuitka.md`, `pyinstaller.md` document builds) |
| `.github/workflows/` | `test.yml` (ruff + bandit lint job, Sphinx docs build with `-W`, pytest by layer), `release.yml` |

## 3. Entry points and public interfaces

| Entry | File | Notes |
| --- | --- | --- |
| `py -m Imervue [--debug] [--software_opengl] [file]` | `Imervue/__main__.py` | GUI application |
| `py -m Imervue.cli <subcommand>` | `Imervue/cli.py` | Headless batch; `list-ops` lists subcommands |
| `py -m Imervue.mcp_server` | `Imervue/mcp_server/__main__.py` | Calls `run()` in `Imervue/mcp_server/server.py` |
| `exe/start_Imervue.py` | — | Launch shim for frozen builds |

Public interfaces other code or users depend on:

- **Plugin API** — subclass `ImervuePlugin` (`Imervue/plugin/plugin_base.py`) and override hooks:
  `on_plugin_loaded`, `on_plugin_unloaded`, `on_build_menu_bar`, `on_build_context_menu`,
  `on_build_main_tabs`, `on_image_loaded`, `on_folder_opened`, `on_image_switched`,
  `on_image_deleted`, `on_key_press`, `get_translations`, `on_app_closing`. Author guide:
  `PLUGIN_DEV_GUIDE.md`.
- **Language API** — `language_wrapper.register_language()` and `merge_translations()`
  (`Imervue/multi_language/language_wrapper.py`).
- **MCP tools** — `Imervue/mcp_server/tools.py` re-exports every handler and registers the tool set;
  handlers live in `tools_read.py` / `tools_edit.py`, definitions in `tool_defs_read.py` /
  `tool_defs_edit.py`, output schemas in `tool_schemas.py`.
- **On-disk formats** — `.imervue` (Paint bundle), `.puppet`, `.imervue-session.json`, XMP
  sidecars, `user_setting.json`; locations in `architecture_explore.md` §11.

## 4. Main flows

1. **Startup** — `Imervue/__main__.py` `main()` → `setup_logging()` + `install_exception_logging()`
   (before the first PySide6 import) → `read_user_setting()` → `load_and_apply_theme()` /
   `load_and_apply_from_settings()` → `ImervueMainWindow` (builds tabs, `create_menu()`) →
   `_init_plugin_system_example()` (`Imervue/integration_guide.py`) →
   `PluginManager.discover_and_load()` → optional `open_path()` for a file given on the command line.
2. **Browse and view** — `open_path()` (`gpu_image_view/images/image_loader.py`) →
   `FolderScanWorker` + `gpu_image_view/tile_loader.py` fill the tile wall → selecting an image
   starts `LoadDeepZoomWorker` with the stored recipe (`recipe_store.get_for_path()`) →
   `GPUImageView` renders deep zoom; plugins receive `on_folder_opened` / `on_image_loaded`.
3. **Edit and delete** — single-image tool: `_open_<feature>()` in `menu/extra_tools_menu.py` →
   `gui/<feature>_dialog.py` → `EffectWorker` (`gui/_apply_save.py`) → `image/<feature>.py` → saved
   copy. Modify tab: slider edits → `Recipe` (`image/recipe.py`) persisted by `image/recipe_store.py`.
   Delete: soft delete in `gpu_image_view/actions/delete.py` → `commit_pending_deletions()` →
   one batch through `system/trash_ops.py`.

## 5. Extension points

| To add | Touch |
| --- | --- |
| A main-program image tool | `Imervue/image/<feature>.py` (pure) + `Imervue/gui/<feature>_dialog.py` (shell, usually on `Imervue/gui/_apply_save.py`) + `_open_<feature>()` in `Imervue/menu/extra_tools_menu.py` |
| A dialog that owns a `QThread` | Inherit `WorkerHostMixin` from `Imervue/plugin/worker_host.py`; do not hand-write teardown |
| A develop step | `Recipe.apply` in `Imervue/image/recipe.py` (keep the `to_dict` / `from_dict` round trip) |
| A plugin | `plugins/<name>/__init__.py` (sets `plugin_class`) + `plugins/<name>/<name>_plugin.py`; all pure logic inside the plugin directory |
| A language | Plugin calling `language_wrapper.register_language()` (reference: `plugins/spanish_translation/`); new UI keys go into `Imervue/multi_language/english.py` first |
| An MCP tool | Handler in `Imervue/mcp_server/tools_read.py` or `tools_edit.py`, its entry in the matching `tool_defs_*.py`, a re-export in `tools.py`, and `Imervue/mcp_server/tool_schemas.py` (parity enforced by `tests/test_mcp_tool_schemas.py`) |
| A CLI subcommand | `Imervue/cli.py` |
| A Paint tool or dock | `Imervue/paint/tools/`, `Imervue/paint/docks/`, routed by `Imervue/paint/tool_dispatcher.py` |
| A theme | `Imervue/system/themes.py` |

## 6. Cross-project boundaries

- **Imervue_Plugins (distribution repo).** `Imervue/plugin/plugin_downloader.py` lists the repo with
  one recursive git-tree call on `main` (`REPO_TREE_URL`), accepts only the categories `plugins` and
  `languages` (`PLUGIN_CATEGORIES`), and downloads only the files directly inside
  `<category>/<plugin>/` from raw.githubusercontent into `plugins_dir()` (`<app_dir>/plugins/`).
  Downloaders released before this change still treat every top-level non-dot directory as a
  category, so the distribution repo must not add other directories until those are out of use.
  Any change under `plugins/<name>/` here must be copied to `D:\Codes\Imervue_Plugins` and pushed
  to `main`; keep every runtime-required file flat (nested `models/`, `assets/` are never fetched).
  Language plugins sit under `languages/` there, the rest under `plugins/`.
- **Extra Tools submenu names.** Plugins in Imervue_Plugins place menu entries with
  `main_window.findChild(QMenu, "extra_tools.<key>")` (`develop_submenu`, `retouch_submenu`, ...;
  names set by `Imervue/menu/extra_tools_menu.py` `submenu_object_name`). Never rename or drop one;
  `tests/test_plugin_menu_placement.py` covers the plugins that use them.
- **Plugin dependencies.** `Imervue/plugin/pip_installer.py` installs a plugin's pip packages at
  runtime, including in frozen builds. Every install runs under the constraints in
  `Imervue/plugin/pip_constraints.py`, which keep all OpenCV distributions below 5: they share one
  `cv2` directory, and OpenCV 5 dropped the Haar cascades face detection needs.
- **Helpers plugins import instead of copying.** Plugins in Imervue_Plugins (`ai_background_remover`,
  `object_splitter`, `safety_review`) call `from Imervue.plugin.pip_installer import _find_python` to
  get an interpreter with pip, and import `_subprocess_kwargs` from the same module for their child
  processes. Both live in `Imervue/plugin/python_finder.py`; `pip_installer` re-exports them, and
  `tests/test_python_finder.py` checks the re-export. Ten image plugins load their input with
  `from Imervue.gui._apply_save import load_rgba`. Keep these import paths working, or change the
  plugins in the same round. Each has shipped since v1.0.56 or earlier, so a newly downloaded plugin
  still runs on older installs.
- **External services.** Every download made by the plugin downloader and pip installer goes through
  an HTTPS-only guard; model downloads from Hugging Face must pin a revision. Codacy and SonarCloud
  analyse only the `main` branch.
- No code dependency on any other repository in this workspace.

## 7. Design constraints

Summaries only; `CLAUDE.md` is the source of truth.

- Every change ships with unit tests and passes `py -m pytest tests/`, `py -m ruff check .` and
  `py -m bandit -c pyproject.toml -r Imervue/ plugins/` (CLAUDE.md "Definition of Done"); both
  gates cover the gitignored, force-added `plugins/`.
- `architecture_explore.md` is updated in the same commit when structure or responsibility changes
  (CLAUDE.md "Architecture Map").
- Commits, PRs, code comments and docs carry no tool or model attribution and no `Co-Authored-By`
  (CLAUDE.md "No AI Attribution").
- Files stay within 1000 lines; no duplicated blocks or repeated literals, no `TODO`, no `print()`
  (log through `Imervue/system/log_setup.py`), no `assert` for runtime validation, Qt resources are
  released (CLAUDE.md "Code Quality").
- Pure-helper tests plus Qt smoke tests on the shared fixtures; tests never write the real
  `user_setting.json` (CLAUDE.md "Unit Tests").
- Test modules that build `QOpenGLWidget` subclasses import the `tests/_qt_skip.py` marker
  (CLAUDE.md "Qt / OpenGL tests on headless CI").
- A feature becomes a plugin only for heavy optional dependencies, failure isolation or independent
  release cadence (CLAUDE.md "Plugins vs Main Program").
- Plugin changes are mirrored to Imervue_Plugins `main` (CLAUDE.md "Mirror plugin changes to the
  distribution repo").
- Every `urlopen` goes through a module-level `_https_urlopen` guard; Hugging Face downloads pin a
  revision (CLAUDE.md "Network & Supply-Chain Safety").
- Suppressions name the tool-specific code with a justification; `.bandit` and `pyproject.toml`
  `[tool.bandit]` stay in sync (CLAUDE.md "Suppressions & Skip Configuration").
- All deletes batch through `Imervue/system/trash_ops.py` (CLAUDE.md "Environment Gotchas").

## 8. When to update this file

Update it in the same commit when:

- a top-level package or directory is added, removed, renamed, or changes responsibility;
- an entry point, the startup sequence, or the tab layout changes;
- the plugin hook set, the downloader contract, or the distribution-repo layout changes;
- an extension point in §5 moves, or a new cross-project dependency appears;
- a hard rule in `CLAUDE.md` is added, removed, or renamed.

Module-level changes (new module, changed purpose, line counts, traps) belong in
`architecture_explore.md`, not here. Refresh the "Last verified" line whenever this file is edited.
