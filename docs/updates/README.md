# docs/updates: update log index

`progress.md` holds only work that is **not done yet**. Everything that *was* done (what changed, measured numbers, decisions, snapshots) is recorded here: **one batch file per month**, one entry per piece of work, each entry with a fixed-format ID and tags, and one row per entry in the index below.

> No TODOs here. If an entry mentions something still open, it only points to it (e.g. "open item: `progress.md` #3"); the item itself lives in `progress.md`.

## How to query

Run from the repository root:

| To find | Command |
|---|---|
| every entry, one line each | `rg -n "^## U-2" docs/updates` |
| entries of one type | `rg -n "^## U-2.*#done" docs/updates` |
| entries with a topic tag | `rg -n "^## U-2.*#<tag>" docs/updates` |
| one day or one month | `rg -n "^## U-202609" docs/updates` |
| the full text of one entry | `rg -n -A 60 "^## U-20260922-01" docs/updates` |
| any keyword | `rg -n "keyword" docs/updates` |

Without `rg`: `git grep -n "^## U-2" -- docs/updates`, or in PowerShell `Select-String -Path docs/updates/*.md -Pattern '^## U-2'`.

## Entry format

```markdown
## U-YYYYMMDD-NN · YYYY-MM-DD · one-line title · #type #topic

- **What**: ...
- **Result / numbers**: ...
- **Files**: `path` ...
- **Evidence**: commit, file:line, link ...
- **Open items**: none / see `progress.md` ...
```

- **ID**: `U-` + date + two-digit sequence for that day. IDs are never renumbered or reused, so code comments and other documents can cite them.
- **Type tag** (exactly one): `#done` finished `progress.md` item, `#snapshot` measurement or inventory, `#decision`, `#incident`, `#migration`, `#docs`, `#release`.
- Topic tags are free-form (`#mcp`, `#wayland`, ...).
- Keep conclusions, numbers, files and evidence; drop the reasoning trail and dead ends.

## Batch rules

1. One file per month: `docs/updates/YYYY-MM.md`. Append new entries at the end.
2. Over about 800 lines, continue in `YYYY-MM-b.md` (then `-c`) and list it in the batch table below.
3. **Claim the ID under a lock.** Several sessions may write this log at the same time (for example parallel autonomous runs), and without a lock two of them pick the same number:
   1. `mkdir docs/updates/.id-lock`. Creating a directory is atomic, so only one writer succeeds. If it already exists, someone else is claiming: wait a few seconds and retry. A lock older than 10 minutes is stale and may be removed.
   2. Find the day's last number with `rg -n "^## U-YYYYMMDD" docs/updates` and write the heading line and the index row.
   3. `rmdir docs/updates/.id-lock`, then fill in the body. Git never tracks the empty lock directory.
   4. Before committing, `rg -c "^## U-<your ID>" docs/updates` must report one match in total. If not, renumber your entry under the lock and fix its index row. Whoever merges a branch renumbers entries that reuse an ID.
4. **One line per index row**: title only (about 60 characters), no summary.
5. Never rewrite a recorded entry. Correct it with a new `#decision` or `#incident` entry and add "→ corrected in U-..." to the old one.

## When a `progress.md` item is done

In the same commit: delete the item from `progress.md`, add a `#done` entry here that names it, and add its index row.

---

## Index (newest first)

| ID | Date | Title | Tags | Batch |
|---|---|---|---|---|
| U-20260923-27 | 2026-09-23 | Split the viewer and main-window constructors into section builders | #done #refactor #main_window #gpu_image_view | [2026-09](2026-09.md) |
| U-20260923-26 | 2026-09-23 | Drop five per-file ruff exemptions that no longer match anything | #done #lint | [2026-09](2026-09.md) |
| U-20260923-25 | 2026-09-23 | Real-application run after the main-window split | #snapshot #main_window | [2026-09](2026-09.md) |
| U-20260923-24 | 2026-09-23 | Split ImervueMainWindow into eight mixins; every module under 1000 lines | #done #refactor #main_window | [2026-09](2026-09.md) |
| U-20260923-23 | 2026-09-23 | Split PaintCanvas: overlays, input and view transform become mixins | #done #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-22 | 2026-09-23 | Real-application run after the viewer split | #snapshot #gpu_image_view | [2026-09](2026-09.md) |
| U-20260923-21 | 2026-09-23 | Split GPUImageView: deep-zoom loading, fitting, prefetch and mouse become mixins | #done #refactor #gpu_image_view | [2026-09](2026-09.md) |
| U-20260923-20 | 2026-09-23 | Split PuppetWorkspace: menus, import and live outputs become mixins | #done #refactor #puppet | [2026-09](2026-09.md) |
| U-20260923-19 | 2026-09-23 | Brush jitter changed on every reopen: seed it with CRC32, not hash() | #incident #annotation | [2026-09](2026-09.md) |
| U-20260923-18 | 2026-09-23 | Split the annotation canvas into drawing, crop and mosaic/blur mixins | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-17 | 2026-09-23 | Move the puppet canvas GL drawing into a mixin; render test on a real rig | #done #refactor #puppet | [2026-09](2026-09.md) |
| U-20260923-16 | 2026-09-23 | Split PaintDocument: geometry, merge and group operations become mixins | #done #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-15 | 2026-09-23 | Move the desktop pet feature toggles into a mixin | #done #refactor #desktop_pet | [2026-09](2026-09.md) |
| U-20260923-14 | 2026-09-23 | Clipboard tests use an in-process fake, not the OS clipboard | #incident #tests | [2026-09](2026-09.md) |
| U-20260923-13 | 2026-09-23 | Split the Modify panel: right-panel builder and splitter sizing become mixins | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-12 | 2026-09-23 | Link slider and spin pairs through one helper; annotation panel under 1000 lines | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-11 | 2026-09-23 | Paint workspace tests waited a fixed time after show() | #incident #tests #paint | [2026-09](2026-09.md) |
| U-20260923-10 | 2026-09-23 | Move the selection and retouch tools into paint/tools/ | #done #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-09 | 2026-09-23 | 10 of 17 plugins failed to load in the EXE: compile every Imervue submodule | #incident #packaging #plugins | [2026-09](2026-09.md) |
| U-20260923-08 | 2026-09-23 | Move the OSD text and HUD geometry helpers out of overlay_painter | #done #refactor #gpu_image_view | [2026-09](2026-09.md) |
| U-20260923-07 | 2026-09-23 | The packaged EXE wrote no log; set it up before Qt is imported | #incident #packaging #logging | [2026-09](2026-09.md) |
| U-20260923-06 | 2026-09-23 | A fixed processEvents count made a worker test fail 4 runs in 5 | #incident #tests | [2026-09](2026-09.md) |
| U-20260923-05 | 2026-09-23 | The EXE shipped no plugins: --include-data-dir skips .py files | #incident #packaging #plugins | [2026-09](2026-09.md) |
| U-20260923-04 | 2026-09-23 | Split mcp_server/tools.py into read, edit and definition modules | #done #refactor #mcp | [2026-09](2026-09.md) |
| U-20260923-03 | 2026-09-23 | Move the PySide6 pin to 6.11.2 | #done #pyside6 #release | [2026-09](2026-09.md) |
| U-20260923-02 | 2026-09-23 | Remove the unused plugin manifest module | #done #plugins #cleanup | [2026-09](2026-09.md) |
| U-20260923-01 | 2026-09-23 | Clear the 153 Sphinx warnings and build the docs with -W in CI | #done #docs #ci | [2026-09](2026-09.md) |
| U-20260922-17 | 2026-09-22 | Face detection on OpenCV 5; keep plugin installs on OpenCV 4 | #done #opencv #plugins | [2026-09](2026-09.md) |
| U-20260922-16 | 2026-09-22 | Mirror safety_review 1.0.1 to Imervue_Plugins | #done #Imervue_Plugins #plugins | [2026-09](2026-09.md) |
| U-20260922-15 | 2026-09-22 | QAction.menu() invalidated cached menus; plugin reload fixed | #done #pyside6 #plugins | [2026-09](2026-09.md) |
| U-20260922-14 | 2026-09-22 | Imervue_Plugins: README becomes a plugin list | #done #Imervue_Plugins #docs | [2026-09](2026-09.md) |
| U-20260922-13 | 2026-09-22 | Offer onnxruntime before the ONNX paths of six plugins | #done #plugins #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260922-12 | 2026-09-22 | Refresh stale version and dependency metadata | #done #housekeeping | [2026-09](2026-09.md) |
| U-20260922-11 | 2026-09-22 | Concurrent pytest runs deleted each other's tmp_path | #incident #tests | [2026-09](2026-09.md) |
| U-20260922-10 | 2026-09-22 | Plugin downloader: two categories, one API request | #done #plugins #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260922-09 | 2026-09-22 | Eight plugins had no menu entry; name the Extra Tools submenus | #incident #plugins #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260922-08 | 2026-09-22 | Run ruff and bandit in CI | #done #ci | [2026-09](2026-09.md) |
| U-20260922-07 | 2026-09-22 | Track the PyInstaller spec files | #done #packaging | [2026-09](2026-09.md) |
| U-20260922-06 | 2026-09-22 | Bring PLUGIN_DEV_GUIDE.md and the hook tables up to date | #done #docs #plugins | [2026-09](2026-09.md) |
| U-20260922-05 | 2026-09-22 | Mirror 13 plugin files; track png_to_icon | #done #Imervue_Plugins #plugins | [2026-09](2026-09.md) |
| U-20260922-04 | 2026-09-22 | Imervue_Plugins: stop tracking .idea/ | #done #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260922-03 | 2026-09-22 | Stop tracking .idea/ and the SFTP settings | #done #housekeeping | [2026-09](2026-09.md) |
| U-20260922-02 | 2026-09-22 | Imervue_Plugins mirror drift found | #snapshot #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260922-01 | 2026-09-22 | Adopt progress/architecture/docs-updates rules | #docs #migration | [2026-09](2026-09.md) |

## Batches

| File | Period | Entries |
|---|---|---:|
| [2026-09.md](2026-09.md) | 2026-09 | 15 |
