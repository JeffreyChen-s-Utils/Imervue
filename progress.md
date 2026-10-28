# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- Complete runtime complexity repair remains: fresh c6ecd0f7 Codacy results cover all 929 runtime Python files, with 495 verified, five data-only and 429 above 20. All 53 production files changed in that cohort are within threshold. SonarCloud passed; Codacy lists three external-editor execution audits plus a verifier subprocess audit and an annotation callback inference warning.
  Next: integrate the independently reviewed callback injection and developer-tool audit policy with the integrated file-tree and tool-state reductions; the second-cohort full suite passed with 14,650 tests and 1,431 existing skips; publish it and obtain fresh hosted analysis. The callback/verifier focused set passed 61 tests. The environment Codacy repository token still returns HTTP 401 with the documented header.

- File-tree follow-up: image_issue_panel.py:95 still calls the absent _FileTreeView._open_in_explorer helper.
  Next: migrate the caller to the shared reveal API with a behavior test and synchronized user documentation. A direct call with one selected path reproduces AttributeError before any OS launch.
