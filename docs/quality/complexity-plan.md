# Production complexity repair

The scope is all runtime Python modules in `Imervue/` and all bundled plugin Python modules in `plugins/`. Tests, developer tools and example scripts are not runtime modules. New runtime files enter the inventory automatically.

Completion requires every runtime code file to have a fresh hosted complexity result at or below the existing threshold of 20, with no unresolved Sonar or Codacy findings, complete behavior validation, synchronized architecture maps, and plugin distribution parity. Empty modules and simple data assignments without calls, imports, functions or control-flow statements are identified explicitly rather than silently omitted. This narrow AST classification permits references between data names and simple addition; it is not a guarantee that every expression is a literal.

## Workflow

1. Capture filename-ordered hosted results with their analyzed commit. Compare every current source against Git blobs from that commit. Reject duplicated pagination rows, missing metrics and stale source evidence.
2. Remove duplicated decisions and represent repeated domain choices directly. Separate responsibilities only where the resulting modules have cohesive production callers. Do not move code outside the runtime roots, raise thresholds, add exclusions, or split arbitrary groups of functions merely to spread the score.
3. Work through archive formats, annotation and Paint state, viewer/navigation, runtime/Puppet, library/media, then remaining application modules and plugins. Re-rank after each batch. A partially reduced file remains open while above 20.
4. Validate public behavior before and after each unit. Run relevant failure and boundary cases, then full pytest, Ruff, Bandit and required documentation checks before source commits. Recheck hosted analysis on the actual published commit.
5. Perform an independent review of source changes and the decision record. Verify the complete inventory again before declaring the goal complete.

## Verification

Run `python scripts/complexity_inventory.py --snapshot docs/quality/complexity-baseline.json --output .audit/complexity-report.json` from the worktree. Exit 0 means complete and within threshold, exit 1 means confirmed threshold violations, and exit 2 means incomplete or stale evidence. The committed snapshot is a baseline, not a permanently valid passing result; refresh it from the hosted analyzer after source changes.

Refresh with `python scripts/complexity_inventory.py --refresh-from-branch fix/main-quality --snapshot docs/quality/complexity-baseline.json --output .audit/complexity-report.json`. The exporter records each filename-ordered page and checks the completed analysis revision before and after capture. A branch whose current head has not completed analysis is rejected.

The verifier uses hosted scores rather than substituting local metrics. Local tools may guide refactoring, but they cannot certify hosted completion. No claim of interchangeability between local and hosted metrics is required by this verification method.

The baseline omits the runtime external-editor module. Codacy's [default ignored paths](https://docs.codacy.com/repositories-configure/ignoring-files/) include directories named `external`; `.codacy.yaml` now explicitly includes `Imervue/external/**` using the documented [include_paths setting](https://docs.codacy.com/repositories-configure/codacy-configuration-file/). The gap remains visible until a fresh hosted analysis confirms coverage. A green quality gate alone is insufficient.
