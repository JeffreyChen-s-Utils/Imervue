# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#22** 7 modules (all with tests) are still imported by nothing in `Imervue/`, `plugins/` or the build specs, so no user can reach them; the owner chose to wire every one (the 27 judged duplicate or obsolete are deleted): `export.contact_sheet_layouts`, `image.caption`, `library.capture_time` / `gpx_geotag`, `multi_language.translation_validation`, `user_settings.metadata_template` / `tag_validator`. The list is `_KNOWN_UNWIRED` in `tests/test_unwired_modules.py`. Next: wire `export/contact_sheet_layouts.py`, then the rest one per commit, each with tests and docs in every language.
- **#49** [UNVERIFIED] Clipping a brush to the manga panel under it never runs: `DispatcherHooks.panel_layout_provider` (`Imervue/paint/tool_dispatcher.py:149`) is never passed by `paint_workspace.py`, so `_panel_layout_provider()` always returns `None`. Next: confirm with a comic project, then pass the project's panel layout.
- **#52** [BLOCKED] `user_guide.md` (around line 649, the Puppet quick start) still opens **File > Examples > March 7th**, a 307-drawable rig that is no longer bundled; another session has the file checked out with uncommitted edits. Next: once it commits, say **File > Examples > Imeru**, the bundled mascot.
