# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#2** Mirror the plugin changes to `Imervue_Plugins` `main` (13 files are behind, see `docs/updates/2026-09.md` U-20260922-02) and decide whether `plugins/png_to_icon/` should be tracked here (workspace X-9).
- **#3** [UNVERIFIED] The Spanish plugin language is missing from the Language menu: `addSeparator` raised `RuntimeError` (`imervue.log:60`, `Imervue/integration_guide.py:96-101`). Seen once, on Python 3.14; reproduce first.
- **#4** 13 files are over the 1000-line limit (`architecture_explore.md` §12); the largest are `Imervue/mcp_server/tools.py` and `Imervue/Imervue_main_window.py`.
- **#5** `Imervue/plugin/plugin_manifest.py` is used only by `tests/test_plugin_manifest.py`, not by `plugin_manager`, and its `plugin_requires_*` attributes are undocumented.
- **#6** `PLUGIN_DEV_GUIDE.md` is out of date: no `on_build_main_tabs`, cites a nonexistent `plugins/example_plugin/`, teaches `print()` (against `CLAUDE.md` Code Quality), and does not say plugins must be flat (workspace X-10).
- **#7** `*.spec` is gitignored, but `packaging/CROSS_PLATFORM.md` and `pyinstaller.md` assume the spec files are in the repository.
- **#8** Stale metadata: `architecture_explore.md` header names `694e63c` / 1.0.86; `docs/conf.py` hardcodes `release`; `dev.toml` (name `Imervue_dev`, version 1.0.9) and `dev_requirements.txt` lack imageio-ffmpeg, defusedxml and watchdog.
- **#9** CI does not run ruff or bandit (`.github/workflows/test.yml`); the quality gate exists only locally.
- **#10** [DECIDE] `examples/*.puppet` (≈37 MB) is tracked; `march_7th.puppet` is a third-party character and `release.yml` packs `examples/` into the EXE — copyright and redistribution risk.
- **#11** Plugin downloader: every top-level directory of `Imervue_Plugins` is treated as a category, so the distribution repository cannot hold any other directory (such as `docs/`). Restrict categories to `plugins` and `languages` (workspace X-18).
- **#12** [DECIDE] `.idea/deployment.xml` is no longer tracked, but this is a public repository and every commit from `6ecc332` (2026-02-13) up to U-20260922-03 still contains it, SFTP user@IP:port included. Either rewrite history (force push to `main` and `dev`) or treat the address as public and harden or move that server (workspace S-10).
