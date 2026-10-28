# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- Main-branch production complexity reduction: the first puppet/document_io.py batch passes all local gates; hosted analysis and the remaining ranked production modules remain. Baseline: 404 of 796 Imervue files exceed Codacy's threshold of 20.
  Next: publish and verify the first batch, then inspect annotation_canvas.py (211) and paint/document.py (197) for repeated branching and cohesive responsibilities.
