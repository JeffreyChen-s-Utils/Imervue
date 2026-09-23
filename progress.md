# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#10** [DECIDE] `examples/*.puppet` (≈37 MB) is tracked; `march_7th.puppet` is a third-party character and `release.yml` packs `examples/` into the EXE — copyright and redistribution risk.
- **#12** [DECIDE] `.idea/deployment.xml` is no longer tracked, but this is a public repository and every commit from `6ecc332` (2026-02-13) up to U-20260922-03 still contains it, SFTP user@IP:port included. Either rewrite history (force push to `main` and `dev`) or treat the address as public and harden or move that server (workspace S-10).
- **#22** [DECIDE] 58 modules (8,803 lines, all with tests) are imported by nothing in `Imervue/` or `plugins/`, so no user can reach them: 34 in `paint/` (e.g. `rich_text.py`, `speech_bubbles.py`, `gradient_editor.py`, `perspective_warp.py`), 6 in `puppet/`, and the rest spread over 9 packages; `paint/watercolor.py`, `paint/comic_formats.py` and `paint/speech_bubbles.py` duplicate wired implementations. The full list is `_KNOWN_UNWIRED` in `tests/test_unwired_modules.py`, which fails on any new one. Next step: the owner picks, per module, wire it into a menu or dock, or delete it with its tests; each change shrinks `_KNOWN_UNWIRED`.
- **#24** 26 functions in `Imervue/` take more than the workspace's 7 parameters: `paint/` (16), `gpu_image_view/` (5), `image/` (2), `mcp_server/` (2), `library/` (1). The widest are `paint/manga_effects.py:51` (11), `paint/speech_bubbles.py:41` (11) and `paint/fill.py:63` (10); `py -m ruff check Imervue --select PLR0913 --config "lint.pylint.max-args=7"` lists them. `PLR0913` is in the ruff ignore list (`pyproject.toml`). Next step: group related options into a frozen dataclass per function (characterisation tests first), one package per commit; then set `pylint.max-args = 7` and drop `PLR0913` from the ignore list.
