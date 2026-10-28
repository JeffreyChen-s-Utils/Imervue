Runtime complexity review against baseline e452ce80cc0b8a78cd62bd20afb5a70ae9f9f1c9.

The goal is lower production complexity while preserving puppet evaluation behavior. This read-only review found one behavior regression. The candidate should receive a narrow correction and regression test before integration.

P2. Authored NaN blend coordinates no longer retain the original sampling result. The change is in Imervue/puppet/runtime_blends.py lines 35-38, combined with runtime_interpolation.py line 15. The original axis sampler fell back to the first and last coordinate and calculated the span when no comparison matched. The shared bracket helper instead returns the final coordinate with weight zero. The special case only checks a NaN sample value, and forces zero weight for a single coordinate. A NaN authored coordinate therefore changes behavior even with a finite parameter value. document_io.py line 691 accepts these coordinates through float conversion without a finiteness guard.

Stable minimal reproduction through the existing public imports:

```python
from math import nan
from Imervue.puppet.document import BlendKey, ParameterBlend
from Imervue.puppet.runtime import sample_blend_forms
blend = ParameterBlend('b', ['x'], [BlendKey([nan], {'r': {'angle': 1.0}})])
sample_blend_forms(blend, {'x': 0.0})
```

The baseline returns {'r': {'angle': nan}}. The candidate returns {'r': {'angle': 1.0}}. The same divergence occurs for a NaN sample value. Multiple-coordinate cases also diverge. Preserve the blend sampler's fallback independently of the parameter/appearance fallback and add a public old/new contract case. Rejecting nonfinite coordinates would be a separate behavioral change, not an equivalent refactor.

Domain cohesion is acceptable overall. Sampling, partial-form merging, sparse grid reduction, geometry composition, bone skinning, morph caching, appearance curves, expressions, poses, and part hierarchy have named owners. Shared curve and form logic removes real duplication. All runtime function definitions without a leading underscore remain available through runtime.py, and the externally consumed _rest_vertices_array import remains. I found no repository caller of a removed helper. One minor ownership mismatch is that generic _form_for lives in runtime_skinning although rigid geometry also imports it; runtime_forms would be the more accurate owner. This is not a blocking finding.

AST comparison found 23 function bodies and signatures identical to baseline, including geometry composition, hierarchy ordering, morph resolution and caches, overlays, parts, batch composition, and form merging. The substantive changes are interval sampling, appearance curve iteration, and the deduplicated sparse-grid merge. Finite endpoint and duplicate-key behavior, sparse corner reduction order, opacity early exit, and cache object retention are preserved by inspection and the tests below. The authored-NaN-coordinate case is absent from the supplied differential matrix.

Validation performed with D:/Codes/Imervue/.venv/Scripts/python.exe and QT_QPA_PLATFORM=offscreen:

- Supplied verify_runtime_equivalence.py replay passed all 1,710 public comparisons against e452ce80.
- Supplied test_runtime_baseline.py passed all 13 new public contract cases on the original implementation.
- Focused current tests passed 86 cases with 34 skips across runtime, runtime_contract, parameter_blend, vertex_morphs, color_tint, bone_hierarchy, expressions_pose, parts, and mesh_edit_cache.
- The minimal authored-NaN regression was executed against both implementations in the same process and reproduced both outputs above.
- All 14 runtime modules, the new test file, and the tracked source/documentation diff were read. Git status remained unchanged by this review.

Limits. No full suite, hosted metric query, new Radon measurement, Ruff rerun, Bandit rerun, GL rendering, or external consumer test was performed. The 34 skipped cases were not executed. The worktree had no .audit directory, so worker audit files were unavailable there. The supplied differential scripts were available in D:/Codes/Imervue-quality-tools and were inspected before replay. This review makes no shipping or hosted-threshold claim.

Correction verification, same review continued.

The P2 authored-NaN-coordinate finding is resolved. runtime_interpolation.bracket now accepts an explicit fallback_to_span option and uses the original full-axis span calculation when no comparison matches. Only sample_blend_forms requests this option. Parameter and appearance callers retain their final-key fallback. The sample-only NaN special case was removed. This preserves the original distinction between blend-axis interpolation and scalar/appearance lookup.

I reran the exact reported public reproduction. Both baseline and corrected candidate now return {'r': {'angle': nan}} for the single NaN coordinate sampled at zero.

Independent correction checks passed:

- The expanded supplied replay matched baseline for 1,950 public calls.
- All 26 public contract cases passed against baseline and against the corrected candidate.
- An additional 10,320 public comparisons matched across sample_blend_forms, sample_parameter_forms, resolve_drawable_color, and resolve_drawable_opacity. The matrix used all coordinate sequences of lengths one through three drawn from negative infinity, -1, 0, 1, positive infinity, and NaN. Every sequence was sampled at ten finite/nonfinite values. This includes duplicate keys, NaN authored coordinates, NaN parameter samples, infinite coordinates, and endpoint clamps.

No remaining blocking findings from this review. The earlier minor _form_for ownership observation remains nonblocking. The prior full-suite, hosted-metric, GL, and external-consumer validation limits still apply. No production source was edited by the reviewer, and no full suite was run.
