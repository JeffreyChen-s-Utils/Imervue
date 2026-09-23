# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#10** [DECIDE] `examples/*.puppet` (≈37 MB) is tracked; `march_7th.puppet` is a third-party character and `release.yml` packs `examples/` into the EXE — copyright and redistribution risk.
- **#12** [DECIDE] `.idea/deployment.xml` is no longer tracked, but this is a public repository and every commit from `6ecc332` (2026-02-13) up to U-20260922-03 still contains it, SFTP user@IP:port included. Either rewrite history (force push to `main` and `dev`) or treat the address as public and harden or move that server (workspace S-10).
- **#19** 17 functions in `Imervue/` are longer than the workspace's 80-line limit, mostly Qt `__init__` / `_build_ui` builders; the largest are `gui/smart_albums_dialog.py:__init__` (95), `puppet/cubism_native_bridge.py:_bind_signatures` (89), `menu/filter_menu.py:build_filter_menu` (87), `gui/slideshow_mp4_dialog.py:__init__` (86) and `paint/stamp_tool.py:stamp_dab` (86). Next step: split each into section builders in the original order (a builder returns the widget and the caller adds it to its layout), one module per commit.
- **#21** 20 broad `except Exception` handlers in `Imervue/` neither narrow the type nor log the traceback (ruff `BLE001`, not yet in the selected rule set; `py -m ruff check Imervue --select BLE` lists them): `gpu_image_view/` (8), `gui/` (9), `menu/` (3). The 107 existing `# noqa: BLE001` comments suppress nothing until `BLE` is selected. Next step: narrow each to the exceptions it can actually see (or log with the traceback and a justified `# noqa: BLE001`), with a regression test per behaviour change, one package per commit; then add `BLE` to `[tool.ruff.lint] select`.
