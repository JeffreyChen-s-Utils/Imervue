# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#10** [DECIDE] `examples/*.puppet` (≈37 MB) is tracked; `march_7th.puppet` is a third-party character and `release.yml` packs `examples/` into the EXE — copyright and redistribution risk.
- **#12** [DECIDE] `.idea/deployment.xml` is no longer tracked, but this is a public repository and every commit from `6ecc332` (2026-02-13) up to U-20260922-03 still contains it, SFTP user@IP:port included. Either rewrite history (force push to `main` and `dev`) or treat the address as public and harden or move that server (workspace S-10).
- **#19** 20 functions in `Imervue/` are longer than the workspace's 80-line limit, mostly Qt `__init__` / `_build_ui` builders; the largest are `paint/docks/brushes.py:FillDock.__init__` (99), `gui/gif_video_dialog.py:_build_ui` (97), `desktop_pet/pet_workspace.py:_build_window_group` (95), `gui/smart_albums_dialog.py:__init__` (95) and `puppet/cubism_native_bridge.py:_bind_signatures` (89). Next step: split each into section builders in the original order (a builder returns the widget and the caller adds it to its layout), one module per commit.
