# progress.md: Imervue

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-10, X-9, X-10, X-18).

## Open

- Main-branch production complexity reduction remains: 434 runtime Python modules in Imervue/ and plugins/ exceed Codacy's existing threshold of 20; external/editors.py has no hosted metric. The complete source inventory contains 882 Python files, including six literal-data or empty modules.
  Next: finish the inventory stage's full test run and publish it, then integrate independently reviewed production reductions with full behavior checks and fresh hosted metrics. Puppet archive and annotation canvas refactors are underway in isolated worktrees; image output-format deduplication has passed focused tests and review. All remain unverified against fresh hosted metrics.
