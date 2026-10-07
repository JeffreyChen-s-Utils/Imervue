# Imervue Architecture

> Short overview of how Imervue is put together: what lives where, how it starts, and where to
> extend it. The detailed per-module map (every package and module, cross-cutting patterns in §10,
> persisted files in §11, known traps in §12) is [`architecture_explore.md`](architecture_explore.md),
> written in Traditional Chinese. This file does not repeat its tables.
>
> Last verified: 2026-10-07 on `dev`; corresponding commit: `git log -1 -- architecture.md`.

## 1. Purpose

Imervue is a PySide6 + OpenGL desktop application (Python >= 3.10; Windows, macOS, Linux) that
puts five workspaces behind one main window: a GPU-accelerated image browser and photo library,
a non-destructive "develop" editor (Modify tab), a raster paint / comic workspace, a 2D rigged
puppet animator compatible with Live2D Cubism, and a desktop-pet overlay driven by the puppet
runtime. Two non-GUI surfaces reuse the same image algorithms: a headless batch CLI and a Model
Context Protocol (MCP) stdio server. Heavy or crash-prone optional dependencies (ONNX runtime,
rembg, OpenCV, downloaded model weights) are kept out of the main program and shipped as plugins;
the exceptions, AI upscale and CLIP semantic search / auto-tag, offer to install onnxruntime on
first use and download their models at pinned revisions.

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
| `scripts/performance_*.py`, `docs/performance/` | Checkout-only benchmark entry point, isolated fixture/profile and native RSS helpers, actual GL frames; raw fixed-hardware baseline and acceptance targets. These tools are not shipped application commands |
| `Imervue/sessions/`, `Imervue/macros/`, `Imervue/external/` | Session/workspace save-restore, macro record/replay, external-editor launcher |
| `Imervue/plugin/` | Plugin base class, manager, downloader, pip installer, `WorkerHostMixin`, the plugin API version (`plugin_api.py`) and the shared tool dialog (`tool_dialog.py`) |
| `Imervue/mcp_server/` | MCP JSON-RPC 2.0 stdio server; no Qt, no optional dependencies |
| `Imervue/cli.py` | Headless batch CLI (NumPy + Pillow paths only, never starts Qt) |
| `plugins/` | Plugin sources (gitignored; tracked files need `git add -f`), mirrored to Imervue_Plugins |
| `tests/` | pytest suite, run from a checkout: neither the wheel nor the sdist carries it; shared fixtures in `tests/conftest.py`, GL skip marker in `tests/_qt_skip.py` |
| `examples/` | The bundled `.puppet` character Imeru, the code that builds it (`examples/puppet/imeru/build.py`: a Blender cel-shaded render, an SDF face shadow map and painted face features, then the rig) and her desktop-pet script |
| `docs/`, `README.md`, `README/` | Sphinx docs and translated READMEs; `README.md` and `docs/en` are canonical |
| `Imervue.spec`, `Imervue_mac.spec`, `packaging/`, `exe/` | PyInstaller specs, AppImage / auto-py-to-exe config, frozen launch shim (`nuitka.md`, `pyinstaller.md` document builds) |
| `.github/workflows/` | `test.yml` (ruff + bandit lint job, Sphinx docs build with `-W`, pytest by layer, then the `publish-dev` job on a push to `dev`), `release.yml` (stable release on a pull request merged into `main`) |
| `.github/requirements/` | `publish.in` and the hash-locked `publish.txt` generated from it: the only thing the two jobs that hold the PyPI token install (the regenerating command is at the top of `publish.in`) |
| `scripts/` | Stdlib-only helpers CI runs, never shipped in the wheel: `dev_release.py` numbers the `Imervue_dev` release and decides whether a build differs from the published one |

## 3. Entry points and public interfaces

| Entry | File | Notes |
| --- | --- | --- |
| `py -m Imervue [--debug] [--software_opengl] [file]` | `Imervue/__main__.py` | GUI application |
| `py -m Imervue.cli <subcommand>` | `Imervue/cli.py` | Headless batch; `list-ops` lists subcommands; every MCP tool is also a subcommand (`Imervue/cli_tools.py`) |
| `py -m Imervue.mcp_server` | `Imervue/mcp_server/__main__.py` | Calls `run()` in `Imervue/mcp_server/server.py` |
| `exe/start_Imervue.py` | — | Launch shim for frozen builds |
| PyPI packages `Imervue` (stable), `Imervue_dev` (dev channel) | `pyproject.toml`, `dev.toml`, `MANIFEST.in` | Both wheels install one top-level package, `Imervue`: package discovery includes `Imervue` and `Imervue.*` only. Neither distribution carries the test suite: `MANIFEST.in` prunes `tests/` from the sdist. Stable: a pull request merged into `main` runs `release.yml`, which bumps `pyproject.toml`, tags and uploads. Dev: the `publish-dev` job of `test.yml` runs after `lint`, `docs`, `fast` and `extended` on a push to `dev`, builds from `dev.toml` and uploads when the commit is still the tip of `dev` and the wheel differs from the newest published one; `scripts/dev_release.py` takes the version from PyPI (newest release plus one patch), so nothing is committed back. Both jobs hold the PyPI token and install nothing but the hash-locked `.github/requirements/publish.txt` (`build`, `twine` and `setuptools`, wheels only; generated from `publish.in` beside it), then build with `python -m build --no-isolation`, so the build backend is the locked `setuptools` too; `tests/test_workflow_actions.py` fails on any other `pip install` in them, on an isolated build, and on a `build-system.requires` the lock does not satisfy |

Public interfaces other code or users depend on:

- **Plugin API** — subclass `ImervuePlugin` (`Imervue/plugin/plugin_base.py`) and override hooks:
  `on_plugin_loaded`, `on_plugin_unloaded`, `on_build_menu_bar`, `on_build_context_menu`,
  `on_build_main_tabs`, `on_image_loaded`, `on_folder_opened`, `on_image_switched`,
  `on_image_deleted`, `on_key_press`, `get_translations`, `on_pet_created`, `on_app_closing`, plus
  the class method `register_languages` (called before the main window is built). Author guide:
  `PLUGIN_DEV_GUIDE.md`. `on_pet_created(pet)` reaches plugins through
  `PluginManager.connect_pet_hooks` (the Desktop Pet tab's `pet_created` signal, and the pet that
  already exists at load / reload; the window calls it again when it builds the Desktop Pet tab after
  the plugins loaded); the pet's plugin surface is listed in its docstring.
- **Language API** — `language_wrapper.register_language()` (from a plugin's
  `register_languages()`) and `merge_translations()`
  (`Imervue/multi_language/language_wrapper.py`).
- **MCP tools** — `Imervue/mcp_server/tools.py` re-exports every handler and registers the tool set;
  handlers live in `tools_read.py` / `tools_edit.py`, definitions in `tool_defs_read.py` /
  `tool_defs_edit.py`, output schemas in `tool_schemas.py`.
- **On-disk formats** — `.imervue` (Paint bundle), `.puppet`, `.imervue-session.json`, XMP
  sidecars, `user_setting.json`; locations in `architecture_explore.md` §11. `.puppet` is a public
  format: specification `Imervue/puppet/FORMAT.md`, JSON Schemas generated by
  `Imervue/puppet/format_schema.py` into `docs/schemas/`, conformance check `puppet-validate`
  (MCP `puppet_validate`), stdlib reference reader `docs/examples/read_puppet.py`.

## 4. Main flows

1. **Startup** — `Imervue/__main__.py` `main()` → `setup_logging()` + `install_exception_logging()`
   (before the first PySide6 import) → `read_user_setting()` → `load_and_apply_theme()` /
   `load_and_apply_from_settings()` → `ImervueMainWindow` (`apply_saved_language()` registers
   plugin languages first when the saved language is not built in; builds the tabs, Puppet and Desktop Pet
   only when they are on in Preferences (`gui/optional_tabs.py`) and then as empty pages whose workspace is
   built when the tab is first opened; `create_menu()`) →
   `_init_plugin_system_example()` (`Imervue/integration_guide.py`) →
   `PluginManager.discover_and_load()` → optional `open_path()` for a file given on the command line.
2. **Browse and view** — `open_path()` (`gpu_image_view/images/image_loader.py`) →
   `FolderScanWorker` + `gpu_image_view/tile_loader.py` fill the tile wall → selecting an image
   starts `LoadDeepZoomWorker` with the stored recipe (`recipe_store.get_for_path()`) →
   `GPUImageView` renders deep zoom; plugins receive `on_folder_opened` / `on_image_loaded`.
3. **Edit and delete** — single-image tool: `_open_<feature>()` in `menu/extra_tools_menu.py` →
   `gui/<feature>_dialog.py` → `EffectWorker` (`gui/_apply_save.py`) → `image/<feature>.py` → saved
   copy. Modify tab: slider edits → `Recipe` (`image/recipe.py`) persisted by `image/recipe_store.py`.
   Modify preview: a per-panel latest-generation scheduler coalesces requests, renders reduced
   then full pixels on the global pool, and installs prepared QImages through queued UI signals.
   Geometry stays full-size; saves/destructive effects resolve canonical pixels first. Jobs own
   immutable source/recipe data and their application-owned signal sender survives panel destruction.
   Paint: entering its tab preserves the open documents; File > Open Current Image in Paint
   and image navigation from the Paint main-tab bar decode first, then open a new document.
   A failed decode leaves every document unchanged. The Deep Zoom E key opens annotations.
   Paint history: dispatcher gestures and explicit layer/material commands commit complete
   editable content per document; restore keeps the document's listeners and surviving
   layer identities while restoring structure, properties, masks, vectors and selections.
   Immutable 256px tiles share unchanged pixels; instrumented brush/eraser commits only
   scan damaged tiles, while unknown edits compare every array. The 512 MiB budget counts
   baseline, both branches, pixel payloads, Python metadata and the weak tile index. Older
   states are pruned; an oversized baseline clears history while preserving live content.
   Snapshot materialization makes independent arrays for background consumers.
   Paint recovery: periodic autosave covers every dirty tab, with stable document identities
   and independent eight-version retention. Restore opens new modified tabs, falling back
   to older readable versions without replacing edits. Native metadata keeps panel layouts.
   Delete: soft delete in `gpu_image_view/actions/delete.py` → `commit_pending_deletions()` →
   one batch through `system/trash_ops.py`.
4. **Batch export** — `gui/batch_export_dialog.py` `_ExportWorker` opens the renderer chosen under
   *Render on* (`image/develop_backends.open_renderer()`; none for the CPU) → per image
   `gui/export_source.open_export_source(path, renderer)` → `develop_backends.render()` (the
   renderer, or `Recipe.apply` on the CPU, also when the renderer fails on that image) →
   `image/save_formats.save_image()`; the renderer is closed when the loop ends.

## 5. Extension points

| To add | Touch |
| --- | --- |
| A main-program image tool | `Imervue/image/<feature>.py` (pure) + `Imervue/gui/<feature>_dialog.py` (shell, usually on `Imervue/gui/_apply_save.py`) + `_open_<feature>()` in `Imervue/menu/extra_tools_menu.py` |
| A dialog that owns a `QThread` | Inherit `WorkerHostMixin` from `Imervue/plugin/worker_host.py`; do not hand-write teardown |
| A plugin dialog that runs one image transform on OK | Inherit `ToolDialogMixin` from `Imervue/plugin/tool_dialog.py` (it includes `WorkerHostMixin`): set `output_suffix` and the toast keys, return the transform from `_transform()`, name optional packages in `_required_packages()`; the plugin then needs plugin API 2 in its `plugin.json` |
| Main-program code that plugins import | Raise `PLUGIN_API_VERSION` in `Imervue/plugin/plugin_api.py` and list what the version adds in its docstring; plugins using it declare `{"min_api_version": N}` in `plugin.json` (`tests/test_plugin_api.py` checks the bundled ones) |
| A develop step | A row in `_STAGES` of `Imervue/image/recipe.py` (keep the `to_dict` / `from_dict` round trip). A stage between `white_balance` and `tone_curve` also needs the GPU Develop plugin (`plugins/gpu_develop/params.py` `GPU_STAGES`), which renders nothing on the GPU until its span matches |
| A develop renderer (another device for the recipe) | A `BackendProvider` registered with `Imervue.image.develop_backends.register()` from a plugin's `on_plugin_loaded`; it must return what `Recipe.apply` does and may run any span through `Recipe.apply_stages()` (reference: `plugins/gpu_develop/`) |
| A plugin | `plugins/<name>/__init__.py` (sets `plugin_class`) + `plugins/<name>/<name>_plugin.py`; all pure logic inside the plugin directory |
| A language | Plugin calling `language_wrapper.register_language()` from its `register_languages()` class method (reference: `plugins/spanish_translation/`); new UI keys go into `Imervue/multi_language/english.py` first |
| An MCP tool | Handler in `Imervue/mcp_server/tools_read.py` or `tools_edit.py`, its entry in the matching `tool_defs_*.py`, a re-export in `tools.py`, and `Imervue/mcp_server/tool_schemas.py` (parity enforced by `tests/test_mcp_tool_schemas.py`); its CLI name in `BRIDGED` in `Imervue/cli_tools.py`, which builds the subcommand from the schema (`tests/test_cli_tools.py` fails until every MCP tool has one) |
| A CLI subcommand | `Imervue/cli.py` (`_SUBCOMMANDS` row plus a `_WRITE_SPEC`, `_REPORTERS` or `_MULTI_COMMANDS` entry); one that mirrors an MCP tool comes from `Imervue/cli_tools.py` instead |
| A Paint tool or dock | `Imervue/paint/tools/`, `Imervue/paint/docks/`, routed by `Imervue/paint/tool_dispatcher.py` |
| A theme | `Imervue/system/themes.py` |

## 6. Cross-project boundaries

- **FrontEngine (optional downstream)** consumes the version 1 `.puppet` archive through
  `Imervue.puppet.document_io.load_puppet`, `Imervue.puppet.canvas.PuppetCanvas`,
  `MotionPlayer`, `IdleDriver`, `InputEngine`, and
  `Imervue.desktop_pet.pet_script` loader/engine. FrontEngine's `puppet` extra requires
  `Imervue>=1.0.90`; it validates container versions/resources before loading and owns
  window geometry, timers and settings without creating Imervue's PetWindow.
  PUPPET entries in FrontEngine scene v1 reference these archives; `.fescene` packages
  copy the referenced assets. Imervue does not read the FrontEngine scene envelope.
  Renaming these runtime imports or changing the container requires coordinated updates
  to `FrontEngine/frontengine/utils/imervue/` and its interchange tests.

- **Imervue_Plugins (distribution repo).** `Imervue/plugin/plugin_downloader.py` lists the repo with
  one recursive git-tree call on `main` (`REPO_TREE_URL`), accepts only the categories `plugins` and
  `languages` (`PLUGIN_CATEGORIES`), and downloads only the files directly inside
  `<category>/<plugin>/` from raw.githubusercontent into `plugins_dir()` (`<app_dir>/plugins/`).
  A plugin or file name that is not one plain path component on every platform (`..`, a
  backslash, a character Windows forbids) is skipped when listing and refused when downloading.
  Downloaders released before this change still treat every top-level non-dot directory as a
  category, so the distribution repo must not add other directories until those are out of use.
  Any change under `plugins/<name>/` here must be copied to `D:\Codes\Imervue_Plugins` and pushed
  to `main`; keep every runtime-required file flat (nested `models/`, `assets/` are never fetched).
  Language plugins sit under `languages/` there, the rest under `plugins/`.
- **Plugin API version.** A plugin's optional `plugin.json` (`{"min_api_version": N}`, read by
  `Imervue/plugin/plugin_api.py`) names the main-program surface it needs; without the file it needs
  1. The downloader refuses a plugin needing more than `PLUGIN_API_VERSION` before swapping it into
  place, and the plugin manager skips it without importing it. Version 2 added
  `Imervue.plugin.tool_dialog` and `Imervue.image.develop_backends`; the nine tool-dialog plugins,
  `ai_object_remove`, `cloud_share` and `gpu_develop` declare it. Installs released before the
  manifest ignore it, so on them such a plugin fails at import time and is skipped (logged). Keep the
  file name, the key and every name an API version lists, or raise the version and change the
  plugins in the same round.
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
  `tests/test_python_finder.py` checks the re-export. Nine image plugins (`ai_colorize`,
  `ai_denoise`, `ai_motion_deblur`, `ai_portrait_relight`, `ai_smart_resize`, `ai_style_transfer`,
  `ai_outpaint`, `npr_filters`, `portrait_mode`) build their dialog on
  `Imervue.plugin.tool_dialog.ToolDialogMixin`, which loads the input with
  `Imervue.gui._apply_save.load_rgba` (an HxWx4 RGBA array as the viewer shows it: RAW developed at
  full size, sRGB, EXIF-upright) through `EffectWorker`, saves `<stem>_<suffix>.png` under a free
  name (`output_path`), and toasts with `notify_saved`. `ai_object_remove` imports `load_rgba`
  from `_apply_save` and `output_path` / `show_toast` from `tool_dialog`; `cloud_share` imports
  `show_toast`; `ai_motion_deblur` and `ai_portrait_relight` import `make_slider`, `ai_colorize` and
  `ai_style_transfer` `slider_row`. Keep these names, the mixin's attributes (`output_suffix`,
  `failed_key`, `failed_text`, `done_key`, `done_text`) and hooks (`_transform`,
  `_required_packages`, `_commit`, `_notify_failure`) working, or change the plugins in the same
  round.
- **Desktop pet plugin surface.** `pet_integrations` (Desktop Pet Integrations) subclasses
  `IntegrationController` from `Imervue.desktop_pet.pet_feature_base` and calls
  `Imervue.system.local_origin.is_allowed_origin`; it relies on the `on_pet_created` hook and on the
  pet window's `play_group`, `speak`, `speak_notification`, `speech_on`, `setting`, `persist`,
  `add_integration`, `remove_integration` and `integration`. It keeps its options in the pet's settings
  under `obs_*`, `twitch_*`, `webhook_*` and `win_notifications_*`. Keep these names, or change the
  plugin in the same round. On an install older than `on_pet_created` the plugin loads but the pet
  never gets the integrations.
- **GPU Develop plugin surface.** `gpu_develop` (in Imervue_Plugins) registers a
  `BackendProvider` with `Imervue.image.develop_backends.register` / `unregister`, renders with
  `Recipe.normalized()`, `Recipe.apply_stages(arr, first, last)` and `STAGE_NAMES` from
  `Imervue.image.recipe`, `is_zero` from `Imervue.image.recipe_adjustments`, and installs `wgpu` with
  `Imervue.plugin.pip_installer.ensure_dependencies`. Keep these names and the stage names from
  `white_balance` to `tone_curve`, or change the plugin in the same round; a pipeline whose span
  differs makes the plugin offer no GPU. An install older than `develop_backends` fails to load the
  plugin (logged) and keeps exporting on the CPU.
- **External services.** Every download made by the plugin downloader and pip installer goes through
  an HTTPS-only guard; model downloads from Hugging Face must pin a revision. Codacy and SonarCloud
  analyse only the `main` branch.
- **Published `.puppet` schema URLs.** Every saved `.puppet` names its schemas in `$schema` as
  `https://raw.githubusercontent.com/JeffreyChen-s-Utils/Imervue/main/docs/schemas/<name>.schema.json`,
  and the schemas carry those URLs as `$id`; editors and other programs fetch them. Keep
  `docs/schemas/` at that path on `main`, and regenerate the files (never hand-edit) when
  `format_schema.py` changes; `tests/test_puppet_format_schema.py` fails when they differ.
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
