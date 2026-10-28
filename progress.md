# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open
### Resolve full-program review FR-01 through FR-16

Verified findings are in `docs/reviews/2026-10-28-full-review.md`. P1: failed overwrite exports, colliding batch motion destinations and maintenance deleting existing images' metadata. P2: worker cancellation/teardown, profile save races, recording outcomes, transfer races, URL encoding, malformed inputs and frozen platform selection.

Next: reproduce FR-01 through FR-03 as regression tests and fix the data-protection boundaries first; then resolve FR-04 through FR-16 with their documented acceptance criteria and repository verification gates. This review did not change application behavior.
