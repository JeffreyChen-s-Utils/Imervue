# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open
- **#75** `tests/test_gpu_image_view_init_state.py::test_constructed_attributes_are_unchanged` fails on `dev`: `1f055a26` added `GPUImageView._tile_max_dimensions` and the pinned attribute list in that test was not updated. Add it there if the attribute is meant to stay.
