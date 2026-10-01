# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#49** [UNVERIFIED] Clipping a brush to the manga panel under it never runs: `DispatcherHooks.panel_layout_provider` (`Imervue/paint/tool_dispatcher.py:149`) is never passed by `paint_workspace.py`, so `_panel_layout_provider()` always returns `None`. Next: confirm with a comic project, then pass the project's panel layout.
- **#52** [BLOCKED] `user_guide.md` (around line 649, the Puppet quick start) still opens **File > Examples > March 7th**, a 307-drawable rig that is no longer bundled; another session has the file checked out with uncommitted edits. Next: once it commits, say **File > Examples > Imeru**, the bundled mascot.
