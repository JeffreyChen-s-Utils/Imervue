# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#10** [DECIDE] `examples/*.puppet` (≈37 MB) is tracked; `march_7th.puppet` is a third-party character and `release.yml` packs `examples/` into the EXE — copyright and redistribution risk.
- **#12** [DECIDE] `.idea/deployment.xml` is no longer tracked, but this is a public repository and every commit from `6ecc332` (2026-02-13) up to U-20260922-03 still contains it, SFTP user@IP:port included. Either rewrite history (force push to `main` and `dev`) or treat the address as public and harden or move that server (workspace S-10).
- **#19** 27 functions in `Imervue/` are longer than the workspace's 80-line limit, mostly Qt `__init__` / `_build_ui` builders; the largest are `gui/annotation_dialog.py:__init__` (118), `paint/manga_menu.py:__init__` (112 and 108, two classes), `gpu_image_view/actions/compare_dialog.py:__init__` (110) and `gui/exif_sidebar.py:__init__` (106). Next step: split each into section builders in the original order (a builder returns the widget and the caller adds it to its layout), one module per commit.
- **#20** 16 dialogs in `Imervue/gui/` still hand-build the label + path edit + Browse row that `gui/dialog_rows.py` provides (`folder_picker_row` / `path_browse_row`): `auto_straighten`, `clone_stamp`, `crop_straighten`, `healing_brush`, `lens_correction`, `noise_sharpen`, `print_layout`, `sky_replace`, `soft_proof` (labelled output or profile rows); `focus_stack`, `hdr_merge`, `panorama`, `stack_blend` (edit + button placed later in the layout); `export_dialog`, `gif_video_dialog` (unlabelled rows); `lut_dialog` (extra Clear button). Next step: a parametrised test pinning each row (label, edit, Browse text, the slot Browse calls) against the current code, then convert one group per commit.
