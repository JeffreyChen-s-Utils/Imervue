# File-tree complexity independent review

No supported behavior findings in the frozen file-tree change against c6ecd0f7.

Scope: file_tree_view.py and its eleven new operation modules, changed reveal tests, new contract tests, and architecture rows. Reviewed repository rules. No source edits, commits, full-suite run.

The view retains state ownership and explicit Python function bindings. An independent descriptor check confirmed that every original class method name remains present and both original static methods remain static methods. Extracted operations continue dispatching through self for original override points. The new shared removal helper keeps single deletion at the first occurrence and batch deletion at every matching occurrence. It creates separate callback path lists, preserves the image-list object, and retains undo, texture release, cache removal, navigation, plugin, and notification order.

AST comparison of baseline functions against the extracted functions found no executable changes to menu construction, sorting, filtering, path helpers, deletion routing, queue pumping, shutdown draining, or GL release and VRAM accounting. Semantic changes are confined to the shared post-removal helper and common lazy toast helper. The toast helper preserves message evaluation only when a toast exists and preserves exception text by capturing the exception in the immediate callback. Rename/duplicate sidecar calls retain their order and arguments. The moved reveal-test patches correctly target the new module globals.

The twelve modules have identifiable responsibilities: Qt events/state, menus, sort controls, search, pending-folder visibility, filesystem commands, deletion routing, viewer deletion, textures, trash workers, feedback, and paths. The aggregate reduction comes from shared notification and removal work; it is not solely a file split. The class binding list makes operation ownership inspectable without a generic dispatch registry.

Independent validation, using D:/Codes/Imervue/.venv/Scripts/python.exe:

- tests/test_file_tree_contract.py, tests/test_file_tree_multiselect.py, tests/test_file_tree_reveal.py: 55 passed in 1.70s. External basetemp D:/Codes/Imervue-quality-tools/test-runs/file-tree-review.
- The 15 new contract tests also passed against the actual c6ecd0f7 module loaded from git show, with a separate external baseline temp directory.
- Read and reran .audit/verify_file_tree_equivalence.py: 1408 viewer-deletion calls matched c6ecd0f7. This matrix covers repeated paths, single/batch selections, grid/deep-zoom states, and callbacks that mutate their supplied lists.
- Checked every original method's class descriptor against baseline AST: all names and staticmethod forms retained.
- Independently measured Lizard 1.22.2 sums of function cyclomatic_complexity: baseline 183, extracted aggregate 172, maximum per-module sum 20 across 12 modules. This confirms an aggregate reduction of 11. Also independently reproduced Radon 6.0.1 cc_visit sums excluding Class blocks: 182 to 171, maximum 20 across 12 modules. These are different metrics; both show the same aggregate reduction of 11. No hosted-metric claim is made.

Remaining integration gates belong to the parent workflow. This focused review does not substitute for the full integrated suite or hosted analysis.
