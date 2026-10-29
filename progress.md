# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- Complexity repair scope (owner decision 2026-10-29): split only runtime files with a hosted Codacy score of 80 or more; 53 remain from the 50186aa8 capture (develop_panel.py 148 first). Each resulting module stays at or below 40 locally. cli.py, workspace.py and image_index.py are done (hosted 17, 18 and pending).
  Next: the owner raises the Codacy file-complexity threshold to 50-60 in the repository quality settings (not reachable from here: the environment Codacy token returns HTTP 401); continue the ranked list in cohorts of four on fix/main-quality (PR #111). Plugin files also need the Imervue_Plugins mirror. canvas_render.py remains at 68, below the new scope.

- File-tree follow-up: image_issue_panel.py:95 still calls the absent _FileTreeView._open_in_explorer helper.
  Next: migrate the caller to the shared reveal API with a behavior test and synchronized user documentation. A direct call with one selected path reproduces AttributeError before any OS launch.


- Interpreter verification can block inside Windows process creation for an invalid executable, before its subprocess timeout applies.
  Next: investigate a bounded, background-safe production probe with preserved interpreter-discovery behavior. The test-only ENOEXEC injection verifies error handling but does not fix or prove this runtime case; no OS dialog cause has been established.

- Pre-existing quirks pinned (not fixed) by the complexity-split contract tests: pip_install_workers._ImportWorker formats `{exc or type(exc).__name__}`, so an exception with an empty message shows as "name: "; control_tooltips_fields reuses an owner's help with its `&` read as a mnemonic, giving a double space; control_tooltips.ensure_tooltip raises AttributeError for a plain QObject.
  Next: fix each with a regression test and update the contract test that pins it (tests/test_pip_installer_contracts.py, tests/test_control_tooltips_contracts.py).

- More pre-existing quirks pinned (not fixed) by the split contracts: a press exactly at (0, 0) never starts a GPU-view drag-select (input_controller_tiles); with a selection, normal brush blend writes the brush RGB into fully transparent pixels outside it (alpha stays 0; brush_dab). The .codacy.yaml bandit entry for clip_search.py and the .bandit B403 comment about its torch pickle loading look stale (no subprocess or pickle code remains there).
  Next: confirm each with a focused test, fix or drop it, and update the contract that pins it.
