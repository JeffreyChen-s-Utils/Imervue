# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- **#57** Finish the pending RAW embedded-XMP rating reader in `image/raw_exif.py` and `image/xmp_sidecar.py`: extended UUID headers, truncated boxes and non-packet TIFF tags need regression coverage. Next: pass the targeted tests and full suite, update the architecture map and update log, then commit the completed change.
