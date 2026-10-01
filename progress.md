# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#56** [UNVERIFIED] Three Paint text tests fail on a local run with `QT_QPA_PLATFORM=offscreen`, on `6200aa5f` already: `tests/test_paint_page_numbering.py::test_start_at_offsets_the_first_page_number`, `tests/test_paint_text.py::test_preview_font_follows_combo_box` (the font family comes back as `Sans Serif`, not `Courier New`) and `tests/test_paint_text_along_selection.py::test_the_text_is_drawn_on_a_new_layer_along_the_outline`. CI's `gui` job passes all three; it does not set `QT_QPA_PLATFORM`. Unconfirmed: the offscreen platform finds no system fonts on Windows. Next: confirm the cause, then give these tests a font that platform can load, or skip them there with a reason.
