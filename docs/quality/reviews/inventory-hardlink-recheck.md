# Inventory hardlink and CLI re-review

The review checks whether the developer inventory preserves source and snapshot files, reports incomplete verification consistently, and retains runtime analysis coverage. It covers the current uncommitted versions of scripts/complexity_inventory.py, tests/test_complexity_inventory.py, .codacy.yaml and docs/quality/complexity-plan.md over HEAD e452ce80cc0b8a78cd62bd20afb5a70ae9f9f1c9. It does not review integrated production changes.

No remaining P1 or P2 finding was identified in this scope.

One P3 boundary finding remains at scripts/complexity_inventory.py line 165. A hosted files response containing a row with a null path raises AttributeError before snapshot validation. Both analysis_report and main catch _REPORT_ERRORS, which excludes AttributeError. This escapes the structured inconclusive result and prevents writing an error report. The independent probe passed a valid completed-analysis metadata response followed by {'data': [{'path': None, 'complexity': 1}], 'pagination': {}} into capture_snapshot through analysis_report. It observed AttributeError with the message "'NoneType' object has no attribute 'endswith'". Validate hosted row paths and pagination shapes and raise ValueError before using string or mapping methods. There is no demonstrated false verification or data loss from this finding.

The prior hardlink overwrite fixes are present. metadata_files checks samefile before and after analysis. write_metadata rejects destinations with multiple hard links, resolves confinement again, and uses the existing atomic replacement helper. The real hardlink regression cases preserve the snapshot, runtime source, and external file. Output errors are inside the main exception handler, while analysis errors still produce an inconclusive report when the output is writable. The Git validator accepts only the three required argument forms and rejects hash-object -w.

The Codacy addition is solely the script path under the Bandit engine. It follows the adjacent developer subprocess tool exemptions. It adds no runtime or complexity exclusion. The plan continues to require every runtime code file, fresh hosted results, and the existing threshold. Its explicit data-only exception matches the implementation. Hosted external-editor coverage remains pending in the plan.

Independent verification used D:/Codes/Imervue/.venv/Scripts/python.exe. The focused command -B -m pytest tests/test_complexity_inventory.py -q -p no:cacheprovider passed all 46 tests in 32.41 seconds. Ruff passed for the script and its test module. The malformed hosted response probe ran in memory and wrote no report or source file.

No source changes, commits, pushes, full-suite execution, foreground input or hosted requests were performed. This review does not establish live service response correctness, hostile concurrent filesystem race safety, or completion of the production complexity program.

## Follow-up verification

The P3 finding above is resolved in the subsequent frozen source. hosted_page now validates the page object, row list, pagination mapping, row mapping and string path before calling methods on those values. Malformed values raise ValueError, which the existing analysis and CLI handlers turn into an inconclusive report. capture_snapshot delegates its page parsing to this helper.

I read the added helper, its capture_snapshot integration and the five new complete CLI regression cases. An independent run of -B -m pytest tests/test_complexity_inventory.py -q -p no:cacheprovider -k malformed_hosted_pages passed all five selected tests with 46 deselected in 6.21 seconds. These cases cover a null path, a list-valued pagination field, null data, a null row and a list-valued page. Each asserts exit 2, a readable inconclusive JSON report and byte-for-byte preservation of the input snapshot.

This closes the only P3 finding from this review. The original finding and original 46-test result remain above as history. This follow-up did not rerun the full focused module, the full repository suite or hosted verification, and did not change source files.
