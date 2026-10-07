# Thumbnail startup inventory: fixed 100,000-file workload

Same baseline-v1 PNG cache, 10 samples, isolated fresh child/profile. OS page cache is not flushed.
Source reference c6e4c610; normalized SHA-256 fingerprints are in the two raw reports.

| Measurement | Before | After |
|---|---:|---:|
| 100k constructor median | 150.13 ms | 0.48 ms |
| 100k constructor p95 | 163.28 ms | 0.62 ms |
| Complete inventory median | synchronous constructor | 227.37 ms |
| Complete inventory p95 | synchronous constructor | 237.03 ms |
| Empty warm constructor p95 | 0.23 ms | 0.40 ms |
| Final accounted entries | 100,000 | 100,000 |

The <=10 ms constructor gate passes. Work moves off startup; full background inventory is slower,
not a throughput improvement. Its extra locks, mutation checks and scheduling protect concurrent
reads/writes/clear; empty construction adds about 0.17 ms p95 for thread setup. No RSS reduction
claim: after-phase RSS peak is 85.49 MiB and includes inventory, while the old synchronous sampler
peaked at 84.96 MiB. The after sampler joins each inventory outside the constructor timer before
starting the next sample, avoiding overlapping scans; the old sampler timed synchronous scans.
Before samples may include release of the prior instance; this does not affect the 10 ms gate.

PNG layout/key version/quota defaults stay unchanged. Foreground mutation timestamps/bytes win
against stale directory stats. Clear invalidates the generation and covers unscanned managed files;
unknown files/directories remain. A reader failing on an old corrupt version cannot delete a valid
atomic rewrite. Locked readable legacy/corrupt files stay accounted; OS failures can prevent quota.
Byte totals remain provisional while initialization is running. A directory should have one cache
owner; the production singleton is shared across windows. Independent processes are outside this
bookkeeping contract. Scanner failure logs and leaves direct cache reads/writes usable.

Reproduce after: `.venv/Scripts/python.exe -X utf8 scripts/performance_benchmark.py --fixtures
.git/performance-baseline-v1 --output <report.json> --only cache --repeats 10` (one line).
Raw: [before](thumbnail-before-20261007.json), [after](thumbnail-after-20261007.json).
Controlled thread/Event regression tests cover stale stats vs reads/rewrites/purge/clear, new puts
after clear, scan quota/legacy cleanup, locked files, failed atomic rewrite and scanner errors.
