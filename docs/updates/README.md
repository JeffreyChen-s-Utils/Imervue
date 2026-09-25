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
| U-20260925-88 | 2026-09-25 | Icons, textures, JPEG 2000 and Netpbm pictures open in the viewer | #feature #formats #browse | [2026-09-b](2026-09-b.md) |
| U-20260925-87 | 2026-09-25 | A JPEG named .jfif, .jpe or .jif opens like any other | #fix #formats #browse #batch | [2026-09-b](2026-09-b.md) |
| U-20260925-86 | 2026-09-25 | The MCP server's folder tools leave out hidden files like the viewer | #fix #mcp #browse | [2026-09-b](2026-09-b.md) |
| U-20260925-85 | 2026-09-25 | Next / previous folder follows the folder tree's order | #fix #browse #sort | [2026-09-b](2026-09-b.md) |
| U-20260925-84 | 2026-09-25 | Hidden files and macOS ._ companions stay out of the wall and the batch tools | #fix #browse #batch #library | [2026-09-b](2026-09-b.md) |
| U-20260925-83 | 2026-09-25 | Refactor: the batch tools share one folder listing | #refactor #batch | [2026-09-b](2026-09-b.md) |
| U-20260925-82 | 2026-09-25 | 16-bit and float greyscale pictures show their real brightness | #fix #formats #viewer #thumbnails | [2026-09-b](2026-09-b.md) |
| U-20260925-81 | 2026-09-25 | A picture another program saves over shows its new version | #fix #viewer #thumbnails #external-editor | [2026-09-b](2026-09-b.md) |
| U-20260925-80 | 2026-09-25 | A photo cut short opens as far as it was read | #fix #viewer #decode #cli #mcp | [2026-09-b](2026-09-b.md) |
| U-20260925-79 | 2026-09-25 | CR3, RW2, ORF and RAF show their EXIF, sort by capture date and keep it in exports | #fix #raw #metadata | [2026-09-b](2026-09-b.md) |
| U-20260925-78 | 2026-09-25 | Sorting by resolution weighs a camera RAW by its real size | #fix #sort #raw | [2026-09-b](2026-09-b.md) |
| U-20260925-77 | 2026-09-25 | A NEF exports to JPEG again: copies leave the camera maker note out | #fix #export #metadata | [2026-09-b](2026-09-b.md) |
| U-20260925-76 | 2026-09-25 | Object Remove's mask worker reports a failed build instead of jamming the tool | #fix #workers #Imervue_Plugins | [2026-09-b](2026-09-b.md) |
| U-20260925-75 | 2026-09-25 | Panoramas past Pillow's 179 MP limit open, one giant decode at a time | #fix #formats #memory | [2026-09-b](2026-09-b.md) |
| U-20260925-74 | 2026-09-25 | Same-size scans no longer share one Modify recipe | #fix #recipe #data-loss | [2026-09-b](2026-09-b.md) |
| U-20260925-73 | 2026-09-25 | A portrait camera RAW's thumbnail stands upright; a RAW without an embedded preview gets one | #fix #raw #orientation | [2026-09-b](2026-09-b.md) |
| U-20260925-72 | 2026-09-25 | Opening a folder sorts from the listing, without a system call per file | #perf #sort | [2026-09-b](2026-09-b.md) |
| U-20260924-100 | 2026-09-24 | Move the metadata-carrying save helpers into in_place_save | #refactor #metadata | [2026-09](2026-09.md) |
| U-20260924-101 | 2026-09-24 | Keep metadata when Modify and the annotation editor save over a file; never write PNG into a RAW | #fix #metadata #data-loss | [2026-09](2026-09.md) |
| U-20260924-102 | 2026-09-24 | AI Upscale: full-size RAW input, no PNG bytes under a .cr2 name, EXIF kept | #fix #metadata #data-loss | [2026-09](2026-09.md) |
| U-20260924-103 | 2026-09-24 | Export keeps camera, lens and capture date, with a metadata policy | #feature #metadata #export | [2026-09](2026-09.md) |
| U-20260924-104 | 2026-09-24 | CLI and Auto-Orient decode like the viewer: upright, sRGB, HEIC readable | #fix #cli #orientation #colour | [2026-09](2026-09.md) |
| U-20260924-105 | 2026-09-24 | Thumbnail cache: drop the fromarray mode conversion Pillow 13 removes | #fix #compat #pillow | [2026-09](2026-09.md) |
| U-20260924-106 | 2026-09-24 | GPS geotag writes JPEGs without piexif; EXIF rewrites keep the thumbnail | #fix #metadata #gps | [2026-09](2026-09.md) |
| U-20260924-107 | 2026-09-24 | Deep-zoom screen-refit test: isolate the immediate chain from the interval watch | #test #flaky | [2026-09](2026-09.md) |
| U-20260924-108 | 2026-09-24 | Docs: Modify's Apply Crop and annotation Save write back, in all ten doc trees | #docs | [2026-09](2026-09.md) |
| U-20260924-109 | 2026-09-24 | Keep EXIF entry types through Pillow re-serialisation (UNDEFINED, SRATIONAL) | #fix #metadata | [2026-09](2026-09.md) |
| U-20260924-110 | 2026-09-24 | EXIF editor works without piexif: JPEG edited through Pillow, Unicode kept | #fix #metadata #exif #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260924-111 | 2026-09-24 | WebP EXIF rewritten in place without piexif; piexif no longer used | #fix #metadata #webp #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260925-71 | 2026-09-25 | Open with Imervue and the watched folder cover every format the viewer opens | #fix #raw #formats | [2026-09-b](2026-09-b.md) |
| U-20260925-70 | 2026-09-25 | Refactor: the MCP server decodes and probes through shown.open_shown and dimensions.probe_image | #refactor #mcp | [2026-09-b](2026-09-b.md) |
| U-20260925-69 | 2026-09-25 | HDR merge, panorama, focus stack, stack blend, paint drops and the CLI develop camera RAW | #fix #raw | [2026-09-b](2026-09-b.md) |
| U-20260925-68 | 2026-09-25 | Animation frames of 10 ms or less play for 100 ms, as in browsers | #fix #animation | [2026-09-b](2026-09-b.md) |
| U-20260925-67 | 2026-09-25 | Sorting by name puts img2 before img10, like the file tree and Explorer | #fix #sort | [2026-09-b](2026-09-b.md) |
| U-20260925-66 | 2026-09-25 | Canon CR3, Panasonic RW2, Pentax PEF and 14 more RAW formats open | #fix #raw #formats | [2026-09-b](2026-09-b.md) |
| U-20260925-65 | 2026-09-25 | Batch workers report a model or folder that fails before the first image | #fix #workers | [2026-09-b](2026-09-b.md) |
| U-20260925-64 | 2026-09-25 | Every image decode catches a picture over the pixel limit | #fix #robustness | [2026-09-b](2026-09-b.md) |
| U-20260925-63 | 2026-09-25 | Tool workers report every failure instead of leaving their dialog stuck | #fix #workers | [2026-09-b](2026-09-b.md) |
| U-20260925-62 | 2026-09-25 | AVIF opens and saves without pillow-heif; the install hint is for HEIC only | #fix #formats #avif | [2026-09-b](2026-09-b.md) |
| U-20260925-61 | 2026-09-25 | Auto-cull scores a camera RAW by its preview, and a huge file no longer ends the batch | #fix #cull #raw | [2026-09](2026-09.md) |
| U-20260925-60 | 2026-09-25 | Paint's Reference dock shows a photo upright and colour-managed | #fix #paint #color | [2026-09](2026-09.md) |
| U-20260925-59 | 2026-09-25 | Combine to PDF / TIFF lays pages upright in sRGB and replaces a file in one step | #fix #data-loss #color | [2026-09](2026-09.md) |
| U-20260925-58 | 2026-09-25 | A failed Export says why instead of doing nothing | #fix #export | [2026-09](2026-09.md) |
| U-20260925-57 | 2026-09-25 | A GIF made without Loop forever plays once, not twice | #fix #animation | [2026-09](2026-09.md) |
| U-20260925-56 | 2026-09-25 | Create GIF / Video suggests a free name and asks before replacing a file | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260925-55 | 2026-09-25 | The replace-existing-file question moves to dialog_rows (refactor) | #refactor #export | [2026-09](2026-09.md) |
| U-20260925-54 | 2026-09-25 | Auto-rotate, EXIF Strip copies and Split Pages number their files instead of replacing | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260925-53 | 2026-09-25 | Export never replaces a file, the photo itself above all, without asking | #fix #export #data-loss | [2026-09](2026-09.md) |
| U-20260925-52 | 2026-09-25 | Picking a free file name moves to system/free_names (refactor) | #refactor #files | [2026-09](2026-09.md) |
| U-20260925-51 | 2026-09-25 | Paint export presets and annotation projects save in one step | #bugfix #paint #annotation #data-loss | [2026-09](2026-09.md) |
| U-20260925-50 | 2026-09-25 | Safety Review overwriting originals replaces each in one step | #bugfix #plugin #safety_review #Imervue_Plugins #data-loss | [2026-09](2026-09.md) |
| U-20260925-49 | 2026-09-25 | Exporting over an existing file replaces it in one step | #bugfix #export #data-loss | [2026-09](2026-09.md) |
| U-20260925-48 | 2026-09-25 | The file tree offers to delete for good what the Recycle Bin refused | #bugfix #delete #file-tree | [2026-09](2026-09.md) |
| U-20260925-47 | 2026-09-25 | Duplicate Finder offers to delete for good what the Recycle Bin refused | #bugfix #delete #duplicates | [2026-09](2026-09.md) |
| U-20260925-46 | 2026-09-25 | Confirmed permanent deletes remove folders and files the Recycle Bin can't take | #bugfix #delete | [2026-09](2026-09.md) |
| U-20260925-45 | 2026-09-25 | Deleting on a drive without a Recycle Bin never destroys the file unasked | #bugfix #delete #data-loss | [2026-09](2026-09.md) |
| U-20260925-44 | 2026-09-25 | Refactor: clear the SonarCloud findings still open on dev | #refactor #sonarcloud | [2026-09](2026-09.md) |
| U-20260925-43 | 2026-09-25 | A very large animation decodes frame by frame instead of all at once | #bugfix #animation #memory | [2026-09](2026-09.md) |
| U-20260925-42 | 2026-09-25 | The .cube reader accepts DaVinci Resolve's INPUT_RANGE and a leading BOM | #bugfix #lut #interop | [2026-09](2026-09.md) |
| U-20260925-41 | 2026-09-25 | JSON files saved with a BOM or invalid UTF-8 no longer fail to load | #bugfix #robustness #encoding | [2026-09](2026-09.md) |
| U-20260925-40 | 2026-09-25 | The recipe store never loses edits to a file it could not read | #bugfix #recipe #data-loss | [2026-09](2026-09.md) |
| U-20260925-39 | 2026-09-25 | Refactor: the unreadable-settings guard becomes a shared UnreadableFileGuard | #refactor #settings | [2026-09](2026-09.md) |
| U-20260925-38 | 2026-09-25 | A start-up warning says the settings file could not be read | #feature #settings #ui | [2026-09](2026-09.md) |
| U-20260925-37 | 2026-09-25 | An unreadable settings file is kept before it is saved over | #bugfix #settings #data-loss | [2026-09](2026-09.md) |
| U-20260925-36 | 2026-09-25 | Face Detection works when OpenCV is installed under a non-ASCII path | #bugfix #face-detection #windows | [2026-09](2026-09.md) |
| U-20260925-35 | 2026-09-25 | Safety Review reads photos in folders with non-ASCII names | #bugfix #plugin #safety_review #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260925-34 | 2026-09-25 | Batch renames that reuse names within the selection land as a whole | #bugfix #rename #file-ops | [2026-09](2026-09.md) |
| U-20260925-33 | 2026-09-25 | EXIF Strip overwrites in one step and keeps the photo's recipe | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260925-32 | 2026-09-25 | Modify recipes follow a photo through lossless rotations and EXIF rewrites | #fix #data-loss #recipe | [2026-09](2026-09.md) |
| U-20260925-31 | 2026-09-25 | Tests never write the real recipe store | #test | [2026-09](2026-09.md) |
| U-20260925-30 | 2026-09-25 | Refactor: get_exif_data moves to the Qt-free exif_merge; the MCP server stays Qt-free | #refactor #mcp | [2026-09](2026-09.md) |
| U-20260925-29 | 2026-09-25 | MCP tools open HEIC and develop camera RAW like the viewer | #fix #mcp | [2026-09](2026-09.md) |
| U-20260925-28 | 2026-09-25 | Refactor: RAW development moves to the Qt-free raw_loader.develop_raw | #refactor | [2026-09](2026-09.md) |
| U-20260925-27 | 2026-09-25 | XMP / annotation sidecars, material library, sessions and pet scripts are written in one step | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260925-26 | 2026-09-25 | Refactor: replace_atomically moves to system/atomic_write | #refactor | [2026-09](2026-09.md) |
| U-20260925-25 | 2026-09-25 | PSD, puppet and paint saves replace the file in one step: a failed save keeps the old one | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260925-24 | 2026-09-25 | Image plugins number their result too, and still load on older installs | #fix #data-loss #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260925-23 | 2026-09-25 | One-shot tools number their result instead of saving over the last one | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260925-22 | 2026-09-25 | Lightroom / darktable keyword hierarchies become library tag paths | #fix #xmp #interop | [2026-09](2026-09.md) |
| U-20260925-21 | 2026-09-25 | XMP: read the rating and keywords a JPEG carries itself (Lightroom, Windows Explorer) | #fix #xmp #interop | [2026-09](2026-09.md) |
| U-20260925-20 | 2026-09-25 | XMP: Lightroom / Bridge / darktable rejects map to the culling Reject both ways | #fix #xmp #interop | [2026-09](2026-09.md) |
| U-20260925-19 | 2026-09-25 | Test: every formatted translation gets the placeholders its text uses | #test #i18n | [2026-09](2026-09.md) |
| U-20260925-18 | 2026-09-25 | Batch Convert hands a replaced original's ratings to its conversion; tree Duplicate copies sidecars | #fix #convert | [2026-09](2026-09.md) |
| U-20260925-17 | 2026-09-25 | Deleted photos take their .xmp and annotation sidecars along | #fix #delete #xmp | [2026-09](2026-09.md) |
| U-20260925-16 | 2026-09-25 | Deleted photos go to the Recycle Bin at shutdown instead of being unlinked | #fix #data-loss #delete | [2026-09](2026-09.md) |
| U-20260925-15 | 2026-09-25 | Photos renamed outside Imervue keep their ratings, tags and library notes | #fix #rename | [2026-09](2026-09.md) |
| U-20260925-14 | 2026-09-25 | Japanese and Korean manuals: three bold spans rendered as literal asterisks | #docs | [2026-09](2026-09.md) |
| U-20260925-13 | 2026-09-25 | Token Batch Rename no longer crashes after renaming; failed renames keep their path | #fix #rename #i18n | [2026-09](2026-09.md) |
| U-20260925-12 | 2026-09-25 | Renamed and moved photos keep their ratings, tags, library notes and sidecars | #fix #data-loss #rename | [2026-09](2026-09.md) |
| U-20260925-11 | 2026-09-25 | XMP sidecars: darktable / digiKam photo.jpg.xmp and Lightroom / Bridge colour labels | #fix #xmp #interop | [2026-09](2026-09.md) |
| U-20260925-10 | 2026-09-25 | Batch Rename and Move / Copy report their results in the UI language | #fix #i18n | [2026-09](2026-09.md) |
| U-20260925-09 | 2026-09-25 | Case-only renames work on Windows: tree, Batch Rename and Token Rename | #fix #rename | [2026-09](2026-09.md) |
| U-20260925-08 | 2026-09-25 | Paint drops, GIF/video maker and annotation editor decode like the viewer | #fix #orientation #colour | [2026-09](2026-09.md) |
| U-20260925-07 | 2026-09-25 | Perceptual hashes see a tagged photo upright: duplicates across orientation are found | #fix #duplicates #orientation | [2026-09](2026-09.md) |
| U-20260925-06 | 2026-09-25 | Deflicker writes JPEG time-lapses (it failed every frame); RAW developed, EXIF kept | #fix #timelapse | [2026-09](2026-09.md) |
| U-20260925-05 | 2026-09-25 | Gallery, contact sheet, print layout, compare, side panels and Ctrl+C decode like the viewer | #fix #orientation #colour | [2026-09](2026-09.md) |
| U-20260925-04 | 2026-09-25 | Move / Copy never overwrites: numbered names, case-aware, re-checked before writing | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260925-03 | 2026-09-25 | XMP sidecar save merges instead of replacing: another editor's RAW settings survive | #fix #data-loss #xmp | [2026-09](2026-09.md) |
| U-20260925-02 | 2026-09-25 | Batch Convert: trash (not delete) only fully converted originals; full-size RAW; keep EXIF | #fix #data-loss #metadata | [2026-09](2026-09.md) |
| U-20260925-01 | 2026-09-25 | Unreadable camera RAW raises OSError, not libraw's own error | #fix #raw | [2026-09](2026-09.md) |
| U-20260924-99 | 2026-09-24 | Lossless Rotate and Rotate All keep JPEG bytes and file metadata | #fix #metadata #rotate | [2026-09](2026-09.md) |
| U-20260924-98 | 2026-09-24 | Keep AI Upscale overwrite and EXIF Strip from truncating animated or multi-page files | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260924-97 | 2026-09-24 | Stop in-place rotate, crop and annotation saves from destroying RAW and multi-frame files | #fix #data-loss | [2026-09](2026-09.md) |
| U-20260924-96 | 2026-09-24 | Export and feed tools the full-size developed RAW | #fix #raw | [2026-09](2026-09.md) |
| U-20260924-95 | 2026-09-24 | Decode Modify and Paint sources like the viewer: full-size RAW, sRGB, upright | #fix #raw | [2026-09](2026-09.md) |
| U-20260924-94 | 2026-09-24 | Colour-manage every preview, tool input and export like the viewer | #fix #color | [2026-09](2026-09.md) |
| U-20260924-93 | 2026-09-24 | Show embedded colour profiles in their real colours in the viewer and thumbnails | #feature #color | [2026-09](2026-09.md) |
| U-20260924-92 | 2026-09-24 | Write GPSVersionID and reject out-of-range coordinates in the geotag writer | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-91 | 2026-09-24 | Turn tagged photos upright in the background remover, object splitter, icon and resize plugins | #fix #exif #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260924-90 | 2026-09-24 | Censor the region Safety Review detected: NudeNet box format and EXIF orientation | #fix #security #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260924-89 | 2026-09-24 | Read tagged photos upright for OCR, CLIP search and the multi-image merges | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-88 | 2026-09-24 | Compute smart crops on the recipe's base and show the last previews upright | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-87 | 2026-09-24 | Translate the plugins' hard-coded error toasts | #i18n #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260924-86 | 2026-09-24 | Run the MCP image tools on the EXIF-upright image | #fix #exif #mcp | [2026-09](2026-09.md) |
| U-20260924-85 | 2026-09-24 | Translate twelve hard-coded toasts and four f-string file filters | #i18n | [2026-09](2026-09.md) |
| U-20260924-84 | 2026-09-24 | Tie every deferred bound-method call to its owner | #fix #qt | [2026-09](2026-09.md) |
| U-20260924-83 | 2026-09-24 | Keep batch-rotated, upscaled and retouched copies upright | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-82 | 2026-09-24 | Keep converted, exported, stripped and sanitised copies upright | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-81 | 2026-09-24 | Load the hand-loading tool dialogs and image layers upright | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-80 | 2026-09-24 | Load tool inputs and the rotate fallback from the EXIF-upright image | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-79 | 2026-09-24 | Check plugin-to-plugin imports resolve too | #test | [2026-09](2026-09.md) |
| U-20260924-78 | 2026-09-24 | Show EXIF-tagged photos upright across the viewer and Modify | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-77 | 2026-09-24 | Drop deferred calls whose widget was destroyed | #fix #qt | [2026-09](2026-09.md) |
| U-20260924-76 | 2026-09-24 | Fix the viewer reload ImportError and check every internal import resolves | #fix #regression #test | [2026-09](2026-09.md) |
| U-20260924-75 | 2026-09-24 | Let Image Organizer sort HEIC, JPEG XL and RAW photos | #feature #formats | [2026-09](2026-09.md) |
| U-20260924-74 | 2026-09-24 | Read RAW pixel dimensions through libraw instead of the embedded preview | #fix #raw | [2026-09](2026-09.md) |
| U-20260924-73 | 2026-09-24 | Export the camera EXIF columns from the Exif sub-IFD | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-72 | 2026-09-24 | Show EXIF and GPS for HEIC and JPEG XL photos | #fix #exif #formats | [2026-09](2026-09.md) |
| U-20260924-71 | 2026-09-24 | Read the capture date from the Exif sub-IFD in Organizer, Timeline and Sanitize | #fix #exif | [2026-09](2026-09.md) |
| U-20260924-70 | 2026-09-24 | Show, drop and index HEIC, JPEG XL and video wherever the viewer opens them | #fix #formats | [2026-09](2026-09.md) |
| U-20260924-69 | 2026-09-24 | Count, not time, the pump_until immediate-return test | #test #flaky | [2026-09](2026-09.md) |
| U-20260924-68 | 2026-09-24 | Offer every viewer format in Open and Relocate, and translate file-dialog filter labels | #i18n #fix | [2026-09](2026-09.md) |
| U-20260924-67 | 2026-09-24 | Label the full-resolution thumbnail entry instead of showing None | #i18n #fix | [2026-09](2026-09.md) |
| U-20260924-66 | 2026-09-24 | Translate the slider range, VRAM tooltip, pet sizes and idle toasts | #i18n #fix | [2026-09](2026-09.md) |
| U-20260924-65 | 2026-09-24 | Qt's own dialog and widget strings follow the UI language | #i18n #feature | [2026-09](2026-09.md) |
| U-20260924-64 | 2026-09-24 | Translate 100 UI keys that hid behind helper calls and table rows | #i18n #fix | [2026-09](2026-09.md) |
| U-20260924-63 | 2026-09-24 | Paint shortcut dialog flags keys other actions already hold | #feature #paint #shortcuts | [2026-09](2026-09.md) |
| U-20260924-62 | 2026-09-24 | Paint shortcut remaps apply to every registry entry, live | #fix #paint #shortcuts | [2026-09](2026-09.md) |
| U-20260924-61 | 2026-09-24 | Paint tab keys have one owner each; 22 dead keys work again | #fix #paint #shortcuts | [2026-09](2026-09.md) |
| U-20260924-60 | 2026-09-24 | Name new paint tabs in the UI language | #i18n #paint | [2026-09](2026-09.md) |
| U-20260924-59 | 2026-09-24 | Translate runtime-built UI keys and the built-in material names | #i18n #paint | [2026-09](2026-09.md) |
| U-20260924-58 | 2026-09-24 | Plugins define the shared AI-menu keys they borrowed | #i18n #plugins #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260924-57 | 2026-09-24 | Translate the last hard-coded English dialog strings | #i18n #gui | [2026-09](2026-09.md) |
| U-20260924-56 | 2026-09-24 | Translate 334 UI strings that every language showed in English | #i18n #gui | [2026-09](2026-09.md) |
| U-20260924-55 | 2026-09-24 | Load rawpy and imageio only when a RAW file is decoded | #perf #startup | [2026-09](2026-09.md) |
| U-20260924-54 | 2026-09-24 | Pin Leaflet with Subresource Integrity; fit single places at city zoom | #fix #security #gui | [2026-09](2026-09.md) |
| U-20260924-53 | 2026-09-24 | Show EXIF values and file names as text in the sidebar | #fix #security #gui | [2026-09](2026-09.md) |
| U-20260924-52 | 2026-09-24 | Keep the desktop pet's credentials out of the support bundle | #fix #security #privacy | [2026-09](2026-09.md) |
| U-20260924-51 | 2026-09-24 | Move the plugin interpreter to CPython 3.12.10 | #deps #security #plugin | [2026-09](2026-09.md) |
| U-20260924-50 | 2026-09-24 | Verify the embeddable Python and install pip from a pinned wheel | #fix #security #supply-chain #plugin | [2026-09](2026-09.md) |
| U-20260924-49 | 2026-09-24 | Pin the upscale models to commits and verify the face-landmark model | #fix #security #supply-chain | [2026-09](2026-09.md) |
| U-20260924-48 | 2026-09-24 | Make the Cubism signature test pass on Python 3.10 | #tests #ci #puppet | [2026-09](2026-09.md) |
| U-20260924-47 | 2026-09-24 | Send Dependabot updates to dev and keep the action pins current | #ci #deps | [2026-09](2026-09.md) |
| U-20260924-46 | 2026-09-24 | Move CI to Node 24 actions pinned by commit | #ci #security #deps | [2026-09](2026-09.md) |
| U-20260924-45 | 2026-09-24 | Require Pillow 12.3.0 or later | #fix #security #deps | [2026-09](2026-09.md) |
| U-20260924-44 | 2026-09-24 | Refuse web-page requests to the desktop pet's webhook | #fix #security #desktop_pet | [2026-09](2026-09.md) |
| U-20260924-43 | 2026-09-24 | Keep web pages out of the puppet's VTube Studio API | #fix #security #puppet | [2026-09](2026-09.md) |
| U-20260924-42 | 2026-09-24 | Refuse puppet archives that expand past 2 GiB | #fix #security #puppet | [2026-09](2026-09.md) |
| U-20260924-41 | 2026-09-24 | Refuse plugin and file names that could leave the plugins folder | #fix #security #plugin | [2026-09](2026-09.md) |
| U-20260924-40 | 2026-09-24 | Guard against unpickling in NumPy and PyTorch loads | #security #tests | [2026-09](2026-09.md) |
| U-20260924-39 | 2026-09-24 | Stop unpickling the semantic-search cache | #fix #security #library | [2026-09](2026-09.md) |
| U-20260924-38 | 2026-09-24 | Extend the size guards to the bundled plugins | #done #refactor #plugins #tests | [2026-09](2026-09.md) |
| U-20260924-37 | 2026-09-24 | Plugins import shared helpers instead of copying them; faster object labelling | #refactor #perf #plugins #Imervue_Plugins | [2026-09](2026-09.md) |
| U-20260924-36 | 2026-09-24 | Share one censor implementation between the app and the frozen-build runner | #done #fix #refactor #safety_review #plugins | [2026-09](2026-09.md) |
| U-20260924-35 | 2026-09-24 | Bring the bundled plugins under the ruff and bandit gates | #done #lint #ci #plugins | [2026-09](2026-09.md) |
| U-20260924-34 | 2026-09-24 | Forbid silent broad handlers and finish #26 | #done #error-handling #plugins #tests | [2026-09](2026-09.md) |
| U-20260924-33 | 2026-09-24 | Narrow the last main-program silent handlers and guard the batch-file worker (#26) | #refactor #error-handling #paint #mcp #trash | [2026-09](2026-09.md) |
| U-20260924-32 | 2026-09-24 | Stop an old Tesseract from quitting the app through the OCR probe | #fix #ocr #error-handling | [2026-09](2026-09.md) |
| U-20260924-31 | 2026-09-24 | Narrow the puppet/ frame handlers and log desktop_pet/ payload failures (#26) | #refactor #error-handling #puppet #desktop_pet | [2026-09](2026-09.md) |
| U-20260924-30 | 2026-09-24 | Narrow the gpu_image_view/ silent broad handlers (#26) | #refactor #error-handling #gpu_image_view | [2026-09](2026-09.md) |
| U-20260924-29 | 2026-09-24 | Log note-save failures and narrow the gui/ silent broad handlers (#26) | #refactor #error-handling #gui | [2026-09](2026-09.md) |
| U-20260924-28 | 2026-09-24 | Narrow or log the library/ silent broad handlers (#26) | #refactor #error-handling #library | [2026-09](2026-09.md) |
| U-20260924-27 | 2026-09-24 | Treat a corrupt WebP EXIF block as unreadable instead of crashing | #fix #image #exif | [2026-09](2026-09.md) |
| U-20260924-26 | 2026-09-24 | Forbid silent suppress(Exception) and finish #25 | #done #error-handling #plugins #tests | [2026-09](2026-09.md) |
| U-20260924-25 | 2026-09-24 | Stop the wallpaper action injecting file names into AppleScript | #fix #security #menu | [2026-09](2026-09.md) |
| U-20260924-24 | 2026-09-24 | Narrow or log the plugin/ and entry-point suppressed failures (#25) | #refactor #error-handling #plugin | [2026-09](2026-09.md) |
| U-20260924-23 | 2026-09-24 | Narrow or log the puppet/ suppressed failures (#25) | #refactor #error-handling #puppet | [2026-09](2026-09.md) |
| U-20260924-22 | 2026-09-24 | Narrow or log the paint/ suppressed failures (#25) | #refactor #error-handling #paint | [2026-09](2026-09.md) |
| U-20260924-21 | 2026-09-24 | Narrow or log the image/ suppressed failures (#25) | #refactor #error-handling #image | [2026-09](2026-09.md) |
| U-20260924-20 | 2026-09-24 | Log desktop-pet shutdown failures instead of suppressing them (#25) | #refactor #error-handling #desktop_pet | [2026-09](2026-09.md) |
| U-20260924-19 | 2026-09-24 | Stop gpu_image_view/ swallowing failures silently (#25) | #refactor #error-handling #gpu_image_view | [2026-09](2026-09.md) |
| U-20260924-18 | 2026-09-24 | One shared reveal-in-file-manager for the file tree and both menus | #refactor #system | [2026-09](2026-09.md) |
| U-20260924-17 | 2026-09-24 | macOS: open the containing folder without an empty argument | #bug #gui #macos | [2026-09](2026-09.md) |
| U-20260924-16 | 2026-09-24 | Stop gui/ swallowing failures silently (#25) | #refactor #error-handling #gui | [2026-09](2026-09.md) |
| U-20260924-15 | 2026-09-24 | Log best-effort failures instead of suppressing them; main window first | #refactor #error-handling #system | [2026-09](2026-09.md) |
| U-20260924-14 | 2026-09-24 | Cap positional parameters at 7 with a guard; keyword-only options are the reasoned exception (closes #24) | #done #tooling #quality | [2026-09](2026-09.md) |
| U-20260924-13 | 2026-09-24 | Collect ToolDispatcher's optional collaborators into DispatcherHooks (#24) | #refactor #paint | [2026-09](2026-09.md) |
| U-20260924-12 | 2026-09-24 | Give the library index search an ImageQuery (#24) | #refactor #library | [2026-09](2026-09.md) |
| U-20260924-11 | 2026-09-24 | Pass polar coordinate mappings their grid, centre and size as pairs (#24) | #refactor #image | [2026-09](2026-09.md) |
| U-20260924-10 | 2026-09-24 | Group coordinate pairs and colours in gpu_image_view's wide signatures (#24) | #refactor #gpu_image_view | [2026-09](2026-09.md) |
| U-20260924-09 | 2026-09-24 | Fold make_slider_spin's size keywords into a compact flag (#24) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260924-08 | 2026-09-24 | Give the batch export worker an ExportSettings object (#24) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260924-07 | 2026-09-24 | Group the image sanitizer's options into UpscaleSpec and SanitizeSettings (#24) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260924-06 | 2026-09-24 | Tighten the complexity ceiling to the workspace's 15; file the parameter-count gap | #tooling #quality | [2026-09](2026-09.md) |
| U-20260924-05 | 2026-09-24 | Webhook 404/401 replies no longer lost to a connection reset (the "flaky" e2e test) | #bug #desktop_pet #tests | [2026-09](2026-09.md) |
| U-20260924-04 | 2026-09-24 | Guard the function- and module-length limits with a test | #tooling #quality | [2026-09](2026-09.md) |
| U-20260924-03 | 2026-09-24 | Split PuppetWorkspace's constructor; no function is over 80 lines any more (closes #19) | #done #refactor #puppet | [2026-09](2026-09.md) |
| U-20260924-02 | 2026-09-24 | Split PuppetCanvas.render_offscreen_puppet into fit, frame and FBO steps (#19) | #refactor #puppet | [2026-09](2026-09.md) |
| U-20260924-01 | 2026-09-24 | Split GPUDabSession.stamp and pin its GL call sequence (#19) | #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-89 | 2026-09-23 | Share one dab-clipping rule across every dab-based paint tool (#19) | #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-88 | 2026-09-23 | Split flood_fill's painting step into _paint_mask (#19) | #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-87 | 2026-09-23 | Split make_brush_cursor into ring, crosshair and slash painters (#19) | #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-86 | 2026-09-23 | Declare the Cubism Core ctypes signatures as a table (#19) | #refactor #puppet | [2026-09](2026-09.md) |
| U-20260923-85 | 2026-09-23 | Move the annotation editor's file actions into a mixin; closes #23 | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-84 | 2026-09-23 | Move the tile badges out of overlay_painter and test them (#23) | #refactor #gpu_image_view | [2026-09](2026-09.md) |
| U-20260923-83 | 2026-09-23 | Close the breadcrumb test's top-level bar | #tests | [2026-09](2026-09.md) |
| U-20260923-82 | 2026-09-23 | A hidden desktop pet no longer pops a speech bubble | #bugfix #desktop_pet | [2026-09](2026-09.md) |
| U-20260923-81 | 2026-09-23 | Move the main window's widget builders into MainWindowLayoutMixin (#23) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-80 | 2026-09-23 | Move PetWindow's window-flag, opacity and fullscreen-hide code into a mixin (#23) | #refactor #desktop_pet | [2026-09](2026-09.md) |
| U-20260923-79 | 2026-09-23 | Restore the app stylesheet between tests too | #tests #flaky | [2026-09](2026-09.md) |
| U-20260923-78 | 2026-09-23 | Stop test_ui_scale's app font leaking into later test files | #tests #flaky | [2026-09](2026-09.md) |
| U-20260923-77 | 2026-09-23 | Move the plugin installer's Python finder into python_finder (#23) | #refactor #plugin | [2026-09](2026-09.md) |
| U-20260923-76 | 2026-09-23 | Move GPUImageView's state initialisers out of the widget (#23) | #refactor #gpu_image_view | [2026-09](2026-09.md) |
| U-20260923-75 | 2026-09-23 | Resync every line count in the architecture map; flag six near-limit modules | #docs #architecture | [2026-09](2026-09.md) |
| U-20260923-74 | 2026-09-23 | Split the main window's closeEvent (#19) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-73 | 2026-09-23 | Split DuplicateDetectionDialog._build_ui (#19) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-72 | 2026-09-23 | Build the CLI parser from a subcommand table (#19) | #refactor #cli | [2026-09](2026-09.md) |
| U-20260923-71 | 2026-09-23 | Split ContactSheetDialog's constructor (#19) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-70 | 2026-09-23 | Guard against modules no production code imports; 58 found | #tooling #architecture | [2026-09](2026-09.md) |
| U-20260923-69 | 2026-09-23 | Combine-to-PDF/TIFF pages and staging-tray adds follow the view order | #bug #menu | [2026-09](2026-09.md) |
| U-20260923-68 | 2026-09-23 | Multi-selection exports and renames follow the view order | #bug #gpu_image_view #gui | [2026-09](2026-09.md) |
| U-20260923-67 | 2026-09-23 | Split SlideshowMp4Dialog's constructor (#19) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-66 | 2026-09-23 | Split the main window's Filter menu builder (#19) | #refactor #menu | [2026-09](2026-09.md) |
| U-20260923-65 | 2026-09-23 | Split SmartAlbumsDialog's constructor (#19) | #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-64 | 2026-09-23 | Pasted and fallback-trashed files no longer overwrite each other | #bug #gpu_image_view #data-loss | [2026-09](2026-09.md) |
| U-20260923-63 | 2026-09-23 | Enable ruff's blind-except rules (closes #21) | #done #tooling #error-handling | [2026-09](2026-09.md) |
| U-20260923-62 | 2026-09-23 | Narrow the blind excepts in gpu_image_view/ (BLE001 batch 6) | #refactor #error-handling #gpu_image_view | [2026-09](2026-09.md) |
| U-20260923-61 | 2026-09-23 | Narrow the blind excepts in gui/ (BLE001 batch 5) | #refactor #error-handling #gui | [2026-09](2026-09.md) |
| U-20260923-60 | 2026-09-23 | EXIF editor: saving works again and User Comment round-trips | #bug #metadata #gui | [2026-09](2026-09.md) |
| U-20260923-59 | 2026-09-23 | Narrow the blind excepts in menu/; share IMAGE_READ_ERRORS (BLE001 batch 4) | #refactor #error-handling #menu #image | [2026-09](2026-09.md) |
| U-20260923-58 | 2026-09-23 | PDF exports report an unwritable target instead of claiming success | #bug #export | [2026-09](2026-09.md) |
| U-20260923-57 | 2026-09-23 | Narrow read_json's blind except (BLE001 batch 3) | #refactor #error-handling #user_settings | [2026-09](2026-09.md) |
| U-20260923-56 | 2026-09-23 | Split expected from unexpected failures in plugin/ (BLE001 batch 2) | #refactor #error-handling #plugin | [2026-09](2026-09.md) |
| U-20260923-55 | 2026-09-23 | Narrow the blind excepts in image/ (BLE001 batch 1) | #refactor #error-handling #image | [2026-09](2026-09.md) |
| U-20260923-54 | 2026-09-23 | Stop the plugin installer's Python probe from rejecting slow interpreters silently | #done #bug #plugin | [2026-09](2026-09.md) |
| U-20260923-53 | 2026-09-23 | Split the pet workspace's Window group builder | #done #refactor #desktop_pet | [2026-09](2026-09.md) |
| U-20260923-52 | 2026-09-23 | Split GifVideoDialog._build_ui into section builders | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-51 | 2026-09-23 | Split FillDock's constructor; share tooltip controls with BrushDock | #done #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-50 | 2026-09-23 | Split PuppetCanvas.__init__ into format, translucency and state groups | #done #refactor #puppet | [2026-09](2026-09.md) |
| U-20260923-49 | 2026-09-23 | Split ExifSidebar's constructor into section builders | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-48 | 2026-09-23 | Split CompareDialog's constructor by panel and tab | #done #refactor #gpu_image_view | [2026-09](2026-09.md) |
| U-20260923-47 | 2026-09-23 | Share the manga config dialogs' controls | #done #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-46 | 2026-09-23 | Split the annotation editor's constructor and menu bar | #done #refactor #gui #annotation | [2026-09](2026-09.md) |
| U-20260923-45 | 2026-09-23 | Build the last four path rows from dialog_rows; #20 closed | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-44 | 2026-09-23 | Build the four stacking dialogs' output rows from dialog_rows | #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-43 | 2026-09-23 | Build nine tool dialogs' output rows and pickers from dialog_rows | #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-42 | 2026-09-23 | Build the upscale dialog's output and button rows from dialog_rows | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-41 | 2026-09-23 | Split BatchExportDialog._build_ui onto the shared dialog rows | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-40 | 2026-09-23 | Fix the culling-dialog test race: a worker ran twice | #done #tests #flaky | [2026-09](2026-09.md) |
| U-20260923-39 | 2026-09-23 | Split BatchConvertDialog._build_ui; folder_row becomes dialog_rows | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-38 | 2026-09-23 | Split PaintCanvas.__init__ into three state initialisers | #done #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-37 | 2026-09-23 | Keep tests off the OS Recycle Bin with an autouse os_trash fixture | #done #tests #flaky | [2026-09](2026-09.md) |
| U-20260923-36 | 2026-09-23 | Split AIUpscaleDialog._build_ui and share the upscale-model combo fill | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-35 | 2026-09-23 | Build three more dialogs' source-folder rows through folder_picker_row | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-34 | 2026-09-23 | Split ImageOrganizerDialog._build_ui and share the folder-picker row | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-33 | 2026-09-23 | Split the annotation dialog's right panel into section builders | #done #refactor #gui #annotation | [2026-09](2026-09.md) |
| U-20260923-32 | 2026-09-23 | Split LayerDock's constructor and share the blend-mode combo | #done #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-31 | 2026-09-23 | Split BrushDock's constructor into section builders | #done #refactor #paint | [2026-09](2026-09.md) |
| U-20260923-30 | 2026-09-23 | Split the puppet workspace's action builder by menu section | #done #refactor #puppet | [2026-09](2026-09.md) |
| U-20260923-29 | 2026-09-23 | Split ImageSanitizeDialog._build_ui into section builders | #done #refactor #gui | [2026-09](2026-09.md) |
| U-20260923-28 | 2026-09-23 | Split build_file_menu into section builders | #done #refactor #menu | [2026-09](2026-09.md) |
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
| [2026-09-b.md](2026-09-b.md) | 2026-09 | 27 |
