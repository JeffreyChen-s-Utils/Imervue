# Context-menu next-stage assessment

Read-only assessment of right_click_menu.py, 874 lines and hosted complexity 162. No edits or tests accompanied this assessment.

Menu composition, selection policies, recovery, navigation, current-image actions, batch metadata/culling, multipage/import operations, library maintenance and Extra Tools are separate candidate responsibilities. The strongest shared decisions are count-dependent result reporting in location tags, keyword indexing and the two culling operations. Keep culling's viewer update separate and before reporting. Other candidates are simple action construction and repeated image-availability checks. Require an aggregate decrease across all resulting modules, not only smaller individual files.

Preserve these contracts:

- Empty image lists yield no current path even with a deep-zoom error. Otherwise the error path precedes the current deep-zoom path.
- Reveal, wallpaper and lossless rotation capture paths during menu construction. Several batch actions instead read selection when triggered.
- Batch actions need grid mode, selection mode and nonempty selection. Selected-image deletion needs only the first two. Current-image deletion is independent, so both entries can coexist.
- Retry chooses erroneous hovered tiles before deep-zoom errors, but execution prioritizes a matching deep-zoom failure over thumbnail failure.
- Relocation replaces the first matching image or falls back to current_index, clears offline/error state and loads the replacement even without a valid updated index.
- Multipage combination and staging preserve viewer order. Other operations currently use list(selected_tiles).
- Wallpaper stays in a worker. Successful lossless rotation reports, clears deep zoom, then reloads.
- Preserve action/separator order, Recent store_refs=False and subsequent plugin contribution dispatch. Keep activation-only imports lazy.

The production entry point is right_click_context_menu, imported by view_mouse.py. Tests also use private helpers and patch original-module selection, reveal and wallpaper dependencies; distinguish those patch points from production compatibility. Existing tests cover right-click actions, selection order and Recent handle recovery. Add old/new action traces for empty, grid, selected-grid, deep-zoom and error states, including callback timing, retry precedence, relocation, missing toast, cancellation and plugin ordering. Mock clipboard, launches and dialogs; retain existing real file-output cases.
