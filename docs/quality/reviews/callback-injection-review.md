# Callback injection independent review

No findings in the scoped change since c6ecd0f7.

Reviewed AnnotationCanvas constructor injection, DevelopPanel creation and cleanup wiring, tests/test_annotation_base_resolver.py, and the added Opengrep exception. The constructor stores the callback without invoking it. DevelopPanel finishes setting source path and recipe before subsequent canvas operations; the constructor contains no resolver calls. The previous positional arguments remain compatible and the new argument is keyword-only and optional. The ensure_full_base expression is unchanged, preserving None handling, callback return values, replacement behavior, and propagation of exceptions and invalid-callback TypeError. Cleanup still removes the callback.

The Opengrep exception adds only scripts/complexity_inventory.py. Its subprocess entry point validates exact inspection argument forms before invocation, resolves Git to an absolute executable, and supplies an argument list with no shell. No new runtime exclusion was added.

Independent validation: D:/Codes/Imervue/.venv/Scripts/python.exe -m pytest tests/test_annotation_base_resolver.py --basetemp=.audit/pytest-callback-review -q -> 3 passed in 0.59s. Read repository CLAUDE.md and the relevant source paths. No source edits, commits, full-suite execution. This review did not rerun hosted analysis or independently reproduce Pylint inference.
