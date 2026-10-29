# Fourth cohort comment and style review

Read-only review of the frozen recipe and puppet canvas cohorts against 926d4a6d. Scope follows recipe-manifest.json and puppet-canvas/frozen-manifest.json under D:/Codes/Imervue-quality-tools. All listed hashes matched when inspected. No source edits, commits or full test suite were performed.

No blocking correctness or maintainability finding. One small comment cleanup is recommended before integration.

- tests/test_puppet_canvas_contracts.py:95 adds narration about patching the method owner before and after extraction. Delete that comment. The following assignment to PuppetCanvas.render_offscreen_puppet.__globals__ already expresses the operation; the extraction history does not belong in the lasting test. No implementation change or architecture sketch is needed.

Tokenized production comments were compared as multisets, so moved comments were not counted as additions. Recipe has 35 comment tokens versus 55 in its baseline module, with zero new tokens and 20 removed. Canvas has 105 versus 122, with zero new tokens and 17 removed. These counts exclude docstrings. This review deleted zero comments, restored none, and recommends the one test-comment deletion above. The existing render-state test's comments were unchanged.

The new canvas contracts have two inline comments. The other, at line 140, explains why the constructor-failure case does not assert immediate destruction of the incomplete Python test double. A direct Python 3.14.4 probe retained the exception traceback and observed no destructor call until the retained exception was released. Keep this explanation of the Python runtime constraint. It does not prove Qt FBO lifetime or excuse weaker native GL verification.

Recipe's type-ignore assignment in recipe_values.py:52 and NOSONAR on dataclasses.replace in recipe_geometry.py:56 are moved baseline suppressions, not newly added bypasses. The two N802 suppressions and twelve Qt/GL coverage pragmas in the canvas owners are also baseline comments. No broad exception catch, silent suppression or cast was newly added. Optional-effect decoding remains outside the application-error catch; the loader functions preserve lazy imports rather than adding eager optional dependencies.

The Recipe normalized method retains the public method while delegating canonical construction. The five optional loaders provide the import boundary for one shared policy. Canvas expression_values is used by evaluation and physics; refresh_rig is shared across parameter, expression, pose and editing operations. These helpers have identifiable ownership and callers. No additional forwarding layer or generic dispatch framework is needed for this cohort.

Public method/signal contracts and moved Qt/GL resource comments are preserved, including context acquisition for frees, temporary surface-format restoration, framebuffer destruction before doneCurrent, state restoration and stencil attachment requirements. Their presence is not newly authored evidence that actual rendering is correct. Native rendering and resource verification remain the behavior review and Linux Mesa CI gates. No new dependency-rule comment required a HOLD, and no constraint encoding or application-code reshape is proposed.

This is a scoped style verdict only. It does not certify full runtime complexity completion, hosted scores, native GL behavior or the full test suite.
