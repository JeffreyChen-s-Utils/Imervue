# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- Complete runtime complexity repair remains. Hosted baseline e452ce80 now includes external/editors.py and has 435 Python files above the unchanged threshold of 20. Local reductions in archive, annotation, Paint, output-format, external-editor and runtime sampler code passed the integrated full suite (14,584 passed; 1,431 existing skips) and still need fresh hosted scores; further modules remain untouched.
  Next: publish this validated batch and inspect fresh Sonar/Codacy checks and complete runtime metrics, then begin the assessed file-tree and tool-state reductions. Three external-editor process-execution audit findings remain unresolved; the environment repository token returns HTTP 401 even with the documented project-token header.

- File-tree follow-up: image_issue_panel.py:95 still calls the absent _FileTreeView._open_in_explorer helper.
  Next: confirm the reveal action reproduction and migrate the caller to the shared reveal API with a behavior test in the next validated stage.
