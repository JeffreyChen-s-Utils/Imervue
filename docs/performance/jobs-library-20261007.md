# Shared job state: 100k library regression check

Same owned v1 fixture, fresh isolated profile/SQLite index, metadata only (pHash disabled), same machine and interpreter as the original baseline. The host power/thermal state and OS file cache are not controlled. Cold means a fresh profile/index, not a flushed filesystem cache.

| Operation | Original baseline p95 (ms) | Final p95 (ms) | Gate |
|---|---:|---:|---|
| Cold metadata index | 29,340.15 | 24,666.73 | <=36,000; one sample |
| Unchanged scan | 25,462.72 | 26,223.88 | <=31,000 and within 20% |
| Single-reader search | 68.81 | 75.68 | within 20%; concurrent writer is #76 |
| Return after scan cancellation | 18.16 | 40.23 | <=50; includes worker pool shutdown |

The changed scan cancellation path meets its pre-existing 50ms absolute limit. It is slower than the original 18.16ms reference and is not advertised as a cancellation speedup. Unchanged index/search paths remain within their original 20% regression limits. These measurements cover headless scanner return, not the job panel, AI inference, export encoding or network throughput; the registry requests cooperative cancellation immediately and retains a blocked real QThread until actual exit in separate tests.

The first implementation eagerly created a result object for every pending item and rewrote every unresolved result at finish: cancellation p95 151.93ms. The intermediate O(1) terminal update still gave p95 66.62ms. Final state stores pending source keys with no per-item object, uses slotted immutable committed results and resolves terminal pending states on demand. Summary/finish are O(1); the panel materializes at most 500 visible results, prioritizes failures and exports complete JSON on explicit request.

All samples remain available: [first](jobs-library-20261007.json), [intermediate](jobs-library-lazy-20261007.json), [final](jobs-library-final-20261007.json). Final measured scanner and JobState source hashes match the staged implementation. The subsequent one-line empty-download-exception guard in plugin_downloader.py is outside this library workload and has its own regression test; the raw report retains the original complete working-tree hash capture. The final report does not imply that later guard was benchmarked.

No small speedup is inferred from these three-sample measurements. Targets from baseline-20261007.md were not relaxed.
