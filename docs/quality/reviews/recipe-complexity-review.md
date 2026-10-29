# Recipe complexity review

No blocking correctness or ownership findings in the frozen recipe candidate against 926d4a6d. This review supports the recipe unit of the complete runtime complexity repair. It does not certify the whole program or hosted complexity.

The twelve manifest entries, comprising ten production files, the new contract test and architecture map, match their SHA-256 values at both review checkpoints. The saved original recipe source matches git show 926d4a6d:Imervue/image/recipe.py after line-ending normalization. Production files were not modified during review.

The shared optional-effect adapter retains the original order. Empty extra skips imports, import failures return the input, option decoding remains outside the application exception handler, and only ValueError/TypeError from application are logged and skipped. Split toning, LUT, threshold/posterize and compositing retain their distinct policies. Table-driven identity checks preserve field order and short-circuiting. Normalization constructs Recipe, while from_dict constructs cls. Public Recipe, STAGE_NAMES, file identities, cache clearing and turned_with_file imports remain available. The moved file-identity/cache, geometry and pixel stage function bodies are unchanged by AST comparison, excluding docstrings. Overall, 29 of 39 original function/method bodies remain identical under that comparison.

The owners are coherent responsibilities: recipe data and stage ordering, codec, neutral-value predicates and normalization, geometry, pixel adjustments, optional effects, distinct color-effect policies, compositing and file identity. Five duplicated optional-effect policies share one implementation. Neutral slider/curve/extra decisions use ordered field categories. Existing recipe_adjustments, recipe_store and recipe_diff remain unchanged. This is more than redistribution of the old file, although it introduces additional modules and two small mixins whose methods rely on Recipe fields.

Independent verification used D:/Codes/Imervue/.venv/Scripts/python.exe with CI=true and QT_QPA_PLATFORM=offscreen.

- recipe_replay.py matched 477 baseline/candidate records, including all 361 named stage ranges, pixels, array identity, normalization, serialized values and hashes. The resulting trace SHA-256 is 6d34d549bc2d96faef4addac925f83b4d084f8d7492504c93ea47e870f19ce70.
- Recipe, recipe-store, recipe-diff and new contract tests passed 196 cases.
- Recipe adjustments, CPU develop-preview pixels, GPU parameter conversion and recipe commands passed 96 additional cases.
- All 50 new contract cases independently passed with the untouched baseline module installed as Imervue.image.recipe. These include decode/apply exceptions, lazy import failure, partial threshold success, LUT errors, subclass construction, copy depth, identity validation bypass, unknown-field precedence, NaN clamping and a pinned hash.
- Scoped Ruff passed. All ten production line counts match the manifest and owning architecture rows.
- Recomputed local Radon function/method sums, excluding Class summary blocks, are 161 before and 137 after. Every resulting module is at most 19. These local figures do not substitute for hosted analysis.

Prove It Works guided the review by requiring exact baseline verification and rerunning comparisons instead of accepting implementation reports. Full integrated pytest, production Bandit, comment/style review and fresh hosted analysis remain parent-stage gates. No GUI or device was opened, and this review does not claim rendering or performance measurements.
