# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- [BLOCKED] Codacy file-complexity threshold: every runtime file that scored 80 or more is split (PR #111, fix/main-quality). Hosted Codacy still flags files above the current threshold of 20; at 60 about 50 files would remain, at 50 about 88.
  Next: the owner raises the threshold in the Codacy repository quality settings (the environment Codacy token returns HTTP 401 here), then decide whether the 60-80 band needs another pass. canvas_render.py remains at 68.

- File-tree follow-up: image_issue_panel.py:95 still calls the absent _FileTreeView._open_in_explorer helper.
  Next: migrate the caller to the shared reveal API with a behavior test and synchronized user documentation. A direct call with one selected path reproduces AttributeError before any OS launch.


- Interpreter verification can block inside Windows process creation for an invalid executable, before its subprocess timeout applies.
  Next: investigate a bounded, background-safe production probe with preserved interpreter-discovery behavior. The test-only ENOEXEC injection verifies error handling but does not fix or prove this runtime case; no OS dialog cause has been established.

- Pre-existing quirks pinned (not fixed) by the complexity-split contract tests: pip_install_workers._ImportWorker formats `{exc or type(exc).__name__}`, so an exception with an empty message shows as "name: "; control_tooltips_fields reuses an owner's help with its `&` read as a mnemonic, giving a double space; control_tooltips.ensure_tooltip raises AttributeError for a plain QObject.
  Next: fix each with a regression test and update the contract test that pins it (tests/test_pip_installer_contracts.py, tests/test_control_tooltips_contracts.py).

- More pre-existing quirks pinned (not fixed) by the split contracts: a press exactly at (0, 0) never starts a GPU-view drag-select (input_controller_tiles); with a selection, normal brush blend writes the brush RGB into fully transparent pixels outside it (alpha stays 0; brush_dab). The .codacy.yaml bandit entry for clip_search.py and the .bandit B403 comment about its torch pickle loading look stale (no subprocess or pickle code remains there).
  Next: confirm each with a focused test, fix or drop it, and update the contract that pins it.

- After the dev merge, user_setting_dict.py and puppet/webcam_tracker.py measure 83 locally (dev added code to both); hosted Codacy scored them 76 and below 80 before the merge.
  Next: check their hosted scores once the merge lands on main and split either one that reaches 80.

- Two local GUI tests fail on main as merged (CI skips them headless): test_main_window_layout::test_constructed_attributes_are_unchanged (the dev merge added `_job_indicator` to the window; `_EXPECTED` lacks it) and test_puppet_webcam_preview_dialog::test_dialog_close_disables_tracker (the tracker stays enabled after `close()`; [UNVERIFIED] the test never shows the dialog, and closing a hidden QDialog may never reach the `done()` override that stops it).
  Next: add `_job_indicator` to the layout snapshot; confirm the webcam cause, then fix the dialog or the test with a regression test for an unshown close.
