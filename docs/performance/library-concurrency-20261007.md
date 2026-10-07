# Library WAL reader isolation

The pre-change Event regression test proved that foreground search waited for a scanner batch.
It did not prove dirty reads: conn() already acquired the write lock. Write serialization protected
foreground tags from rollback, but prevented WAL from providing independent reads.

A separate query-only connection now returns committed data per eager query call. A single
SQL statement uses its implicit SQLite snapshot; compound tag queries use BEGIN/ROLLBACK.
Explicit transactions for every single-row lookup were measured and removed as excess overhead.
Reads inside an owning write batch use the writer and see their own changes. Close and path changes
wait for active calls; locks always order writer then reader. Schema 2, WAL and public conn() remain. The additive idx_images_sort index covers
(taken_at DESC, mtime DESC), eliminating a temporary catalog-wide sort for limited searches
when capture dates are unknown/equal. Existing schema-2 catalogs gain it on open; building it
once costs time and disk space, and inserts maintain one more index.
The existing serialized writer is sufficient; no additional writer queue or mandatory dependency.
Direct raw conn() users must hold the write lock or write_batch themselves. Fingerprints release
snapshots between 1,000-row keyset pages; concurrent changes may cause a safe extra rescan.

| Fixed 100,000-row synthetic catalog, 30 samples | Before | After |
| --- | ---: | ---: |
| Single reader median | 41.28 ms | 0.062 ms |
| Single reader p95 | 46.62 ms | 0.392 ms |
| Search with held writer median | 314.04 ms | 0.105 ms |
| Search with held writer p95 | 321.89 ms | 0.152 ms |

The writer holds a transaction for up to 250 ms before rollback; the reader releases it after
search finishes. Rows have NULL taken_at and identical mtime. Before the sort index,
the LIMIT query examined/sorted 100k rows; after it, this common name filter stops after
100 matches. Highly selective/no-match filters can still inspect the full catalog. This deliberately controlled workload differs from a filesystem scan. Search during a
writer passes <=100 ms; single-reader p95 decreases, within the <=20% regression gate. Thirty
samples do not establish hardware-independent latency. OS page cache is not flushed.
Foreground mutations still wait for the scanner's short write chunk; metadata probing happens
before the transaction. Writes, rollback and close are correctness-tested, not claimed asynchronous.

Reproduce from the checkout using its environment:

```powershell
.venv\Scripts\python.exe -X utf8 scripts/library_concurrency_benchmark.py --output report.json
.venv\Scripts\python.exe -X utf8 scripts/performance_benchmark.py --fixtures .git/performance-baseline-v1 --output library.json --only library-large --repeats 3
```

Raw controlled reports: library-concurrency-before-20261007.json and
library-concurrency-after-20261007.json. The final measurement was repeated after removing excess transactions and adding the sort index; its normalized source
fingerprint matches the completed implementation.
The separate real fixed-fixture scanner report is library-readers-final-20261007.json.

The first filesystem run overlapped focused tests and had a warm p95 of 38,606 ms, above
the 31,000 ms gate. It is retained as library-readers-interleaved-20261007.json; the
controlled rerun stops test workloads. No improvement is inferred from an overlapping run.

The explicit-single-query-transaction intermediate run is retained separately; its warm
p95 was 33,429 ms. After removing those transactions, warm p95 fell to 29,718 ms but
search p95 was 103.40 ms. EXPLAIN confirmed a temporary sort for equal dates; the final
composite index is verified by a query-plan regression test. Full fixture reports preserve
those intermediate outcomes; no threshold was relaxed.

Final fixed-fixture application path (100k files, three scans, 30 searches): cold index
30,687.51 ms (<=36,000); incremental p95 28,304.36 ms (<=31,000); search p95
0.129 ms (<=100 and no single-reader regression); cancellation p95 33.11 ms (<=50).
No test workload ran concurrently. These timings exclude OS cold-cache control.
