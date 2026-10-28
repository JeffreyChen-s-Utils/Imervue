# Paint tool-state next-stage assessment

Read-only assessment of the 983-line Imervue/paint/tool_state.py. No source edits or test execution accompanied this assessment. Proposed boundaries and budgets are unverified until implemented and measured.

Most setters repeat comparison, assignment, persistence, notification and changed-result handling. Brush/fill snapshot replacement duplicates unknown-field validation; numeric normalization repeats clamps; state and sub-tool encoding repeat field lists; RGB and color conversion overlap. Consolidate these decisions before separating responsibilities.

Keep ToolState dataclass fields, singleton, listener ownership, persistence hook and common change publication in tool_state.py. Preserve named methods and existing exports, including BrushSettings and constants used by brush_presets.py. Candidate owners are immutable settings/conversion policies, brush/fill snapshot updates, color/history operations, color decoding, ordinary options, gradient updates, ruler updates, sub-tool operations, sub-tool encoding and whole-state encoding. Target every resulting module at or below 20, with an aggregate decrease; no boundary is justified solely by its score.

Contracts requiring operation traces before implementation:

- Committed foreground changes emit color before history. Equal foreground values can return False while still recording history and emitting its event.
- Applying a sub-tool can save and emit tool before snapshot replacement, then save again and emit brush followed by fill even for equal snapshots.
- Gradient updates mutate sequentially; later conversion errors can retain earlier changes without saving or notifying. Brush/fill replacement is atomic instead.
- Listener iteration copies the list, unsubscription is repeatable, and callback exceptions propagate.
- Persisted foreground None reloads as black; background None remains transparent.
- Sub-tool fill encoding omits gap_close_px while whole-state fill encoding includes it. Sharing an unrestricted dataclass encoder would change the persisted format.
- Malformed top-level brush/fill numbers can raise; malformed sub-tool entries are discarded on TypeError/ValueError.
- Loaded color history preserves duplicates; interactive history deduplicates and moves the chosen color to the front.

The existing test_paint_tool_state.py has 98 test functions, with additional consumers covered by brush presets, gradient wiring, magnetic-lasso wiring, pen smoothing, swatch palettes and snap-to-panel tests. Add old/new traces of event order, persisted snapshots, save counts, callback mutation, partial failures, malformed loads, transparent foreground reload and sub-tool gap_close_px. Final-state assertions alone cannot prove those contracts.
