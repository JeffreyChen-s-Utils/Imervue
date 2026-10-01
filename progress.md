# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#53** [BLOCKED] The `publish-dev` job of `.github/workflows/test.yml` fails at **Publish to PyPI** on every push to `dev` with `HTTPError: 403 Forbidden from https://upload.pypi.org/legacy/`: the repository secret `PYPI_API_TOKEN` may not upload to the project `Imervue_dev`. Nothing newer than 1.0.7 is published, and each `Tests` run on `dev` ends red although `lint`, `docs`, `fast` and `extended` pass (U-20261001-54). Next: the owner stores, under the same secret name, a PyPI token that may upload to both `Imervue` and `Imervue_dev`; the next push to `dev` then publishes 1.0.10 (workspace X-13).
- **#56** [UNVERIFIED] Three Paint text tests fail on a local run with `QT_QPA_PLATFORM=offscreen`, on `6200aa5f` already: `tests/test_paint_page_numbering.py::test_start_at_offsets_the_first_page_number`, `tests/test_paint_text.py::test_preview_font_follows_combo_box` (the font family comes back as `Sans Serif`, not `Courier New`) and `tests/test_paint_text_along_selection.py::test_the_text_is_drawn_on_a_new_layer_along_the_outline`. CI's `gui` job passes all three; it does not set `QT_QPA_PLATFORM`. Unconfirmed: the offscreen platform finds no system fonts on Windows. Next: confirm the cause, then give these tests a font that platform can load, or skip them there with a reason.
