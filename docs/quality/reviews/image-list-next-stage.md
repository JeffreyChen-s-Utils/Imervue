# Image-list next-stage assessment

Read-only assessment of the 725-line image_list_view.py, hosted complexity 162. No source changes or tests accompanied this assessment.

The module combines row metadata, thumbnail decoding, asynchronous fetch lifecycle, model identity/reset, cell presentation, sorting, rating presentation, keyboard input, context actions and view setup. Candidate owners should consolidate repeated lazy-fetch decisions, failure payload emission, alignment handling and selected-path operations before extraction. Preserve ImageListModel, ImageListView and star_at imports; distinguish compatibility exports from test patch locations for _ThumbWorker and _MAX_THUMB_RETRIES.

Behavior contracts needed before refactoring:

- Sorting uses existing metadata. Missing numbers are zero, not path fallbacks. Completed fetches do not resort. Negative columns preserve order; unknown positive columns sort naturally by filename. Stable ties retain input order. Persistent indexes follow row identity, including duplicate paths.
- set_paths with no metadata index retains the previous index but clears retry/stale/in-flight state. Fetch tracking is path-based while result lookup chooses the first matching row.
- Refetch preserves an old icon and remains lazy when idle. In-flight stale results are discarded and immediately retried. Failures get two retries; unexpected errors log while both expected and unexpected failures emit completion.
- Workers create detached QImages; QPixmap creation remains on the GUI thread.
- Edit shortcuts precede Enter and Ctrl+C. Escape and Undo work without selection. F1 through F5 accept Shift but reject Ctrl/Alt overrides.
- Rating clicks affect the clicked row before base selection. Delete restores the original minimum selected row after model rebuilding. Menus use existing selection, reveal/open its first path and relocate its first missing path.

Existing test_image_list_view.py covers many sorting, persistent-index, retries, refresh, shortcut, rating and rendering behaviors. test_folder_scan_performance.py covers lazy population and cached metadata. Add old/new traces for all sort columns/ties, duplicate rows, late same-path completion after reset, repeated refetch during retry, signal roles/order, shortcut precedence and callback-triggered rebuilds. A correctness defect discovered by those traces belongs in a separate fix, not an undocumented equivalence change. Measure the total across all resulting owners and require each at or below 20 with a real aggregate decrease.
