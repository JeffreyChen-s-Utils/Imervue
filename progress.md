# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#3** [UNVERIFIED] The Spanish plugin language is missing from the Language menu: `addSeparator` raised `RuntimeError` (`imervue.log:60`, `Imervue/integration_guide.py:96-101`). Seen once, on Python 3.14; reproduce first.
- **#4** 13 files are over the 1000-line limit (`architecture_explore.md` §12); the largest are `Imervue/mcp_server/tools.py` and `Imervue/Imervue_main_window.py`.
- **#5** `Imervue/plugin/plugin_manifest.py` is used only by `tests/test_plugin_manifest.py`, not by `plugin_manager`, and its `plugin_requires_*` attributes are undocumented.
- **#10** [DECIDE] `examples/*.puppet` (≈37 MB) is tracked; `march_7th.puppet` is a third-party character and `release.yml` packs `examples/` into the EXE — copyright and redistribution risk.
- **#12** [DECIDE] `.idea/deployment.xml` is no longer tracked, but this is a public repository and every commit from `6ecc332` (2026-02-13) up to U-20260922-03 still contains it, SFTP user@IP:port included. Either rewrite history (force push to `main` and `dev`) or treat the address as public and harden or move that server (workspace S-10).
- **#13** The six plugins with an optional ONNX path (ai_colorize, ai_denoise, ai_motion_deblur, ai_object_remove, ai_portrait_relight, ai_style_transfer) fail with an ImportError toast when onnxruntime is missing and offer no install. Gate the ONNX branch of each dialog's commit (e.g. `plugins/ai_denoise/ai_denoise_plugin.py` `_commit`) on `ensure_dependencies([("onnxruntime", "onnxruntime")])`.
- **#14** Plugins → Reload Plugins re-runs `on_build_menu_bar` without removing the previous entries (`Imervue/menu/plugin_menu.py:240-243`), so every reload duplicates plugin entries (Extra Tools 114 → 122 in an offscreen probe), and the old entries keep calling the unloaded instances.
- **#15** The Sphinx build prints 153 docutils warnings (inline literal / strong start-string without end-string), all in the translated `docs/*/index.rst` (zh-cn, zh-tw, ja, ko lead): inline markup closed directly before CJK text is not recognised and needs an escaped space after the end-string. Fix, then consider building with `-W` in CI.
