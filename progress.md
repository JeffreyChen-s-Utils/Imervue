# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- Complete runtime complexity repair remains. Fresh 27bf0693 analysis covers 953 runtime Python files: 521 verified, five data-only and 427 above 20, with no missing/stale scores. All file-tree/tool-state modules meet the threshold; develop_panel.py remains above it. SonarCloud and Codacy PR checks passed, but whole-branch Codacy still lists three external-editor execution audits.
  Next: publish the validated image-list/context-menu cohort and verify fresh hosted scores and whole-branch issues. Its full rerun passed 14,711 tests with 1,431 existing skips. Both independent reviews passed; the per-cell dispatch allocations were removed and rechecked. Context-menu integration passed 72 focused checks. The environment Codacy repository token still returns HTTP 401 with the documented header.

- File-tree follow-up: image_issue_panel.py:95 still calls the absent _FileTreeView._open_in_explorer helper.
  Next: migrate the caller to the shared reveal API with a behavior test and synchronized user documentation. A direct call with one selected path reproduces AttributeError before any OS launch.


- Interpreter verification can block inside Windows process creation for an invalid executable, before its subprocess timeout applies.
  Next: investigate a bounded, background-safe production probe with preserved interpreter-discovery behavior. The test-only ENOEXEC injection verifies error handling but does not fix or prove this runtime case; no OS dialog cause has been established.
