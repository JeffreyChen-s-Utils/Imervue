# Production complexity cohort

Six production responsibilities were reviewed before integration. Local scores guide the work; they are not interchangeable with Codacy scores and do not certify the hosted threshold.

| Responsibility | Local measurement before → after | Evidence |
| --- | --- | --- |
| Puppet archive codecs | Radon block sum 226 → 212 | 2,317 old/new archive cases; independent codec review |
| Annotation canvas | Function/method sum 211 → 177 | 1,000 hit comparisons, 81 style comparisons, six rendered pixel comparisons |
| Paint document | Function/method sum 198 → 176 | Public contract tests and nested callback/order/cache review |
| Output formats | Local complexity 24 → 20 | 38 focused tests and independent review |
| External editors | Local complexity 22 → 19 | Original Popen launch retained; 35 focused reviewer tests |
| Puppet runtime | Local aggregate 182 → 154 | 1,950 supplied plus 10,320 independent old/new comparisons |

All resulting production files in these units measure at most 20 locally. Fresh hosted analysis is pending. The external-editor execution audit findings remain unresolved; a smaller local complexity score does not resolve a security audit.

The first integrated full run found a translation-guard false positive: 14,520 passed, 1 failed, 1,431 skipped. The guard now distinguishes direct Python export containers from UI translation pairs. Nine focused tests and an independent review passed. The complete rerun including external-editor and runtime changes passed: 14,584 passed, 1,431 existing skips, exit 0 (758.47 seconds). Ruff and production Bandit passed after integration; fresh hosted checks remain required before the batch is verified.
