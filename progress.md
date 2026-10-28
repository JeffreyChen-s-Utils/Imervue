# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- Complete runtime complexity repair remains. Fresh 926d4a6d analysis covers 974 runtime Python files: 544 verified, five data-only and 425 above 20, with no missing/stale scores. All 23 image-list/context-menu modules meet the threshold. GitHub CI, SonarCloud and Codacy PR checks passed, but whole-branch Codacy still lists three external-editor execution audits.
  Next: finish recipe and puppet-canvas contracts, obtain independent reviews, integrate and validate the next production cohort. Existing canvas_render.py remains outside that canvas.py extraction and above threshold. The environment Codacy repository token still returns HTTP 401 with the documented header.

- File-tree follow-up: image_issue_panel.py:95 still calls the absent _FileTreeView._open_in_explorer helper.
  Next: migrate the caller to the shared reveal API with a behavior test and synchronized user documentation. A direct call with one selected path reproduces AttributeError before any OS launch.


- Interpreter verification can block inside Windows process creation for an invalid executable, before its subprocess timeout applies.
  Next: investigate a bounded, background-safe production probe with preserved interpreter-discovery behavior. The test-only ENOEXEC injection verifies error handling but does not fix or prove this runtime case; no OS dialog cause has been established.
