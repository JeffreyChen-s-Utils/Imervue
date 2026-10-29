# Annotation complexity review

The goal is to reduce annotation canvas complexity while preserving annotation editing behavior. This independent review found no blocking correctness or security findings in the frozen runtime and test changes against HEAD 31768a0f8cbd8b89354d09c527516d423d0a3d25.

The review read the complete tracked canvas diff, all nine new runtime modules, all four new test modules, the architecture map diff, and relevant existing drawing, crop, destructive, dialog and canvas composition code. It checked signal timing, undo snapshots and list ordering, event routing, text commit reentrancy, painter transforms and restoration, coordinate rounding, compatibility aliases and Qt method resolution.

No P0, P1 or P2 findings were found. The shared style policy preserves the prior selected-kind filters, clamp behavior, update timing and absence of undo or change signals. The combined path hit test preserves the endpoint-only policy for line and arrow and the full segment chain for freehand. The command lookup still updates only the first matching ID. The shortcut table preserves Shift+Save and Shift+Y behavior. Pointer routing, drag state transitions, text lifecycle, compositing and coordinate mapping moved without behavioral changes.

The mixin split is acceptable within this repository's existing widget pattern. AnnotationCanvas already combined crop, drawing and destructive mixins. PaintCanvas combines view, input and overlays, while DevelopPanel combines preview and right-panel responsibilities. This change adds named responsibility groups without adding mutable state, duplicate caches, callback forwarding or competing methods. Runtime inspection found no duplicate method definitions across the annotation classes in the MRO. There are eight direct mixin bases and ten effective mixins because pointer routing inherits selection drag and creation. QWidget remains the final implementation for unhandled key events.

A nonblocking maintainability limitation remains. These mixins share the canvas's implicit state contract and do not make that state independently encapsulated. Following a gesture can require reading pointer routing, selection or creation, commands and the owning canvas. The extraction makes responsibilities locatable but should not be presented as removing this coupling. Under Minimize Reader Load, the existing house pattern, cohesive module names, unchanged state ownership and absence of forwarding layers justify accepting this bounded split. A future state redesign would be a separate behavioral-risk project.

Independent verification completed entirely in the background with D:/Codes/Imervue/.venv/Scripts/python.exe and QT_QPA_PLATFORM=offscreen.

- The four new test files passed, 66 tests in 8.91 seconds. The command used pytest -q -p no:cacheprovider and PYTHONDONTWRITEBYTECODE=1.
- An in-memory baseline loaded from git show HEAD:Imervue/gui/annotation_canvas.py matched the changed implementation on 1,000 deterministic randomized hit-test cases and 81 sequential style comparisons.
- Hidden QWidget.render output matched the baseline byte for byte for base pixels, committed annotations, selection, a transient drawing, a destructive preview and a crop overlay.
- An unhandled key event reached QWidget without error. The new pointer tests also delivered Qt events through QCoreApplication.sendEvent and verified draw, move, resize, crop, freehand, text reentrancy and save behavior.
- Runtime identity checks confirmed the three command aliases through annotation_canvas and annotation_dialog, plus fit, distance, resize and handle geometry aliases.

The sorted runtime and new-test file aggregate SHA-256 was 14a867375150775779210ed229003ec61f4f760510f881f25735067d2ab1c968. The digest incorporates each relative POSIX path followed by that file's raw bytes, sorted by pathlib path. It covers annotation_canvas.py and every untracked file under Imervue/gui and tests at review time.

Verification limits remain. This reviewer did not rerun the full suite, lint or bandit because the parent has a separate verification stage. The hosted complexity value was not verified. Offscreen rendering does not prove native desktop focus, device scaling, actual modal interaction or every drawing brush's visual parity. The destructive prompt was not opened by this review. Existing source behavior is the parity baseline, so this verdict does not claim that unrelated pre-existing annotation limitations were fixed.

No runtime, test or tracked documentation files were changed by this review. The only intentional file write was this audit report.
