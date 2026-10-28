# Complexity inventory independent re-review

The goal is to bring every runtime Python module in `Imervue/` and `plugins/` within the existing hosted complexity threshold without losing behavior or omitting runtime code. This review covers the inventory, its tests, `docs/quality/`, and `progress.md`. It does not certify completion of the production repair.

No remaining P1 or P2 finding was identified in this review. The prior false-pass paths are fixed. The actual production result remains inconclusive with 434 threshold violations and one missing metric.

## Verified prior fixes

- Directory traversal now propagates scan failures through `os.walk`'s `onerror` handler and rejects directory links before descent. Focused tests exercise an unreadable directory, a directory link, and a Python file inside a cache-named directory.
- Git freshness hashes the same captured byte buffer that the AST classifier and reported SHA-256 use. The verifier then repeats path enumeration and checks file bytes for changes. Focused tests cover changed bytes during hashing and a separate-read mismatch.
- Snapshot validation rejects noncanonical POSIX paths before storing scores. Both doubled separators and dot-segment aliases have passing regression tests.
- The exporter requests filename ordering, follows recorded cursors, rejects repeated cursors and duplicate file rows, and checks completed branch analysis before and after capture. Focused tests cover those conditions, including an unanalyzed branch head and a changed revision.
- The evidence trail explicitly narrows the earlier calibration claim to exploratory observations. The plan uses hosted metrics as the certification source. It no longer claims reproducible equivalence between local and hosted metrics.

## Evidence from this review

`py -B -m pytest tests/test_complexity_inventory.py -q -p no:cacheprovider` completed with 28 passed in 55.50 seconds. This includes the three non-HTTPS rejection cases. The parent subsequently renamed the translation classification test and clarified the plan wording without changing behavior. I read those updated lines.

A fresh in-memory `inventory` run returned exactly the saved `.audit/complexity-report.json`. It used analysis revision `31768a0f8cbd8b89354d09c527516d423d0a3d25` and reported 882 sources, 441 verified, six data-only, 434 over threshold, one missing analysis, and zero changed since analysis. The missing metric belongs to `Imervue/external/editors.py`.

An independent filesystem enumeration found the same 882 paths. Every reported SHA-256 matched the corresponding on-disk bytes after the run. The baseline contains 875 distinct Python paths and nine page records. The page records count 888 returned rows before the exporter's Python filter.

The AST exemption accepts bare names and addition expressions. Direct probes of `UNKNOWN` and `VALUE = LEFT + RIGHT` both returned `data_only`. The revised plan now explicitly describes that structural rule and disclaims a literal-only guarantee. This closes the minor wording issue raised during this review. No above-threshold escape was demonstrated from that distinction.

The `Prove It Works` principle shaped this review by requiring a fresh real-tree inventory and independent path/hash comparisons instead of accepting the prior report alone.

## Limits

I did not rerun the live hosted capture or independently authenticate historical service responses. The committed snapshot remains a trusted input, with a repeatable exporter and page summaries rather than archived full HTTP responses. I did not run the full test suite, Ruff, or Bandit in this review because the parent is running the required checks. Passing this instrumentation review does not satisfy the production reduction, hosted finding cleanup, or repository commit gates.

No production source or shared review target was changed by this reviewer. The only written artifact is this report. All commands ran in the background without desktop input or credential access.
