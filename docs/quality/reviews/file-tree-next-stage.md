# File-tree next-stage assessment

Read-only assessment of Imervue/gui/file_tree_view.py before the next production stage. This is a plan, not a completed refactor or hosted verification.

The 945-line module combines tree presentation, context menus, filesystem commands, deletion routing, trash-worker lifecycle, and viewer deletion effects. The strongest reduction is shared viewer deletion effects with a separate owner for the asynchronous trash queue.

Preserve the distinction between single deletion (first matching image occurrence) and batch deletion (all matching occurrences and original undo indices). Share effects only after each caller determines its exact removed entries. Keep GL cleanup and VRAM accounting together. Queue extraction must preserve request order, success filtering, grouped trash calls, per-request notifications, and shutdown flushing.

Existing test_file_tree_multiselect.py covers routing, batching, notifications, permanent-delete decisions, undo, and plugin dispatch. Add contracts for duplicate image entries, mixed image/folder/loose-file requests, completion during shutdown, and callbacks that queue more work. Preserve existing texture-release, context-switch, missing-context, rename/duplicate sidecar, case-only rename, menu-reveal, proxy-sort, and raw-model-sort checks. Exercise keyboard and menu entry points as well as helpers. Search filtering, pending-delete hiding, restoration, and directory reload need a combined case.

Then separate filesystem commands and menu construction along those responsibilities, reuse file_tree_sort.normalize_sort_key, and preserve compatibility exports of _FileTreeView and _next_duplicate_name from Imervue_main_window. Measure the aggregate across all resulting modules to demonstrate a real reduction rather than only distributing the score.

A separate defect is confirmed by source inspection: image_issue_panel.py:95 calls absent _FileTreeView._open_in_explorer. The shared supported API is Imervue.system.file_manager.reveal_or_warn(path, select=True). Track the caller migration and a user-action regression case independently from the equivalence refactor. No OS file-manager launch was attempted during this assessment.
