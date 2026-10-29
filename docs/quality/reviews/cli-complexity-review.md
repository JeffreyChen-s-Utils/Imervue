# CLI complexity review

No blocking correctness or ownership finding in the frozen CLI candidate against fabb4666. This review supports the CLI unit of the complete runtime complexity repair. It does not certify the full program or hosted complexity.

All thirteen manifest hashes matched at the beginning and end of review. The saved baseline_cli.py matches git show fabb4666:Imervue/cli.py after line-ending normalization. Existing cli_tools.py and cli_output.py also match their baseline bytes. No candidate source or test was edited during review.

The three changed original functions are path-policy helpers. Optional output handling retains its early None result and context-specific error text while sharing the parent-traversal decision. The removed str(Path.parent) condition was always true for Path objects; parent existence still controls mkdir. Fifty-one of fifty-four original function ASTs remain identical. The domain boundaries separate paths, native writers, pipeline steps/validation, reports, batch publication, worker cancellation, composite commands, presets and parser construction. This adds ten modules and an explicit compatibility export list, but does not transfer complexity into existing CLI collaborators or introduce a second command framework. The aggregate reduction is modest and real.

Inspection confirmed dispatch precedence, lazy bridged-command creation, validation/error ordering, Namespace mutation timing, and preserved writer decoding/metadata behavior. The shared _WRITE_SPEC remains owned by the public entry module and used by run. The pipeline and reporter maps remain shared objects. Moved functions use their owning module globals; tests that substitute internal dependencies use the function's actual globals. Bytecode inspection of all 53 top-level owned functions and their nested code objects found no unresolved global names.

Worker cancellation still sets the Event and cancels queued work before leaving the executor context that waits for active encoders. Result publication preserves input order, report/source/output conflict checks, report-failure precedence over interrupted exit status, and exception propagation for unexpected worker failures. Pipeline decoding still accepts the original JSON forms and only wraps TypeError during stage application.

Independent verification used D:/Codes/Imervue/.venv/Scripts/python.exe with offscreen Qt and CI=true for focused tests.

- CLI, CLI tools, CLI output, output policy and new contracts passed 308 cases with exit 0.
- All seventeen new contracts passed against the untouched baseline module in a separate review basetemp. The threaded cancellation case uses real worker Events and verifies cancellation before join.
- replay.py matched the help/action shape of all 67 commands and 38 execution cases. Comparison includes exact normalized stdout/stderr, exit codes, source/output file hashes and JSON reports. Its parser trace hash is 4f4ea2d415b8c5b08521025451120ca57300c123ca6b07ed65d9b9acc4dbf13c.
- smoke.py passed five real background module-entry cases and a fresh-process assertion that importing the CLI loads no Qt, OpenGL or Imervue.gui module.
- Scoped Ruff passed. audit.py independently reproduced Function complexity 152 to 150, excluding Class summary blocks, with every resulting owner at most 19.

The scoped comment/deslop review found no blocking finding and recommends no edits. Tokenized production comments decrease from 25 to 14, with zero added tokens. The new contract test has no inline comments. The two NOSONAR-bearing comments in cli_paths.py are moved baseline comments on the same validated-path mkdir operation, not new suppression scope. No broad catch, cast, type bypass, extra generic registry or forwarding machinery was introduced. Existing API docstrings and the cancellation-order contract remain useful. No comment was deleted or restored by this reviewer; there are no new HOLD items, architecture flags, constraint-encoding proposals or comment-review reruns.

Prove It Works guided exact baseline verification, re-running the supplied comparisons, and exercising the real subprocess entry instead of accepting implementation summaries. Full integrated pytest, production security scans, architecture total regeneration and fresh source-matched hosted analysis remain parent-stage gates.
