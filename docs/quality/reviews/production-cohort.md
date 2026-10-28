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

Hosted verification of c6ecd0f7 subsequently completed. Filename-ordered capture and source-blob comparison verified every one of the 53 changed runtime files at or below 20, with no missing or stale runtime analysis. The complete inventory has 495 within-threshold files, five data-only modules and 429 above threshold (down from 435). Evidence: docs/quality/complexity-c6ecd0f7.json. SonarCloud passed. Codacy still reports three external-editor execution audits, a developer-verifier subprocess audit and a callback inference warning; threshold success does not resolve those findings.

Hosted aggregate comparison over each original file and its resulting production modules:

| Unit | e452ce80 | c6ecd0f7 | Resulting files | Maximum file score |
| --- | ---: | ---: | ---: | ---: |
| archive | 224 | 211 | 15 | 20 |
| runtime | 182 | 160 | 14 | 20 |
| annotation | 211 | 178 | 10 | 20 |
| paint | 197 | 178 | 12 | 20 |
| formats | 24 | 20 | 1 | 20 |
| editors | 22 | 19 | 1 | 19 |

The combined hosted sum decreases from 860 to 766. This compares the same six responsibilities including all newly extracted files; it does not count disappearance of the original large-file score as the whole reduction. Local Radon and hosted scores differ, particularly in runtime hierarchy ordering, so the hosted table is the completion evidence for this cohort. It does not cover the remaining 429 over-threshold modules.
