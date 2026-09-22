# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#4** 13 files are over the 1000-line limit (`architecture_explore.md` §12); the largest are `Imervue/mcp_server/tools.py` and `Imervue/Imervue_main_window.py`.
- **#10** [DECIDE] `examples/*.puppet` (≈37 MB) is tracked; `march_7th.puppet` is a third-party character and `release.yml` packs `examples/` into the EXE — copyright and redistribution risk.
- **#12** [DECIDE] `.idea/deployment.xml` is no longer tracked, but this is a public repository and every commit from `6ecc332` (2026-02-13) up to U-20260922-03 still contains it, SFTP user@IP:port included. Either rewrite history (force push to `main` and `dev`) or treat the address as public and harden or move that server (workspace S-10).
- **#16** PySide6 is pinned to 6.11.1 (`pyproject.toml`, `requirements.txt`, `dev.toml`, `uv.lock`, `.github/workflows/release.yml`), which has the `QAction.menu()` wrapper-invalidation bug fixed upstream in 6.11.2 (U-20260922-15). Bump the pin everywhere, run the full suite and a release build.
