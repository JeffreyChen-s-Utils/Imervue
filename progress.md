# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- Complete runtime complexity repair remains. Fresh 50186aa8 analysis covers 992 runtime Python files: 563 verified, five data-only and 424 above 20, with no missing/stale scores. All ten recipe modules meet the threshold, but canvas_frame.py remains at 22. GitHub CI and the Codacy PR check passed; Sonar failed on a NaN test assertion and also lists fifteen Qt naming findings. Whole-branch Codacy lists three moved MD5 findings plus three external-editor execution audits.
  Next: capture fresh hosted analysis for the workspace/CLI/canvas_frame commit and confirm canvas_frame.py is within 20; then continue the next-ranked modules (image-index is in progress in its own worktree; canvas_render.py remains at 68). The environment Codacy repository token still returns HTTP 401 with the documented header.

- File-tree follow-up: image_issue_panel.py:95 still calls the absent _FileTreeView._open_in_explorer helper.
  Next: migrate the caller to the shared reveal API with a behavior test and synchronized user documentation. A direct call with one selected path reproduces AttributeError before any OS launch.


- Interpreter verification can block inside Windows process creation for an invalid executable, before its subprocess timeout applies.
  Next: investigate a bounded, background-safe production probe with preserved interpreter-discovery behavior. The test-only ENOEXEC injection verifies error handling but does not fix or prove this runtime case; no OS dialog cause has been established.
