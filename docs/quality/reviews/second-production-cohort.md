# Second production complexity cohort

The file-tree and Paint tool-state changes remove repeated decisions while preserving existing entry points and event order. The file tree keeps the Qt view as state owner and binds cohesive operation functions. Paint keeps ToolState as state owner and shares change publication and settings conversion through existing-style domain mixins.

| Unit | Local Radon function/method sum before | After | Resulting modules | Maximum module sum |
| --- | ---: | ---: | ---: | ---: |
| File tree | 182 | 171 | 12 | 20 |
| Paint tool state | 172 | 142 | 14 | 18 |

These local sums exclude Radon Class summary blocks and cannot certify Codacy thresholds. Hosted baseline scores for the original files are 182 and 176 respectively. Fresh hosted analysis is still required for every resulting module.

Independent file-tree verification passed 55 focused tests, 15 new contracts against the baseline and 1,408 old/new viewer-deletion comparisons. The integrated focused/structural set passed 67 tests. Independent tool-state verification passed 149 focused tests, 24 baseline contracts and 422 operation/load comparisons covering persisted snapshots and listener observations.

The callback dependency is now supplied when constructing AnnotationCanvas. Its call remains lazy and replaceable; existing positional arguments, None handling and error propagation are unchanged. The callback/verifier focused set passed 61 tests. Pylint's not-callable check passes on all changed runtime modules. Opengrep's audited developer-tool exception now includes the checkout-only verifier, matching its existing Bandit policy; no runtime or complexity exclusion was added.

Ruff and production Bandit pass. Independent behavior and comment/style reviews found no blocking findings. The integrated full suite passed: 14,650 passed, 1,431 existing skips, exit 0 in 496.87 seconds. Publication and hosted verification remain pending. The original three external-editor process-execution audit findings remain open, and the complete program still has 429 files above threshold at the published c6ecd0f7 baseline.
