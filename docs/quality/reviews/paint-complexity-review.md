# PaintDocument complexity review

The goal is to preserve PaintDocument behavior while reducing file complexity through cohesive responsibilities. I reviewed the frozen runtime and test changes in D:/Codes/Imervue-paint-quality against its HEAD. No blocking correctness or maintainability findings were identified.

## Scope and evidence

I read the tracked document.py diff, all eleven new runtime modules, and all of tests/test_paint_document_contracts.py. The eleven modules contain ten mixins and one pure visibility helper. I compared the extracted methods with the original methods using Python ASTs, then inspected the changed bodies and their callers. I also inspected document_groups.py, document_merge.py, document_geometry.py, undo_stack.py, document loading calls, and the relevant existing tests.

The ownership-sensitive paths retain their previous bodies. These include __deepcopy__, adopt_content, replace_state, duplicate_active_layer, mask creation/application, selection storage, and full/partial composite computation. Listener iteration now uses _emit_changed, which still copies the listener list before callbacks. State mutation and reference-index adjustment still precede notification. Selection changes preserve composite cache state. Both explicit invalidation and property changes clear the cache and damage rectangle before callbacks.

The private-method search found the existing group-to-_resolve_layer, geometry-to-_remap_all_selections, and merge-to-_is_layer_effectively_visible calls. Their names and behavior remain available. The new shared property helper is also used by the mask-enabled setter. All original PaintDocument methods remain reachable. An in-memory MRO check found no callable method collisions. I found no repository subclass or monkeypatch caller relying on the old document.composite_stack lookup location.

I independently ran the following four test files with D:/Codes/Imervue/.venv/Scripts/python.exe and QT_QPA_PLATFORM=offscreen. The run passed 149 tests in 6.94 seconds with exit code 0.

- tests/test_paint_document_contracts.py
- tests/test_paint_document.py
- tests/test_paint_document_deepcopy.py
- tests/test_paint_undo_stack.py

An additional in-memory differential probe loaded the old document.py directly from git HEAD. Five scenarios triggered nested callbacks during selection, property, damage, insertion, and reference updates. Each callback read the composite, and the first callback also changed pixels, marked damage, and changed a property. Old and new implementations produced equal notification sequences, active/reference indices, lock state, pixels, and cache-identity observations.

## Cohesion judgment

The new mixins follow the existing document group, merge, and geometry pattern. They leave document identity, owned content fields, cloning/adoption, and listener storage in PaintDocument. Creation, ordering, state installation, masks, saved selections, and compositing each have recognizable responsibilities. Shared insertion and property mutation helpers remove repeated mutation and notification sequences.

The split increases navigation between files. The mask-enabled setter depends on the property helper, and visibility used by merge is reached through the reference mixin's retained wrapper. These are small and visible dependencies consistent with the existing mixin pattern. They do not justify rejecting the change. The pure visibility function has one direct wrapper caller, with reference lookup and merge visibility sharing that wrapper. This is the least independently valuable split, but its behavior is direct and its compatibility purpose is clear.

Minimize Reader Load shaped this judgment. I evaluated actual cross-file dependencies and preserved ownership, rather than treating the file score alone as proof of improvement. Prove It Works shaped verification through direct tests and baseline comparison.

## Limits and reporting details

The audit JSON records a local Radon baseline of 198 and a new combined score of 176, with all twelve affected runtime files at or below 20. The task brief's 197 must remain separately labelled if it came from hosted analysis. I read the audit values but did not independently reproduce them. Radon is absent from the explicitly required Python environment, so my initial combined probe failed at its import before running any checks. I removed that optional measurement and successfully reran the behavioral probe. No dependency was installed.

I did not run the full suite, hosted analysis, visible UI, OS input, clipboard operations, or network/credential operations. Those release gates remain with the parent. The new tests cover the intended public contract instead of mixin names, but they are not an exhaustive proof over arbitrary user-defined coercion objects or external consumers that monkeypatch module globals. Normal supported inputs and the inspected repository callers showed no regression.

No runtime or test files were edited. This report is the only authored artifact.
